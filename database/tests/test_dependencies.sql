-- ============================================================================
-- Show-book-kar — constraint dependency tests
-- Owner: M | Reviewer: H, S
-- ============================================================================
--
-- Negative tests for NOT NULL and foreign-key dependency rules. Each script
-- is an isolated transaction and must fail with the expected SQLSTATE.
--
-- Expected SQLSTATEs:
--   23502  not_null_violation
--   23503  foreign_key_violation
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/tests/test_dependencies.sql
-- ============================================================================

-- 1. NOT NULL: users.email
BEGIN;
INSERT INTO users (id, password_hash, name, role) VALUES (1, 'hash', 'NoEmail');
ROLLBACK;
-- expect: 23502

-- 2. NOT NULL: movies.title
BEGIN;
INSERT INTO movies (id, language, duration_minutes) VALUES (1, 'English', 90);
ROLLBACK;
-- expect: 23502

-- 3. NOT NULL: theatres.city
BEGIN;
INSERT INTO theatres (id, name) VALUES (1, 'The Grand');
ROLLBACK;
-- expect: 23502

-- 4. NOT NULL: screens.theatre_id
BEGIN;
INSERT INTO screens (id, name, capacity_total) VALUES (1, 'Main', 200);
ROLLBACK;
-- expect: 23502

-- 5. NOT NULL: seats.row_label
BEGIN;
INSERT INTO seats (id, screen_id, seat_number, seat_type) VALUES (1, 1, 1, 'standard');
ROLLBACK;
-- expect: 23502

-- 6. NOT NULL: shows.start_at
BEGIN;
INSERT INTO shows (id, movie_id, screen_id, end_at, base_price)
VALUES (1, 1, 1, '2026-01-01 12:00', 5.00);
ROLLBACK;
-- expect: 23502

-- 7. NOT NULL: bookings.user_id
BEGIN;
INSERT INTO bookings (id, show_id, status, total_amount) VALUES (1, 1, 'PENDING', 5.00);
ROLLBACK;
-- expect: 23502

-- 8. NOT NULL: booking_seats.show_id
BEGIN;
INSERT INTO booking_seats (booking_id, seat_id, price) VALUES (1, 1, 5.00);
ROLLBACK;
-- expect: 23502

-- 9. NOT NULL: payments.amount
BEGIN;
INSERT INTO payments (id, booking_id, status) VALUES (1, 1, 'PENDING');
ROLLBACK;
-- expect: 23502

-- 10. NOT NULL: refunds.amount
BEGIN;
INSERT INTO refunds (id, payment_id, status) VALUES (1, 1, 'REQUESTED');
ROLLBACK;
-- expect: 23502

-- 11. FK: bookings.user_id -> users
BEGIN;
INSERT INTO bookings (id, user_id, show_id, status, total_amount)
VALUES (2, 9999, 1, 'PENDING', 5.00);
ROLLBACK;
-- expect: 23503

-- 12. FK: bookings.show_id -> shows
BEGIN;
INSERT INTO bookings (id, user_id, show_id, status, total_amount)
VALUES (3, 1, 9999, 'PENDING', 5.00);
ROLLBACK;
-- expect: 23503

-- 13. FK: payment.booking_id -> bookings
BEGIN;
INSERT INTO payments (id, booking_id, amount, status)
VALUES (1, 9999, 5.00, 'PENDING');
ROLLBACK;
-- expect: 23503

-- 14. FK: refund.payment_id -> payments
BEGIN;
INSERT INTO refunds (id, payment_id, booking_id, amount, status)
VALUES (1, 9999, 1, 5.00, 'REQUESTED');
ROLLBACK;
-- expect: 23503

-- 15. FK: booking_seats.seat_id -> show_seats
BEGIN;
INSERT INTO booking_seats (booking_id, show_id, seat_id, price)
VALUES (1, 1, 9999, 5.00);
ROLLBACK;
-- expect: 23503
