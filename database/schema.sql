-- ============================================================================
-- Show-book-kar — PostgreSQL schema
-- Owner: M | Reviewer: H (backend/API fit) then S (UI fields)
-- ============================================================================
--
-- Target: 11 core tables in dependency order:
--   users -> movies -> theatres -> screens -> seats -> shows -> show_seats
--   -> bookings -> booking_seats -> payments -> refunds
--
-- Design notes (documented for review):
--   * All money is NUMERIC, all event/show timestamps are TIMESTAMPTZ.
--   * A physical seat is NOT "booked"; its status is tracked per show in
--     show_seats (see seats.status for seat type only).
--   * Hold expiry and ownership live on show_seats.
--   * bookings/payments are never cascade-deleted; history is append-only
--     except status columns.
--   * show_seats uses a composite primary key (show_id, seat_id) and
--     booking_seats uses the matching composite foreign key.
--
-- Loading: load this file from a COMPLETELY EMPTY database:
--   psql -v ON_ERROR_STOP=1 -f database/schema.sql
-- Second run: expect a clean "already exists" failure (or design a safe
-- repeatable version later) — do not silently re-run on a populated DB.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- users
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id              INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email           TEXT            NOT NULL,
    password_hash   TEXT            NOT NULL,
    name            TEXT            NOT NULL,
    role            TEXT            NOT NULL DEFAULT 'customer'
        CONSTRAINT users_role_check CHECK (role IN ('customer', 'admin')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT users_email_unique UNIQUE (email)
);
-- Comment on constraint: uniqueness is enforced here; separate admin table
-- is an alternative role-storage design (see M stage 9).

-- ----------------------------------------------------------------------------
-- movies
-- ----------------------------------------------------------------------------
CREATE TABLE movies (
    id              SERIAL          PRIMARY KEY,
    title           TEXT            NOT NULL,
    language        TEXT            NOT NULL DEFAULT 'English',
    duration_minutes INTEGER         NOT NULL CHECK (duration_minutes > 0),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- theatres
-- ----------------------------------------------------------------------------
CREATE TABLE theatres (
    id              SERIAL          PRIMARY KEY,
    name            TEXT            NOT NULL,
    city            TEXT            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- screens
-- ----------------------------------------------------------------------------
CREATE TABLE screens (
    id              SERIAL          PRIMARY KEY,
    theatre_id      INTEGER         NOT NULL
        REFERENCES theatres (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    name            TEXT            NOT NULL,
    capacity_total  INTEGER         NOT NULL CHECK (capacity_total > 0)
        CONSTRAINT screens_capacity_check CHECK (capacity_total > 0),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT screens_theatre_name_unique UNIQUE (theatre_id, name)
);
-- Comment: together with the UNIQUE on (theatre_id, name), a screen name is
-- unique within its theatre.

-- ----------------------------------------------------------------------------
-- seats
-- ----------------------------------------------------------------------------
CREATE TABLE seats (
    id                  SERIAL          PRIMARY KEY,
    screen_id           INTEGER         NOT NULL
        REFERENCES screens (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    row_label           TEXT            NOT NULL,
    seat_number         INTEGER         NOT NULL,
    seat_type           TEXT            NOT NULL
        CONSTRAINT seats_type_check CHECK (seat_type IN ('standard', 'vip')),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT seats_screen_row_number_unique UNIQUE (screen_id, row_label, seat_number)
);
-- Comment: the physical coordinate (screen_id, row_label, seat_number) is
-- globally unique per screen, not per show. Status is NOT stored here —
-- show_seats is the authoritative per-show state.

-- ----------------------------------------------------------------------------
-- shows
-- ----------------------------------------------------------------------------
CREATE TABLE shows (
    id                  SERIAL          PRIMARY KEY,
    movie_id            INTEGER         NOT NULL
        REFERENCES movies (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    screen_id           INTEGER         NOT NULL
        REFERENCES screens (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    start_at            TIMESTAMPTZ     NOT NULL,
    end_at              TIMESTAMPTZ     NOT NULL,
    base_price          NUMERIC(10, 2)  NOT NULL
        CONSTRAINT shows_price_check CHECK (base_price >= 0),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT shows_time_check CHECK (end_at > start_at),
    CONSTRAINT shows_movie_screen_unique UNIQUE (movie_id, screen_id, start_at)
);
-- Comment: overlap prevention is also handled at the SHOW level below and at
-- the SCREEN level via an exclusion constraint (see database/triggers.sql and
-- database/indexes.sql depending on the agreed approach).

-- ----------------------------------------------------------------------------
-- show_seats
-- ----------------------------------------------------------------------------
CREATE TABLE show_seats (
    show_id             INTEGER         NOT NULL
        REFERENCES shows (id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
    seat_id             INTEGER         NOT NULL
        REFERENCES seats (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    status              TEXT            NOT NULL
        CONSTRAINT show_seats_status_check CHECK (status IN ('AVAILABLE', 'HELD', 'BOOKED')),
    hold_expires_at     TIMESTAMPTZ,
    price               NUMERIC(10, 2)  NOT NULL
        CONSTRAINT show_seats_price_check CHECK (price >= 0),
    held_by_booking_id  INTEGER,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (show_id, seat_id),
    CONSTRAINT show_seats_held_by_fkey CHECK ((held_by_booking_id IS NULL) OR (held_by_booking_id <> 0))
);
-- Comment: composite PK means one show_seats row per (show, seat); composite
-- FK on booking_seats points back to this pair. hold_expires_at is NULL when
-- the row is AVAILABLE or BOOKED. held_by_booking_id is NULL for
-- AVAILABLE/BOOKED and otherwise holds the booking that owns the hold.

-- ----------------------------------------------------------------------------
-- bookings
-- ----------------------------------------------------------------------------
CREATE TABLE bookings (
    id                  SERIAL          PRIMARY KEY,
    user_id             INTEGER         NOT NULL
        REFERENCES users (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    show_id             INTEGER         NOT NULL
        REFERENCES shows (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    status              TEXT            NOT NULL
        CONSTRAINT bookings_status_check CHECK (status IN (
            'PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED'
        )),
    total_amount        NUMERIC(10, 2)  NOT NULL
        CONSTRAINT bookings_amount_check CHECK (total_amount >= 0),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT bookings_user_show_unique UNIQUE (user_id, show_id)
);
-- Comment: a booking refers to one show only; the composite FK to show_seats
-- (see booking_seats) guarantees each booking_seats row belongs to the same
-- show.

-- ----------------------------------------------------------------------------
-- booking_seats
-- ----------------------------------------------------------------------------
CREATE TABLE booking_seats (
    booking_id          INTEGER         NOT NULL
        REFERENCES bookings (id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
    show_id             INTEGER         NOT NULL
        REFERENCES shows (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    seat_id             INTEGER         NOT NULL
        REFERENCES show_seats (show_id, seat_id)
            ON DELETE RESTRICT
            ON UPDATE CASCADE,
    price               NUMERIC(10, 2)  NOT NULL
        CONSTRAINT booking_seats_price_check CHECK (price >= 0),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT booking_seats_booking_show_unique
        UNIQUE (booking_id, show_id, seat_id)
);
-- Comment: a composite FK from (booking_id, show_id, seat_id) to
-- (bookings.id, show_seats.show_id, show_seats.seat_id). The composite FK on
-- (show_id, seat_id) back to show_seats guarantees the booking's show matches
-- the seat's show. Multiple rows (one per seat) are allowed; a booking never
-- repeats a seat because (booking_id, show_id, seat_id) is unique.

-- ----------------------------------------------------------------------------
-- payments
-- ----------------------------------------------------------------------------
CREATE TABLE payments (
    id                  SERIAL          PRIMARY KEY,
    booking_id          INTEGER         NOT NULL
        REFERENCES bookings (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    amount              NUMERIC(10, 2)  NOT NULL
        CONSTRAINT payments_amount_check CHECK (amount >= 0),
    status              TEXT            NOT NULL
        CONSTRAINT payments_status_check CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED')),
    transaction_ref     TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT payments_booking_unique UNIQUE (booking_id)
);
-- Comment: one successful payment per booking (enforced by UNIQUE on
-- booking_id). transaction_ref is NULL until a controlled simulation result
-- produces one; it is unique only where present (see database/triggers.sql for
-- the trigger-level unique index if the team prefers).

-- ----------------------------------------------------------------------------
-- refunds
-- ----------------------------------------------------------------------------
CREATE TABLE refunds (
    id                  SERIAL          PRIMARY KEY,
    payment_id          INTEGER         NOT NULL
        REFERENCES payments (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    booking_id          INTEGER         NOT NULL
        REFERENCES bookings (id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT,
    amount              NUMERIC(10, 2)  NOT NULL
        CONSTRAINT refunds_amount_check CHECK (amount >= 0),
    status              TEXT            NOT NULL
        CONSTRAINT refunds_status_check CHECK (status IN ('REQUESTED', 'APPROVED', 'REJECTED')),
    reason              TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT refunds_payment_unique UNIQUE (payment_id)
);
-- Comment: a refund is a separate record; a payment is fully refunded only
-- after the sum of its refunds reaches the payment amount.
