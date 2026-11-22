# Show-book-kar

Movie ticket booking and seat reservation system.

| | |
|---|---|
| **Course** | DBMS project |
| **Stack** | PostgreSQL + pgAdmin 4, Python + Flask, HTML / CSS / JavaScript |
| **Team** | M (database), H (backend/API), S (frontend) |
| **Database** | `show-book-kar` |
| **Status** | Database layer complete and validated; Flask backend not started yet |

This README covers what is in the repository right now, what changed recently, and how to create and load the database from scratch in pgAdmin 4.

The 18-day task breakdown, phase gates, acceptance checklists and DBMS viva notes live in **[workplan.md](workplan.md)**.

---

## 1. Repository layout

```text
show-book-kar/
├── README.md                     this file: setup + what is here
├── workplan.md                   the full project plan and phase checklist
├── .gitignore
├── .env.example                  environment template (copy to .env, see section 8)
├── requirements.txt              Python dependencies for the project
├── database/
│   ├── schema.sql                11 tables, named constraints, indexes section
│   ├── functions.sql             hold/release functions (the write path)
│   ├── seed.sql                  deterministic sample data (regenerated, do not hand-edit)
│   ├── queries.sql               read queries used by the API/UI
│   ├── views.sql                 availability and booking-history views
│   ├── indexes.sql               measured indexes with comments
│   ├── DESIGN_NOTE.md            entities, keys, status values, business rules
│   ├── TRANSACTION.md            hold/booking transaction boundaries and locking
│   ├── ER Diagram.png            ER diagram
│   ├── scripts/
│   │   ├── generate_seed.py      regenerates seed.sql deterministically
│   │   ├── load_schema.sql       psql wrapper notes for schema-only load
│   │   └── reset_database.sql    psql wrapper notes for a full reset
│   └── tests/
│       ├── README.md             how the negative tests are meant to be run
│       ├── test_negative_constraints.sql
│       ├── test_dependencies.sql
│       ├── test_hold_expiry.sql
│       ├── test_payment_refund.sql
│       ├── test_reports.sql
│       ├── test_concurrency.sql
│       └── test_concurrency.md
└── docs/
    └── diagrams/                 ER source files (Mermaid) go here
```

`.env.example` and `requirements.txt` at the repository root are the only configuration templates: use them for the backend (section 8).

`backend/` exists and is complete: `app.py` (app factory + error handlers), `db.py` (psycopg2 connection and transactions), `auth.py` (bcrypt + session), `errors.py` (SQLSTATE/signal -> HTTP mapping), `validators.py` (request parsing), `routes/` (health, catalog, auth, bookings, admin, reports) and `tests/` (pytest, 74 tests). `backend/README.md` is the API + database contract the frontend builds against. The env file and dependency list stay at the repository root, as the templates expect; `frontend/` is S's part.

---

## 2. What was added

| File | What it is | Why it exists |
|---|---|---|
| `database/scripts/generate_seed.py` | Deterministic seed generator (`random.seed(7)`, Python 3.13) | `seed.sql` is ~60 KB of rows. Regenerating beats hand-editing, and the same input always produces the same file. It maps Python `None` to real SQL `NULL`, emits tables in foreign-key dependency order, and appends the sequence-resync block. |
| `database/scripts/load_schema.sql` | Documented schema-only load steps | Creating tables without data, for the "run it twice / clean database" test in the plan. |
| `database/scripts/reset_database.sql` | Documented full-reset steps | The exact drop-then-rebuild sequence so nobody improvises a destructive command. |
| `database/tests/test_*.sql` | Negative and behaviour tests | Each one deliberately violates one rule and must fail with a specific SQLSTATE, proving the constraint is real. |
| `database/tests/README.md` | Test index and run instructions | Explains that a pass means a *non-zero exit* plus the *expected SQLSTATE*. |
| `database/tests/test_concurrency.md` | Two-session race procedure | Evidence script for the row-locking demo. |
| ~~`backend/.env.example`~~ | Removed | Superseded by the root `.env.example`. The backend reads the same flat `DB_*` variables; do not recreate a second template. |
| ~~`backend/requirements.txt`~~ | Removed | The root `requirements.txt` is the only dependency list and it pins `psycopg2-binary`. Do not introduce `psycopg` v3 or `pg8000` alongside it. |
| `.env.example` (root) | Flat env template | Alternative host/port/user/password configuration used by the plan's Phase 0 checklist. |
| `requirements.txt` (root) | Full dependency list | Flask, Flask-Cors, psycopg2-binary, python-dotenv, bcrypt, python-dateutil, pytest, requests, waitress. |
| `.gitignore` | Ignore rules | Keeps `.env`, caches, virtualenvs, database dumps and logs out of Git. |

---

## 3. What changed in existing files

| File | Change | Reason |
|---|---|---|
| `database/schema.sql` | `users.id` changed from `GENERATED ALWAYS AS IDENTITY` to `GENERATED BY DEFAULT AS IDENTITY`. Every other table uses `SERIAL`. | `seed.sql` inserts explicit ids because bookings and theatres reference them. `ALWAYS` rejects that with SQLSTATE `428C9`. `BY DEFAULT` keeps the identity column while allowing the seed to supply values. |
| `database/schema.sql` | `show_seats` now carries `show_seats_held_by_fkey` (`held_by_booking_id IS NULL OR > 0`) and `show_seats_hold_consistency`, which ties `status` to `hold_expires_at` and `held_by_booking_id`. | An earlier seed wrote `held_by_booking_id = 0`, which no real booking owned. The CHECK now encodes the actual rule: AVAILABLE has no hold data, HELD has both, BOOKED has an owner but no expiry. |
| `database/schema.sql` | `booking_seats` has the composite foreign key `(show_id, seat_id) -> show_seats(show_id, seat_id)` alongside its plain FKs. | Guarantees a booked row belongs to the same show as the seat row, which a plain `seat_id` FK cannot express. |
| `database/schema.sql` | `screens.capacity_total` is `NOT NULL CHECK (> 0)`. | It was missing from the insert path and broke the seed with `23502`. |
| `database/seed.sql` | Fully regenerated. 4 `CONFIRMED` bookings (1-2 BOOKED seats each) and 1 `PENDING` booking (1 HELD seat) now reference real booking ids; 185 seats remain `AVAILABLE`. | Held/booked seats must point at a booking that exists. `held_by_booking_id = 0` was rejected by the schema. |
| `database/seed.sql` | Ends with a `DO $$ ... $$` block that runs `setval(pg_get_serial_sequence(...), MAX(id))` for every serial/identity table. | Inserting explicit ids leaves sequences at 1, so the first row the Flask app inserts would collide on the primary key. |
| `database/seed.sql` | Uses real `NULL` (not the string `'NULL'`) for `hold_expires_at` and `held_by_booking_id` on AVAILABLE and BOOKED rows. | Placeholder text would violate the timestamp type and the hold-consistency CHECK. |
| `database/tests/test_negative_constraints.sql` | The duplicate `show_seats` case now supplies `hold_expires_at` and `held_by_booking_id`. | With the new consistency CHECK, the row must be valid except for the duplicate it is testing. |
| `.sql` and `.md` files | Normalised to pure ASCII. | pgAdmin 4 refuses to open SQL files containing bidirectional Unicode characters, and the em dash/arrow characters triggered that warning. |
| `.gitignore` | Unresolved merge-conflict markers removed; the two halves merged. `database/scripts/load_schema.sql` and `reset_database.sql` are no longer ignored. | The conflict markers made half the file invalid. Ignoring those two real project scripts meant they could never be committed. |

---

## 4. Current seed contents

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

Two caveats, so nobody trips over them later:

- Every seeded user shares the demo password **`Passw0rd!`**, stored as a real bcrypt digest (rounds=10). `alice@example.com` is a customer and `admin1@example.com` is an admin. The digests are precomputed in `generate_seed.py` so regenerating the file stays byte-for-byte reproducible.
- The seeded timeline is now coherent: catalogue rows created 1 November 2026, all five bookings on 20-22 November 2026, shows on 2-4 December 2026, payments 20 November, the refund 24 November. Every booking therefore sits 10-12 days before its show, so a cancellation-cutoff rule can be exercised. The one seeded `HELD` seat expires five minutes before its show starts (3 December 09:55), so the demo can still pay for that booking; create a separate row if you need to demonstrate `release-expired-holds`.

---

## 5. Set up the database in pgAdmin 4

There is no `psql` requirement here. Everything below is done through the pgAdmin 4 GUI.

### 5.1 Create the database

1. In the left **Browser** tree, expand your PostgreSQL server (it asks for the password the first time; tick *Save password* so it stays connected).
2. Right-click **Databases** -> **Create** -> **Database...**
3. **Database**: `show-book-kar` (hyphen, exactly as used throughout this repo). **Owner**: `postgres`. Leave the rest at defaults.
4. Click **Save**.
5. The new database appears under **Databases**. If it shows a red cross badge, it simply is not connected yet: click its arrow or right-click -> **Connect Database**. The badge disappears.

Confirm you are pointed at the right database before doing anything else:

```sql
SELECT current_database(), current_schema(), current_user;
```

`current_database()` must be `show-book-kar` and `current_schema()` must be `public`.

### 5.2 Load the schema

1. Right-click **`show-book-kar`** -> **Query Tool**.
2. Click the **Open File** icon (folder, top-left of the Query Tool toolbar).
3. Select `database/schema.sql` from this repository.
4. Press **F5** (or the **Execute/Refresh** button, the play icon).

Do **not** paste commands such as `\i database/schema.sql` into the Query Tool. `\i` is a `psql` meta-command, not SQL, and pgAdmin reports `syntax error at or near "\"`. Opening the file with the folder icon is the equivalent.

Expect `CREATE TABLE` eleven times with no error. To confirm:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

You should see `booking_seats`, `bookings`, `movies`, `payments`, `refunds`, `screens`, `seats`, `show_seats`, `shows`, `theatres`, `users`.

### 5.3 Load the seed data

1. In the same Query Tool, click **Open File** again.
2. Select `database/seed.sql`.
3. Press **F5**.

Before the seed, load `database/functions.sql` the same way (Open File -> F5). It
creates `fn_hold_seats`, `fn_release_expired_holds` and `fn_pending_holds`, which
the backend calls for holds; the schema alone is not enough to run the write path.
Order matters: schema, then functions, then seed.

The file contains one multi-row `INSERT` per table plus a final `DO` block. A clean run raises no error. pgAdmin's Query Tool runs each statement in autocommit mode, so a successful run is already committed; there is no separate "save" step.

### 5.4 Verify the load

Row counts (`t` is aliased so the results line up alphabetically):

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

Expected: 5, 7, 740, 15, 12, 17, 5, 192, 7, 4, 1 - matching the table in section 4.

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

---

## 6. Resetting the database

Use this whenever the schema changes or a load fails halfway. It destroys all data in `public`, which is fine because everything here is reproducible from `schema.sql` + `seed.sql`.

1. Open **Query Tool** on `show-book-kar`.
2. Run:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

3. Re-run `database/schema.sql` (section 5.2).
4. Re-run `database/seed.sql` (section 5.3).
5. Re-run the checks in section 5.4.

Without the `DROP SCHEMA` step, a second run of `schema.sql` fails with `42P07 relation already exists`, because the script is intentionally not idempotent.

---

## 7. Regenerating `seed.sql`

Do not hand-edit `seed.sql`; change the generator and re-run it.

```bash
python database/scripts/generate_seed.py
```

On this machine, `python` may resolve to the Microsoft Store stub, so use the explicit interpreter path:

```bash
"/c/Users/Mayank Prasad/AppData/Local/Programs/Python/Python313/python" database/scripts/generate_seed.py
```

The script rewrites `database/seed.sql` (LF endings, ASCII only) and prints the table count. Reload the database afterwards using section 6.

---

## 8. Backend configuration

The backend is not written yet; only the environment template and the dependency list exist, both at the repository root.

Create your local environment file from the template:

```bash
cp .env.example .env
```

Then edit `.env` and set the database values to match the database you created in section 5:

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=show-book-kar
DB_USER=postgres
DB_PASSWORD=your_db_password_here
```

Two things to watch in the template:

- Its `DB_NAME` default is `show_book_kar` (underscores), but this repo creates and documents the database as `show-book-kar` (hyphens). Set `DB_NAME` to whichever name you actually created in pgAdmin. If you settle on the hyphenated name, a `psql` one-liner needs quoting: `psql "postgresql://postgres:...@localhost:5432/show-book-kar"`.
- Its `FLASK_APP=backend/app.py` points at a file that does not exist yet. Keep it as is if you will create `backend/app.py` in Block 3; otherwise change it to the path of your entry point.

The template also carries `SECRET_KEY`, `HOLD_DURATION_MINUTES` (5) and `CANCELLATION_CUTOFF_HOURS` (2), which the hold and cancellation work will read instead of hard-coded values.

`.env` is ignored by Git; `.env.example` is committed. Never put a real password in the example file.

Install dependencies with:

```bash
pip install -r requirements.txt
```

The root `requirements.txt` installs `psycopg2-binary`, so import it as `psycopg2`. Pick one PostgreSQL driver and stick to it: do not add `psycopg` (v3) or `pg8000` alongside it, and do not import two drivers in the same project.

---

## 9. Running the constraint tests

Each file in `database/tests/` contains a statement that **must fail**. In pgAdmin, open the file in Query Tool and run it against a scratch database: a red error message is the pass condition, and the message must contain the SQLSTATE listed in `database/tests/README.md`.

| Test file | Expected SQLSTATE |
|---|---|
| `test_negative_constraints.sql` | `23505` unique, `23514` check, `23503` foreign key |
| `test_dependencies.sql` | `23502` not-null, FK rejections |
| `test_hold_expiry.sql` | expiry/reclaim behaviour |
| `test_payment_refund.sql` | payment/refund state rules |
| `test_reports.sql` | report totals versus hand calculations |
| `test_concurrency.sql` | two-session seat race (see `test_concurrency.md`) |

Run them against a scratch database, not the demo database, since a failed transaction there leaves nothing behind but a mistake in the seed data costs another reload.

---

## 10. Database documentation index

| Document | Contents |
|---|---|
| `database/DESIGN_NOTE.md` | Entities, relationships, keys, status values and the agreed business rules (5-minute hold, cancellation cutoff, failed-payment release). Frozen for the first integration pass. |
| `database/TRANSACTION.md` | The hold/booking transaction: locking order, rollback conditions, why `show_seats` exists. |
| `database/queries.sql` | Read queries behind the API and UI, including empty-result behaviour, plus the three admin report queries. |
| `database/functions.sql` | The write path: hold, pay, cancel, release-expired and show scheduling, with their signal messages. |
| `database/views.sql` | Availability and booking-history views. |
| `database/indexes.sql` | Indexes with the query pattern and `EXPLAIN` evidence that justifies each one. |
| `database/ER Diagram.png` | The ER diagram. |
| `workplan.md` | The 18-day plan, phase gates, DoD and acceptance checklists. |

---

## 11. Common load errors

| Error | Cause | Fix |
|---|---|---|
| `428C9` - cannot insert a non-DEFAULT value into column "id" | `users.id` is still `GENERATED ALWAYS AS IDENTITY`, i.e. an older `schema.sql` | Run section 6 with the current `schema.sql`, then reload the seed |
| `23514` - violates check constraint `show_seats_held_by_fkey` | Older seed wrote `held_by_booking_id = 0` | Regenerate with section 7 and reload |
| `23514` - violates `show_seats_hold_consistency` | A `HELD`/`BOOKED` row is missing its hold fields, or `AVAILABLE` has them | Regenerate the seed; do not patch individual rows |
| `23505` - duplicate key `seats_screen_row_number_unique` | `seats.screen_id` was pointed at a theatre instead of a screen | Regenerate the seed |
| `42830` - no unique constraint matching given keys for `booking_seats` | Schema predates the composite `(show_id, seat_id)` FK | Reload the current `schema.sql` |
| `42P01` - relation "users" does not exist | Schema was never loaded, or Query Tool is attached to another database | Check `current_database()`, then section 5.2 |
| `42P07` - relation already exists | `schema.sql` run twice without a reset | Section 6 |
| `syntax error at or near "\"` | `\i` pasted into Query Tool | Use the Open File icon instead |
| Seed runs "successfully" but tables are empty | Wrong database selected, or the load was rolled back after an error | `SELECT current_database();` then the counts in section 5.4 |
| Database icon shows a red cross | pgAdmin has no open connection to it | Click to expand it, or right-click -> Connect Database |

---

## 12. Next steps

Order of work is in `workplan.md`. H's backend is finished; what remains is:

1. **M**: review or replace `database/functions.sql` (H wrote the reference implementation), and decide on the two outstanding schema items in `backend/README.md` section 8 - an exclusion constraint on `shows` and a primary key for `booking_seats`.
2. **M**: replace the `database/tests/*.sql` stubs; the behaviours they describe are currently covered by `backend/tests/`.
3. **S**: frontend against `backend/README.md` - movie list, movie detail, seat map with legend, hold -> pay, booking history, cancel, and the admin screens.
4. Run the join demo from a clean database (sections 5-6), with the API on port 5000 and `.venv/Scripts/python -m pytest backend/tests -q` as the regression check.
