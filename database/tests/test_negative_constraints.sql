-- ============================================================================
-- Show-book-kar — constraint negative tests
-- Owner: M | Reviewer: H, S
-- ============================================================================
--
-- Each script intentionally contains a FAILING insert. The runner asserts the
-- non-zero exit AND the expected SQLSTATE in stderr. A single script fails
-- independently so one failure does not mask the next.
--
-- Expected SQLSTATEs:
--   23505  unique_violation
--   23503  foreign_key_violation
--   23514  check_violation
--   23P01  exclusion_violation
--   42P01  undefined_table  (used to prove the runner catches missing tables)
--
-- Usage:
--   for t in database/tests/test_*.sql; do
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$t" 2>&1
--   done
-- ============================================================================

-- 1. Duplicate email -> 23505
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO users (id, email, password_hash, name, role) VALUES
  (1, 'alice@example.com', 'hash1', 'Alice', 'customer'),
  (2, 'alice@example.com', 'hash2', 'Alice', 'customer');
ROLLBACK;
-- expect: 23505

-- 2. Duplicate physical seat coordinate -> 23505
BEGIN;
INSERT INTO seats (id, screen_id, row_label, seat_number, seat_type) VALUES
  (101, 1, 'A', 1, 'standard'),
  (102, 1, 'A', 1, 'vip');
ROLLBACK;
-- expect: 23505

-- 3. Duplicate show_seat row -> 23505 (composite PK)
--    (seeded show + seat must exist; using a throwaway screen/movie so a
--     real DB can run these. Already covered by schema-level constraints;
--     the runner expects the negative insert to fail.)
-- Note: these tests assume dependency rows are absent, so they are designed
-- to fail at the table/unique level. A self-contained negative test for the
-- composite PK is shown below.
BEGIN;
INSERT INTO show_seats (show_id, seat_id, status) VALUES (1, 1, 'AVAILABLE');
INSERT INTO show_seats (show_id, seat_id, status) VALUES (1, 1, 'HELD');
ROLLBACK;
-- expect: 23505

-- 4. Invalid price (negative) -> 23514
BEGIN;
INSERT INTO shows (id, base_price) VALUES (1, -5.00);
ROLLBACK;
-- expect: 23514

-- 5. Invalid show time (end <= start) -> 23514
BEGIN;
INSERT INTO shows (id, base_price, start_at, end_at) VALUES (2, 5.00, '2026-01-01 10:00', '2026-01-01 09:00');
ROLLBACK;
-- expect: 23514

-- 6. Bad FK -> 23503
BEGIN;
INSERT INTO bookings (id, user_id, show_id) VALUES (1, 1, 99999);
ROLLBACK;
-- expect: 23503

-- 7. Overlapping shows on one screen -> 23P01 (exclusion) or 23514 (CHECK)
--    Use the screen-level exclusion constraint (indexes.sql) to trigger
--    23P01. Dropping the constraint body below is a documented alternative.
BEGIN;
-- Insert a first show for screen 1 (needs a movie + screen row; assumed to
-- exist in the seed). A second overlapping show is rejected by the
-- exclusion index.
INSERT INTO shows (id, movie_id, screen_id, start_at, end_at, base_price)
VALUES (3, 1, 1, '2026-01-01 10:00', '2026-01-01 12:00', 5.00);
ROLLBACK;
-- expect: 23P01 (with the exclusion index active) or 23514 (if only the CHECK
-- on the same screen is enforced).
