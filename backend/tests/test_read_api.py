"""Tests for the Part B read API and the shared error envelope."""

from __future__ import annotations


def test_health_reports_database_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["schema_loaded"] is True


def test_list_movies_returns_seeded_catalogue(client):
    response = client.get("/api/movies")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 15
    assert len(body["movies"]) == 15
    assert body["movies"][0]["id"] == 1
    assert set(body["movies"][0]) == {
        "id",
        "title",
        "language",
        "duration_minutes",
        "created_at",
    }


def test_movie_detail_includes_shows(client):
    response = client.get("/api/movies/3")
    assert response.status_code == 200
    body = response.get_json()
    assert body["movie"]["id"] == 3
    assert body["date"] is None
    assert len(body["shows"]) == 4
    first = body["shows"][0]
    assert first["theatre_name"]
    # money is serialised as a string, timestamps as ISO-8601
    assert isinstance(first["base_price"], str)
    assert "T" in first["start_at"]


def test_movie_date_filter_is_half_open(client):
    same_day = client.get("/api/movies/3?date=2026-12-02").get_json()
    next_day = client.get("/api/movies/3?date=2026-12-03").get_json()
    assert len(same_day["shows"]) == 4
    assert same_day["shows"][0]["start_at"].startswith("2026-12-02")
    assert next_day["shows"] == []


def test_invalid_date_uses_error_envelope(client):
    response = client.get("/api/movies/3?date=02-12-2026")
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "INVALID_DATE",
        "message": "The date filter must use the YYYY-MM-DD format.",
    }


def test_missing_movie_is_404(client):
    response = client.get("/api/movies/9999")
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"


def test_show_detail_has_venue_and_counts(client):
    response = client.get("/api/shows/5")
    assert response.status_code == 200
    body = response.get_json()
    show = body["show"]
    assert show["show_id"] == 5
    assert show["movie_title"]
    assert show["theatre_city"]
    assert show["show_base_price"]


def test_show_seat_map_lists_every_seat(client):
    response = client.get("/api/shows/5/seats")
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["seats"]) == 16
    counts = body["counts"]
    assert counts["total_count"] == 16
    assert (
        counts["available_count"] + counts["held_count"] + counts["booked_count"]
        == counts["total_count"]
    )
    statuses = {seat["status"] for seat in body["seats"]}
    assert statuses <= {"AVAILABLE", "HELD", "BOOKED"}
    assert any(seat["status"] == "HELD" for seat in body["seats"])


def test_missing_show_is_404(client):
    response = client.get("/api/shows/9999/seats")
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.get_json()["error"] == "NOT_FOUND"
