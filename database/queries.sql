-- ============================================================================
-- Show-book-kar - read queries
-- Owner: M | Reviewer: H (for API fit) then S (for UI fields)
-- ============================================================================
--
-- These queries are the building blocks for H's read-only API routes. They
-- are parameterised the way the routes call them; H passes bind values as
-- $1/$2 etc. Every query must behave correctly (NOT fail) when it returns
-- no rows, and must order/filter predictably.
--
-- Usage in psql:
--   \pset tuples_only on
--   \ef \gset  (or copy into db.py / db.py helper)
-- ============================================================================

-- 1. List movies
--    behaviour: empty result -> zero rows (not NULL); no ORDER BY means
--    unspecified order, so H should add ORDER BY id if a stable list matters.
SELECT id, title, language, duration_minutes, created_at
FROM movies
ORDER BY id;

-- 2. Fetch a movie by ID
--    behaviour: missing id -> zero rows
SELECT id, title, language, duration_minutes, created_at
FROM movies
WHERE id = $1;

-- 3. List future shows for a movie (and optionally a date)
--    behaviour: no matching shows -> zero rows
--    $1 = movie_id (required), $2 = calendar date filter (optional)
--    The date filter is a half-open day range: it returns shows starting on
--    that calendar date only, not every show on or after it.
SELECT s.id, s.start_at, s.end_at, s.base_price, sc.id AS screen_id, sc.name AS screen_name, th.id AS theatre_id, th.name AS theatre_name, th.city
FROM shows s
JOIN screens sc ON sc.id = s.screen_id
JOIN theatres th ON th.id = sc.theatre_id
WHERE s.movie_id = $1
  AND ($2::date IS NULL OR (s.start_at >= $2::date
                            AND s.start_at < ($2::date + INTERVAL '1 day')))
ORDER BY s.start_at;

-- 4. Fetch a show's theatre and screen
--    behaviour: missing show -> zero rows
SELECT s.id             AS show_id,
       s.start_at      AS show_start_at,
       s.end_at        AS show_end_at,
       s.base_price    AS show_base_price,
       sc.id           AS screen_id,
       sc.name         AS screen_name,
       th.id           AS theatre_id,
       th.name         AS theatre_name,
       th.city         AS theatre_city
FROM shows s
JOIN screens sc ON sc.id = s.screen_id
JOIN theatres th ON th.id = sc.theatre_id
WHERE s.id = $1;

-- 5. List seats for a show with statuses and prices
--    behaviour: show not found -> zero rows; no seats -> zero rows
SELECT ss.show_id      AS show_id,
       ss.seat_id      AS seat_id,
       ss.status       AS status,
       ss.price        AS price,
       s.row_label     AS row_label,
       s.seat_number   AS seat_number,
       s.seat_type     AS seat_type
FROM show_seats ss
JOIN seats s ON s.id = ss.seat_id
WHERE ss.show_id = $1
ORDER BY s.row_label, s.seat_number;

-- 6. Availability count for a show
--    behaviour: shows not found -> 0; a "held" seat is NOT available; an
--    expired-but-not-yet-reclaimed hold is NOT available until reclaimed.
SELECT COUNT(*) AS available_count
FROM show_seats ss
JOIN seats s ON s.id = ss.seat_id
WHERE ss.show_id = $1
  AND ss.status = 'AVAILABLE';

-- 7. Show's seat availability (total vs held vs booked vs available)
--    behaviour: zero rows when the show doesn't exist
SELECT COUNT(*) FILTER (WHERE ss.status = 'AVAILABLE')      AS available_count,
       COUNT(*) FILTER (WHERE ss.status = 'HELD')          AS held_count,
       COUNT(*) FILTER (WHERE ss.status = 'BOOKED')        AS booked_count,
       COUNT(*)                                            AS total_count
FROM show_seats ss
WHERE ss.show_id = $1;

-- 8. Revenue for a date range (admin report)
--    behaviour: an empty range returns one row of zeroes, never NULL or no row.
--    $1/$2 = optional inclusive date bounds on created_at (NULL = unbounded).
--    gross  = successful payments taken, refunds = requested or approved
--    refunds filed, net = gross - refunds. A REQUESTED refund is subtracted
--    because the money is committed to the customer even before approval.
WITH paid AS (
    SELECT COUNT(*)                           AS payment_count,
           COALESCE(SUM(p.amount), 0)         AS gross
    FROM payments p
    WHERE p.status = 'SUCCESS'
      AND ($1::date IS NULL OR p.created_at >= $1::date)
      AND ($2::date IS NULL OR p.created_at < ($2::date + INTERVAL '1 day'))
), refunded AS (
    SELECT COUNT(*)                           AS refund_count,
           COALESCE(SUM(r.amount), 0)         AS refunds
    FROM refunds r
    WHERE r.status IN ('REQUESTED', 'APPROVED')
      AND ($1::date IS NULL OR r.created_at >= $1::date)
      AND ($2::date IS NULL OR r.created_at < ($2::date + INTERVAL '1 day'))
)
SELECT paid.payment_count,
       paid.gross,
       refunded.refund_count,
       refunded.refunds,
       paid.gross - refunded.refunds AS net
FROM paid, refunded;

-- 9. Occupancy per show for a date range (admin report)
--    behaviour: no shows in range -> zero rows; a show with no seats reports
--    occupancy_pct NULL rather than dividing by zero.
SELECT v.show_id,
       m.title            AS movie_title,
       v.theatre_name,
       v.screen_name,
       v.show_start_at,
       v.booked_count,
       v.held_count,
       v.available_count,
       v.total_count,
       ROUND(100.0 * v.booked_count / NULLIF(v.total_count, 0), 1) AS occupancy_pct
FROM vw_show_availability v
JOIN movies m ON m.id = v.movie_id
WHERE ($1::date IS NULL OR v.show_start_at >= $1::date)
  AND ($2::date IS NULL OR v.show_start_at < ($2::date + INTERVAL '1 day'))
ORDER BY v.show_start_at, v.show_id;

-- 10. Top movies by confirmed revenue (admin report)
--    behaviour: only CONFIRMED bookings count, so cancelled and expired
--    bookings contribute nothing; a movie with no bookings is absent.
--    $1 = limit (positive integer).
SELECT m.id                AS movie_id,
       m.title,
       COUNT(DISTINCT b.id) AS booking_count,
       COUNT(bs.seat_id)    AS seats_sold,
       COALESCE(SUM(bs.price), 0) AS revenue
FROM movies m
JOIN shows sh    ON sh.movie_id = m.id
JOIN bookings b  ON b.show_id = sh.id AND b.status = 'CONFIRMED'
JOIN booking_seats bs ON bs.booking_id = b.id
GROUP BY m.id, m.title
ORDER BY revenue DESC, m.id
LIMIT $1;

