"""Pytest fixtures and builders.

The read tests run against the loaded development database (``show-book-kar``),
which the seed makes deterministic. Every test that can write is followed by
``reset_seed_state`` (autouse), so the seeded demo data - five bookings, their
payments and refund, 185 AVAILABLE / 6 BOOKED / 1 HELD seats - is exactly the
same for every run.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend import db
from backend.app import create_app

TEST_EMAIL_PREFIX = "pytest."

# Seeded rows that must survive every test.
SEED_BOOKING_IDS = (1, 2, 3, 4, 5)
SEED_MAX_ID = {"shows": 12, "seats": 740, "screens": 7, "theatres": 5, "movies": 15}


@pytest.fixture(scope="session")
def app():
    # PROPAGATE_EXCEPTIONS is off so the registered error handlers produce the
    # real API envelopes instead of pytest seeing raw tracebacks.
    return create_app({"TESTING": True, "PROPAGATE_EXCEPTIONS": False})


@pytest.fixture()
def client(app):
    return app.test_client()


def reset_seed_state() -> None:
    """Delete everything a test could have written, back to the seeded state."""
    with db.transaction() as cur:
        # Bookings and their dependent rows (payments/refunds are RESTRICT).
        cur.execute(
            "DELETE FROM refunds WHERE booking_id NOT IN %s", (SEED_BOOKING_IDS,)
        )
        cur.execute(
            "DELETE FROM payments WHERE booking_id NOT IN %s", (SEED_BOOKING_IDS,)
        )
        cur.execute(
            "DELETE FROM booking_seats WHERE booking_id NOT IN %s", (SEED_BOOKING_IDS,)
        )
        cur.execute("DELETE FROM bookings WHERE id NOT IN %s", (SEED_BOOKING_IDS,))
        cur.execute(
            """
            UPDATE show_seats
               SET status = 'AVAILABLE',
                   hold_expires_at = NULL,
                   held_by_booking_id = NULL
             WHERE held_by_booking_id IS NOT NULL
               AND held_by_booking_id NOT IN %s
            """,
            (SEED_BOOKING_IDS,),
        )

        # Catalogue rows created by admin tests, in dependency order.
        cur.execute("DELETE FROM show_seats WHERE show_id > %s", (SEED_MAX_ID["shows"],))
        cur.execute("DELETE FROM shows WHERE id > %s", (SEED_MAX_ID["shows"],))
        cur.execute("DELETE FROM seats WHERE id > %s", (SEED_MAX_ID["seats"],))
        cur.execute("DELETE FROM screens WHERE id > %s", (SEED_MAX_ID["screens"],))
        cur.execute("DELETE FROM theatres WHERE id > %s", (SEED_MAX_ID["theatres"],))
        cur.execute("DELETE FROM movies WHERE id > %s", (SEED_MAX_ID["movies"],))


@pytest.fixture(autouse=True)
def clean_state():
    """Restore the seed after every test and drop accounts tests registered."""
    yield
    reset_seed_state()
    with db.transaction() as cur:
        cur.execute(
            "DELETE FROM users WHERE email LIKE %s", (TEST_EMAIL_PREFIX + "%",)
        )


@pytest.fixture()
def clean_booking_state(clean_state):
    """Kept for readability: state cleanup is automatic."""
    return clean_state


@pytest.fixture()
def make_show():
    """Schedule a show on a free screen and return its row."""
    counter = itertools.count()

    def factory(
        price=Decimal("200.00"),
        *,
        movie_id: int = 1,
        screen_id: int = 2,
        hours: int = 2,
        starts_in_minutes: int | None = None,
    ) -> dict:
        if starts_in_minutes is None:
            start = (
                datetime.now(timezone.utc) + timedelta(days=40 + next(counter))
            ).replace(microsecond=0)
        else:
            start = (datetime.now(timezone.utc) + timedelta(minutes=starts_in_minutes)).replace(microsecond=0)

        row = db.fetch_one(
            "SELECT show_id, movie_id, screen_id, start_at, end_at, base_price, seat_count "
            "FROM fn_create_show(%s, %s, %s, %s, %s)",
            (movie_id, screen_id, start, start + timedelta(hours=hours), Decimal(price)),
        )
        return dict(row)

    return factory


@pytest.fixture()
def make_hold():
    """Hold N available seats for a seeded user, straight through the function."""

    def factory(email: str, show_id: int, count: int = 1) -> dict:
        user = db.fetch_one("SELECT id FROM users WHERE email = %s", (email,))
        seats = db.fetch_all(
            "SELECT seat_id FROM show_seats WHERE show_id = %s AND status = 'AVAILABLE' "
            "ORDER BY seat_id LIMIT %s",
            (show_id, count),
        )
        seat_ids = [row["seat_id"] for row in seats]
        hold = db.fetch_one(
            "SELECT booking_id, status, hold_expires_at, total_amount "
            "FROM fn_hold_seats(%s, %s, %s, %s)",
            (user["id"], show_id, seat_ids, 5),
        )
        return {
            "booking_id": hold["booking_id"],
            "seat_ids": seat_ids,
            "total_amount": hold["total_amount"],
        }

    return factory
