-- ============================================================================
-- Show-book-kar — read queries
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
--    $1 = movie_id (required), $2 = start-of-day filter (optional)
SELECT s.id, s.start_at, s.end_at, s.base_price, sc.id AS screen_id, sc.name AS screen_name, th.id AS theatre_id, th.name AS theatre_name, th.city
FROM shows s
JOIN screens sc ON sc.id = s.screen_id
JOIN theatres th ON th.id = sc.theatre_id
WHERE s.movie_id = $1
  AND ($2::timestamptz IS NULL OR s.start_at >= $2)
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
