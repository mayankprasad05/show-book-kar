# Show-book-kar

Movie ticket booking and seat reservation system built on PostgreSQL and Flask. It covers the full path from browsing the catalogue to holding seats, paying, cancelling and reviewing bookings, plus an admin area for scheduling shows and reading sales reports.

Seat availability is enforced by the database, not the client: a seat is `AVAILABLE`, `HELD` or `BOOKED`, a hold lasts five minutes, and payment, cancellation and hold expiry run inside SQL functions so two users cannot buy the same seat.

| | |
|---|---|
| **Stack** | PostgreSQL, Python 3 + Flask, HTML / CSS / JavaScript |
| **Database** | `show-book-kar` (11 tables, 6 functions, 2 views) |
| **API tests** | 74 pytest cases |

## Features

- Movie catalogue with title, language and runtime on a poster-style grid.
- Showtimes per movie with theatre, screen, start time and base price.
- Interactive seat map with a status legend and per-seat prices.
- Seat holds with a 5-minute expiry and a 10-seat limit per booking.
- Checkout that confirms the booking and records the payment.
- Cancellation up to 2 hours before the show, which files a refund request.
- Booking history for the signed-in user.
- Admin screens for movies, theatres, screens and shows, plus revenue reports.
- Session-cookie authentication with bcrypt password hashes and an admin role.

## Repository layout

```text
show-book-kar/
  README.md                     setup, running and reference (this file)
  requirements.txt              Python dependencies
  .env.example                  environment template (copy to .env)
  backend/
    app.py                      Flask app factory, JSON and CORS setup
    db.py                       psycopg2 connections and transactions
    auth.py                     bcrypt hashing, sessions, role checks
    errors.py                   SQLSTATE / signal -> HTTP error mapping
    validators.py               request parsing and validation
    routes/                     health, catalog, auth, bookings, admin, reports
    tests/                      pytest suite (74 tests)
    README.md                   API contract, error reference, DB contract
  frontend/
    index.html                  movie catalogue
    movie.html                  movie detail and showtimes
    seats.html                  seat map and hold
    checkout.html               payment
    bookings.html               booking history and cancellation
    login.html, register.html   account screens
    admin/index.html            administration and reports
    static/                     css/ and js/ used by the pages
  database/
    schema.sql                  11 tables with named constraints
    functions.sql               hold, pay, cancel, release, scheduling
    views.sql                   availability and booking-history views
    indexes.sql                 indexes with the queries that justify them
    queries.sql                 read queries used by the API
    seed.sql                    deterministic sample data
    DESIGN_NOTE.md              entities, keys, status values, business rules
    TRANSACTION.md              transaction boundaries and locking
    ER Diagram.png              ER diagram
    scripts/
      generate_seed.py          regenerates seed.sql
      load_schema.sql           schema-only load steps
      reset_database.sql        full reset steps
    tests/                      SQL negative tests and the concurrency procedure
```

## Prerequisites

- PostgreSQL 14 or newer, reachable on `localhost:5432` (developed and verified against 18.6).
- Python 3.11 or newer (developed on 3.13).
- pgAdmin 4, or any other client that can run a `.sql` file.
- A terminal. On Windows, Git Bash is a convenient choice because the commands below use POSIX paths.

## Database setup

The scripts are plain SQL files and are loaded in this order. Skipping `functions.sql` leaves the write path broken: tables exist, but holding, paying and cancelling fail because the functions are missing.

### 1. Create the database

In pgAdmin 4, expand your PostgreSQL server, right-click **Databases** -> **Create** -> **Database...**, set **Database** to `show-book-kar` (with hyphens) and **Owner** to `postgres`, then click **Save**. If the new database shows a red cross badge it is simply not connected yet; click it or right-click -> **Connect Database**.

Confirm you are pointed at the right place before loading anything:

```sql
SELECT current_database(), current_schema(), current_user;
```

`current_database()` must be `show-book-kar` and `current_schema()` must be `public`.

### 2. Load the files in order

Use **Query Tool** on `show-book-kar` for each file. Click the **Open File** icon (folder, top-left of the Query Tool toolbar), select the file, then press **F5**.

1. `database/schema.sql` - creates the 11 tables
2. `database/functions.sql` - creates `fn_hold_seats`, `fn_pay_booking`, `fn_cancel_booking`, `fn_create_show`, `fn_release_expired_holds`, `fn_pending_holds`
3. `database/views.sql` - creates `vw_show_availability`, `vw_booking_history`
4. `database/indexes.sql` - creates the indexes
5. `database/seed.sql` - inserts the sample data

Do not paste `\i database/schema.sql` into the Query Tool. `\i` is a `psql` meta-command, not SQL, and pgAdmin reports `syntax error at or near "\"`. Opening the file with the folder icon is the equivalent. The Query Tool runs in autocommit mode, so a successful run is already committed.

### 3. Verify the load

Row counts:

```sql
SELECT 'theatres' AS t, COUNT(*) FROM theatres
UNION ALL SELECT 'screens', COUNT(*) FROM screens
UNION ALL SELECT 'seats', COUNT(*) FROM seats
UNION ALL SELECT 'movies', COUNT(*) FROM movies
UNION ALL SELECT 'shows', COUNT(*) FROM shows
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'bookings', COUNT(*) FROM bookings
UNION ALL SELECT 'show_seats', COUNT(*) FROM show_seats
UNION ALL SELECT 'booking_seats', COUNT(*) FROM booking_seats
UNION ALL SELECT 'payments', COUNT(*) FROM payments
UNION ALL SELECT 'refunds', COUNT(*) FROM refunds
ORDER BY t;
```

Expected: 5, 7, 740, 15, 12, 17, 5, 192, 7, 4, 1 - matching the seed table below.

Seat status split, which is the check that proves the hold logic seeded correctly:

```sql
SELECT status, COUNT(*) FROM show_seats GROUP BY status ORDER BY status;
```

Expected: `AVAILABLE 185`, `BOOKED 6`, `HELD 1`.

Referential integrity spot-check (both should return 0):

```sql
SELECT COUNT(*) AS orphan_holds
FROM show_seats ss
WHERE ss.held_by_booking_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.id = ss.held_by_booking_id);

SELECT COUNT(*) AS bad_seat_bookings
FROM booking_seats bs
WHERE NOT EXISTS (
    SELECT 1 FROM show_seats ss
    WHERE ss.show_id = bs.show_id AND ss.seat_id = bs.seat_id
);
```

Sequence resync check, so future inserts do not collide:

```sql
SELECT last_value FROM users_id_seq;   -- expect 17
```

Persistence check: right-click `show-book-kar` -> **Disconnect Database**, then **Connect Database**, and re-run the count query. If the numbers survive the reconnect, the data is on disk.

## Seed data

The seed is deterministic: the same generator always produces the same file, so every machine starts from the same demo state.

| Table | Rows |
|---|---|
| `theatres` | 5 |
| `screens` | 7 |
| `seats` | 740 |
| `movies` | 15 |
| `shows` | 12 |
| `users` | 17 (15 customers, 2 admins) |
| `bookings` | 5 (4 CONFIRMED, 1 PENDING) |
| `show_seats` | 192 (185 AVAILABLE, 6 BOOKED, 1 HELD) |
| `booking_seats` | 7 |
| `payments` | 4 (all SUCCESS) |
| `refunds` | 1 (REQUESTED) |

Every seeded account uses the password **`Passw0rd!`**. `alice@example.com` is a customer and `admin1@example.com` is an admin. Passwords are stored as bcrypt digests, never as plaintext.

The timeline is coherent for demos: catalogue rows were created on 1 November 2026, all five bookings fall on 20-22 November 2026, shows run on 2-4 December 2026, payments were taken on 20 November and the refund was requested on 24 November. Each booking therefore sits 10-12 days before its show, so the cancellation cutoff can be exercised. The single seeded `HELD` seat expires five minutes before its show starts (3 December 09:55), so that booking can still be paid; create a separate hold if you want to demonstrate `fn_release_expired_holds`.

## Configuration

Copy the template and fill it in:

```bash
cp .env.example .env
```

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=show-book-kar
DB_USER=postgres
DB_PASSWORD=your_db_password_here
SECRET_KEY=some-random-string
HOLD_DURATION_MINUTES=5
CANCELLATION_CUTOFF_HOURS=2
```

- `DB_NAME` is the database created above. `backend/db.py` defaults to the same name, so the only value you must supply is `DB_PASSWORD`.
- `SECRET_KEY` signs the session cookie. Change it from the template value before any shared or public demo.
- `HOLD_DURATION_MINUTES` and `CANCELLATION_CUTOFF_HOURS` are read by the hold and cancel routes; the same rules also live in SQL, so keep the two in step.
- `CORS_ORIGINS` is optional and defaults to `*`; set it explicitly before serving anything other than local development.

`.env` is ignored by Git. `.env.example` is committed and must never contain a real password.

## Install dependencies

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

On macOS or Linux use `.venv/bin/pip` instead. The pinned driver is `psycopg2-binary`, imported as `psycopg2`; do not add `psycopg` (v3) or `pg8000` alongside it.

## Run

The API and the static pages are two servers on two ports. Start each in its own terminal.

### API on port 5000

```bash
.venv/Scripts/python -m flask --app backend.app run --port 5000 --host 127.0.0.1
```

`backend.app` is the module holding the `create_app()` factory. Verify it is serving and connected:

```bash
curl -s http://127.0.0.1:5000/api/health
```

Expected: `"status": "ok"`, `"database": "ok"`, `"schema_loaded": true` and the PostgreSQL server version. A `503` means PostgreSQL is unreachable, which is usually a wrong `DB_PASSWORD`, a wrong `DB_NAME`, or a server that is not running.

### Frontend on port 8000

The pages sit at the root of `frontend/` and reference their assets as `static/...`, so the server root must be `frontend/`, not `frontend/static/`:

```bash
.venv/Scripts/python -m http.server 8000 --directory frontend
```

Open <http://127.0.0.1:8000/> and sign in with one of the demo accounts above.

### Use one hostname for both

`frontend/static/js/config.js` derives the API origin from `window.location.hostname` on port 5000, and the session cookie is `SameSite=Lax`. A page loaded from `127.0.0.1` that calls `localhost:5000` (or the reverse) is a cross-site request, so the browser drops the cookie and login fails silently with nothing in the API log. Pick one host and use it for both:

- <http://127.0.0.1:8000/> with `http://127.0.0.1:5000/api`, or
- <http://localhost:8000/> with `http://localhost:5000/api`.

To point the pages elsewhere, set `window.SBK_API_BASE` before the page's modules load.

## API

The full contract - endpoints, request and response fields, status codes, error format, session and role rules, and the database function signatures - is in [`backend/README.md`](backend/README.md). In short:

- All endpoints are under `/api`.
- Money is a JSON string (`"138.29"`) and timestamps are ISO-8601 with an offset.
- Errors always look like `{"error": "CODE", "message": "..."}`, for example `SEAT_UNAVAILABLE` or `HOLD_LIMIT_EXCEEDED`.
- The session cookie is `HttpOnly` and `SameSite=Lax`; admin routes also require the admin role.

## Tests

Run the API suite from the repository root:

```bash
.venv/Scripts/python -m pytest backend/tests -q
```

Expect 74 passed. The suite runs against the database named by `DB_NAME` in `.env` and restores the seeded state after every test, so it is safe to re-run against the demo database. It does delete any booking outside ids 1-5 together with its payments and refunds, so use a scratch database when the demo data must be preserved:

```bash
DB_NAME=show_book_kar_verify .venv/Scripts/python -m pytest backend/tests -q
```

The scripts in `database/tests/` are manual probes for constraints and concurrent holds, documented in `database/tests/README.md`. Their expected outcomes are currently exercised by the API suite above, so treat them as procedures to run by hand rather than as an automated test run.

## Resetting the database

Use this whenever the schema changes or a load fails halfway. It destroys all data in `public`, which is fine because everything is reproducible from `schema.sql` and `seed.sql`.

1. Open **Query Tool** on `show-book-kar`.
2. Run:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

3. Reload the files from the database setup steps above, in the same order.
4. Re-run the verification queries.

Without the `DROP SCHEMA` step, a second run of `schema.sql` fails with `42P07 relation already exists`, because the script is intentionally not idempotent.

## Regenerating the seed

`seed.sql` is generated output; change the generator instead of editing the file.

```bash
.venv/Scripts/python database/scripts/generate_seed.py
```

The script uses a fixed random seed, writes the file with LF endings and ASCII only, and prints the table count. Reload the database afterwards using the reset steps above.

## Database documentation

| Document | Contents |
|---|---|
| `database/DESIGN_NOTE.md` | Entities, relationships, keys, status values and business rules. |
| `database/TRANSACTION.md` | Hold and booking transaction boundaries: locking order, rollback conditions, why `show_seats` exists. |
| `database/queries.sql` | Read queries behind the API and UI, including empty-result behaviour, plus the admin report queries. |
| `database/functions.sql` | The write path: hold, pay, cancel, release-expired and show scheduling, with their signal messages. |
| `database/views.sql` | Availability and booking-history views. |
| `database/indexes.sql` | Each index with the query pattern and `EXPLAIN` evidence that justifies it. |
| `database/ER Diagram.png` | The ER diagram. |
| `backend/README.md` | API contract, error reference, session rules, database contract and known follow-ups. |

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `42P01` - relation "users" does not exist | Schema was never loaded, or the Query Tool is attached to another database | Check `current_database()`, then load `schema.sql` |
| `42P07` - relation already exists | `schema.sql` ran twice without a reset | Reset the database first |
| `42883` - function `fn_hold_seats` does not exist | `schema.sql` was loaded but `functions.sql` was not | Load `functions.sql` after the schema |
| `syntax error at or near "\"` | `\i` pasted into the Query Tool | Use the Open File icon instead |
| Seed runs "successfully" but tables are empty | Wrong database selected, or the load was rolled back after an error | Run `SELECT current_database();` and the counts above |
| Database icon shows a red cross | pgAdmin has no open connection to it | Click to expand it, or right-click -> Connect Database |
| API returns `503` from `/api/health` | PostgreSQL unreachable | Check `DB_PASSWORD` and `DB_NAME` in `.env`, and that the server is running |
| Login succeeds but the next request is anonymous | Pages and API opened on different hostnames | Use `127.0.0.1` for both, or `localhost` for both |

## Known limitations

These are deliberate stopping points of the current schema, not accidental omissions:

- `shows` has no exclusion constraint preventing two overlapping shows on the same screen; scheduling checks for overlap in `fn_create_show` instead.
- `booking_seats` has no primary key of its own; uniqueness of a seat within a booking is enforced through `show_seats`.
- Refunds are recorded and can be requested, but there is no admin approval step yet.
- `CORS_ORIGINS` defaults to `*`, which suits local development only.
