"""Admin reports.

Every number is computed in SQL (``database/queries.sql`` #8-#10 and
``vw_show_availability``); these routes only validate parameters and shape the
response. Reports are read-only and admin-only.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend import auth, db, validators
from backend.errors import ApiError

reports_bp = Blueprint("reports", __name__, url_prefix="/api/admin/reports")

MAX_TOP_MOVIES = 50

# database/queries.sql #8
REVENUE = """
    WITH paid AS (
        SELECT COUNT(*)                   AS payment_count,
               COALESCE(SUM(p.amount), 0) AS gross
        FROM payments p
        WHERE p.status = 'SUCCESS'
          AND (%s::date IS NULL OR p.created_at >= %s::date)
          AND (%s::date IS NULL OR p.created_at < (%s::date + INTERVAL '1 day'))
    ), refunded AS (
        SELECT COUNT(*)                   AS refund_count,
               COALESCE(SUM(r.amount), 0) AS refunds
        FROM refunds r
        WHERE r.status IN ('REQUESTED', 'APPROVED')
          AND (%s::date IS NULL OR r.created_at >= %s::date)
          AND (%s::date IS NULL OR r.created_at < (%s::date + INTERVAL '1 day'))
    )
    SELECT paid.payment_count,
           paid.gross,
           refunded.refund_count,
           refunded.refunds,
           paid.gross - refunded.refunds AS net
    FROM paid, refunded
"""

# database/queries.sql #9
OCCUPANCY = """
    SELECT v.show_id,
           m.title            AS movie_title,
           v.theatre_name,
           v.screen_name,
           v.show_start_at,
           v.booked_count,
           v.held_count,
           v.available_count,
           v.total_count,
           ROUND(100.0 * v.booked_count / NULLIF(v.total_count, 0), 1) AS occupancy_pct
    FROM vw_show_availability v
    JOIN movies m ON m.id = v.movie_id
    WHERE (%s::date IS NULL OR v.show_start_at >= %s::date)
      AND (%s::date IS NULL OR v.show_start_at < (%s::date + INTERVAL '1 day'))
    ORDER BY v.show_start_at, v.show_id
"""

# database/queries.sql #10
TOP_MOVIES = """
    SELECT m.id                      AS movie_id,
           m.title,
           COUNT(DISTINCT b.id)      AS booking_count,
           COUNT(bs.seat_id)         AS seats_sold,
           COALESCE(SUM(bs.price), 0) AS revenue
    FROM movies m
    JOIN shows sh         ON sh.movie_id = m.id
    JOIN bookings b       ON b.show_id = sh.id AND b.status = 'CONFIRMED'
    JOIN booking_seats bs ON bs.booking_id = b.id
    GROUP BY m.id, m.title
    ORDER BY revenue DESC, m.id
    LIMIT %s
"""


@reports_bp.before_request
def _require_admin():
    if auth.current_user() is None:
        raise ApiError(401, "UNAUTHORIZED", "Sign in to continue.")
    if auth.current_user()["role"] != "admin":
        raise ApiError(403, "FORBIDDEN", "Administrator access is required.")


@reports_bp.get("/revenue")
def revenue():
    """Cash-flow report: successful payments minus refunds in a date range.

    Both bounds are optional and inclusive; without them the range is all time.
    """
    start, end = validators.date_range()
    row = db.fetch_one(REVENUE, (start, start, end, end, start, start, end, end))
    return jsonify(
        {
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
            "payment_count": row["payment_count"],
            "gross": row["gross"],
            "refund_count": row["refund_count"],
            "refunds": row["refunds"],
            "net": row["net"],
        }
    )


@reports_bp.get("/occupancy")
def occupancy():
    """Per-show fill rate for shows starting inside the range."""
    start, end = validators.date_range()
    rows = db.fetch_all(OCCUPANCY, (start, start, end, end))
    return jsonify({"count": len(rows), "shows": rows})


@reports_bp.get("/top-movies")
def top_movies():
    """Movies ranked by confirmed-booking revenue."""
    raw = request.args.get("limit", "10")
    try:
        limit = int(raw)
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "limit must be a positive integer.") from None
    if limit <= 0 or limit > MAX_TOP_MOVIES:
        raise ApiError(
            400, "VALIDATION_ERROR", f"limit must be between 1 and {MAX_TOP_MOVIES}."
        )

    rows = db.fetch_all(TOP_MOVIES, (limit,))
    return jsonify({"count": len(rows), "movies": rows})
