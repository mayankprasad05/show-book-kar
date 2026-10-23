# Show-book-kar — Complete Project Execution Plan

**Task breakdown for three team members: M, H, and S.**

- **Project:** Show-book-kar — Movie Ticket Booking and Seat Reservation System
- **Primary objective:** Demonstrate core DBMS concepts through a working movie-booking application.
- **Recommended stack:** PostgreSQL + pgAdmin, Python + Flask, HTML + CSS + JavaScript.
- **Team:** M, H, S
- **Planning horizon:** 18 working days (adjust to your actual deadline).
- **Priority:** Database correctness and demonstrable DBMS concepts first; interface polish second.

---

## Contents

- [0. How to use this plan](#0-how-to-use-this-plan)
- [1. Scope and requirements](#1-scope-and-requirements)
- [2. Architecture and interfaces](#2-architecture-and-interfaces)
- [3. Database design and schema checklist](#3-database-design-and-schema-checklist)
- [4. Detailed task ownership by phase](#4-detailed-task-ownership-by-phase)
  - [Phase 0: Team setup and agreement (Day 1)](#phase-0-team-setup-and-agreement-day-1)
  - [Phase 1: ER diagram, schema and seed data (Days 1–3)](#phase-1-er-diagram-schema-and-seed-data-days-13)
  - [Phase 2: Read queries and database-side inventory (Days 3–4)](#phase-2-read-queries-and-database-side-inventory-days-34)
  - [Phase 3: Atomic seat hold and booking (Days 4–6)](#phase-3-atomic-seat-hold-and-booking-days-46)
  - [Phase 4: Payment simulation, confirmation and expiry (Days 6–7)](#phase-4-payment-simulation-confirmation-and-expiry-days-67)
  - [Phase 5: Cancellation, refund records and booking history (Days 7–8)](#phase-5-cancellation-refund-records-and-booking-history-days-78)
  - [Phase 6: Authentication and admin CRUD (Days 8–11)](#phase-6-authentication-and-admin-crud-days-811)
  - [Phase 7: Reports, views, triggers and indexes (Days 11–14)](#phase-7-reports-views-triggers-and-indexes-days-1114)
  - [Phase 8: Integration, QA and concurrency evidence (Days 14–16)](#phase-8-integration-qa-and-concurrency-evidence-days-1416)
  - [Phase 9: Documentation, presentation and final demo (Days 16–18)](#phase-9-documentation-presentation-and-final-demo-days-1618)
- [5. Detailed database object checklist](#5-detailed-database-object-checklist)
- [6. Git and collaboration checklist](#6-git-and-collaboration-checklist)
- [7. Definition of Done](#7-definition-of-done)
- [8. Final acceptance checklist](#8-final-acceptance-checklist)
- [9. Suggested final demo sequence](#9-suggested-final-demo-sequence)
- [10. Important implementation cautions](#10-important-implementation-cautions)

---

## 0. How to use this plan

- [ ] Put this file at the root of the repository as `PROJECT_PLAN.md`.
- [ ] Treat each checkbox as a task that must be completed and reviewed.
- [ ] The person listed as **Owner** is responsible for delivery; **Reviewer** checks correctness.
- [ ] A task is not complete just because code exists. It must be run, tested, and documented.
- [ ] Commit small, meaningful changes to Git rather than waiting until the end.
- [ ] Do not create separate implementations of the same business rule in multiple places. Agree on the database contract first.
- [ ] If a task is blocked, record the blocker in the issue tracker or team notes and notify the other two members.
- [ ] Keep the scope fixed until the P0 requirements work end-to-end. Optional features must not delay booking correctness.

### Responsibility summary

| Member | Primary ownership | Secondary responsibility |
| ------ | ----------------- | ------------------------ |
| **M** | Database design, PostgreSQL schema, constraints, SQL functions, views, indexes, seed data | Review booking transactions and help prepare DBMS viva |
| **H** | Flask backend, database connection, booking/cancellation services, transaction handling, API validation | Integrate database functions and help test concurrency |
| **S** | Frontend, user flows, admin screens, integration testing, documentation and demo preparation | Review usability and verify the end-to-end workflow |

**Shared ownership:** all three members must understand the ER diagram, normalization, booking transaction, concurrency test, and project limitations. The owner writes/implements; the other members review and test.

### Working agreement

- [ ] Use one shared Git repository.
- [ ] Use feature branches such as `db/schema`, `backend/booking`, and `frontend/seat-map`.
- [ ] Never commit passwords, `.env`, virtual environments, database dumps containing real user data, or generated cache files.
- [ ] Use synthetic sample users and sample payments only.
- [ ] Use parameterized SQL queries; do not build SQL by concatenating user input.
- [ ] Keep all multi-step booking operations in a database transaction.
- [ ] Use consistent names: `snake_case` for SQL tables/columns and Python functions.
- [ ] Agree on API request/response formats before frontend/backend integration.
- [ ] Each member reviews at least one major deliverable owned by another member.
- [ ] At the end of each workday, update task status and push working changes.

---

## 1. Scope and requirements

### 1.1 P0: required features

- [ ] Browse movies.
- [ ] View movie details.
- [ ] Browse theatres and scheduled shows.
- [ ] View seats for a selected show.
- [ ] Select one or more seats.
- [ ] Create an atomic temporary hold on all requested seats.
- [ ] Prevent two users from holding/booking the same seat for the same show.
- [ ] Simulate payment success and failure.
- [ ] Confirm a booking only after successful simulated payment.
- [ ] Release seats on payment failure or hold expiry.
- [ ] View a user's booking history.
- [ ] Cancel an eligible booking.
- [ ] Record payment and refund statuses without deleting historical records.
- [ ] Provide basic admin CRUD for movies, theatres, screens, seats, and shows.
- [ ] Show basic reports.
- [ ] Demonstrate constraints, transactions, locking, joins, aggregation, indexes and query plans.

### 1.2 P1: implement after P0 works

- [ ] Audit trail for booking status changes.
- [ ] Views for availability and reports.
- [ ] Stored function/procedure for a key database workflow.
- [ ] Trigger for audit logging, if it improves clarity.
- [ ] Index comparison using `EXPLAIN ANALYZE`.
- [ ] Friendly empty states and error messages.
- [ ] Basic role separation between customer and administrator.

### 1.3 Out of scope for the initial submission

- [ ] Do not integrate a real payment gateway.
- [ ] Do not add AI recommendations, microservices, message queues, or a distributed architecture.
- [ ] Do not add complex coupons, loyalty points, social features, or multiple currencies unless all P0 work is complete.
- [ ] Do not store card numbers or payment credentials.
- [ ] Do not rely on frontend state as the source of truth for seat availability.

### 1.4 Agree on business rules before coding

- [ ] A movie can have many shows.
- [ ] A theatre contains screens; a screen contains physical seats.
- [ ] A show is scheduled on one screen and features one movie.
- [ ] A screen must not have overlapping shows. Validate this with database logic or a PostgreSQL exclusion constraint.
- [ ] A physical seat is not itself "booked"; its status is tracked per show.
- [ ] A seat is available for a show only when its `show_seats` row is `AVAILABLE`, or a valid expired hold can safely be reclaimed.
- [ ] A booking may contain multiple seats, but all requested seats must be held together or none should be held.
- [ ] A booking must refer to one show only.
- [ ] A confirmed booking requires a successful simulated payment.
- [ ] Booking, seat, and payment records are updated transactionally where they are within the same database.
- [ ] Cancellation must not delete booking/payment history.
- [ ] A refund is a separate record; a payment is marked fully refunded only after the full amount has been refunded.
- [ ] Define the hold duration (recommended: 5 minutes) and cancellation cutoff (choose a documented rule).
- [ ] Define whether a failed payment immediately releases seats or leaves them held for a retry. For the simple version, release them after a failed attempt.
- [ ] Decide which statuses are valid and use the same spelling in SQL, Python and JavaScript.
- [ ] Store money as `NUMERIC`, not floating-point types.
- [ ] Store timestamps consistently with `TIMESTAMPTZ`.
- [ ] Do not trust a `user_id` sent by the browser; derive the current user from the authenticated session.

---

## 2. Architecture and interfaces

### 2.1 Simple architecture

```text
Browser (HTML/CSS/JavaScript)
          |
          | HTTP requests / JSON
          v
Flask backend
  - routes and input validation
  - authentication/authorization
  - booking service
  - transaction boundaries
          |
          | parameterized SQL / database functions
          v
PostgreSQL
  - relational tables and constraints
  - row-level locking
  - transactions
  - views, functions, triggers, indexes
```

### 2.2 Agree on API contracts before integration

Suggested routes; use these names consistently or document agreed alternatives.

| Method | Route | Purpose | Owner |
| ------ | ----- | ------- | ----- |
| GET | `/api/movies` | List/search movies | H |
| GET | `/api/movies/<movie_id>` | Movie details | H |
| GET | `/api/shows?movie_id=...&date=...` | List matching shows | H |
| GET | `/api/shows/<show_id>/seats` | Seat map and current statuses | H |
| POST | `/api/bookings/hold` | Attempt an atomic seat hold | H |
| POST | `/api/bookings/<booking_id>/pay` | Simulate payment result | H |
| GET | `/api/bookings` | Current user's booking history | H |
| GET | `/api/bookings/<booking_id>` | One authorized booking | H |
| POST | `/api/bookings/<booking_id>/cancel` | Cancel an eligible booking | H |
| GET | `/api/admin/reports/revenue` | Revenue report | H |
| POST/PUT/DELETE | `/api/admin/...` | Admin CRUD | H |

M owns the database structures/queries behind these routes. S owns the frontend calls and display behavior. H owns API implementation and integration.

### Example request/response contracts

**Hold seats request**

```json
{
  "show_id": 101,
  "seat_ids": [12, 13]
}
```

Successful response:

```json
{
  "booking_id": 501,
  "status": "PENDING",
  "hold_expires_at": "2026-10-23T12:05:00Z",
  "total_amount": "500.00"
}
```

Conflict response (HTTP 409):

```json
{
  "error": "SEAT_UNAVAILABLE",
  "message": "One or more selected seats are no longer available."
}
```

- [ ] H documents all request fields, response fields, HTTP status codes and error formats.
- [ ] M confirms database statuses and data types match the API contract.
- [ ] S confirms the UI can render success, validation errors, conflicts, loading states and empty states.

---

## 3. Database design and schema checklist

### 3.1 Tables

Recommended core tables:

1. `users`
2. `movies`
3. `theatres`
4. `screens`
5. `seats`
6. `shows`
7. `show_seats`
8. `bookings`
9. `booking_seats`
10. `payments`
11. `refunds`

Optional, after core functionality:

12. `booking_events` (audit trail)
13. `admin_users`, or a role column on `users`, depending on the authentication design.

### 3.2 Required constraints

- [ ] Primary key on every entity table.
- [ ] Foreign keys for every relationship.
- [ ] Unique user email.
- [ ] Unique screen name within a theatre.
- [ ] Unique physical seat coordinate within a screen: `(screen_id, row_label, seat_number)`.
- [ ] Composite primary key on `show_seats(show_id, seat_id)`.
- [ ] Composite foreign key from `booking_seats(show_id, seat_id)` to `show_seats(show_id, seat_id)`.
- [ ] Ensure a booking's `show_id` matches each associated booking-seat row, using a composite unique key/FK or a rigorously enforced alternative.
- [ ] Check constraints for positive movie duration, valid show times, nonnegative prices and amounts, and valid status values.
- [ ] Unique transaction reference when present.
- [ ] Prevent duplicate assignment of the same seat within a booking.
- [ ] Ensure only the owning booking can release a held seat.
- [ ] Ensure the total amount is calculated from server/database prices, never accepted as authoritative from the browser.
- [ ] Ensure the screen belongs to the theatre selected by the admin; the show references the intended screen.
- [ ] Consider a PostgreSQL exclusion constraint or trigger/transactional validation to prevent overlapping shows on the same screen.

### 3.3 Schema design tasks

**Owner: M | Reviewer: H**

- [ ] Create `database/schema.sql`.
- [ ] Create tables in dependency order so referenced tables exist first.
- [ ] Use identity columns or another consistent primary-key generation strategy.
- [ ] Name all constraints meaningfully.
- [ ] Add `NOT NULL` where values are required.
- [ ] Add `CHECK` constraints for numeric values and statuses.
- [ ] Add foreign-key delete/update actions intentionally; avoid cascading deletes for bookings and payments.
- [ ] Add the `show_seats` composite primary key.
- [ ] Add the composite foreign keys described above.
- [ ] Add constraints for duplicate emails, screens and seats.
- [ ] Decide whether `total_seats` is derived from `seats`; avoid maintaining duplicate facts unless necessary.
- [ ] Decide how show-seat prices are assigned and saved.
- [ ] Add `created_at` fields where useful.
- [ ] Use `TIMESTAMPTZ` for event/show timestamps.
- [ ] Test the schema from an empty database, not just an already-populated local database.
- [ ] Verify a second run either fails clearly or is safely repeatable by design.
- [ ] Add explanatory SQL comments for non-obvious constraints.
- [ ] Ask H to review all constraints needed by booking and cancellation.
- [ ] Ask S to review fields needed to display movies, showtimes, seats and bookings.

### 3.4 Normalization deliverables

**Owner: M | Reviewers: H and S**

- [ ] Write a list of functional dependencies for each main relation.
- [ ] Explain the primary key and candidate keys.
- [ ] Explain how the design satisfies 1NF.
- [ ] Explain how partial dependencies are avoided for 2NF.
- [ ] Explain how transitive dependencies are avoided for 3NF where applicable.
- [ ] Explain why movie details are not repeated in each booking.
- [ ] Explain why theatre/screen/seat data are separated.
- [ ] Explain why show-specific seat status belongs in `show_seats`, not `seats`.
- [ ] Explain why `price_at_booking` is a historical snapshot.
- [ ] Document any intentionally stored derived values, such as `total_amount`, and how they are validated.
- [ ] Include a before/after example of a poorly normalized booking table and the decomposed design.

---

## 4. Detailed task ownership by phase

### Phase 0: Team setup and agreement (Day 1)

#### M

- [ ] Create the initial database concept note.
- [ ] List entities and relationships.
- [ ] Propose table names and keys.
- [ ] List integrity rules and status values.
- [ ] Create a schema review checklist.

#### H

- [ ] Create the repository and Flask project skeleton.
- [ ] Set up a Python virtual environment.
- [ ] Create `requirements.txt` with agreed dependencies.
- [ ] Add a `.gitignore` for `.env`, `.venv/`, `__pycache__/`, logs and generated files.
- [ ] Create environment variable examples in `.env.example` without secrets.
- [ ] Propose API routes and JSON error format.
- [ ] Verify the backend can start with a basic health route.

#### S

- [ ] Create the project README outline.
- [ ] List user stories for customer and admin.
- [ ] Sketch the movie, show, seat-map, checkout, booking-history and admin screens.
- [ ] Decide navigation and basic visual style.
- [ ] Create frontend folder structure.
- [ ] Create a task board or checklist with owner, status and blocker fields.

#### Shared gate

- [ ] All three agree on P0 scope.
- [ ] All three agree on table names, status names and API contract draft.
- [ ] Everyone can run the repository locally.

**Exit criteria:** a shared design exists; nobody is independently inventing a conflicting schema or API.

---

### Phase 1: ER diagram, schema and seed data (Days 1–3)

#### M — Database lead

- [ ] Draw the ER diagram.
- [ ] Convert the ER model to relational tables.
- [ ] Define PKs, FKs, candidate keys and unique constraints.
- [ ] Define status values and allowed transitions.
- [ ] Write `database/schema.sql`.
- [ ] Write `database/seed.sql`.
- [ ] Add synthetic sample users, movies, theatres, screens and seats.
- [ ] Add multiple shows on different screens and times.
- [ ] Generate `show_seats` for every sample show.
- [ ] Include a few deliberately conflicting/invalid inserts in a separate test script.
- [ ] Test duplicate email rejection.
- [ ] Test duplicate physical seat rejection.
- [ ] Test duplicate show-seat rejection.
- [ ] Test invalid prices and show times.
- [ ] Test invalid foreign keys.
- [ ] Document how to reset and recreate the database.

#### H — Backend preparation

- [ ] Create Flask app factory or a small `app.py`.
- [ ] Create `db.py` for PostgreSQL connection management.
- [ ] Select a PostgreSQL driver and document installation.
- [ ] Load database connection settings from environment variables.
- [ ] Add a health endpoint.
- [ ] Add a database connectivity check.
- [ ] Add consistent exception handling.
- [ ] Confirm that a failed database request does not expose credentials or stack traces to the client.
- [ ] Review M's schema from the perspective of API needs.
- [ ] Identify any missing columns/constraints before the schema is frozen.

#### S — Requirements and documentation

- [ ] Draw use-case diagram or write use cases.
- [ ] Create a first UI wireframe.
- [ ] Draft user flow: movie → show → seats → hold → payment → confirmation.
- [ ] Draft cancellation flow.
- [ ] Start the project report: title, abstract, problem statement, objectives and scope.
- [ ] Prepare an initial data dictionary.
- [ ] Review the ER diagram for understandable naming and missing relationships.
- [ ] Check whether the planned schema can support the required UI.

#### Shared gate

- [ ] M demonstrates schema creation from an empty database.
- [ ] H connects Flask to the database.
- [ ] S can explain the ER diagram and main user flow.
- [ ] Freeze table/column names for the first integration pass.

**Exit criteria:** a reproducible database exists, sample data loads, and Flask can connect.

---

### Phase 2: Read queries and database-side inventory (Days 3–4)

#### M

- [ ] Write a query to list movies.
- [ ] Write a query to fetch a movie by ID.
- [ ] Write a query to list future shows for a movie/date.
- [ ] Write a query to fetch a show's theatre and screen.
- [ ] Write a query to list seats for a show with statuses and prices.
- [ ] Write an availability count query.
- [ ] Check query behavior for no matching rows.
- [ ] Check ordering and filtering.
- [ ] Add indexes only where justified by common query patterns.
- [ ] Save reusable queries in `database/queries.sql`.

#### H

- [ ] Implement `GET /api/movies`.
- [ ] Implement `GET /api/movies/<movie_id>`.
- [ ] Implement `GET /api/shows`.
- [ ] Implement `GET /api/shows/<show_id>/seats`.
- [ ] Validate numeric IDs and date filters.
- [ ] Return predictable JSON response shapes.
- [ ] Return 404 for missing movie/show IDs.
- [ ] Return empty arrays for valid queries with no results.
- [ ] Use parameterized SQL.
- [ ] Add basic route tests.

#### S

- [ ] Build movie-list page.
- [ ] Build movie details section/page.
- [ ] Build showtime list.
- [ ] Build seat-map layout with legend.
- [ ] Add loading, empty and error states.
- [ ] Use API data rather than hardcoded movie/seat data in the integrated version.
- [ ] Make available/held/booked states visually distinguishable.
- [ ] Prevent selection of seats that the latest API response marks unavailable.
- [ ] Keep frontend seat state as a display aid only; backend remains authoritative.

#### Shared gate

- [ ] Browse movies from the real database through the browser.
- [ ] Open a show and load seat statuses from PostgreSQL.
- [ ] Confirm no core page relies on fake data after integration.

---

### Phase 3: Atomic seat hold and booking (Days 4–6)

#### M — Database booking logic

- [ ] Review the exact booking transaction with H before implementation.
- [ ] Decide whether core booking logic lives in parameterized SQL in the service or in a PostgreSQL function. Use one authoritative path.
- [ ] Ensure requested seat IDs are unique in the request.
- [ ] Ensure all requested seats belong to the specified show.
- [ ] Lock selected `show_seats` rows in a consistent order.
- [ ] Verify every requested row was found.
- [ ] Verify all seats are available or reclaimable expired holds.
- [ ] Ensure expired holds are reclaimed only after rechecking their expiry.
- [ ] Insert one `bookings` record.
- [ ] Insert one `booking_seats` row per requested seat.
- [ ] Calculate total from database prices.
- [ ] Set seats to `HELD`, set `held_by_booking_id`, and set expiry.
- [ ] Ensure all operations commit or roll back together.
- [ ] Ensure a failed hold leaves no orphan booking/seat records.
- [ ] Add a query to inspect a booking and its seats.
- [ ] Document transaction boundaries and locking rationale.

#### H — Backend booking service

- [ ] Implement `POST /api/bookings/hold`.
- [ ] Validate request JSON.
- [ ] Reject an empty seat list.
- [ ] Reject duplicate seat IDs.
- [ ] Reject malformed or excessively large requests.
- [ ] Start one database transaction for the complete hold operation.
- [ ] Lock and recheck seat rows inside the transaction.
- [ ] Create booking and seat records.
- [ ] Calculate the price on the server/database.
- [ ] Commit on success.
- [ ] Roll back on any exception or unavailable seat.
- [ ] Return booking ID, status, expiry and amount.
- [ ] Return HTTP 409 for a seat conflict.
- [ ] Return safe, actionable error messages.
- [ ] Ensure exceptions do not leave the connection in an open transaction.
- [ ] Add tests for one-seat and multi-seat requests.
- [ ] Add tests for one unavailable seat among several requested seats.
- [ ] Confirm the failed multi-seat request holds none of the requested seats.

#### S — Seat-selection and hold UI

- [ ] Render seats from the API.
- [ ] Allow selecting multiple available seats.
- [ ] Show selected seat labels.
- [ ] Calculate a provisional display total, clearly treating the backend total as authoritative.
- [ ] Disable the continue button when no seats are selected.
- [ ] Submit show ID and selected seat IDs to the hold API.
- [ ] Handle success by saving/displaying the returned booking ID.
- [ ] Handle conflict by showing a message and refreshing the seat map.
- [ ] Handle network/server errors.
- [ ] Prevent double-click duplicate submissions in the UI.
- [ ] Do not mark seats as booked just because the user selected them.
- [ ] Display hold expiry if returned by the API.

#### Shared gate

- [ ] A valid hold creates exactly one booking and the expected seat rows.
- [ ] A conflicting hold creates no partial reservation.
- [ ] The database, not the frontend, determines whether a seat is available.
- [ ] M and H can explain row locking and rollback; S can demonstrate the conflict state.

---

### Phase 4: Payment simulation, confirmation and expiry (Days 6–7)

#### M

- [ ] Define payment status constraints.
- [ ] Define the booking/payment state transitions.
- [ ] Ensure payment amount matches the booking amount.
- [ ] Decide how repeated payment requests are handled.
- [ ] Add constraints/indexes needed for transaction references and booking lookup.
- [ ] Write SQL for successful confirmation.
- [ ] Write SQL for failed payment handling.
- [ ] Write SQL to release expired holds safely.
- [ ] Ensure expiry only releases seats still held by the same booking.
- [ ] Ensure a late expiry task cannot release a confirmed or reassigned seat.
- [ ] Add test cases for expired, confirmed and already released holds.

#### H

- [ ] Implement `POST /api/bookings/<booking_id>/pay`.
- [ ] Accept a controlled simulation result (success/failure) for demo purposes only.
- [ ] Do not accept arbitrary payment amount from the client.
- [ ] Lock the booking and relevant seat records.
- [ ] Verify booking status and hold expiry.
- [ ] On success, insert/update payment record, confirm booking and mark seats `BOOKED` atomically.
- [ ] On failure, record the failure and release the hold according to the agreed policy.
- [ ] Reject attempts to pay an expired/cancelled booking.
- [ ] Make repeated requests safe; do not create duplicate successful payments.
- [ ] Implement a simple expiry function/task or admin-triggered expiry endpoint.
- [ ] Add tests for success, failure, repeated requests and late payment attempts.

#### S

- [ ] Build checkout/order summary.
- [ ] Display seat labels, show details and server-calculated total.
- [ ] Add clearly labeled simulated payment success/failure controls.
- [ ] Display booking confirmation and booking ID.
- [ ] Display payment failure without falsely showing confirmation.
- [ ] Handle expired hold responses.
- [ ] Refresh the seat map after success/failure.
- [ ] Add a "My bookings" link after confirmation.
- [ ] Capture screenshots for successful and failed payment flows.

#### Shared gate

- [ ] Success produces a confirmed booking and booked seats.
- [ ] Failure does not produce a confirmed booking.
- [ ] Expiry frees abandoned seats safely.
- [ ] Repeated payment requests do not duplicate successful payment records.

---

### Phase 5: Cancellation, refund records and booking history (Days 7–8)

#### M

- [ ] Finalize cancellation eligibility rule.
- [ ] Define refund status values.
- [ ] Add `refunds` table constraints and indexes.
- [ ] Ensure cancellation does not delete booking/payment history.
- [ ] Write the cancellation transaction.
- [ ] Ensure only seats owned by the target booking can be released.
- [ ] Define how partial refunds are represented.
- [ ] Add booking-history query.
- [ ] Add payment/refund history query.
- [ ] Add tests for duplicate cancellation, late cancellation and invalid booking state.

#### H

- [ ] Implement `GET /api/bookings`.
- [ ] Implement `GET /api/bookings/<booking_id>`.
- [ ] Enforce ownership/authorization for both routes.
- [ ] Implement `POST /api/bookings/<booking_id>/cancel`.
- [ ] Verify booking status and cancellation cutoff.
- [ ] Lock booking/seats and execute the transaction.
- [ ] Record refund request/status if applicable.
- [ ] Return current booking, payment and refund states.
- [ ] Return safe errors for already-cancelled and ineligible bookings.
- [ ] Test that one user cannot cancel another user's booking.

#### S

- [ ] Build booking-history page.
- [ ] Show movie, showtime, seat labels, amount and booking status.
- [ ] Add cancellation button only when eligible.
- [ ] Ask for confirmation before cancellation.
- [ ] Show cancellation/refund status.
- [ ] Refresh booking history after cancellation.
- [ ] Display clear messages for failed cancellation.
- [ ] Test empty history and multiple bookings.

#### Shared gate

- [ ] Cancellation preserves historical data.
- [ ] Released seats become available only when policy allows.
- [ ] Refund state is explicit and consistent.
- [ ] Authorization checks prevent cross-user access.

---

### Phase 6: Authentication and admin CRUD (Days 8–11)

#### M

- [ ] Decide how user roles are stored.
- [ ] Add a role field or separate admin table if required.
- [ ] Add uniqueness/validation rules for user accounts.
- [ ] Define safe deletion rules for movies and shows with bookings.
- [ ] Provide admin queries for movies, theatres, screens, seats and shows.
- [ ] Prevent destructive deletion of referenced booking/payment history.
- [ ] Add database constraints for admin-created records.
- [ ] Review any changes to the frozen schema with H.

#### H

- [ ] Implement registration/login if included in the final scope.
- [ ] Hash passwords with a standard password-hashing library; never store plaintext passwords.
- [ ] Implement session handling or another simple, documented authentication mechanism.
- [ ] Protect booking routes.
- [ ] Protect admin routes with role checks.
- [ ] Implement admin create/update/list routes for movies.
- [ ] Implement admin create/update/list routes for theatres and screens.
- [ ] Implement seat setup for screens.
- [ ] Implement show scheduling.
- [ ] Validate show start/end time.
- [ ] Prevent overlapping shows on the same screen.
- [ ] Use parameterized queries and validate all inputs.
- [ ] Test unauthenticated access and non-admin access to admin routes.

#### S

- [ ] Build login/register screens if in scope.
- [ ] Add navigation based on user role.
- [ ] Build admin movie management form/table.
- [ ] Build theatre/screen management form/table.
- [ ] Build seat setup UI or a simple documented seed-data workflow.
- [ ] Build show scheduling form.
- [ ] Display validation errors returned by the API.
- [ ] Add confirmation before destructive actions.
- [ ] Ensure the customer UI cannot expose admin controls as a security substitute; server-side authorization is required.
- [ ] Test forms with missing, invalid and duplicate data.

#### Shared gate

- [ ] Admin actions are protected on the backend.
- [ ] Invalid data is rejected by both appropriate validation and database constraints.
- [ ] Existing booking history remains intact after catalogue changes.

---

### Phase 7: Reports, views, triggers and indexes (Days 11–14)

#### M — Database lead

- [ ] Create a view for show availability.
- [ ] Create a query/view for booking history.
- [ ] Create a report for bookings by movie/show.
- [ ] Create a report for successful payment amounts.
- [ ] Create a cancellation/refund report.
- [ ] Avoid counting failed payments as collected money.
- [ ] Avoid double-counting payments when joining multiple one-to-many relations.
- [ ] Create an audit table if in scope.
- [ ] Add a trigger or explicit service-level audit insertion; choose one clear source of truth.
- [ ] Create indexes for real filter/join patterns.
- [ ] Capture `EXPLAIN ANALYZE` output before/after selected indexes.
- [ ] Document why each index exists and its trade-off.
- [ ] Test reports against hand-calculated sample data.

#### H

- [ ] Implement report endpoints.
- [ ] Use database views or queries instead of duplicating report calculations in Python.
- [ ] Validate date filters and pagination where needed.
- [ ] Add admin authorization to reports.
- [ ] Return consistent numeric/decimal values.
- [ ] Add tests for empty date ranges and multiple payments/refunds.
- [ ] Review performance and transaction behavior for major endpoints.

#### S

- [ ] Build admin dashboard summary cards.
- [ ] Build booking/revenue/cancellation report tables.
- [ ] Add date filters if time permits.
- [ ] Display empty-state messages.
- [ ] Add a basic audit-event list if implemented.
- [ ] Capture screenshots of reports for the final report.
- [ ] Ensure labels distinguish gross successful payments, refunds and net amount.

#### Shared gate

- [ ] Every report matches known sample calculations.
- [ ] Index claims are supported by recorded query-plan evidence.
- [ ] No report double-counts payment or refund rows.

---

### Phase 8: Integration, QA and concurrency evidence (Days 14–16)

#### M

- [ ] Run all schema and constraint tests from a clean database.
- [ ] Verify all foreign keys and composite keys.
- [ ] Verify all status constraints.
- [ ] Verify hold expiry and cancellation SQL.
- [ ] Help run the two-session locking test.
- [ ] Save SQL scripts and screenshots/logs for evidence.
- [ ] Review final schema against the ER diagram.

#### H

- [ ] Run backend unit/integration tests.
- [ ] Test transaction rollback on every failure path.
- [ ] Test multi-seat booking where one seat is unavailable.
- [ ] Test duplicate requests.
- [ ] Test malformed request bodies.
- [ ] Test missing database connection behavior.
- [ ] Test user authorization and admin authorization.
- [ ] Confirm every database connection/transaction is properly closed or rolled back.
- [ ] Test two simultaneous booking requests using separate sessions/requests.
- [ ] Verify conflict responses are correct and no duplicate reservation is created.
- [ ] Record the test steps and results.

#### S

- [ ] Test every customer page from beginning to end.
- [ ] Test every admin form.
- [ ] Test on the agreed browser and screen size.
- [ ] Test loading, empty, conflict, success and server-error states.
- [ ] Check seat map updates after hold, payment, expiry and cancellation.
- [ ] Check navigation and refresh behavior.
- [ ] Check labels, currency formatting and timestamps.
- [ ] Capture final screenshots.
- [ ] Make a list of UI bugs and resolve P0 issues first.

#### Shared test scenarios

- [ ] User books one available seat.
- [ ] User books multiple available seats.
- [ ] One unavailable seat causes the entire multi-seat hold to fail.
- [ ] Two sessions attempt the same seat.
- [ ] Two sessions attempt different seats.
- [ ] Payment succeeds.
- [ ] Payment fails.
- [ ] Payment is retried or repeated.
- [ ] Hold expires.
- [ ] A late payment attempt is rejected.
- [ ] Confirmed booking is cancelled within the permitted window.
- [ ] Ineligible cancellation is rejected.
- [ ] A user tries to access another user's booking.
- [ ] An unauthenticated/non-admin user tries an admin operation.
- [ ] Reports match manually calculated results.

**Exit criteria:** all P0 test cases pass; known issues are written down; no critical booking-integrity bug remains.

---

### Phase 9: Documentation, presentation and final demo (Days 16–18)

#### M — DBMS documentation

- [ ] Finalize ER diagram.
- [ ] Finalize relational schema and data dictionary.
- [ ] Write normalization explanation.
- [ ] Document PKs, FKs, unique constraints and CHECK constraints.
- [ ] Document transaction boundaries and row locking.
- [ ] Document concurrency test and observed result.
- [ ] Document indexes and query-plan comparison.
- [ ] Document views, functions, triggers and audit logic.
- [ ] Provide a clean database setup script.
- [ ] Prepare DBMS viva questions and answers.

#### H — Backend documentation

- [ ] Document installation and environment configuration.
- [ ] Document how to start Flask.
- [ ] Document all API routes and request/response formats.
- [ ] Explain the booking service and transaction handling.
- [ ] Explain error handling and authorization.
- [ ] Provide dependency installation commands.
- [ ] Verify the app starts from a fresh clone using README instructions.
- [ ] Prepare a backend walkthrough for the demo.

#### S — Report and presentation lead

- [ ] Write abstract and problem statement.
- [ ] Write objectives and scope.
- [ ] Add requirements and use cases.
- [ ] Add architecture diagram and ER diagram.
- [ ] Add screenshots of all key workflows.
- [ ] Add test plan and test results.
- [ ] Add limitations and future enhancements.
- [ ] Prepare slide deck.
- [ ] Prepare a short live demo sequence.
- [ ] Ensure screenshots do not expose secrets or personal data.
- [ ] Combine the report sections and check formatting.
- [ ] Check spelling, consistent terminology and references.

#### Shared final review

- [ ] All members can explain every table and relationship.
- [ ] All members can explain why the `show_seats` table exists.
- [ ] All members can explain why the booking transaction locks rows.
- [ ] All members can explain rollback and atomicity.
- [ ] All members can explain how duplicate seat booking is prevented.
- [ ] All members can explain the limits of a simulated payment.
- [ ] All members can run the project using the README.
- [ ] Run the complete demo at least twice on a clean, known dataset.
- [ ] Tag the final version in Git.

---

## 5. Detailed database object checklist

### `users`

- [ ] Primary key.
- [ ] Unique email.
- [ ] Non-null name and password hash.
- [ ] Role/authorization design documented.
- [ ] Passwords never stored in plaintext.

### `movies`

- [ ] Primary key.
- [ ] Required title/language fields.
- [ ] Positive duration check.
- [ ] Search/list query.
- [ ] Admin create/update operations.

### `theatres`

- [ ] Primary key.
- [ ] Required name/city fields.
- [ ] Relationship to screens.
- [ ] Admin create/update operations.

### `screens`

- [ ] Primary key and theatre foreign key.
- [ ] Unique screen name per theatre.
- [ ] Valid seat setup.
- [ ] Overlapping-show prevention for the screen.

### `seats`

- [ ] Primary key and screen foreign key.
- [ ] Unique row/number within screen.
- [ ] Valid seat type.
- [ ] No per-show booking state stored here.

### `shows`

- [ ] Primary key.
- [ ] Movie and screen foreign keys.
- [ ] Start/end timestamps.
- [ ] End time after start time.
- [ ] Nonnegative base price.
- [ ] No overlapping shows on the same screen.
- [ ] Indexes for movie/time and screen/time access.

### `show_seats`

- [ ] Composite primary key `(show_id, seat_id)`.
- [ ] Foreign keys to shows and seats.
- [ ] Valid status values.
- [ ] Nonnegative show-specific price.
- [ ] Hold owner and expiry fields.
- [ ] Seed/population process for each show.
- [ ] Row-level locking for hold/confirmation/cancellation operations.
- [ ] Safe expired-hold reclamation.
- [ ] No duplicate seat assignment for the same show.

### `bookings`

- [ ] Primary key.
- [ ] User and show foreign keys.
- [ ] Valid status values.
- [ ] Nonnegative total.
- [ ] Creation timestamp.
- [ ] Booking ownership authorization.
- [ ] Status transitions documented.
- [ ] Historical records retained.

### `booking_seats`

- [ ] Booking foreign key.
- [ ] Composite reference to the matching show-seat row.
- [ ] Ensure booking and seat refer to the same show.
- [ ] Store price at booking.
- [ ] Prevent duplicate seat rows within one booking.
- [ ] Calculate booking total from authoritative prices.

### `payments`

- [ ] Booking foreign key.
- [ ] Nonnegative amount.
- [ ] Valid status values.
- [ ] Unique transaction reference where present.
- [ ] Repeated payment request behavior documented.
- [ ] No false successful payment on booking failure.

### `refunds`

- [ ] Payment foreign key.
- [ ] Nonnegative amount.
- [ ] Valid status values.
- [ ] Successful refund total cannot exceed the refundable amount.
- [ ] Partial and full refunds distinguished.
- [ ] Original payment history retained.

### Optional `booking_events`

- [ ] Event primary key.
- [ ] Booking foreign key.
- [ ] Previous/new status.
- [ ] Timestamp and reason.
- [ ] Event insertion cannot silently invalidate the booking transaction.
- [ ] Audit records are not editable by ordinary users.

---

## 6. Git and collaboration checklist

### Repository structure

```text
show-book-kar/
├── README.md
├── PROJECT_PLAN.md
├── .gitignore
├── .env.example
├── requirements.txt
├── database/
│   ├── schema.sql
│   ├── seed.sql
│   ├── queries.sql
│   ├── indexes.sql
│   ├── views.sql
│   ├── functions.sql
│   ├── triggers.sql
│   └── tests/
├── backend/
│   ├── app.py
│   ├── db.py
│   ├── routes/
│   ├── services/
│   └── tests/
├── frontend/
│   ├── templates/
│   └── static/
│       ├── css/
│       └── js/
├── docs/
│   ├── diagrams/
│   ├── screenshots/
│   ├── test-results/
│   └── report/
└── tests/
    ├── test_plan.md
    └── test_concurrency.md
```

### Suggested branch and review rules

- [ ] M creates `db/schema` and `db/queries` branches.
- [ ] H creates `backend/api` and `backend/booking` branches.
- [ ] S creates `frontend/pages` and `docs/report` branches.
- [ ] Use pull requests or at least request a peer review before merging.
- [ ] Never merge a schema change without updating the SQL scripts and notifying H.
- [ ] Never change an API response without notifying S.
- [ ] Keep seed data reproducible.
- [ ] Add test steps to the commit/PR description.
- [ ] Merge small changes frequently.
- [ ] Before final submission, clone the repository into a clean folder and follow the README.

### Suggested commit examples

- `db: add core relational schema and constraints`
- `db: seed sample movies and show seats`
- `backend: add show listing API`
- `backend: implement atomic seat hold`
- `frontend: add show seat selection`
- `test: cover concurrent seat booking`
- `docs: add ER diagram and DBMS test evidence`

---

## 7. Definition of Done

A feature is complete only when all applicable checks pass:

- [ ] Requirements are understood by the owner and reviewer.
- [ ] Code/SQL is committed to the shared repository.
- [ ] Database changes can be recreated from scripts.
- [ ] Input validation and error cases are covered.
- [ ] No secrets are committed.
- [ ] Tests pass.
- [ ] The relevant frontend/backend/database pieces are integrated.
- [ ] The owner has demonstrated the feature to at least one teammate.
- [ ] Documentation is updated.
- [ ] Known limitations are recorded.

A task should be marked **Blocked** rather than silently skipped if it depends on an unfinished schema, API, or design decision.

---

## 8. Final acceptance checklist

### Database and DBMS concepts

- [ ] ER diagram and relational schema are complete.
- [ ] Normalization is explained.
- [ ] PK/FK/UNIQUE/CHECK/NOT NULL constraints are demonstrated.
- [ ] Joins, subqueries, grouping and aggregate queries are demonstrated.
- [ ] Transactions and rollback are demonstrated.
- [ ] Row-level locking is demonstrated with two sessions.
- [ ] Simultaneous same-seat requests cannot both succeed.
- [ ] Holds expire safely.
- [ ] Cancellation and refund records stay consistent.
- [ ] Views, functions and/or triggers are documented if included.
- [ ] Index/query-plan comparison includes actual evidence.

### Application

- [ ] Movie browsing works.
- [ ] Show browsing works.
- [ ] Seat map is database-backed.
- [ ] Multi-seat hold works.
- [ ] Payment simulation and confirmation work.
- [ ] Booking history works.
- [ ] Cancellation works.
- [ ] Admin functions are authorized.
- [ ] Errors are understandable and safe.
- [ ] No critical UI or API issue remains.

### Submission

- [ ] README setup instructions work on a fresh clone.
- [ ] SQL scripts run in the documented order.
- [ ] Report and diagrams are complete.
- [ ] Test evidence and screenshots are included.
- [ ] Presentation is ready.
- [ ] All three team members can explain the core DBMS design.

---

## 9. Suggested final demo sequence

1. Start PostgreSQL and Flask; open the web app.
2. Browse movies and select a show.
3. Open the seat map and choose two available seats.
4. Create a hold and show the booking ID/expiry.
5. Simulate successful payment and show confirmation.
6. Open booking history and show the confirmed booking.
7. Demonstrate a failed payment or expired hold and show seats released.
8. Open two database sessions and demonstrate competing requests for the same seat.
9. Show that only one request can claim the seat.
10. Run a SQL query showing the booking, seats, payment and statuses.
11. Demonstrate cancellation and refund records.
12. Show a report query/view and the index/query-plan evidence.

### Suggested speaking split

- **M:** ER diagram, schema, constraints, normalization, indexes and SQL reports.
- **H:** backend architecture, booking transaction, row locks, rollback and API behavior.
- **S:** UI workflow, test scenarios, screenshots, results and overall project presentation.

Every member should still be ready to answer questions about the entire system.

---

## 10. Important implementation cautions

- A frontend seat map can become stale; always recheck and lock seats in the database before holding them.
- Lock rows in a consistent order to reduce deadlock risk.
- A transaction that locks only rows it finds must also verify that every requested seat row was found.
- Expired holds must be reclaimed transactionally and conditionally.
- Do not use a unique constraint on `(show_id, seat_id)` in `booking_seats` if you intend to preserve multiple historical booking attempts for the same seat. Instead, enforce current ownership through `show_seats` state/hold ownership and the transaction protocol.
- Do not delete bookings or payments when a booking is cancelled.
- A PostgreSQL transaction cannot make a real external payment provider atomic with the database; the initial project uses simulated payments.
- A status check constraint restricts values but does not by itself enforce every legal status transition. Enforce transitions in a transaction/service or database function.
- Use synthetic data only and keep all credentials outside Git.
- Do not claim performance improvements without measured query-plan evidence.
- Keep the project DBMS-centric. A reliable transaction and a clear concurrency demonstration are more valuable than many unrelated features.

---

> **Team reminder:** M owns the database design and SQL, H owns backend services and transaction integration, and S owns the UI, end-to-end testing and documentation. Review each other's work at phase gates. The final goal is not just a website that appears to book tickets; it is a relational database system that preserves correctness when requests fail or happen simultaneously.
