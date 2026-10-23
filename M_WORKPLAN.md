# M Workplan — Database Implementation

Execution plan for everything **M** owns in [README.md](README.md) (the project execution plan). Each stage below groups M's scattered README tasks into one dependency-ordered sequence, with the files to produce, how to verify them, and the review gate that must pass before moving on.

**Repo state:** the repository currently contains only `README.md`. Every file listed below is to be created.

- **Owner:** M — database design, PostgreSQL schema, constraints, SQL functions, views, indexes, seed data.
- **Reviewers:** H (backend/API fit), S (fields needed by the UI, report/diagram quality).
- **Stack:** PostgreSQL + pgAdmin.

---

## 1. Task inventory (what M owes)

| README source | M tasks | Notes |
| --- | --- | --- |
| §0 Working agreement (shared) | shared | Git hygiene, parameterized SQL, transactions |
| §2.2 API contract check | 1 | Confirm DB statuses/types match the API contract |
| §3.3 Schema design tasks | 19 | Owner M, reviewer H |
| §3.4 Normalization deliverables | 11 | Owner M, reviewers H and S |
| §5 Detailed database object checklist | 70 | Per-table acceptance lens (users → `booking_events`) |
| Phase 0 — Setup (Day 1) | 5 | Concept note, entities, keys, statuses, review checklist |
| Phase 1 — ER, schema, seed (Days 1–3) | 16 | ER diagram, `schema.sql`, `seed.sql`, negative tests |
| Phase 2 — Read queries (Days 3–4) | 10 | List/fetch queries, indexes, `queries.sql` |
| Phase 3 — Seat hold (Days 4–6) | 16 | The booking transaction and locking protocol |
| Phase 4 — Payment/expiry (Days 6–7) | 11 | Confirmation, failure, safe hold release |
| Phase 5 — Cancellation (Days 7–8) | 10 | Cancellation transaction, refunds, history queries |
| Phase 6 — Auth/admin (Days 8–11) | 8 | Roles, admin queries, safe deletion rules |
| Phase 7 — Reports/indexes (Days 11–14) | 13 | Views, reports, audit, `EXPLAIN ANALYZE` evidence |
| Phase 8 — QA/concurrency (Days 14–16) | 7 | Clean-DB tests, two-session locking evidence |
| Phase 9 — Documentation (Days 16–18) | 10 | Data dictionary, normalization, viva pack |
| **Total M-attributable checkboxes** | **207** | Some are cross-checked in §5 against phases |

---

## 2. Stage overview

| Stage | Days | Deliverables | README source | Gate |
| --- | --- | --- | --- | --- |
| 0. Decisions and design note | 1 | `database/DESIGN_NOTE.md` | Phase 0 M | Team agrees on P0 scope, names, statuses |
| 1. ER diagram → relational mapping | 1–2 | `docs/diagrams/er.md` | Phase 1 M, §3.4 | H and S can read it; S checks UI fields |
| 2. `schema.sql` | 2–3 | `database/schema.sql` | Phase 1 M, §3.3 | Schema review with H; names frozen |
| 3. Seed data and reset | 3 | `database/seed.sql` | Phase 1 M | Loads from an empty database |
| 4. Constraint tests | 3–4 | `database/tests/*.sql` | Phase 1 M, §5 | Every negative test fails with the expected SQLSTATE |
| 5. Read queries | 3–4 | `database/queries.sql` | Phase 2 M | H serves them through the API |
| 6. Booking hold transaction | 4–6 | `database/functions.sql`, `database/TRANSACTION.md` | Phase 3 M, §1.4 | Shared gate: no partial holds |
| 7. Payment, confirmation, expiry | 6–7 | `database/functions.sql` (payment/expiry) | Phase 4 M | Shared gate: expiry never frees a confirmed seat |
| 8. Cancellation and refunds | 7–8 | cancellation SQL, history queries | Phase 5 M | Shared gate: history preserved |
| 9. Roles, admin queries, deletion rules | 8–11 | admin queries, role constraints | Phase 6 M | Schema changes re-reviewed with H |
| 10. Views, reports, audit, indexes | 11–14 | `views.sql`, `functions.sql`, `triggers.sql`, `indexes.sql` | Phase 7 M, §3.4 | Reports match hand calculations |
| 11. Concurrency evidence | 14–16 | `database/tests/concurrency.sql`, `docs/test-results/` | Phase 8 M | Two-session test recorded |
| 12. Documentation and viva pack | 16–18 | data dictionary, normalization, setup script | Phase 9 M, §3.4 | All members can run it from a clean clone |

Stages 4–5 may run in parallel with H's Phase 2 backend work. Stages 6–8 must be reviewed with H **before** H implements the matching routes — the database contract comes first (README §0: agree on the database contract; do not duplicate business rules).

---

## 3. Stages

### Stage 0 — Decisions and design note (Day 1)

**Do**

- [ ] List entities and relationships; propose table names and keys (`users`, `movies`, `theatres`, `screens`, `seats`, `shows`, `show_seats`, `bookings`, `booking_seats`, `payments`, `refunds`, optional `booking_events`).
- [ ] Define integrity rules and **status values with allowed transitions** for: booking, show-seat (hold), payment, refund.
- [ ] Settle the open business rules from §1.4 in writing: hold duration (5 min), cancellation cutoff, failed-payment policy (release immediately for v1), repeated-payment behavior.
- [ ] Write the schema review checklist used in Stage 2.
- [ ] Confirm with H that DB statuses and data types match the API contract (§2.2): money as `NUMERIC`, timestamps as `TIMESTAMPTZ`, status spellings identical in SQL/Python/JavaScript.

**Files:** `database/DESIGN_NOTE.md` (entities, status dictionary, transition table, decisions).

**Verify:** the status dictionary names every status value that appears in `CHECK` constraints — no status exists in code but not in the dictionary.

**Gate:** Phase 0 shared gate — all three agree on P0 scope, table names, status names, API contract draft.

---

### Stage 1 — ER diagram and relational mapping (Days 1–2)

**Do**

- [ ] Draw the ER diagram (entities, attributes, PKs, relationships, cardinalities, participation).
- [ ] Convert the ER model to relational tables; show the mapping decisions (M:N → `booking_seats`, `show_seats`).
- [ ] Define PKs, FKs, candidate keys and unique constraints.
- [ ] Start §3.4: functional dependencies per relation, primary/candidate keys, 1NF/2NF/3NF reasoning.

**Files:** `docs/diagrams/er.md` (Mermaid ER diagram, exportable for the report).

**Verify:** every table planned in Stage 2 appears in the diagram, and every FK in the diagram has a matching narrative line.

**Gate:** H confirms the model supports the API contract; S confirms it supports the UI and names are understandable (README Phase 1).

---

### Stage 2 — `schema.sql` (Days 2–3)

**Do** (the §3.3 checklist, in one file)

- [ ] Create tables in dependency order: `users` → `movies` → `theatres` → `screens` → `seats` → `shows` → `show_seats` → `bookings` → `booking_seats` → `payments` → `refunds`.
- [ ] Identity columns (or one consistent PK strategy); meaningfully named constraints.
- [ ] `NOT NULL` where required; `CHECK` for positive duration, valid show times, nonnegative prices/amounts, valid statuses.
- [ ] Unique: user email; screen name per theatre; physical seat coordinate `(screen_id, row_label, seat_number)`.
- [ ] Composite PK `show_seats(show_id, seat_id)`; composite FK `booking_seats(show_id, seat_id)` → `show_seats(show_id, seat_id)`; booking `show_id` consistency enforced.
- [ ] FK delete/update actions chosen deliberately — **no cascade** on bookings/payments.
- [ ] `created_at` where useful; `TIMESTAMPTZ` everywhere.
- [ ] Decide `total_seats` derivation and how show-seat prices are assigned; comment non-obvious constraints in SQL.
- [ ] Overlap prevention for shows on one screen (exclusion constraint with `btree_gist`, or documented trigger/validation).
- [ ] Decide whether `booking_seats` uses a unique `(show_id, seat_id)` — README §10 says **no**, if historical attempts must be preserved; enforce ownership via `show_seats` state instead. Record the decision in `DESIGN_NOTE.md`.

**Verify**

```bash
createdb showbookkar
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql   # 2nd run: fails clearly or is safely repeatable — by design
```

Also test from an **empty** database, not a populated dev database.

**Gate:** H reviews every constraint needed by booking and cancellation; S reviews fields needed for movies, showtimes, seats, bookings; then **freeze table/column names** for the first integration pass (README Phase 1 gate).

---

### Stage 3 — Seed data and reset (Day 3)

**Do**

- [ ] `database/seed.sql`: synthetic users, movies, theatres, screens, seats, several shows across screens/times.
- [ ] Generate `show_seats` rows for **every** seeded show.
- [ ] Document how to reset and recreate the database (README Phase 1 M).

**Verify:** after reset + seed, hand-check an availability count (total seats − held − booked) against a `SELECT` count; keep the numbers in the seed notes.

**Gate:** M demonstrates schema creation from an empty database (README Phase 1 gate).

---

### Stage 4 — Constraint and negative tests (Days 3–4)

**Do** — `database/tests/` with deliberately failing inserts (README Phase 1 M):

- [ ] Duplicate email → `23505` unique_violation.
- [ ] Duplicate physical seat coordinate → `23505`.
- [ ] Duplicate `show_seats` row → `23505`.
- [ ] Invalid price (negative) and invalid show time (end ≤ start) → `23514` check_violation.
- [ ] Invalid / missing foreign key → `23503`.
- [ ] Overlapping shows on one screen → `23P01` exclusion_violation (or the agreed validation error).
- [ ] Each test isolated (own transaction / own script) so one failure doesn't mask the next.

**Verify:** run each script and assert both the non-zero exit **and** the expected SQLSTATE in stderr; store the transcript as evidence:

```bash
for t in database/tests/test_*.sql; do
  psql "$DATABASE_URL" -f "$t" 2>&1 | tee -a docs/test-results/constraint-tests.log
done
```

**Gate:** every §5 object-checklist constraint item for the core tables is covered by a passing (positive) or expected-failing (negative) test.

---

### Stage 5 — Read queries (Days 3–4)

**Do** — save reusable queries in `database/queries.sql` (README Phase 2 M):

- [ ] List movies; fetch movie by ID.
- [ ] List future shows for a movie/date; fetch a show's theatre and screen.
- [ ] List seats for a show with statuses and prices.
- [ ] Availability count query.
- [ ] Check behavior for no matching rows (NULL vs empty), ordering and filtering.
- [ ] Add indexes **only** where justified by a real query pattern (records go in Stage 10's `indexes.sql`).

**Gate:** browse movies and open a seat map from the real database through H's API (README Phase 2 gate).

---

### Stage 6 — Atomic seat hold transaction (Days 4–6)

**First, the decision:** put the core booking logic in **one authoritative path** — parameterized SQL in H's service *or* a PostgreSQL function. Review with H before implementing (README Phase 3 M). Recommendation for a DBMS project: a database function, because it keeps locking/atomicity demonstrable in two `psql` sessions without the backend running.

**Do**

- [ ] Reject duplicate seat IDs in the request; verify all requested seats belong to the specified show.
- [ ] Lock selected `show_seats` rows **in a consistent order** (e.g. by `seat_id`) to reduce deadlock risk.
- [ ] Verify **every** requested row was found — a lock over found rows proves nothing about rows that weren't found.
- [ ] Verify all seats are `AVAILABLE`, or reclaim an expired hold only after rechecking its expiry inside the same transaction.
- [ ] Insert one `bookings` row + one `booking_seats` row per seat; compute the total from **database** prices, never from the client.
- [ ] Set `HELD`, `held_by_booking_id`, hold expiry; all of it commits or rolls back together — a failed hold leaves no orphan booking/seat rows.
- [ ] Add a query to inspect a booking and its seats; document transaction boundaries and locking rationale in `database/TRANSACTION.md`.

**Verify:** one-seat hold, multi-seat hold, and a multi-seat hold where one seat is unavailable → **zero** rows created (Script rollback proof: `SELECT count(*) FROM bookings WHERE id = ...` returns nothing).

**Gate:** shared gate — exactly one booking and the expected seat rows on success; no partial reservation on conflict; the database (not the frontend) decides availability.

---

### Stage 7 — Payment, confirmation and expiry (Days 6–7)

**Do**

- [ ] Payment status constraints and the booking/payment state-transition table (documented in `DESIGN_NOTE.md`; enforce transitions in the transaction/function — a `CHECK` alone does not enforce order).
- [ ] SQL for successful confirmation: insert/update payment, set booking `CONFIRMED`, set seats `BOOKED` — atomically, amount equal to the booking amount.
- [ ] SQL for failed payment: record the failure, release the hold per the agreed policy (v1: release immediately).
- [ ] SQL to release expired holds safely: only seats still held **by the same booking**; a late expiry must never free a confirmed or reassigned seat.
- [ ] Handle repeated payment requests idempotently — never two successful payments for one booking.
- [ ] Constraints/indexes for transaction references and booking lookup.

**Verify:** test cases for expired, confirmed, already-released holds and a late payment attempt.

**Gate:** shared gate — success confirms, failure does not, expiry frees abandoned seats only, repeats don't duplicate payments.

---

### Stage 8 — Cancellation and refunds (Days 7–8)

**Do**

- [ ] Finalize the cancellation eligibility rule (cutoff) and refund status values.
- [ ] `refunds` table constraints and indexes: nonnegative amounts, valid statuses, refunded total ≤ refundable, partial vs full distinguishable, original payment retained.
- [ ] Cancellation transaction: release only seats owned by the target booking; **never delete** booking/payment history.
- [ ] Booking-history query and payment/refund history query (feed H's `GET /api/bookings`).
- [ ] Tests: duplicate cancellation, late cancellation, invalid booking state.

**Gate:** shared gate — history preserved, released seats become available only per policy, refund state explicit.

---

### Stage 9 — Roles, admin queries, safe deletion (Days 8–11)

**Do**

- [ ] Decide role storage (role column on `users`, or separate admin table) and add account uniqueness/validation.
- [ ] Admin queries for movies, theatres, screens, seats, shows (create/update/list).
- [ ] Define safe deletion rules for movies/shows that have bookings; prevent destructive deletion of referenced booking/payment history.
- [ ] Add DB constraints for admin-created records; re-review any schema change with H before it lands.

**Gate:** invalid data rejected by both validation and constraints; existing booking history intact after catalogue changes (README Phase 6 gate).

---

### Stage 10 — Views, reports, audit, indexes (Days 11–14)

**Do**

- [ ] `database/views.sql`: show-availability view, booking-history view.
- [ ] Reports: bookings by movie/show; successful payment amounts; cancellation/refund report — never count failed payments as collected money; never double-count when joining one-to-many relations.
- [ ] Audit: create `booking_events` if in scope; pick **one** source of truth (trigger *or* service-level insert) and document it (`triggers.sql`).
- [ ] `database/indexes.sql`: indexes for real filter/join patterns, each with a SQL comment saying why it exists.
- [ ] Capture `EXPLAIN ANALYZE` before/after for each index and record the trade-off (write cost) — no performance claim without measured evidence (§10).
- [ ] Test every report against hand-calculated sample data.

**Gate:** every report matches the hand calculation; index claims backed by stored query plans (README Phase 7 gate).

---

### Stage 11 — Concurrency evidence (Days 14–16)

**Do**

- [ ] Re-run all schema and constraint tests from a clean database; verify FKs, composite keys, status constraints, expiry and cancellation SQL.
- [ ] Run the two-session locking test with H: session A takes the hold, session B attempts the same seat → B must block, then fail with `409`/conflict; **no duplicate reservation** ever exists.
- [ ] Also run two sessions on different seats → both succeed.
- [ ] Save scripts and output as evidence: `database/tests/concurrency.sql`, logs/screenshots in `docs/test-results/`, narrative in `tests/test_concurrency.md`.
- [ ] Review the final schema against the ER diagram; update the diagram if it drifted.

**Verify:** `SELECT` the booking, seats, payment and statuses after each run; keep the transcript for the report.

**Gate:** all P0 test cases pass; no critical booking-integrity bug remains (README Phase 8 exit criteria).

---

### Stage 12 — Documentation and viva pack (Days 16–18)

**Do**

- [ ] Finalize the ER diagram and relational schema; write the data dictionary (`docs/report/database-design.md`, handed to S for the report).
- [ ] Complete §3.4: functional dependencies, 1NF/2NF/3NF reasoning, why show-seat status lives in `show_seats`, why `price_at_booking` is a snapshot, derived-value justification, before/after decomposition example.
- [ ] Document PKs/FKs/UNIQUE/CHECK, transaction boundaries and row locking, the concurrency test and observed result, indexes with query-plan comparison, views/functions/triggers/audit logic.
- [ ] Provide a clean database setup script (schema → seed → verification) that runs from a fresh clone.
- [ ] Prepare DBMS viva questions and answers.

**Gate:** all three members can run the project from the README, explain every table and relationship, and explain `show_seats`, locking, rollback, duplicate-seat prevention and simulated-payment limits (README Phase 9 shared review).

---

## 4. Cross-cutting rules for every stage

- One authoritative path for each business rule — never two implementations of the same rule (README §0).
- Parameterized SQL only; never concatenate user input.
- Money as `NUMERIC`; timestamps as `TIMESTAMPTZ`; identical status spellings across SQL, Python, JavaScript.
- Never delete bookings or payments; history is append-only except status columns.
- Synthetic data only; no credentials in Git.
- Commit small, meaningful changes (`db: ...`) and push working state at the end of each workday.
- A blocked task is marked **Blocked** with the reason, not silently skipped (README §7).

---

## 5. M's Definition of Done

- [ ] Schema recreatable from scripts on an empty database; second run behaves by design.
- [ ] All §3.3 (19) and §3.4 (11) checkboxes pass review; §5 checklist (70 items) verified table by table.
- [ ] All negative tests fail with the expected SQLSTATE; all positive tests pass.
- [ ] Booking hold is atomic: conflicting multi-seat requests leave zero rows.
- [ ] Expiry, cancellation and refund never corrupt or delete history.
- [ ] Concurrency evidence recorded (two sessions, same seat, one winner).
- [ ] Every index claim has `EXPLAIN ANALYZE` evidence; every report matches hand calculations.
- [ ] ER diagram, data dictionary, normalization write-up and setup script are finished and consistent with the shipped schema.
- [ ] Reviewed by H (constraints/queries) and S (UI fields, diagram clarity) at each stage gate.
