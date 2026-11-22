"""Admin catalogue management and show scheduling.

The whole blueprint is guarded in one place (``before_request``), so a new admin
route cannot be added without the role check. Writes stay parameterised; the
PATCH helper builds its SET list from a whitelist of column names, never from
the request body.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from psycopg2 import sql as psql

from backend import auth, db, validators
from backend.errors import ApiError

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.before_request
def _require_admin():
    if auth.current_user() is None:
        raise ApiError(401, "UNAUTHORIZED", "Sign in to continue.")
    if auth.current_user()["role"] != "admin":
        raise ApiError(403, "FORBIDDEN", "Administrator access is required.")


def _patch(table: str, row_id: int, changes: dict, label: str) -> dict:
    """UPDATE only the whitelisted keys present in ``changes``."""
    if not changes:
        raise ApiError(400, "VALIDATION_ERROR", "Send at least one field to update.")

    assignments = psql.SQL(", ").join(
        psql.SQL("{} = %s").format(psql.Identifier(column)) for column in changes
    )
    query = psql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
        psql.Identifier(table), assignments
    )
    row = db.fetch_one(query, (*changes.values(), row_id))
    if row is None:
        raise ApiError(404, "NOT_FOUND", f"{label} not found.")
    return row


# ---------------------------------------------------------------------------
# Movies
# ---------------------------------------------------------------------------
@admin_bp.get("/movies")
def list_movies():
    rows = db.fetch_all(
        "SELECT id, title, language, duration_minutes, created_at "
        "FROM movies ORDER BY id"
    )
    return jsonify({"count": len(rows), "movies": rows})


@admin_bp.post("/movies")
def create_movie():
    body = validators.json_body()
    movie = db.fetch_one(
        """
        INSERT INTO movies (title, language, duration_minutes)
        VALUES (%s, %s, %s)
        RETURNING id, title, language, duration_minutes, created_at
        """,
        (
            validators.required_text(body, "title", label="Title"),
            validators.optional_text(body, "language", label="Language") or "English",
            validators.positive_int(body.get("duration_minutes"), "duration_minutes"),
        ),
    )
    return jsonify({"movie": movie}), 201


@admin_bp.patch("/movies/<int:movie_id>")
def update_movie(movie_id: int):
    body = validators.json_body()
    changes = {}
    if "title" in body:
        changes["title"] = validators.required_text(body, "title", label="Title")
    if "language" in body:
        changes["language"] = validators.required_text(
            body, "language", label="Language", max_length=40
        )
    if "duration_minutes" in body:
        changes["duration_minutes"] = validators.positive_int(
            body.get("duration_minutes"), "duration_minutes"
        )
    return jsonify({"movie": _patch("movies", movie_id, changes, "Movie")})


# ---------------------------------------------------------------------------
# Theatres
# ---------------------------------------------------------------------------
@admin_bp.get("/theatres")
def list_theatres():
    rows = db.fetch_all(
        """
        SELECT t.id, t.name, t.city, t.created_at,
               COUNT(sc.id) AS screen_count
        FROM theatres t
        LEFT JOIN screens sc ON sc.theatre_id = t.id
        GROUP BY t.id, t.name, t.city, t.created_at
        ORDER BY t.id
        """
    )
    return jsonify({"count": len(rows), "theatres": rows})


@admin_bp.post("/theatres")
def create_theatre():
    body = validators.json_body()
    theatre = db.fetch_one(
        """
        INSERT INTO theatres (name, city) VALUES (%s, %s)
        RETURNING id, name, city, created_at
        """,
        (
            validators.required_text(body, "name", label="Name"),
            validators.required_text(body, "city", label="City", max_length=80),
        ),
    )
    return jsonify({"theatre": theatre}), 201


# ---------------------------------------------------------------------------
# Screens and their seats
# ---------------------------------------------------------------------------
@admin_bp.get("/screens")
def list_screens():
    rows = db.fetch_all(
        """
        SELECT sc.id, sc.name, sc.capacity_total, sc.theatre_id,
               t.name AS theatre_name, t.city AS theatre_city,
               COUNT(se.id) AS seat_count
        FROM screens sc
        JOIN theatres t ON t.id = sc.theatre_id
        LEFT JOIN seats se ON se.screen_id = sc.id
        GROUP BY sc.id, sc.name, sc.capacity_total, sc.theatre_id, t.name, t.city
        ORDER BY sc.id
        """
    )
    return jsonify({"count": len(rows), "screens": rows})


@admin_bp.post("/screens")
def create_screen():
    body = validators.json_body()
    screen = db.fetch_one(
        """
        INSERT INTO screens (theatre_id, name, capacity_total)
        VALUES (%s, %s, %s)
        RETURNING id, theatre_id, name, capacity_total, created_at
        """,
        (
            validators.positive_int(body.get("theatre_id"), "theatre_id"),
            validators.required_text(body, "name", label="Name", max_length=80),
            validators.positive_int(body.get("capacity_total"), "capacity_total"),
        ),
    )
    return jsonify({"screen": screen}), 201


@admin_bp.post("/screens/<int:screen_id>/seats")
def create_screen_seats(screen_id: int):
    """Create seats in bulk from a row layout.

    Body: ``{"rows": [{"row_label": "A", "count": 10, "seat_type": "standard"}]}``.
    Seats are 1-numbered inside each row; the screen's ``capacity_total`` caps
    the total, so a layout can never overfill the room.
    """
    body = validators.json_body()
    layout = body.get("rows")
    if not isinstance(layout, list) or not layout:
        raise ApiError(400, "VALIDATION_ERROR", "rows must be a non-empty list.")

    screen = db.fetch_one(
        "SELECT id, capacity_total FROM screens WHERE id = %s", (screen_id,)
    )
    if screen is None:
        raise ApiError(404, "NOT_FOUND", "Screen not found.")

    planned: list[tuple] = []
    for spec in layout:
        if not isinstance(spec, dict):
            raise ApiError(400, "VALIDATION_ERROR", "Every row must be an object.")
        label = validators.required_text(spec, "row_label", label="row_label", max_length=4)
        count = validators.positive_int(spec.get("count"), "count")
        seat_type = validators.choice(
            spec.get("seat_type"), ("standard", "vip"), "seat_type", default="standard"
        )
        planned.extend((label, number, seat_type) for number in range(1, count + 1))

    existing = db.fetch_one(
        "SELECT COUNT(*) AS n FROM seats WHERE screen_id = %s", (screen_id,)
    )["n"]
    if existing + len(planned) > screen["capacity_total"]:
        raise ApiError(
            400,
            "CAPACITY_EXCEEDED",
            f"Screen capacity is {screen['capacity_total']} and "
            f"{existing + len(planned)} seats were requested.",
        )

    with db.transaction() as cur:
        cur.executemany(
            "INSERT INTO seats (screen_id, row_label, seat_number, seat_type) "
            "VALUES (%s, %s, %s, %s)",
            [(screen_id, label, number, seat_type) for label, number, seat_type in planned],
        )
        cur.execute(
            "SELECT id, row_label, seat_number, seat_type FROM seats "
            "WHERE screen_id = %s ORDER BY row_label, seat_number",
            (screen_id,),
        )
        seats = [dict(row) for row in cur.fetchall()]

    return jsonify({"screen_id": screen_id, "created": len(planned), "seats": seats}), 201


# ---------------------------------------------------------------------------
# Shows
# ---------------------------------------------------------------------------
@admin_bp.get("/shows")
def list_shows():
    day = validators.date_param(request.args.get("date"))
    rows = db.fetch_all(
        """
        SELECT v.show_id, m.title AS movie_title, v.theatre_name, v.screen_name,
               v.show_start_at, v.show_end_at, v.show_base_price,
               v.booked_count, v.held_count, v.available_count, v.total_count
        FROM vw_show_availability v
        JOIN movies m ON m.id = v.movie_id
        WHERE (%s::date IS NULL OR (v.show_start_at >= %s::date
                                    AND v.show_start_at < (%s::date + INTERVAL '1 day')))
        ORDER BY v.show_start_at, v.show_id
        """,
        (day, day, day),
    )
    return jsonify({"count": len(rows), "shows": rows})


@admin_bp.post("/shows")
def create_show():
    """Schedule a show and materialise its seat rows (fn_create_show)."""
    body = validators.json_body()
    show = db.fetch_one(
        "SELECT show_id, movie_id, screen_id, start_at, end_at, base_price, seat_count "
        "FROM fn_create_show(%s, %s, %s, %s, %s)",
        (
            validators.positive_int(body.get("movie_id"), "movie_id"),
            validators.positive_int(body.get("screen_id"), "screen_id"),
            validators.iso_datetime(body.get("start_at"), "start_at"),
            validators.iso_datetime(body.get("end_at"), "end_at"),
            validators.money(body.get("base_price"), "base_price"),
        ),
    )
    return jsonify({"show": show}), 201
