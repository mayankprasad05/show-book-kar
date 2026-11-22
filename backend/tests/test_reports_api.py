"""Tests for Part H: admin reports computed in SQL."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

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


def test_reports_require_admin(app, client):
    assert client.get("/api/admin/reports/revenue").status_code == 401

    alice = app.test_client()
    login(alice, ALICE)
    assert alice.get("/api/admin/reports/revenue").status_code == 403
    assert alice.get("/api/admin/reports/occupancy").status_code == 403
    assert alice.get("/api/admin/reports/top-movies").status_code == 403


def test_revenue_matches_the_payment_and_refund_tables(admin_client):
    expected = db.fetch_one(
        """
        SELECT (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'SUCCESS') AS gross,
               (SELECT COALESCE(SUM(amount), 0) FROM refunds
                 WHERE status IN ('REQUESTED', 'APPROVED')) AS refunds,
               (SELECT COUNT(*) FROM payments WHERE status = 'SUCCESS') AS payment_count,
               (SELECT COUNT(*) FROM refunds
                 WHERE status IN ('REQUESTED', 'APPROVED')) AS refund_count
        """
    )

    body = admin_client.get("/api/admin/reports/revenue").get_json()

    assert body["from"] is None and body["to"] is None
    assert Decimal(body["gross"]) == expected["gross"]
    assert Decimal(body["refunds"]) == expected["refunds"]
    assert Decimal(body["net"]) == expected["gross"] - expected["refunds"]
    assert body["payment_count"] == expected["payment_count"]
    assert body["refund_count"] == expected["refund_count"]


def test_revenue_respects_the_date_range(admin_client):
    # Seeded payments were taken on 2026-11-20, the refund filed on 2026-11-24.
    payments_only = admin_client.get(
        "/api/admin/reports/revenue?from=2026-11-20&to=2026-11-20"
    ).get_json()
    assert payments_only["refund_count"] == 0
    assert Decimal(payments_only["refunds"]) == Decimal("0.00")
    assert Decimal(payments_only["net"]) == Decimal(payments_only["gross"])
    assert payments_only["payment_count"] > 0

    refunds_only = admin_client.get(
        "/api/admin/reports/revenue?from=2026-11-24&to=2026-11-24"
    ).get_json()
    assert refunds_only["payment_count"] == 0
    assert Decimal(refunds_only["gross"]) == Decimal("0.00")
    assert refunds_only["refund_count"] == 1

    empty = admin_client.get(
        "/api/admin/reports/revenue?from=2030-01-01&to=2030-01-31"
    ).get_json()
    assert empty["payment_count"] == 0
    assert empty["refund_count"] == 0
    assert Decimal(empty["net"]) == Decimal("0.00")


def test_revenue_rejects_a_reversed_range(admin_client):
    response = admin_client.get(
        "/api/admin/reports/revenue?from=2026-12-31&to=2026-01-01"
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "INVALID_DATE"


def test_occupancy_matches_the_availability_view(admin_client):
    body = admin_client.get("/api/admin/reports/occupancy").get_json()
    assert body["count"] == 12

    expected = db.fetch_all(
        "SELECT show_id, booked_count, held_count, available_count, total_count "
        "FROM vw_show_availability ORDER BY show_start_at, show_id"
    )
    for reported, view in zip(body["shows"], expected, strict=True):
        assert reported["show_id"] == view["show_id"]
        assert reported["booked_count"] == view["booked_count"]
        assert reported["held_count"] == view["held_count"]
        assert reported["total_count"] == view["total_count"]
        # Postgres ROUND() is half-up; Python's round() is half-to-even.
        expected_pct = (
            Decimal(view["booked_count"]) * 100 / Decimal(view["total_count"])
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        assert Decimal(str(reported["occupancy_pct"])) == expected_pct


def test_occupancy_date_range_can_be_empty(admin_client):
    body = admin_client.get(
        "/api/admin/reports/occupancy?from=2030-01-01&to=2030-01-02"
    ).get_json()
    assert body == {"count": 0, "shows": []}


def test_top_movies_ranks_confirmed_revenue(admin_client, make_show, make_hold, client):
    # Baseline: the seeded confirmed bookings.
    baseline = admin_client.get("/api/admin/reports/top-movies").get_json()
    assert baseline["count"] >= 1
    revenues = [Decimal(movie["revenue"]) for movie in baseline["movies"]]
    assert revenues == sorted(revenues, reverse=True)

    # Add a confirmed booking on a different movie and it must appear top.
    login(client, ALICE)
    show = make_show(price=Decimal("999.00"), movie_id=2)
    hold = make_hold(ALICE[0], show["show_id"])
    assert (
        client.post(
            f"/api/bookings/{hold['booking_id']}/pay", json={"simulate": "success"}
        ).status_code
        == 200
    )

    after = admin_client.get("/api/admin/reports/top-movies").get_json()
    assert after["count"] == baseline["count"] + 1
    leader = after["movies"][0]
    assert Decimal(leader["revenue"]) == Decimal("999.00")
    assert leader["seats_sold"] == 1
    assert leader["booking_count"] == 1


def test_top_movies_validates_the_limit(admin_client):
    assert admin_client.get("/api/admin/reports/top-movies?limit=0").status_code == 400
    assert admin_client.get("/api/admin/reports/top-movies?limit=abc").status_code == 400
    assert admin_client.get("/api/admin/reports/top-movies?limit=500").status_code == 400
    assert admin_client.get("/api/admin/reports/top-movies?limit=1").get_json()["count"] == 1
