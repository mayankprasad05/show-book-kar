# Design Note — Show-book-kar

Owner: M | Reviewers: H (API fit), S (UI fields)
Status: frozen for the first integration pass (Block 2 gate)

## 1. Entities and relationships

```text
users 1---M movies 1---M shows 1---1 screens 1---M seats 1---M shows
  |          |              |              |
  |          |              |              +---M show_seats
  |          |              |                    (per-show status)
  |          |              +---M shows
  |          +---M movies
  +---M bookings 1---M booking_seats 1---M payments 1---M refunds
```

- A **user** books through bookings.
- A **movie** can have many shows.
- A **theatre** contains many screens.
- A **screen** contains many seats.
- A **show** is scheduled on one screen and features one movie.
- A **seat** is physical and belongs to a screen; it is NOT itself "booked".
- A **show_seats** row is the authoritative per-show seat state.
- A **booking** references one show; **booking_seats** holds the seats and
  their snapshotted prices.
- A **payment** is one per booking.
- A **refund** is one per payment.

## 2. Table names and keys

| Table          | PK                 | Notable unique/FK                  |
| -------------- | ------------------ | ---------------------------------- |
| users          | id (identity)      | email unique                       |
| movies         | id (serial)        |                                    |
| theatres       | id (serial)        |                                    |
| screens        | id (serial)        | (theatre_id, name) unique          |
| seats          | id (serial)        | (screen_id, row_label, seat_number) unique |
| shows          | id (serial)        | (movie_id, screen_id, start_at) unique; time check |
| show_seats     | (show_id, seat_id) | FK to shows + seats (composite)   |
| bookings       | id (serial)        | (user_id, show_id) unique          |
| booking_seats  | (booking_id, show_id, seat_id) | composite FK to show_seats |
| payments       | id (serial)        | booking_id unique                  |
| refunds        | id (serial)        | payment_id unique                  |

## 3. Status values and allowed transitions

### bookings

| Status    | Allowed next                              |
| --------- | ----------------------------------------- |
| PENDING   | CONFIRMED (after successful payment); EXPIRED (hold expiry); CANCELLED (within cutoff) |
| CONFIRMED | CANCELLED (within cutoff)                 |
| CANCELLED | (terminal)                                |
| EXPIRED   | (terminal)                                |

### show_seats (hold state)

| Status    | Allowed next                              |
| --------- | ----------------------------------------- |
| AVAILABLE | HELD (hold); (otherwise stays)            |
| HELD      | BOOKED (on successful payment); AVAILABLE (release on payment failure/expiry) |
| BOOKED    | (terminal)                                |

### payments

| Status  | Allowed next                     |
| ------- | -------------------------------- |
| PENDING | SUCCESS / FAILED                 |
| SUCCESS | (terminal; fully refunded if refunded) |
| FAILED  | PENDING (retry) / SUCCESS        |

Repeated payment requests are idempotent: a second SUCCESS for the same
booking is a no-op, never a duplicate.

### refunds

| Status    | Allowed next |
| --------- | ------------ |
| REQUESTED | APPROVED / REJECTED |
| APPROVED  | (terminal)   |
| REJECTED  | (terminal)   |

## 4. Business rules (README §1.4, agreed before coding)

- Hold duration: 5 minutes (recommended).
- Cancellation cutoff: choose a documented rule; default: cancellable within
  24 hours of booking, or any time if a documented cutoff is reached.
- Failed payment: release seats immediately (simple version) after recording
  the failure.
- Repeated payment: idempotent.
- All money as NUMERIC; all event timestamps as TIMESTAMPTZ.
- Never trust user_id from the browser; derive the current user from the
  authenticated session.
- A seat is available for a show only when `show_seats.status = 'AVAILABLE'`
  or an expired hold can be safely reclaimed inside the same transaction.
- A booking must reference one show only.
- A confirmed booking requires a successful simulated payment.
- Booking/seat/payment records are updated transactionally.
- Cancellation must not delete booking/payment history.
- A refund is a separate record; a payment is fully refunded only after the
  full amount has been refunded.

## 5. Schema review checklist (continues to Block 2 gate)

- [ ] All 11 core tables present in dependency order.
- [ ] Identity PKs everywhere; consistent PK strategy.
- [ ] Named constraints; NOT NULL where required; CHECK for numeric/status;
  NOT NULL name/city fields.
- [ ] Unique email; unique screen name per theatre; unique seat coordinate
  (screen_id, row_label, seat_number).
- [ ] Composite PK on show_seats(show_id, seat_id); composite FK
  booking_seats(show_id, seat_id).
- [ ] booking show_id consistency enforced via composite FK.
- [ ] FK actions deliberate — no cascade on bookings/payments.
- [ ] created_at on entity tables; TIMESTAMPTZ anywhere time matters.
- [ ] overlap prevention agreed (exclusion constraint or trigger).
- [ ] show_seats holds status, hold_expires_at, held_by_booking_id.
- [ ] prices NUMERIC(10,2) — no floating point.
- [ ] Schema recreated from a clean database; second run fails clearly or is
  safely repeatable.
- [ ] H reviews constraints; S reviews fields; names frozen.
