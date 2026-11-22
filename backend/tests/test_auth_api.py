"""Tests for Part C: session auth, guards, and owner-scoped booking reads."""

from __future__ import annotations

from flask import jsonify

from backend import auth, db
from backend.app import create_app

ALICE = {"email": "alice@example.com", "password": "Passw0rd!"}
ADMIN = {"email": "admin1@example.com", "password": "Passw0rd!"}
NEW_USER = {
    "name": "Test User",
    "email": "pytest.one@example.com",
    "password": "Secret123",
}


def register(client, **overrides):
    body = dict(NEW_USER)
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


def login(client, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def test_register_creates_customer_and_signs_in(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["role"] == "customer"
    assert body["user"]["email"] == NEW_USER["email"]
    assert "password" not in response.get_data(as_text=True)

    # The cookie from registration is a working session.
    assert client.get("/api/auth/me").get_json()["user"]["email"] == NEW_USER["email"]

    # Stored as a bcrypt digest, never plaintext.
    row = db.fetch_one(
        "SELECT password_hash FROM users WHERE email = %s", (NEW_USER["email"],)
    )
    assert row["password_hash"] != NEW_USER["password"]
    assert row["password_hash"].startswith("$2b$")
    assert auth.verify_password(NEW_USER["password"], row["password_hash"]) is True


def test_register_rejects_duplicate_email(client):
    assert register(client).status_code == 201
    duplicate = register(client, name="Someone Else")
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "EMAIL_TAKEN"


def test_register_validates_input(client):
    cases = [
        ({"password": "short"}, "VALIDATION_ERROR"),
        ({"email": "not-an-email"}, "VALIDATION_ERROR"),
        ({"name": "   "}, "VALIDATION_ERROR"),
        ({"password": "x" * 100}, "VALIDATION_ERROR"),
    ]
    for overrides, code in cases:
        response = register(client, **overrides)
        assert response.status_code == 400, overrides
        assert response.get_json()["error"] == code

    # None of the rejected attempts created an account.
    assert (
        db.fetch_one(
            "SELECT id FROM users WHERE email = %s", (NEW_USER["email"],)
        )
        is None
    )


# ---------------------------------------------------------------------------
# Login / logout / me
# ---------------------------------------------------------------------------
def test_login_succeeds_for_seeded_customer(client):
    response = login(client, **ALICE)
    assert response.status_code == 200
    user = response.get_json()["user"]
    assert user["email"] == ALICE["email"]
    assert user["role"] == "customer"
    assert "password_hash" not in user
    assert client.get("/api/auth/me").status_code == 200


def test_login_rejects_bad_credentials_without_enumeration(client):
    wrong_password = login(client, ALICE["email"], "not-the-password")
    unknown_email = login(client, "nobody@example.com", "not-the-password")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.get_json()["error"] == "INVALID_CREDENTIALS"
    assert wrong_password.get_json() == unknown_email.get_json()


def test_me_requires_a_session(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error"] == "UNAUTHORIZED"


def test_logout_ends_the_session(client):
    login(client, **ALICE)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_seeded_admin_can_sign_in(client):
    response = login(client, **ADMIN)
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "admin"


def test_role_cannot_be_escalated_through_registration(client):
    response = register(client, role="admin")
    assert response.status_code == 201
    assert response.get_json()["user"]["role"] == "customer"


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def test_admin_guard_blocks_customers():
    app = create_app({"TESTING": True, "PROPAGATE_EXCEPTIONS": False})
    app.add_url_rule(
        "/api/_probe/admin",
        "_admin_probe",
        auth.admin_required(lambda: jsonify({"ok": True})),
    )
    client = app.test_client()

    login(client, **ALICE)  # customer
    assert client.get("/api/_probe/admin").status_code == 403

    client.post("/api/auth/logout")
    login(client, **ADMIN)  # admin
    assert client.get("/api/_probe/admin").status_code == 200


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
def test_bookings_require_login(client):
    response = client.get("/api/bookings")
    assert response.status_code == 401
    assert response.get_json()["error"] == "UNAUTHORIZED"


def test_bookings_list_contains_only_the_callers_bookings(client):
    login(client, **ALICE)
    response = client.get("/api/bookings")
    assert response.status_code == 200

    body = response.get_json()
    assert body["count"] == 1
    booking = body["bookings"][0]
    assert booking["booking_id"] == 1
    assert booking["user_id"] == 1
    assert booking["movie_title"]
    assert booking["theatre_name"]
    assert booking["seats"], "a confirmed booking must list its seats"
    assert all(seat["status"] == "BOOKED" for seat in booking["seats"])
    assert isinstance(booking["booking_total_amount"], str)


def test_cannot_read_another_users_booking(client):
    login(client, **ALICE)
    # Booking 2 belongs to bob.
    response = client.get("/api/bookings/2")
    assert response.status_code == 403
    assert response.get_json()["error"] == "FORBIDDEN"


def test_own_booking_detail_is_returned(client):
    login(client, **ALICE)
    response = client.get("/api/bookings/1")
    assert response.status_code == 200
    booking = response.get_json()["booking"]
    assert booking["booking_id"] == 1
    assert len(booking["seats"]) >= 1


def test_missing_booking_is_404(client):
    login(client, **ALICE)
    response = client.get("/api/bookings/99999")
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"


def test_unicode_password_round_trips(client):
    body = dict(NEW_USER, email="pytest.unicode@example.com", password="pässwörd-123")
    assert client.post("/api/auth/register", json=body).status_code == 201
    client.post("/api/auth/logout")
    assert login(client, body["email"], body["password"]).status_code == 200
