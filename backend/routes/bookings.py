"""Booking reads for the signed-in customer.

``vw_booking_history`` is one row per (booking, seat), so the routes group those
rows into one booking object with a ``seats`` array. Ownership is always taken
from the session: a ``user_id`` in the URL or body is never consulted.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend import auth, db, validators
from backend.errors import ApiError

bookings_bp = Blueprint("bookings", __name__, url_prefix="/api")

# A single hold is bounded so one request cannot lock a whole screen.
MAX_SEATS_PER_HOLD = 10

# vw_booking_history carries the booking and seat columns; the joins add what
# the history screen needs to render a row (movie, venue, show time).
BOOKING_HISTORY = """
    SELECT v.booking_id,
           v.user_id,
           v.show_id,
           v.booking_status,
           v.booking_total_amount,
           v.booking_created_at,
           v.seat_id,
           v.seat_row_label,
           v.seat_number,
           v.seat_status,
           v.seat_price_at_booking,
           sh.start_at  AS show_start_at,
           sh.end_at    AS show_end_at,
           m.id         AS movie_id,
           m.title      AS movie_title,
           sc.name      AS screen_name,
           th.name      AS theatre_name,
           th.city      AS theatre_city
    FROM vw_booking_history v
    JOIN shows sh    ON sh.id = v.show_id
    JOIN movies m    ON m.id = sh.movie_id
    JOIN screens sc  ON sc.id = sh.screen_id
    JOIN theatres th ON th.id = sc.theatre_id
    WHERE v.user_id = %s
      AND (%s::integer IS NULL OR v.booking_id = %s::integer)
    ORDER BY v.booking_created_at DESC, v.booking_id DESC,
             v.seat_row_label, v.seat_number
"""

_HEADER_KEYS = (
    "booking_id",
    "user_id",
    "show_id",
    "booking_status",
    "booking_total_amount",
    "booking_created_at",
    "show_start_at",
    "show_end_at",
    "movie_id",
    "movie_title",
    "screen_name",
    "theatre_name",
    "theatre_city",
)


def _group_by_booking(rows: list) -> list[dict]:
    """One row per seat -> one object per booking, seats nested and ordered."""
    grouped: dict[int, dict] = {}
    for row in rows:
        booking = grouped.get(row["booking_id"])
        if booking is None:
            booking = {key: row[key] for key in _HEADER_KEYS}
            booking["seats"] = []
            grouped[row["booking_id"]] = booking

        if row["seat_id"] is not None:  # LEFT JOIN in the view: may be empty
            booking["seats"].append(
                {
                    "seat_id": row["seat_id"],
                    "row_label": row["seat_row_label"],
                    "seat_number": row["seat_number"],
                    "status": row["seat_status"],
                    "price": row["seat_price_at_booking"],
                }
            )
    return list(grouped.values())


def _owned_booking_or_error(booking_id: int, user_id: int) -> None:
    """404 when the booking does not exist, 403 when it belongs to someone else."""
    owner = db.fetch_one("SELECT user_id FROM bookings WHERE id = %s", (booking_id,))
    if owner is None:
        raise ApiError(404, "NOT_FOUND", "Booking not found.")
    if owner["user_id"] != user_id:
        raise ApiError(403, "FORBIDDEN", "You do not have access to this booking.")


@bookings_bp.get("/bookings")
@auth.login_required
def list_bookings():
    """Every booking of the signed-in user, newest first."""
    user = auth.require_user()
    rows = db.fetch_all(BOOKING_HISTORY, (user["id"], None, None))
    bookings = _group_by_booking(rows)
    return jsonify({"count": len(bookings), "bookings": bookings})


@bookings_bp.get("/bookings/<int:booking_id>")
@auth.login_required
def booking_detail(booking_id: int):
    """One booking, only if it belongs to the signed-in user."""
    user = auth.require_user()
    _owned_booking_or_error(booking_id, user["id"])

    rows = db.fetch_all(BOOKING_HISTORY, (user["id"], booking_id, booking_id))
    bookings = _group_by_booking(rows)
    if not bookings:
        # The booking row exists but the view produced nothing (impossible while
        # the show still exists); report it rather than returning an empty object.
        raise ApiError(404, "NOT_FOUND", "Booking not found.")
    return jsonify({"booking": bookings[0]})


# ---------------------------------------------------------------------------
# Hold (Part D)
# ---------------------------------------------------------------------------
# The whole rule lives in database/functions.sql: this route validates the
# request shape, runs one transaction, and lets the database decide.
HOLD_SEATS = """
    SELECT booking_id, status, hold_expires_at, total_amount
    FROM fn_hold_seats(%s, %s, %s, %s)
"""

HELD_SEAT_ROWS = """
    SELECT ss.seat_id, s.row_label, s.seat_number, ss.price, ss.status
    FROM show_seats ss
    JOIN seats s ON s.id = ss.seat_id
    WHERE ss.show_id = %s
      AND ss.seat_id = ANY (%s)
    ORDER BY s.row_label, s.seat_number
"""


@bookings_bp.post("/bookings")
@auth.login_required
def create_hold():
    """Hold seats for the signed-in user; all-or-nothing.

    The user id comes from the session, and the amount from show_seats.price:
    neither can be supplied by the browser.
    """
    user = auth.require_user()
    body = validators.json_body()

    show_id = validators.positive_int(body.get("show_id"), "show_id")
    seat_ids = body.get("seat_ids")

    if not isinstance(seat_ids, list) or not seat_ids:
        raise ApiError(
            400, "INVALID_SEATS", "seat_ids must be a non-empty list of seat ids."
        )
    if any(isinstance(seat, bool) or not isinstance(seat, int) or seat <= 0 for seat in seat_ids):
        raise ApiError(
            400, "INVALID_SEATS", "Every seat id must be a positive integer."
        )
    if len(set(seat_ids)) != len(seat_ids):
        raise ApiError(400, "INVALID_SEATS", "seat_ids must not repeat a seat.")
    if len(seat_ids) > MAX_SEATS_PER_HOLD:
        raise ApiError(
            400,
            "INVALID_SEATS",
            f"At most {MAX_SEATS_PER_HOLD} seats can be held in one booking.",
        )

    hold_minutes = int(current_app.config["HOLD_DURATION_MINUTES"])

    # One transaction: the booking, its seat rows and the hold all commit
    # together, and a SEAT_UNAVAILABLE leaves no trace.
    with db.transaction() as cur:
        cur.execute(HOLD_SEATS, (user["id"], show_id, seat_ids, hold_minutes))
        hold = dict(cur.fetchone())

        cur.execute(HELD_SEAT_ROWS, (show_id, seat_ids))
        seats = [dict(row) for row in cur.fetchall()]

    location = f"/api/bookings/{hold['booking_id']}"
    return (
        jsonify(
            {
                "booking": {
                    "booking_id": hold["booking_id"],
                    "status": hold["status"],
                    "show_id": show_id,
                    "hold_expires_at": hold["hold_expires_at"],
                    "hold_duration_minutes": hold_minutes,
                    "total_amount": hold["total_amount"],
                    "seats": seats,
                }
            }
        ),
        201,
        {"Location": location},
    )


# ---------------------------------------------------------------------------
# Payment and cancellation (Parts E and F)
# ---------------------------------------------------------------------------
# Both are single calls into database/functions.sql: ownership, state, hold
# expiry and the cancellation cutoff are decided there, in one transaction.
PAY_BOOKING = """
    SELECT booking_id, booking_status, payment_status, amount
    FROM fn_pay_booking(%s, %s, %s)
"""

CANCEL_BOOKING = """
    SELECT booking_id, booking_status, refund_status, refund_amount
    FROM fn_cancel_booking(%s, %s, %s)
"""


@bookings_bp.post("/bookings/<int:booking_id>/pay")
@auth.login_required
def pay_booking(booking_id: int):
    """Confirm a held booking with a simulated payment.

    ``simulate`` is ``success`` (default) or ``failure``; a decline is a normal
    answer (``200`` with ``payment_status: FAILED``) so the client can retry
    while the hold is still live.
    """
    user = auth.require_user()
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_BODY", "Send a JSON object body.")

    simulate = validators.choice(
        body.get("simulate"), ("success", "failure"), "simulate", default="success"
    )
    result = db.fetch_one(PAY_BOOKING, (booking_id, user["id"], simulate))
    return jsonify({"booking": result})


@bookings_bp.post("/bookings/<int:booking_id>/cancel")
@auth.login_required
def cancel_booking(booking_id: int):
    """Cancel a confirmed booking before the cutoff and file a refund request."""
    user = auth.require_user()
    cutoff = int(current_app.config["CANCELLATION_CUTOFF_HOURS"])
    result = db.fetch_one(CANCEL_BOOKING, (booking_id, user["id"], cutoff))
    return jsonify(
        {"booking": result, "cancellation_cutoff_hours": cutoff}
    )
