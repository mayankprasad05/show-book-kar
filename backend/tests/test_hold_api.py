"""Tests for Part D: the atomic seat hold.

Each writing test uses the ``clean_booking_state`` fixture, which restores the
seeded bookings and seat rows afterwards, so the suite can be re-run on the same
database and the seeded demo data stays intact.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend import db

ALICE = ("alice@example.com", "Passw0rd!")
BOB = ("bob@example.com", "Passw0rd!")


def login(client, credentials):
    return client.post(
        "/api/auth/login",
        json={"email": credentials[0], "password": credentials[1]},
    )


def seats_of(show_id: int, limit: int | None = None) -> list:
    rows = db.fetch_all(
        "SELECT seat_id, price FROM show_seats WHERE show_id = %s ORDER BY seat_id",
        (show_id,),
    )
    return rows[:limit] if limit else rows


def seat_ids_of(show_id: int, limit: int) -> list[int]:
    return [row["seat_id"] for row in seats_of(show_id, limit)]


def hold(client, show_id: int, seat_ids: list):
    return client.post("/api/bookings", json={"show_id": show_id, "seat_ids": seat_ids})


def booking_count(show_id: int) -> int:
    return db.fetch_one(
        "SELECT COUNT(*) AS n FROM bookings WHERE show_id = %s", (show_id,)
    )["n"]


# ---------------------------------------------------------------------------
# Guards and validation
# ---------------------------------------------------------------------------
def test_hold_requires_login(client):
    response = hold(client, 6, seat_ids_of(6, 1))
    assert response.status_code == 401
    assert response.get_json()["error"] == "UNAUTHORIZED"


def test_hold_rejects_an_empty_or_malformed_seat_list(client, clean_booking_state):
    login(client, ALICE)
    cases = [
        ({"show_id": 6, "seat_ids": []}, "INVALID_SEATS"),
        ({"show_id": 6, "seat_ids": [11, 11]}, "INVALID_SEATS"),
        ({"show_id": 6, "seat_ids": ["11"]}, "INVALID_SEATS"),
        ({"show_id": 6, "seat_ids": ["abc"]}, "INVALID_SEATS"),
        ({"show_id": 6, "seat_ids": list(range(1, 12))}, "INVALID_SEATS"),
        ({"show_id": "6", "seat_ids": [11]}, "VALIDATION_ERROR"),
        ({"seat_ids": [11]}, "VALIDATION_ERROR"),
    ]
    for body, code in cases:
        response = client.post("/api/bookings", json=body)
        assert response.status_code == 400, body
        assert response.get_json()["error"] == code, body

    assert booking_count(6) == 0


def test_hold_rejects_unknown_show(client, clean_booking_state):
    login(client, ALICE)
    response = hold(client, 9999, seat_ids_of(6, 1))
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"


def test_hold_rejects_a_seat_that_is_not_part_of_the_show(client, clean_booking_state):
    # seat_id identifies the physical seat, and every mock show uses screen 1,
    # so a seat from another screen is a seat this show has no row for.
    login(client, ALICE)
    own = seat_ids_of(6, 1)[0]
    foreign = db.fetch_one(
        "SELECT id FROM seats WHERE id NOT IN "
        "(SELECT seat_id FROM show_seats WHERE show_id = 6) ORDER BY id LIMIT 1"
    )["id"]

    response = hold(client, 6, [own, foreign])
    assert response.status_code == 400
    assert response.get_json()["error"] == "INVALID_SEATS"

    # Nothing was written: the valid seat is untouched and no booking exists.
    assert booking_count(6) == 0
    assert (
        db.fetch_one(
            "SELECT status FROM show_seats WHERE show_id = 6 AND seat_id = %s",
            (own,),
        )["status"]
        == "AVAILABLE"
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_hold_creates_a_pending_booking_and_holds_the_seats(client, clean_booking_state):
    login(client, ALICE)
    chosen = seats_of(6, 2)
    seat_ids = [row["seat_id"] for row in chosen]

    response = hold(client, 6, seat_ids)
    assert response.status_code == 201

    booking = response.get_json()["booking"]
    assert booking["status"] == "PENDING"
    assert booking["show_id"] == 6
    assert booking["hold_duration_minutes"] == 5
    assert Decimal(booking["total_amount"]) == sum(row["price"] for row in chosen)

    expiry = datetime.fromisoformat(booking["hold_expires_at"])
    now = datetime.now(timezone.utc)
    assert now + timedelta(minutes=4) < expiry < now + timedelta(minutes=6)

    assert {seat["seat_id"] for seat in booking["seats"]} == set(seat_ids)
    assert all(seat["status"] == "HELD" for seat in booking["seats"])
    assert response.headers["Location"] == f"/api/bookings/{booking['booking_id']}"

    # The database agrees: HELD, owned by this booking, expiry stored.
    rows = db.fetch_all(
        "SELECT status, hold_expires_at, held_by_booking_id FROM show_seats "
        "WHERE show_id = 6 AND seat_id = ANY (%s)",
        (seat_ids,),
    )
    assert {row["status"] for row in rows} == {"HELD"}
    assert {row["held_by_booking_id"] for row in rows} == {booking["booking_id"]}
    assert all(row["hold_expires_at"] is not None for row in rows)

    # And it shows up in the caller's own history.
    listing = client.get("/api/bookings").get_json()
    assert booking["booking_id"] in [item["booking_id"] for item in listing["bookings"]]


def test_client_cannot_set_the_amount(client, clean_booking_state):
    login(client, ALICE)
    seat = seats_of(10, 1)[0]

    response = client.post(
        "/api/bookings",
        json={"show_id": 10, "seat_ids": [seat["seat_id"]], "total_amount": "1.00"},
    )
    assert response.status_code == 201
    assert Decimal(response.get_json()["booking"]["total_amount"]) == seat["price"]


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------
def test_second_user_is_blocked_and_the_first_hold_survives(app, client, clean_booking_state):
    login(client, ALICE)
    seat_id = seat_ids_of(6, 1)[0]
    first = hold(client, 6, [seat_id])
    assert first.status_code == 201
    first_booking_id = first.get_json()["booking"]["booking_id"]

    bob = app.test_client()
    login(bob, BOB)
    second = hold(bob, 6, [seat_id])

    assert second.status_code == 409
    assert second.get_json()["error"] == "SEAT_UNAVAILABLE"

    row = db.fetch_one(
        "SELECT status, held_by_booking_id FROM show_seats "
        "WHERE show_id = 6 AND seat_id = %s",
        (seat_id,),
    )
    assert row["status"] == "HELD"
    assert row["held_by_booking_id"] == first_booking_id


def test_one_unavailable_seat_rejects_the_whole_hold(app, client, clean_booking_state):
    login(client, ALICE)
    blocked, free = seat_ids_of(7, 2)
    assert hold(client, 7, [blocked]).status_code == 201

    bob = app.test_client()
    login(bob, BOB)
    response = hold(bob, 7, [blocked, free])

    assert response.status_code == 409
    assert response.get_json()["error"] == "SEAT_UNAVAILABLE"

    # The free seat was not partially reserved and bob has no booking at all.
    assert (
        db.fetch_one(
            "SELECT status FROM show_seats WHERE show_id = 7 AND seat_id = %s", (free,)
        )["status"]
        == "AVAILABLE"
    )
    assert (
        db.fetch_one(
            "SELECT b.id FROM bookings b JOIN users u ON u.id = b.user_id "
            "WHERE u.email = %s AND b.show_id = 7",
            (BOB[0],),
        )
        is None
    )


def test_second_hold_for_the_same_show_is_rejected(client, clean_booking_state):
    login(client, ALICE)
    first, second = seat_ids_of(8, 2)

    assert hold(client, 8, [first]).status_code == 201
    response = hold(client, 8, [second])

    assert response.status_code == 409
    assert response.get_json()["error"] == "INVALID_STATE"
    # The second seat was not touched by the rejected request.
    assert (
        db.fetch_one(
            "SELECT status FROM show_seats WHERE show_id = 8 AND seat_id = %s",
            (second,),
        )["status"]
        == "AVAILABLE"
    )


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------
def test_expired_hold_is_released_and_reclaimable(app, client, clean_booking_state):
    login(client, ALICE)
    seat_id = seat_ids_of(9, 1)[0]
    first = hold(client, 9, [seat_id]).get_json()["booking"]

    # Age the hold past its window without waiting five minutes.
    with db.transaction() as cur:
        cur.execute(
            "UPDATE show_seats SET hold_expires_at = NOW() - INTERVAL '1 minute' "
            "WHERE show_id = 9 AND seat_id = %s",
            (seat_id,),
        )

    bob = app.test_client()
    login(bob, BOB)
    response = hold(bob, 9, [seat_id])
    assert response.status_code == 201
    new_booking = response.get_json()["booking"]
    assert new_booking["booking_id"] != first["booking_id"]

    # The abandoned hold was released and its booking expired.
    assert (
        client.get(f"/api/bookings/{first['booking_id']}").get_json()["booking"][
            "booking_status"
        ]
        == "EXPIRED"
    )
    row = db.fetch_one(
        "SELECT status, held_by_booking_id FROM show_seats "
        "WHERE show_id = 9 AND seat_id = %s",
        (seat_id,),
    )
    assert row["status"] == "HELD"
    assert row["held_by_booking_id"] == new_booking["booking_id"]


# ---------------------------------------------------------------------------
# Concurrency: the scenario from workplan Phase 8
# ---------------------------------------------------------------------------
def test_two_sessions_race_for_one_seat(app, clean_booking_state):
    seat_id = seat_ids_of(11, 1)[0]
    barrier = threading.Barrier(2)
    results: dict[str, int] = {}

    def attempt(name: str, credentials: tuple[str, str]) -> None:
        client = app.test_client()
        login(client, credentials)
        barrier.wait()
        results[name] = hold(client, 11, [seat_id]).status_code

    threads = [
        threading.Thread(target=attempt, args=("alice", ALICE)),
        threading.Thread(target=attempt, args=("bob", BOB)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results.values()) == [201, 409], results

    held = db.fetch_all(
        "SELECT held_by_booking_id FROM show_seats "
        "WHERE show_id = 11 AND seat_id = %s AND status = 'HELD'",
        (seat_id,),
    )
    assert len(held) == 1
    assert booking_count(11) == 1
