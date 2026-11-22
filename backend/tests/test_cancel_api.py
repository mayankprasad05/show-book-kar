"""Tests for Part F: cancellation, refunds and the booking window."""

from __future__ import annotations

from decimal import Decimal

from backend import db

ALICE = ("alice@example.com", "Passw0rd!")
BOB = ("bob@example.com", "Passw0rd!")


def login(client, credentials):
    return client.post(
        "/api/auth/login",
        json={"email": credentials[0], "password": credentials[1]},
    )


def pay(client, booking_id: int):
    return client.post(f"/api/bookings/{booking_id}/pay", json={"simulate": "success"})


def cancel(client, booking_id: int):
    return client.post(f"/api/bookings/{booking_id}/cancel")


def confirmed_booking(client, make_show, make_hold, email=ALICE[0], **show_kwargs) -> dict:
    """Hold, pay, and return the booking id plus the show."""
    show = make_show(**show_kwargs)
    hold = make_hold(email, show["show_id"])
    assert pay(client, hold["booking_id"]).status_code == 200
    return {"booking_id": hold["booking_id"], "show_id": show["show_id"]}


def booking_row(booking_id: int) -> dict:
    return db.fetch_one(
        "SELECT status, total_amount FROM bookings WHERE id = %s", (booking_id,)
    )


def test_cancel_requires_login(client, make_show, make_hold):
    # Build the booking through SQL: logging in would defeat the point.
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])
    response = cancel(client, hold["booking_id"])
    assert response.status_code == 401


def test_cancel_confirmed_booking_files_refund_and_frees_seats(client, make_show, make_hold):
    login(client, ALICE)
    booking = confirmed_booking(client, make_show, make_hold, price=Decimal("150.00"))

    response = cancel(client, booking["booking_id"])
    assert response.status_code == 200

    body = response.get_json()
    assert body["booking"]["booking_status"] == "CANCELLED"
    assert body["booking"]["refund_status"] == "REQUESTED"
    assert Decimal(body["booking"]["refund_amount"]) == Decimal("150.00")
    assert body["cancellation_cutoff_hours"] == 2
    assert booking_row(booking["booking_id"])["status"] == "CANCELLED"

    # The seat is sellable again.
    seats = db.fetch_all(
        "SELECT ss.status, ss.hold_expires_at, ss.held_by_booking_id FROM show_seats ss "
        "JOIN booking_seats bs ON bs.show_id = ss.show_id AND bs.seat_id = ss.seat_id "
        "WHERE bs.booking_id = %s",
        (booking["booking_id"],),
    )
    assert {row["status"] for row in seats} == {"AVAILABLE"}
    assert all(row["hold_expires_at"] is None for row in seats)
    assert all(row["held_by_booking_id"] is None for row in seats)

    refund = db.fetch_one(
        "SELECT status, amount FROM refunds WHERE booking_id = %s",
        (booking["booking_id"],),
    )
    assert refund["status"] == "REQUESTED"
    assert refund["amount"] == Decimal("150.00")


def test_cancel_twice_is_rejected(client, make_show, make_hold):
    login(client, ALICE)
    booking = confirmed_booking(client, make_show, make_hold)

    assert cancel(client, booking["booking_id"]).status_code == 200
    second = cancel(client, booking["booking_id"])

    assert second.status_code == 409
    assert second.get_json()["error"] == "INVALID_STATE"


def test_cancel_pending_hold_is_rejected(client, make_show, make_hold):
    login(client, ALICE)
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])

    response = cancel(client, hold["booking_id"])
    assert response.status_code == 409
    assert response.get_json()["error"] == "INVALID_STATE"
    assert booking_row(hold["booking_id"])["status"] == "PENDING"


def test_cancel_inside_the_cutoff_is_rejected(client, make_show, make_hold):
    login(client, ALICE)
    # Starts in 30 minutes; the configured cutoff is 2 hours.
    booking = confirmed_booking(client, make_show, make_hold, starts_in_minutes=30)

    response = cancel(client, booking["booking_id"])
    assert response.status_code == 409
    assert response.get_json()["error"] == "CANCELLATION_NOT_ALLOWED"
    assert booking_row(booking["booking_id"])["status"] == "CONFIRMED"

    # The seats stay booked.
    seats = db.fetch_all(
        "SELECT status FROM show_seats WHERE held_by_booking_id = %s",
        (booking["booking_id"],),
    )
    assert {row["status"] for row in seats} == {"BOOKED"}


def test_cannot_cancel_another_users_booking(app, client, make_show, make_hold):
    login(client, ALICE)
    booking = confirmed_booking(client, make_show, make_hold)

    bob = app.test_client()
    login(bob, BOB)
    response = cancel(bob, booking["booking_id"])

    assert response.status_code == 403
    assert response.get_json()["error"] == "FORBIDDEN"
    assert booking_row(booking["booking_id"])["status"] == "CONFIRMED"


def test_cancel_unknown_booking_is_404(client):
    login(client, ALICE)
    response = cancel(client, 999999)
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"


def test_cancelled_seats_can_be_booked_again(client, make_show, make_hold):
    """Regression: a dead booking must not block re-booking (schema fix)."""
    login(client, ALICE)
    booking = confirmed_booking(client, make_show, make_hold)
    assert cancel(client, booking["booking_id"]).status_code == 200

    seat_ids = [
        row["seat_id"]
        for row in db.fetch_all(
            "SELECT seat_id FROM show_seats WHERE show_id = %s AND status = 'AVAILABLE' "
            "ORDER BY seat_id LIMIT 1",
            (booking["show_id"],),
        )
    ]
    again = client.post(
        "/api/bookings", json={"show_id": booking["show_id"], "seat_ids": seat_ids}
    )
    assert again.status_code == 201
    assert again.get_json()["booking"]["status"] == "PENDING"


def test_cancelled_booking_cannot_be_paid(client, make_show, make_hold):
    login(client, ALICE)
    booking = confirmed_booking(client, make_show, make_hold)
    assert cancel(client, booking["booking_id"]).status_code == 200

    response = pay(client, booking["booking_id"])
    assert response.status_code == 409
    assert response.get_json()["error"] == "INVALID_STATE"
