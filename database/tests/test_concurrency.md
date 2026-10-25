# Concurrency test — Show-book-kar

Owner: M | Reviewer: H
Location: `database/tests/test_concurrency.sql` + `docs/test-results/`

## What it demonstrates

Two sessions race for the same seat. Only one can win. This proves the
database-level row locking and atomicity that the hold transaction relies on.

## Steps

1. Prepare a scratch database: load `schema.sql`, then `seed.sql`.
2. Start Session A and Session B (two `psql` connections, or two app
   instances).
3. Session A runs `BEGIN; SELECT ... FROM show_seats WHERE show_id=$1 AND
   seat_id=$2 FOR UPDATE;` and then issues the hold. It should succeed and
   commit.
4. Session B runs the same hold while A holds the lock. Session B must block
   until A commits, then re-read the seat, find it HELD, and fail with a
   clean 409/SEAT_UNAVAILABLE.
5. Verify: after both sessions finish, the booking/seat tables contain
   **exactly one** successful booking and the winning seat is HELD, while the
   losing session created **zero** rows.

## Positive control

Run the same two sessions but have them take **different** seats. Both must
succeed, proving the lock is per-seat and does not serialise unrelated holds.

## Evidence

Save the transcripts, queries, and any screenshots in
`docs/test-results/`. Record the exact SQLSTATE and HTTP status each
session received.

## Result log format

```text
session_a: hold succeeded, booking_id=501, seat=42 -> HELD
session_b: hold failed, error=SEAT_UNAVAILABLE, rows_created=0
final: bookings=1, seats(HELD)=1, seats(AVAILABLE)=n-1
```
