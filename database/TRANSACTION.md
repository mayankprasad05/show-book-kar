# Booking Hold Transaction — database/TRANSACTION.md

## 1. Authoritative path

Core booking logic lives in the **database** (a PostgreSQL function or a
parameterized SQL service), exactly **one** place. This keeps locking and
atomicity demonstrable in two `psql` sessions without the backend running.

Recommended for this DBMS project: a database function, because it keeps the
transaction in one place and lets M demonstrate the two-session hold test
purely in SQL.

## 2. The hold transaction (pseudocode, real SQL in functions.sql)

```sql
BEGIN;

-- 1. Requested seat ids must be unique in the request (enforced by H's route).

-- 2. All requested seats belong to the requested show.
--    SELECT seat_id FROM show_seats WHERE show_id=$1 AND seat_id IN ($2...)

-- 3. Lock selected show_seats rows in a consistent order (by seat_id) to
--    reduce deadlock risk:
--    SELECT ... FROM show_seats WHERE show_id=$1 AND seat_id IN (...)
--    ORDER BY seat_id FOR UPDATE;

-- 4. Verify every requested row was found.
--    A lock over *found* rows proves nothing about rows that were not found.
--    Count the locked rows; if the count < number of requested seats ->
--    fail with "unavailable" and ROLLBACK.

-- 5. Verify every seat is AVAILABLE, or reclaim an expired hold only after
--    rechecking its expiry INSIDE the same transaction:
--      SELECT status, hold_expires_at FROM show_seats ... FOR UPDATE
--      WHERE status = 'HELD' AND hold_expires_at < NOW() -> reclaim
--      (UPDATE show_seats SET status='AVAILABLE', held_by_booking_id=NULL
--       WHERE ... AND hold_expires_at < NOW())

-- 6. Insert one bookings row and one booking_seats row per seat.
--    total_amount computed from DATABASE prices (show_seats.price), never
--    accepted as authoritative from the client.

-- 7. Set seats to HELD, held_by_booking_id, expiry — all in the same
--    transaction.

COMMIT;
```

## 3. Failure rule

A failed hold leaves **zero** orphan rows: the INSERTs happen in step 6, and
any exception before `COMMIT` rolls back the whole transaction. No partial
reservation is ever created, and the database (not the frontend) decides
availability.

## 4. Locking rationale

- `FOR UPDATE` on `show_seats` rows serialises concurrent holds for the same
  seat. Because rows are locked in a consistent order (by `seat_id`), the
  snapshot avoids the classic deadlock between two sessions fighting over
  different seats.
- The lock also acts as the re-read: a hold sees the rows it locked, so a
  concurrent payment/cancellation that freed a seat is only visible if the
  hold re-checks expiry inside the same transaction.
- Overlapping holds for the same seat are impossible: only one session can
  hold the `FOR UPDATE` lock at a time.

## 5. Overlap prevention for shows on one screen

Preventing two shows starting at the same time is enforced in two places,
depending on the agreed approach:

1. **Show level** — `UNIQUE (movie_id, screen_id, start_at)` plus a
   `CHECK (end_at > start_at)` in `shows`.
2. **Screen level** — an exclusion constraint (or a trigger) rejecting any
   new show on a screen that already has an overlapping show.

Which one is authoritative is decided with H before functions.sql is
written. See database/indexes.sql for the exclusion index if the exclusion
constraint is chosen.
