"""Tests for Part G: admin catalogue routes, seat setup and show scheduling."""

from __future__ import annotations

import pytest

from backend import db

ADMIN = ("admin1@example.com", "Passw0rd!")
ALICE = ("alice@example.com", "Passw0rd!")


def login(client, credentials):
    return client.post(
        "/api/auth/login",
        json={"email": credentials[0], "password": credentials[1]},
    )


@pytest.fixture()
def admin_client(app):
    client = app.test_client()
    login(client, ADMIN)
    return client


@pytest.fixture()
def customer_client(app):
    client = app.test_client()
    login(client, ALICE)
    return client


def make_theatre(admin_client, name="Test Theatre"):
    response = admin_client.post(
        "/api/admin/theatres", json={"name": name, "city": "Pune"}
    )
    assert response.status_code == 201
    return response.get_json()["theatre"]


def make_screen(admin_client, theatre_id, capacity=20, name="Test Screen"):
    response = admin_client.post(
        "/api/admin/screens",
        json={"theatre_id": theatre_id, "name": name, "capacity_total": capacity},
    )
    assert response.status_code == 201
    return response.get_json()["screen"]


def add_seats(admin_client, screen_id, rows):
    return admin_client.post(
        f"/api/admin/screens/{screen_id}/seats", json={"rows": rows}
    )


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def test_admin_routes_require_authentication(client):
    for path in ("/api/admin/movies", "/api/admin/shows", "/api/admin/theatres"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json()["error"] == "UNAUTHORIZED"


def test_admin_routes_reject_customers(customer_client):
    assert customer_client.get("/api/admin/movies").status_code == 403
    assert (
        customer_client.post("/api/admin/movies", json={"title": "X", "duration_minutes": 10}).status_code
        == 403
    )
    assert customer_client.get("/api/admin/reports/revenue").status_code == 403


# ---------------------------------------------------------------------------
# Movies
# ---------------------------------------------------------------------------
def test_create_movie_then_patch_it(admin_client):
    created = admin_client.post(
        "/api/admin/movies",
        json={"title": "Test Movie", "duration_minutes": 121},
    )
    assert created.status_code == 201
    movie = created.get_json()["movie"]
    assert movie["title"] == "Test Movie"
    assert movie["language"] == "English"

    patched = admin_client.patch(
        f"/api/admin/movies/{movie['id']}",
        json={"title": "Test Movie (Director's Cut)", "duration_minutes": 130},
    )
    assert patched.status_code == 200
    assert patched.get_json()["movie"]["title"] == "Test Movie (Director's Cut)"
    assert patched.get_json()["movie"]["duration_minutes"] == 130


def test_movie_validation(admin_client):
    bad_duration = admin_client.post(
        "/api/admin/movies", json={"title": "Zero", "duration_minutes": 0}
    )
    assert bad_duration.status_code == 400
    assert bad_duration.get_json()["error"] == "VALIDATION_ERROR"

    missing_title = admin_client.post("/api/admin/movies", json={"duration_minutes": 90})
    assert missing_title.status_code == 400

    listing = admin_client.get("/api/admin/movies").get_json()
    assert all(movie["title"] != "Zero" for movie in listing["movies"])


def test_patch_requires_a_field_and_an_existing_row(admin_client):
    empty = admin_client.patch("/api/admin/movies/1", json={})
    assert empty.status_code == 400
    assert empty.get_json()["error"] == "VALIDATION_ERROR"

    missing = admin_client.patch("/api/admin/movies/999999", json={"title": "Ghost"})
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Theatres, screens and seats
# ---------------------------------------------------------------------------
def test_create_theatre_screen_and_seats(admin_client):
    theatre = make_theatre(admin_client)
    screen = make_screen(admin_client, theatre["id"], capacity=20)

    response = add_seats(
        admin_client,
        screen["id"],
        [
            {"row_label": "A", "count": 10, "seat_type": "standard"},
            {"row_label": "B", "count": 5, "seat_type": "vip"},
        ],
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["created"] == 15
    assert len(body["seats"]) == 15
    assert {seat["seat_type"] for seat in body["seats"]} == {"standard", "vip"}

    listed = admin_client.get("/api/admin/screens").get_json()["screens"]
    created_screen = [item for item in listed if item["id"] == screen["id"]][0]
    assert created_screen["seat_count"] == 15


def test_screen_capacity_is_enforced(admin_client):
    theatre = make_theatre(admin_client)
    screen = make_screen(admin_client, theatre["id"], capacity=10)

    response = add_seats(admin_client, screen["id"], [{"row_label": "A", "count": 11}])
    assert response.status_code == 400
    assert response.get_json()["error"] == "CAPACITY_EXCEEDED"

    assert add_seats(admin_client, screen["id"], [{"row_label": "A", "count": 10}]).status_code == 201
    again = add_seats(admin_client, screen["id"], [{"row_label": "B", "count": 1}])
    assert again.status_code == 400
    assert again.get_json()["error"] == "CAPACITY_EXCEEDED"


def test_seat_setup_validates_its_input(admin_client):
    theatre = make_theatre(admin_client)
    screen = make_screen(admin_client, theatre["id"], capacity=10)

    assert add_seats(admin_client, screen["id"], []).status_code == 400
    assert (
        add_seats(admin_client, screen["id"], [{"row_label": "A", "count": 0}]).status_code
        == 400
    )
    assert (
        add_seats(
            admin_client, screen["id"], [{"row_label": "A", "count": 2, "seat_type": "gold"}]
        ).status_code
        == 400
    )
    assert (
        admin_client.post(
            "/api/admin/screens/999999/seats", json={"rows": [{"row_label": "A", "count": 1}]}
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Shows
# ---------------------------------------------------------------------------
def test_schedule_show_materialises_seats(admin_client):
    theatre = make_theatre(admin_client)
    screen = make_screen(admin_client, theatre["id"], capacity=12)
    add_seats(admin_client, screen["id"], [{"row_label": "A", "count": 12}])

    response = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 1,
            "screen_id": screen["id"],
            "start_at": "2027-03-05T10:00:00+05:30",
            "end_at": "2027-03-05T12:00:00+05:30",
            "base_price": "175.50",
        },
    )
    assert response.status_code == 201
    show = response.get_json()["show"]
    assert show["seat_count"] == 12

    seats = db.fetch_all(
        "SELECT status, price FROM show_seats WHERE show_id = %s", (show["show_id"],)
    )
    assert len(seats) == 12
    assert {row["status"] for row in seats} == {"AVAILABLE"}
    assert {str(row["price"]) for row in seats} == {"175.50"}


def test_overlapping_show_on_the_same_screen_is_rejected(admin_client):
    theatre = make_theatre(admin_client)
    screen = make_screen(admin_client, theatre["id"], capacity=5)
    add_seats(admin_client, screen["id"], [{"row_label": "A", "count": 5}])

    first = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 1,
            "screen_id": screen["id"],
            "start_at": "2027-03-06T10:00:00+05:30",
            "end_at": "2027-03-06T12:00:00+05:30",
            "base_price": "100.00",
        },
    )
    assert first.status_code == 201

    overlapping = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 2,
            "screen_id": screen["id"],
            "start_at": "2027-03-06T11:00:00+05:30",
            "end_at": "2027-03-06T13:00:00+05:30",
            "base_price": "100.00",
        },
    )
    assert overlapping.status_code == 409
    assert overlapping.get_json()["error"] == "SHOW_OVERLAP"

    # Back-to-back on the same screen is allowed.
    back_to_back = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 2,
            "screen_id": screen["id"],
            "start_at": "2027-03-06T12:00:00+05:30",
            "end_at": "2027-03-06T14:00:00+05:30",
            "base_price": "100.00",
        },
    )
    assert back_to_back.status_code == 201


def test_show_scheduling_validates_input(admin_client):
    theatre = make_theatre(admin_client)
    screen = make_screen(admin_client, theatre["id"], capacity=5)
    add_seats(admin_client, screen["id"], [{"row_label": "A", "count": 5}])

    past = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 1,
            "screen_id": screen["id"],
            "start_at": "2020-01-01T10:00:00+05:30",
            "end_at": "2020-01-01T12:00:00+05:30",
            "base_price": "100.00",
        },
    )
    assert past.status_code == 400
    assert past.get_json()["error"] == "VALIDATION_ERROR"

    backwards = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 1,
            "screen_id": screen["id"],
            "start_at": "2027-03-07T12:00:00+05:30",
            "end_at": "2027-03-07T10:00:00+05:30",
            "base_price": "100.00",
        },
    )
    assert backwards.status_code == 400

    no_timezone = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 1,
            "screen_id": screen["id"],
            "start_at": "2027-03-07T10:00:00",
            "end_at": "2027-03-07T12:00:00",
            "base_price": "100.00",
        },
    )
    assert no_timezone.status_code == 400

    unknown_screen = admin_client.post(
        "/api/admin/shows",
        json={
            "movie_id": 1,
            "screen_id": 999999,
            "start_at": "2027-03-07T10:00:00+05:30",
            "end_at": "2027-03-07T12:00:00+05:30",
            "base_price": "100.00",
        },
    )
    assert unknown_screen.status_code == 404
    assert unknown_screen.get_json()["error"] == "NOT_FOUND"


def test_admin_show_list_includes_counts(admin_client):
    response = admin_client.get("/api/admin/shows")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 12  # the seeded shows
    first = body["shows"][0]
    assert first["total_count"] == 16
    assert first["available_count"] + first["held_count"] + first["booked_count"] == 16
