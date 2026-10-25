# Constraint tests

Owner: M | Reviewers: H, S
Location: `database/tests/`

## What they verify

Each script in this directory contains a **deliberately failing** insert that
must fail with the expected SQLSTATE. The point is to prove the schema
enforces the right rules:

| Test | Must fail with |
| ----- | -------------- |
| Duplicate email | `23505` unique_violation |
| Duplicate physical seat coordinate | `23505` |
| Duplicate show_seat row | `23505` (composite PK) |
| Invalid price / show time | `23514` check_violation |
| Bad foreign key | `23503` |
| Overlapping shows on one screen | `23P01` exclusion_violation |
| Missing table | `42P01` undefined_table |

## How to run

```bash
for t in database/tests/test_*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$t" 2>&1 \
  | tee -a docs/test-results/constraint-tests.log
done
```

Each script uses `BEGIN`/`ROLLBACK` so one failure never masks the next. The
runner must check **both**:

1. **non-zero exit** (the test actually failed), **and**
2. the **expected SQLSTATE** appears in stderr.

## Important

- These tests are **negative**. Do not add rows to the database to satisfy
  them; they are run against a scratch database.
- Every negative test is isolated in its own transaction, so a failure never
  masks the next one.
- If a test fails with the wrong SQLSTATE, the schema is too permissive (or
  too strict) and must be fixed before review.
