-- ============================================================================
-- Show-book-kar — views
-- Owner: M | Reviewer: H (for query shape) then S (for report/dashboard use)
-- ============================================================================
--
-- Views keep the read model separated from the base tables. They are the
-- source for H's report and S's admin-dashboard queries, and they are
-- refreshed on every read — no denormalised snapshot to keep consistent.
-- ============================================================================

-- 1. Show availability view: per-show seat counts for a display
--    behaviour: a show with zero show_seats will return exactly one row with
--    zeroes (because the aggregate is computed over the LEFT JOIN). A missing
--    show returns zero rows.
CREATE VIEW vw_show_availability AS
SELECT s.id             AS show_id,
       s.movie_id       AS movie_id,
       s.screen_id      AS screen_id,
       s.start_at       AS show_start_at,
       s.end_at         AS show_end_at,
       s.base_price     AS show_base_price,
       sc.id            AS screen_id_2,
       sc.name          AS screen_name,
       th.id            AS theatre_id,
       th.name          AS theatre_name,
       th.city          AS theatre_city,
       COUNT(ss.seat_id)Filter (WHERE ss.status = 'AVAILABLE') AS available_count,
       COUNT(ss.seat_id)Filter (WHERE ss.status = 'HELD')      AS held_count,
       COUNT(ss.seat_id)Filter (WHERE ss.status = 'BOOKED')     AS booked_count,
       COUNT(ss.seat_id)                                        AS total_count
FROM shows s
JOIN screens sc ON sc.id = s.screen_id
JOIN theatres th ON th.id = sc.theatre_id
LEFT JOIN show_seats ss ON ss.show_id = s.id
GROUP BY s.id, sc.id, th.id
ORDER BY s.start_at;

-- 2. Booking history view: one row per booking with the seats it holds
--    behaviour: a booking with no booking_seats rows still appears once (LEFT
--    JOIN) with seat columns NULL. Only the requesting user's bookings are
--    visible to H; see H's route-level authorization (do not rely on this
--    view alone for access control).
CREATE VIEW vw_booking_history AS
SELECT b.id              AS booking_id,
       b.user_id         AS user_id,
       b.show_id         AS show_id,
       b.status          AS booking_status,
       b.total_amount    AS booking_total_amount,
       b.created_at      AS booking_created_at,
       s.id              AS seat_id,
       s.row_label       AS seat_row_label,
       s.seat_number     AS seat_number,
       ss.status         AS seat_status,
       ss.price          AS seat_price_at_booking
FROM bookings b
JOIN shows s ON s.id = b.show_id
LEFT JOIN booking_seats bs ON bs.booking_id = b.id
LEFT JOIN seats s ON s.id = bs.seat_id
                    AND s.screen_id = (
                        SELECT sc.id
                        FROM screens sc
                        WHERE sc.id = (SELECT sc2.id FROM screens sc2 JOIN shows sh2 ON sh2.screen_id = sc2.id WHERE sh2.id = b.show_id)
                    )
                    -- The join above is simplified; the route-level query
                    -- materialises seats with their screen to avoid the
                    -- sub-select. It is documented here for completeness.
ORDER BY b.created_at DESC;
