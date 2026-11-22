-- ============================================================================
-- Show-book-kar - transactional functions (write path)
-- Owner: M | Called by: H (backend) | Reviewer: S (error codes)
-- ============================================================================
--
-- This file is the single authoritative home of the booking rules. H wrote the
-- hold path as a reference implementation so the backend could be built and
-- tested before M landed the final version; M owns this file and should review
-- it, then add fn_pay_booking / fn_cancel_booking for Part E.
--
-- Conventions:
--   * Locking order is fixed by "ORDER BY seat_id" so two concurrent holds on
--     overlapping seat sets cannot deadlock: the second waits, re-reads the
--     committed row, and fails cleanly.
--   * Failures raise with a short signal message instead of a numeric code;
--     backend/errors.py maps those messages to HTTP status codes.
--   * Amounts always come from show_seats.price, never from a caller.
--
-- Load order: schema.sql -> functions.sql -> views.sql -> indexes.sql -> seed.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- fn_release_expired_holds
-- Puts expired HELD seats back to AVAILABLE and expires PENDING bookings that
-- no longer hold any seat. Safe to call at any time; the hold path calls it
-- before deciding availability.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_release_expired_holds()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    v_released integer;
BEGIN
    WITH released AS (
        UPDATE show_seats ss
           SET status             = 'AVAILABLE',
               hold_expires_at    = NULL,
               held_by_booking_id = NULL
         WHERE ss.status = 'HELD'
           AND ss.hold_expires_at IS NOT NULL
           AND ss.hold_expires_at <= NOW()
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_released FROM released;

    -- A PENDING booking with no remaining HELD seat can never be paid for.
    UPDATE bookings b
       SET status = 'EXPIRED'
     WHERE b.status = 'PENDING'
       AND NOT EXISTS (
           SELECT 1
             FROM show_seats ss
            WHERE ss.held_by_booking_id = b.id
              AND ss.status = 'HELD'
       );

    RETURN v_released;
END;
$$;

-- ----------------------------------------------------------------------------
-- fn_hold_seats
-- Atomically reserves seats for a user for p_hold_minutes and returns the new
-- PENDING booking. Either every requested seat is held, or nothing changes.
--
-- Signals: SHOW_NOT_FOUND, INVALID_SEATS, SEAT_UNAVAILABLE, INVALID_STATE
-- (the user already has an active booking for this show -
--  bookings_user_show_active_unique).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_hold_seats(
    p_user_id      integer,
    p_show_id      integer,
    p_seat_ids     integer[],
    p_hold_minutes integer
)
RETURNS TABLE (
    booking_id      integer,
    status          text,
    hold_expires_at timestamptz,
    total_amount    numeric
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
DECLARE
    c_default_hold constant integer := 5;
    v_seats    integer[];
    v_wanted   integer;
    v_found    integer;
    v_total    numeric(10, 2);
    v_expires  timestamptz;
    v_booking  integer;
    v_show_start timestamptz;
BEGIN
    IF p_hold_minutes IS NULL OR p_hold_minutes <= 0 THEN
        p_hold_minutes := c_default_hold;
    END IF;

    -- 1. Normalise and validate the requested seats.
    v_seats  := ARRAY(SELECT DISTINCT s FROM unnest(p_seat_ids) AS s ORDER BY s);
    v_wanted := COALESCE(array_length(v_seats, 1), 0);

    IF v_wanted = 0 THEN
        RAISE EXCEPTION 'INVALID_SEATS';
    END IF;

    SELECT sh.start_at INTO v_show_start
      FROM shows sh
     WHERE sh.id = p_show_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'SHOW_NOT_FOUND';
    END IF;

    IF v_show_start <= NOW() THEN
        RAISE EXCEPTION 'SHOW_STARTED';
    END IF;

    SELECT COUNT(*) INTO v_found
      FROM show_seats ss
     WHERE ss.show_id = p_show_id
       AND ss.seat_id = ANY (v_seats);

    IF v_found <> v_wanted THEN
        -- At least one seat does not belong to this show.
        RAISE EXCEPTION 'INVALID_SEATS';
    END IF;

    -- 2. One *active* booking per user per show (schema:
    -- bookings_user_show_active_unique). A cancelled or expired booking must
    -- not stop the user from booking the same show again.
    IF EXISTS (
        SELECT 1 FROM bookings b
         WHERE b.user_id = p_user_id
           AND b.show_id = p_show_id
           AND b.status IN ('PENDING', 'CONFIRMED')
    ) THEN
        RAISE EXCEPTION 'INVALID_STATE';
    END IF;

    -- 3. Reclaim expired holds before deciding what is available.
    PERFORM fn_release_expired_holds();

    -- 4. Lock this show's requested rows in seat order, then check them.
    PERFORM 1
       FROM show_seats ss
      WHERE ss.show_id = p_show_id
        AND ss.seat_id = ANY (v_seats)
      ORDER BY ss.seat_id
        FOR UPDATE;

    IF EXISTS (
        SELECT 1 FROM show_seats ss
         WHERE ss.show_id = p_show_id
           AND ss.seat_id = ANY (v_seats)
           AND ss.status <> 'AVAILABLE'
    ) THEN
        RAISE EXCEPTION 'SEAT_UNAVAILABLE';
    END IF;

    -- 5. Price is the per-show price, never a caller-supplied amount.
    SELECT COALESCE(SUM(ss.price), 0) INTO v_total
      FROM show_seats ss
     WHERE ss.show_id = p_show_id
       AND ss.seat_id = ANY (v_seats);

    v_expires := NOW() + make_interval(mins => p_hold_minutes);

    INSERT INTO bookings (user_id, show_id, status, total_amount)
    VALUES (p_user_id, p_show_id, 'PENDING', v_total)
    RETURNING id INTO v_booking;

    INSERT INTO booking_seats (booking_id, show_id, seat_id, price)
    SELECT v_booking, p_show_id, ss.seat_id, ss.price
      FROM show_seats ss
     WHERE ss.show_id = p_show_id
       AND ss.seat_id = ANY (v_seats)
     ORDER BY ss.seat_id;

    UPDATE show_seats ss
       SET status             = 'HELD',
           hold_expires_at    = v_expires,
           held_by_booking_id = v_booking
     WHERE ss.show_id = p_show_id
       AND ss.seat_id = ANY (v_seats);

    RETURN QUERY
        SELECT v_booking, 'PENDING'::text, v_expires, v_total;
END;
$$;

-- ----------------------------------------------------------------------------
-- fn_hold_expiry_summary
-- Small reporting helper used by the backend/tests to see what a hold costs
-- without duplicating the arithmetic. Returns one row per PENDING booking.
-- ----------------------------------------------------------------------------
-- ----------------------------------------------------------------------------
-- fn_pay_booking
-- Confirms a PENDING booking whose hold is still alive, or records a failed
-- attempt. Repeating the call on a CONFIRMED booking returns the existing state
-- instead of charging twice (the schema allows one payment row per booking).
--
-- Signals: BOOKING_NOT_FOUND, FORBIDDEN, INVALID_STATE, HOLD_EXPIRED
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_pay_booking(
    p_booking_id integer,
    p_user_id    integer,
    p_simulate   text
)
RETURNS TABLE (
    booking_id     integer,
    booking_status text,
    payment_status text,
    amount         numeric
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
DECLARE
    v_booking      bookings%ROWTYPE;
    v_seat_count   integer;
    v_live_count   integer;
    v_payment      payments%ROWTYPE;
    v_reference    text;
BEGIN
    IF p_simulate IS NULL OR p_simulate NOT IN ('success', 'failure') THEN
        RAISE EXCEPTION 'INVALID_SIMULATION';
    END IF;

    SELECT * INTO v_booking
      FROM bookings b
     WHERE b.id = p_booking_id
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'BOOKING_NOT_FOUND';
    END IF;

    IF v_booking.user_id <> p_user_id THEN
        RAISE EXCEPTION 'FORBIDDEN';
    END IF;

    -- Idempotent repeat: a confirmed booking is already paid.
    IF v_booking.status = 'CONFIRMED' THEN
        SELECT * INTO v_payment
          FROM payments p
         WHERE p.booking_id = p_booking_id;

        RETURN QUERY
            SELECT v_booking.id,
                   v_booking.status,
                   COALESCE(v_payment.status, 'SUCCESS'::text),
                   v_booking.total_amount;
        RETURN;
    END IF;

    IF v_booking.status <> 'PENDING' THEN
        RAISE EXCEPTION 'INVALID_STATE';
    END IF;

    -- The hold must still be alive for every seat. Nothing is written before
    -- this check: a raise here rolls the whole attempt back and leaves the
    -- expired rows for fn_release_expired_holds to reclaim.
    PERFORM 1
       FROM show_seats ss
      WHERE ss.held_by_booking_id = p_booking_id
      ORDER BY ss.seat_id
        FOR UPDATE;

    SELECT COUNT(*) INTO v_seat_count
      FROM booking_seats bs
     WHERE bs.booking_id = p_booking_id;

    SELECT COUNT(*) INTO v_live_count
      FROM show_seats ss
     WHERE ss.held_by_booking_id = p_booking_id
       AND ss.status = 'HELD'
       AND ss.hold_expires_at IS NOT NULL
       AND ss.hold_expires_at > NOW();

    IF v_seat_count = 0 OR v_live_count <> v_seat_count THEN
        RAISE EXCEPTION 'HOLD_EXPIRED';
    END IF;

    -- Simulated decline: record the attempt, keep the seats HELD so the user
    -- can retry inside the same hold window.
    IF p_simulate = 'failure' THEN
        INSERT INTO payments (booking_id, amount, status, transaction_ref)
        VALUES (p_booking_id, v_booking.total_amount, 'FAILED', NULL)
        ON CONFLICT ON CONSTRAINT payments_booking_unique
        DO UPDATE SET amount      = EXCLUDED.amount,
                      status      = 'FAILED',
                      transaction_ref = NULL,
                      created_at  = NOW();

        RETURN QUERY
            SELECT p_booking_id, v_booking.status, 'FAILED'::text, v_booking.total_amount;
        RETURN;
    END IF;

    v_reference := 'txn_' || lpad(p_booking_id::text, 6, '0')
                   || '_' || to_char(NOW(), 'YYYYMMDDHH24MISS');

    INSERT INTO payments (booking_id, amount, status, transaction_ref)
    VALUES (p_booking_id, v_booking.total_amount, 'SUCCESS', v_reference)
    ON CONFLICT ON CONSTRAINT payments_booking_unique
    DO UPDATE SET amount          = EXCLUDED.amount,
                  status          = 'SUCCESS',
                  transaction_ref = EXCLUDED.transaction_ref,
                  created_at      = NOW();

    -- Confirmed: the expiry disappears, the owner stays.
    UPDATE show_seats ss
       SET status          = 'BOOKED',
           hold_expires_at = NULL
     WHERE ss.held_by_booking_id = p_booking_id
       AND ss.status = 'HELD';

    UPDATE bookings b
       SET status = 'CONFIRMED'
     WHERE b.id = p_booking_id;

    RETURN QUERY
        SELECT p_booking_id, 'CONFIRMED'::text, 'SUCCESS'::text, v_booking.total_amount;
END;
$$;

-- ----------------------------------------------------------------------------
-- fn_cancel_booking
-- Cancels a CONFIRMED booking before the cutoff, frees its seats and files a
-- refund request when a successful payment exists.
--
-- Signals: BOOKING_NOT_FOUND, FORBIDDEN, INVALID_STATE, CANCELLATION_NOT_ALLOWED
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_cancel_booking(
    p_booking_id   integer,
    p_user_id      integer,
    p_cutoff_hours integer
)
RETURNS TABLE (
    booking_id    integer,
    booking_status text,
    refund_status text,
    refund_amount numeric
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
DECLARE
    c_default_cutoff constant integer := 2;
    v_booking      bookings%ROWTYPE;
    v_start        timestamptz;
    v_payment      payments%ROWTYPE;
    v_refund       refunds%ROWTYPE;
BEGIN
    IF p_cutoff_hours IS NULL OR p_cutoff_hours < 0 THEN
        p_cutoff_hours := c_default_cutoff;
    END IF;

    SELECT * INTO v_booking
      FROM bookings b
     WHERE b.id = p_booking_id
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'BOOKING_NOT_FOUND';
    END IF;

    IF v_booking.user_id <> p_user_id THEN
        RAISE EXCEPTION 'FORBIDDEN';
    END IF;

    IF v_booking.status = 'CANCELLED' THEN
        RAISE EXCEPTION 'INVALID_STATE';
    END IF;

    IF v_booking.status <> 'CONFIRMED' THEN
        -- PENDING holds are abandoned (they expire), EXPIRED cannot be cancelled.
        RAISE EXCEPTION 'INVALID_STATE';
    END IF;

    SELECT sh.start_at INTO v_start
      FROM shows sh
     WHERE sh.id = v_booking.show_id
       FOR UPDATE;

    IF v_start - make_interval(hours => p_cutoff_hours) < NOW() THEN
        RAISE EXCEPTION 'CANCELLATION_NOT_ALLOWED';
    END IF;

    PERFORM 1
       FROM show_seats ss
      WHERE ss.show_id = v_booking.show_id
        AND ss.held_by_booking_id = p_booking_id
      ORDER BY ss.seat_id
        FOR UPDATE;

    UPDATE show_seats ss
       SET status             = 'AVAILABLE',
           hold_expires_at    = NULL,
           held_by_booking_id = NULL
     WHERE ss.show_id = v_booking.show_id
       AND ss.held_by_booking_id = p_booking_id;

    UPDATE bookings b
       SET status = 'CANCELLED'
     WHERE b.id = p_booking_id;

    SELECT * INTO v_payment
      FROM payments p
     WHERE p.booking_id = p_booking_id
       AND p.status = 'SUCCESS';

    IF NOT FOUND THEN
        RETURN QUERY
            SELECT p_booking_id, 'CANCELLED'::text, NULL::text, NULL::numeric;
        RETURN;
    END IF;

    SELECT * INTO v_refund
      FROM refunds r
     WHERE r.payment_id = v_payment.id;

    IF NOT FOUND THEN
        INSERT INTO refunds (payment_id, booking_id, amount, status, reason)
        VALUES (v_payment.id, p_booking_id, v_payment.amount, 'REQUESTED',
                'Customer cancelled the booking')
        RETURNING * INTO v_refund;
    END IF;

    RETURN QUERY
        SELECT p_booking_id, 'CANCELLED'::text, v_refund.status, v_refund.amount;
END;
$$;

-- ----------------------------------------------------------------------------
-- fn_create_show
-- Schedules a show and materialises its show_seats rows. Rejects overlaps on
-- the same screen under a row lock, which is the guard the schema cannot
-- express (there is no exclusion constraint yet).
--
-- Signals: MOVIE_NOT_FOUND, SCREEN_NOT_FOUND, INVALID_TIME_RANGE,
--          INVALID_PRICE, SCREEN_HAS_NO_SEATS, SHOW_OVERLAP
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_create_show(
    p_movie_id   integer,
    p_screen_id  integer,
    p_start_at   timestamptz,
    p_end_at     timestamptz,
    p_base_price numeric
)
RETURNS TABLE (
    show_id    integer,
    movie_id   integer,
    screen_id  integer,
    start_at   timestamptz,
    end_at     timestamptz,
    base_price numeric,
    seat_count integer
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
DECLARE
    v_show_id    integer;
    v_seat_count integer;
BEGIN
    IF p_start_at IS NULL OR p_end_at IS NULL OR p_end_at <= p_start_at THEN
        RAISE EXCEPTION 'INVALID_TIME_RANGE';
    END IF;

    IF p_start_at <= NOW() THEN
        RAISE EXCEPTION 'INVALID_TIME_RANGE';
    END IF;

    IF p_base_price IS NULL OR p_base_price < 0 THEN
        RAISE EXCEPTION 'INVALID_PRICE';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM movies m WHERE m.id = p_movie_id) THEN
        RAISE EXCEPTION 'MOVIE_NOT_FOUND';
    END IF;

    -- Lock the screen: two schedulers cannot pass the overlap check together.
    PERFORM 1
       FROM screens sc
      WHERE sc.id = p_screen_id
        FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'SCREEN_NOT_FOUND';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM shows sh
         WHERE sh.screen_id = p_screen_id
           AND tstzrange(sh.start_at, sh.end_at, '[)')
               && tstzrange(p_start_at, p_end_at, '[)')
    ) THEN
        RAISE EXCEPTION 'SHOW_OVERLAP';
    END IF;

    INSERT INTO shows (movie_id, screen_id, start_at, end_at, base_price)
    VALUES (p_movie_id, p_screen_id, p_start_at, p_end_at, p_base_price)
    RETURNING id INTO v_show_id;

    -- Every seat of a show costs the show's base price, matching seed.sql; the
    -- per-seat price is snapshotted into show_seats so a later price change
    -- cannot rewrite history.
    INSERT INTO show_seats (show_id, seat_id, status, price)
    SELECT v_show_id,
           s.id,
           'AVAILABLE',
           p_base_price
      FROM seats s
     WHERE s.screen_id = p_screen_id
     ORDER BY s.row_label, s.seat_number;

    SELECT COUNT(*) INTO v_seat_count
      FROM show_seats ss
     WHERE ss.show_id = v_show_id;

    IF v_seat_count = 0 THEN
        RAISE EXCEPTION 'SCREEN_HAS_NO_SEATS';
    END IF;

    RETURN QUERY
        SELECT v_show_id, p_movie_id, p_screen_id, p_start_at, p_end_at,
               p_base_price, v_seat_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- fn_hold_expiry_summary
-- Small reporting helper used by the backend/tests to see what a hold costs
-- without duplicating the arithmetic. Returns one row per PENDING booking.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_pending_holds()
RETURNS TABLE (
    booking_id      integer,
    user_id         integer,
    show_id         integer,
    seat_count      integer,
    total_amount    numeric,
    hold_expires_at timestamptz
)
LANGUAGE sql
STABLE
AS $$
    SELECT b.id,
           b.user_id,
           b.show_id,
           COUNT(bs.seat_id)::integer,
           b.total_amount,
           MIN(ss.hold_expires_at)
      FROM bookings b
      JOIN show_seats ss ON ss.held_by_booking_id = b.id AND ss.status = 'HELD'
      LEFT JOIN booking_seats bs ON bs.booking_id = b.id
     WHERE b.status = 'PENDING'
     GROUP BY b.id, b.user_id, b.show_id, b.total_amount
     ORDER BY b.id;
$$;
