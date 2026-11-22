# Backend - Show-book-kar

Owner: H | Reviewers: M (database contract), S (API fields)

Flask JSON API over PostgreSQL. This file is the contract: S builds the frontend
against section 3, M reviews the database functions listed in section 6.

Status: **H's backend is complete** - health, catalogue reads, session auth,
hold, payment, cancellation, admin CRUD and reports are implemented and covered
by `backend/tests/` (74 tests). Remaining work in the project is S's frontend,
M's review of `database/functions.sql`, and the database test stubs.

---

## 1. Frozen decisions

| Decision | Value | Why |
|---|---|---|
| PostgreSQL driver | **psycopg2** (`psycopg2-binary`) | The only driver in the root `requirements.txt`. Do not add `psycopg` (v3) or `pg8000`. |
| Configuration | Flat `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` from `.env` | Matches `.env.example`. `DATABASE_URL` is not used. |
| Business rules | Only in the database (`database/functions.sql`) | One authoritative path; Python validates shape, owns the transaction boundary and maps errors. |
| SQL parameters | `%s` placeholders, always bound | `queries.sql` uses `$1`; converted on copy. No string interpolation of user input. |
| Money in JSON | String, e.g. `"138.29"` | `NUMERIC(10,2)` cannot round-trip through a float safely. |
| Timestamps in JSON | ISO-8601 with offset | Columns are `TIMESTAMPTZ`. |
| Identity | Flask signed session holding `user_id` + `role` | A `user_id` from the browser is never trusted. |
| Error shape | `{"error": "CODE", "message": "..."}` | One shape for every failure, including framework 404s. |
| Request bodies | JSON object | `400 INVALID_BODY` otherwise. |

Python handles validation, authorization, transaction boundaries and error
mapping. It never decides whether a seat is free, whether a hold expired, or
whether a refund is due - those questions are answered by SQL in one
transaction.

---

## 2. Running and testing

```bash
cp .env.example .env                      # then set DB_PASSWORD
.venv/Scripts/pip install -r requirements.txt

psql -v ON_ERROR_STOP=1 -f database/schema.sql
psql -v ON_ERROR_STOP=1 -f database/functions.sql
psql -v ON_ERROR_STOP=1 -f database/views.sql
psql -v ON_ERROR_STOP=1 -f database/indexes.sql
psql -v ON_ERROR_STOP=1 -f database/seed.sql

.venv/Scripts/python -m flask --app backend.app run --port 5000
.venv/Scripts/python -m pytest backend/tests -q
```

The suite runs against `DB_NAME` from `.env` and restores the seeded state after
every test, so it is safe to re-run against the demo database. Point it at a
scratch database by overriding the variable:

```bash
DB_NAME=show_book_kar_verify .venv/Scripts/python -m pytest backend/tests -q
```

Layout:

```text
backend/
├── app.py           app factory, JSON defaults, CORS, error handlers, blueprints
├── db.py            psycopg2 connection, transaction(), fetch_all/fetch_one
├── auth.py          bcrypt, session, current_user, login_required/admin_required
├── errors.py        ApiError + SQLSTATE/SIGNAL -> HTTP mapping (the only place)
├── validators.py    request parsing: ints, text, money, ISO timestamps, dates
├── routes/
│   ├── health.py    GET /api/health
│   ├── catalog.py   movies, movie detail, show detail, seat map
│   ├── auth.py      register, login, logout, me
│   ├── bookings.py  list, detail, hold, pay, cancel
│   ├── admin.py     movies/theatres/screens/seats/shows
│   └── reports.py   revenue, occupancy, top movies
├── tests/           conftest + one module per slice
└── README.md        this file
```

---

## 3. Endpoints

All routes live under `/api`. `Auth` column: `-` public, `user` signed in,
`admin` signed in with `role = 'admin'`.

### Health

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | - | Database reachable, schema loaded, server version/time. `503` when PostgreSQL is unreachable. |

### Catalogue

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/movies` | - | All movies, ordered by id. `{count, movies[]}` |
| GET | `/api/movies/<id>` | - | One movie plus its shows; optional `?date=YYYY-MM-DD` (half-open day). `{movie, date, shows[]}` |
| GET | `/api/shows/<id>` | - | Show with movie title, venue and seat counters. `{show, counts}` |
| GET | `/api/shows/<id>/seats` | - | Seat map ordered by row/number. `{show_id, counts, seats[]}` |

An unknown id is `404 NOT_FOUND` before the dependent query runs, so a seat map
is never an empty list for a show that does not exist.

### Auth

| Method | Path | Auth | Body | Success |
|---|---|---|---|---|
| POST | `/api/auth/register` | - | `{name, email, password}` | `201 {user}`, signed in |
| POST | `/api/auth/login` | - | `{email, password}` | `200 {user}`, signed in |
| POST | `/api/auth/logout` | - | - | `200 {status: "signed_out"}` |
| GET | `/api/auth/me` | user | - | `200 {user}` |

`user` is `{id, email, name, role, created_at}`; `password_hash` is never
serialised. Passwords: bcrypt cost 10, at least 8 characters, at most 72 bytes.
Unknown email and wrong password return the **same** `401 INVALID_CREDENTIALS`.
Registration always creates role `customer`; a `role` in the body is ignored.

### Bookings

| Method | Path | Auth | Body | Success |
|---|---|---|---|---|
| GET | `/api/bookings` | user | - | `{count, bookings[]}` - the caller's only |
| GET | `/api/bookings/<id>` | user | - | `{booking}`; `404` missing, `403` not yours |
| POST | `/api/bookings` | user | `{show_id, seat_ids[]}` | `201 {booking}` + `Location`; holds for `HOLD_DURATION_MINUTES` |
| POST | `/api/bookings/<id>/pay` | user | `{simulate?: "success"\|"failure"}` | `200 {booking}` |
| POST | `/api/bookings/<id>/cancel` | user | - | `200 {booking, cancellation_cutoff_hours}` |

A booking object:

```json
{ "booking_id": 6, "user_id": 1, "show_id": 6,
  "booking_status": "PENDING", "booking_total_amount": "330.00",
  "booking_created_at": "2026-11-16T19:07:00+05:30",
  "show_start_at": "2026-12-02T10:00:00+05:30",
  "movie_id": 3, "movie_title": "Interstellar",
  "screen_name": "Screen 1", "theatre_name": "PVR Inorbit", "theatre_city": "Mumbai",
  "seats": [ { "seat_id": 1, "row_label": "A", "seat_number": 1,
               "status": "BOOKED", "price": "165.00" } ] }
```

The hold response also carries `hold_expires_at`, `hold_duration_minutes` and
`show_id`, because the client needs the deadline before it can pay.

**Hold**: at most 10 seats, no duplicates, positive integers; `total_amount`,
`user_id` and `status` in the body are ignored (the database sets them). A hold
is all-or-nothing: one unavailable seat rejects the request and nothing is
written.

**Pay**: `simulate` defaults to `success`. A decline is a normal answer -
`200` with `payment_status: "FAILED"` and the booking still `PENDING` - so the
user can retry inside the hold window. Repeating a successful payment is
idempotent: the same `SUCCESS` is returned and no second payment row is created.
Paying after the hold expired is `409 HOLD_EXPIRED` with no writes at all.

**Cancel**: `CONFIRMED` only, and only until `CANCELLATION_CUTOFF_HOURS` before
the show. Seats return to `AVAILABLE`, the booking becomes `CANCELLED`, and a
`REQUESTED` refund is filed for the successful payment. Cancelling twice is
`409 INVALID_STATE`. After cancelling, the same user **can** book that show
again.

### Admin

The whole blueprint requires `role = 'admin'`; the guard is a single
`before_request`, so a new admin route cannot be added unguarded.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/admin/movies` | - | `{count, movies[]}` |
| POST | `/api/admin/movies` | `{title, language?, duration_minutes}` | `201` |
| PATCH | `/api/admin/movies/<id>` | any of `{title, language, duration_minutes}` | `200`; whitelisted columns only |
| GET | `/api/admin/theatres` | - | includes `screen_count` |
| POST | `/api/admin/theatres` | `{name, city}` | `201` |
| GET | `/api/admin/screens` | - | includes `theatre_name`, `seat_count` |
| POST | `/api/admin/screens` | `{theatre_id, name, capacity_total}` | `201` |
| POST | `/api/admin/screens/<id>/seats` | `{rows: [{row_label, count, seat_type?}]}` | `201`; capped by `capacity_total` |
| GET | `/api/admin/shows` | - | optional `?date=`; includes availability counts |
| POST | `/api/admin/shows` | `{movie_id, screen_id, start_at, end_at, base_price}` | `201`; creates the seat rows |

Seat setup example - 10 standard seats in row A, 5 VIP in row B:

```json
{ "rows": [ { "row_label": "A", "count": 10 },
            { "row_label": "B", "count": 5, "seat_type": "vip" } ] }
```

Show scheduling rejects a start in the past, `end_at <= start_at`, a missing
timezone, a negative price, a screen with no seats (`400`), and an overlap on
the same screen (`409 SHOW_OVERLAP`). Back-to-back shows are allowed. Each seat
of the new show is priced at `base_price`, matching `seed.sql`.

### Reports

| Method | Path | Query | Returns |
|---|---|---|---|
| GET | `/api/admin/reports/revenue` | `?from=&to=` | `{from,to,payment_count,gross,refund_count,refunds,net}` |
| GET | `/api/admin/reports/occupancy` | `?from=&to=` | `{count, shows[]}` |
| GET | `/api/admin/reports/top-movies` | `?limit=1..50` | `{count, movies[]}` |

Definitions are deliberately different and must not be conflated:

- **revenue** is cash flow: successful payments minus refunds with status
  `REQUESTED` or `APPROVED`, in the range. A `REQUESTED` refund is already
  committed money, so it is subtracted immediately. Empty range -> zeroes, not
  an empty object.
- **occupancy** is a per-show fill rate from `vw_show_availability`;
  `occupancy_pct` is `NULL` only if a show has no seats.
- **top-movies** counts only `CONFIRMED` bookings, so cancelled and expired
  bookings contribute nothing even though their payment rows still exist.

---

## 4. Error reference

Every failure - including framework 404s and method errors - uses
`{"error": "CODE", "message": "..."}`.

| Source | Signal / SQLSTATE | HTTP | `error` |
|---|---|---|---|
| Database | `SEAT_UNAVAILABLE` | 409 | `SEAT_UNAVAILABLE` |
| Database | `INVALID_SEATS` | 400 | `INVALID_SEATS` |
| Database | `SHOW_NOT_FOUND`, `BOOKING_NOT_FOUND`, `MOVIE_NOT_FOUND`, `SCREEN_NOT_FOUND` | 404 | `NOT_FOUND` |
| Database | `HOLD_EXPIRED` | 409 | `HOLD_EXPIRED` |
| Database | `INVALID_STATE` | 409 | `INVALID_STATE` |
| Database | `CANCELLATION_NOT_ALLOWED` | 409 | `CANCELLATION_NOT_ALLOWED` |
| Database | `SHOW_STARTED`, `SHOW_OVERLAP` | 409 | same as signal |
| Database | `FORBIDDEN` | 403 | `FORBIDDEN` |
| Database | `INVALID_TIME_RANGE`, `INVALID_PRICE`, `INVALID_SIMULATION`, `SCREEN_HAS_NO_SEATS` | 400 | `VALIDATION_ERROR` |
| Database | `23505` unique_violation | 409 | `CONFLICT` |
| Database | `23503` foreign_key_violation | 400 | `INVALID_REFERENCE` |
| Database | `23502` / `23514` | 400 | `VALIDATION_ERROR` |
| Database | `23P01` exclusion_violation | 409 | `CONFLICT` |
| Database | any other `P0001` | 409 | `CONFLICT` (signal text as message) |
| Route | missing session | 401 | `UNAUTHORIZED` |
| Route | bad credentials | 401 | `INVALID_CREDENTIALS` |
| Route | non-admin on admin route | 403 | `FORBIDDEN` |
| Route | duplicate email | 409 | `EMAIL_TAKEN` |
| Route | malformed body/field | 400 | `VALIDATION_ERROR` / `INVALID_BODY` / `INVALID_SEATS` / `INVALID_DATE` / `CAPACITY_EXCEEDED` |
| Anything else | - | 500 | `INTERNAL_ERROR` (generic message, details only in the log) |

`INTERNAL_ERROR` never contains SQL, DSNs, credentials or stack traces.

---

## 5. Session and role rules

| Item | Value |
|---|---|
| Session cookie | Flask signed cookie with `user_id` + `role`; `HttpOnly`, `SameSite=Lax` |
| CORS | `/api/*` with credentials; `CORS_ORIGINS` env var (default `*`) |
| Stale account | each request re-reads the user row; a deleted account is signed out |
| Session fixation | `login` clears the existing session before setting the new one |
| Logout | clears the cookie; see the limitation in section 8 |

---

## 6. Database contract

`database/functions.sql` is the write path. Signals are raised as
`RAISE EXCEPTION 'SIGNAL'` and mapped in section 4.

| Function | Returns | Signals |
|---|---|---|
| `fn_hold_seats(p_user_id, p_show_id, p_seat_ids int[], p_hold_minutes)` | `booking_id, status, hold_expires_at, total_amount` | `SHOW_NOT_FOUND`, `SHOW_STARTED`, `INVALID_SEATS`, `INVALID_STATE`, `SEAT_UNAVAILABLE` |
| `fn_pay_booking(p_booking_id, p_user_id, p_simulate)` | `booking_id, booking_status, payment_status, amount` | `BOOKING_NOT_FOUND`, `FORBIDDEN`, `INVALID_STATE`, `HOLD_EXPIRED`, `INVALID_SIMULATION` |
| `fn_cancel_booking(p_booking_id, p_user_id, p_cutoff_hours)` | `booking_id, booking_status, refund_status, refund_amount` | `BOOKING_NOT_FOUND`, `FORBIDDEN`, `INVALID_STATE`, `CANCELLATION_NOT_ALLOWED` |
| `fn_create_show(p_movie_id, p_screen_id, p_start_at, p_end_at, p_base_price)` | `show_id, movie_id, screen_id, start_at, end_at, base_price, seat_count` | `INVALID_TIME_RANGE`, `INVALID_PRICE`, `MOVIE_NOT_FOUND`, `SCREEN_NOT_FOUND`, `SHOW_OVERLAP`, `SCREEN_HAS_NO_SEATS` |
| `fn_release_expired_holds()` | `released int` | - |
| `fn_pending_holds()` | one row per PENDING booking | - |

`show_seats_hold_consistency` ties the columns together, so a partial update
fails with `23514`:

| Status | `hold_expires_at` | `held_by_booking_id` |
|---|---|---|
| `AVAILABLE` | NULL | NULL |
| `HELD` | NOT NULL | NOT NULL |
| `BOOKED` | NULL | NOT NULL |

**Who owns what.** H wrote `database/functions.sql` as the reference
implementation so the backend could be built and verified end to end while M's
version was pending. M owns the file and should review or replace it; the
backend depends only on the signatures and signal names above.

---

## 7. Transactions, locking and idempotency

- Every route uses `db.transaction()`: one connection, one transaction, commit
  on success, rollback on any exception, connection always closed.
- `fn_hold_seats` locks the requested `show_seats` rows with `SELECT ... FOR
  UPDATE` **ordered by `seat_id`**, then re-checks availability. Concurrent holds
  serialize; the loser sees the committed `HELD` row and gets
  `SEAT_UNAVAILABLE`. Fixed lock order also rules out deadlocks between two
  overlapping requests.
- `fn_create_show` locks the screen row before its overlap check, so two
  schedulers cannot both pass.
- `fn_pay_booking` locks the booking and its seats, and checks hold expiry
  **before** writing anything, so `HOLD_EXPIRED` leaves no partial state.
- Payments are unique per booking (`payments_booking_unique`); the retry path
  updates the existing row instead of inserting a second one, which makes
  repeated payment idempotent.
- A rejected request never leaves a booking, a `booking_seats` row, a payment,
  a refund or a seat status change behind. The tests assert this per failure
  path.

---

## 8. Known gaps and follow-ups

1. **Server-side session revocation.** Flask sessions are client-side, so
   logout clears the browser's cookie but a previously captured cookie stays
   valid until it expires. Fixing this needs a session table or a
   `users.session_version` column checked on each request.
2. **No exclusion constraint on `shows`.** Overlap prevention for the admin
   route is a locked check inside `fn_create_show`; a concurrent `psql` INSERT
   can still create an overlap. An `EXCLUDE USING gist (screen_id WITH =,
   tstzrange(start_at, end_at) WITH &&)` constraint is the durable fix.
3. **`booking_seats` has no primary key** (only `UNIQUE(booking_id, show_id,
   seat_id)`); harmless today but worth adding.
4. **Refunds are filed, never approved.** `refunds.status` stays `REQUESTED`;
   there is no admin approve/reject route yet.
5. **CORS default is `*`.** Fine for local development; set `CORS_ORIGINS`
   before any deployment.
6. **`database/tests/*.sql` are still stubs** and the negative tests still
   cannot produce their stated SQLSTATEs; the behaviour they describe is now
   covered by `backend/tests/`.
