"""Tests for Part E: payment confirmation, idempotency and declines."""

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


def pay(client, booking_id: int, simulate: str | None = None):
    body = {} if simulate is None else {"simulate": simulate}
    return client.post(f"/api/bookings/{booking_id}/pay", json=body)


def payments_for(booking_id: int) -> list:
    return db.fetch_all(
        "SELECT status, amount, transaction_ref FROM payments WHERE booking_id = %s",
        (booking_id,),
    )


def seats_of(booking_id: int) -> list:
    return db.fetch_all(
        "SELECT ss.status, ss.hold_expires_at, ss.held_by_booking_id "
        "FROM show_seats ss JOIN booking_seats bs "
        "  ON bs.show_id = ss.show_id AND bs.seat_id = ss.seat_id "
        "WHERE bs.booking_id = %s ORDER BY ss.seat_id",
        (booking_id,),
    )


def test_pay_requires_login(client, make_show, make_hold):
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])
    response = pay(client, hold["booking_id"])
    assert response.status_code == 401
    assert response.get_json()["error"] == "UNAUTHORIZED"


def test_pay_confirms_the_booking_and_books_the_seats(client, make_show, make_hold):
    show = make_show(price=Decimal("120.00"))
    hold = make_hold(ALICE[0], show["show_id"], count=2)
    login(client, ALICE)

    response = pay(client, hold["booking_id"])
    assert response.status_code == 200

    booking = response.get_json()["booking"]
    assert booking["booking_status"] == "CONFIRMED"
    assert booking["payment_status"] == "SUCCESS"
    assert Decimal(booking["amount"]) == hold["total_amount"]

    rows = seats_of(hold["booking_id"])
    assert {row["status"] for row in rows} == {"BOOKED"}
    assert all(row["hold_expires_at"] is None for row in rows)

    payments = payments_for(hold["booking_id"])
    assert len(payments) == 1
    assert payments[0]["status"] == "SUCCESS"
    assert payments[0]["transaction_ref"].startswith("txn_")


def test_repeat_payment_is_idempotent(client, make_show, make_hold):
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])
    login(client, ALICE)

    first = pay(client, hold["booking_id"])
    second = pay(client, hold["booking_id"])

    assert first.status_code == second.status_code == 200
    assert first.get_json() == second.get_json()
    assert len(payments_for(hold["booking_id"])) == 1


def test_declined_payment_keeps_the_hold_and_a_retry_can_succeed(
    client, make_show, make_hold
):
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])
    login(client, ALICE)

    declined = pay(client, hold["booking_id"], "failure")
    assert declined.status_code == 200
    assert declined.get_json()["booking"]["payment_status"] == "FAILED"
    assert declined.get_json()["booking"]["booking_status"] == "PENDING"

    # Seats are still held, so the customer can try again inside the window.
    assert {row["status"] for row in seats_of(hold["booking_id"])} == {"HELD"}
    assert payments_for(hold["booking_id"])[0]["status"] == "FAILED"
    assert len(payments_for(hold["booking_id"])) == 1

    retried = pay(client, hold["booking_id"])
    assert retried.status_code == 200
    assert retried.get_json()["booking"]["booking_status"] == "CONFIRMED"

    payments = payments_for(hold["booking_id"])
    assert len(payments) == 1, "the retry must reuse the payment row, not add one"
    assert payments[0]["status"] == "SUCCESS"


def test_cannot_pay_another_users_booking(app, client, make_show, make_hold):
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])

    bob = app.test_client()
    login(bob, BOB)
    response = pay(bob, hold["booking_id"])

    assert response.status_code == 403
    assert response.get_json()["error"] == "FORBIDDEN"
    assert (
        db.fetch_one(
            "SELECT status FROM bookings WHERE id = %s", (hold["booking_id"],)
        )["status"]
        == "PENDING"
    )


def test_pay_unknown_booking_is_404(client):
    login(client, ALICE)
    response = pay(client, 999999)
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"


def test_pay_after_the_hold_expired_is_rejected(client, make_show, make_hold):
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])
    login(client, ALICE)

    with db.transaction() as cur:
        cur.execute(
            "UPDATE show_seats SET hold_expires_at = NOW() - INTERVAL '1 minute' "
            "WHERE held_by_booking_id = %s",
            (hold["booking_id"],),
        )

    response = pay(client, hold["booking_id"])
    assert response.status_code == 409
    assert response.get_json()["error"] == "HOLD_EXPIRED"

    # Nothing was written: no payment, booking still PENDING.
    assert payments_for(hold["booking_id"]) == []
    assert (
        db.fetch_one(
            "SELECT status FROM bookings WHERE id = %s", (hold["booking_id"],)
        )["status"]
        == "PENDING"
    )


def test_invalid_simulation_is_rejected(client, make_show, make_hold):
    show = make_show()
    hold = make_hold(ALICE[0], show["show_id"])
    login(client, ALICE)

    response = pay(client, hold["booking_id"], "maybe")
    assert response.status_code == 400
    assert response.get_json()["error"] == "VALIDATION_ERROR"
