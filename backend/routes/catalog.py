"""Public catalogue reads: movies, their shows, and a show's seat map.

Statements are the parameterised queries from ``database/queries.sql``, copied
with ``%s`` placeholders instead of ``$1``/``$2``. The only additions are the
movie columns on the show lookup (the show page needs its title) and the
availability counts on the show payload.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend import db, validators
from backend.errors import ApiError

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api")

# database/queries.sql #1
LIST_MOVIES = """
    SELECT id, title, language, duration_minutes, created_at
    FROM movies
    ORDER BY id
"""

# database/queries.sql #2
MOVIE_BY_ID = """
    SELECT id, title, language, duration_minutes, created_at
    FROM movies
    WHERE id = %s
"""

# database/queries.sql #3 - $2 is a calendar date, matched as a half-open day.
SHOWS_FOR_MOVIE = """
    SELECT s.id, s.start_at, s.end_at, s.base_price,
           sc.id AS screen_id, sc.name AS screen_name,
           th.id AS theatre_id, th.name AS theatre_name, th.city
    FROM shows s
    JOIN screens sc ON sc.id = s.screen_id
    JOIN theatres th ON th.id = sc.theatre_id
    WHERE s.movie_id = %s
      AND (%s::date IS NULL OR (s.start_at >= %s::date
                                AND s.start_at < (%s::date + INTERVAL '1 day')))
    ORDER BY s.start_at
"""

# database/queries.sql #4 plus the movie it belongs to.
SHOW_BY_ID = """
    SELECT s.id            AS show_id,
           s.movie_id      AS movie_id,
           m.title         AS movie_title,
           s.start_at      AS show_start_at,
           s.end_at        AS show_end_at,
           s.base_price    AS show_base_price,
           sc.id           AS screen_id,
           sc.name         AS screen_name,
           th.id           AS theatre_id,
           th.name         AS theatre_name,
           th.city         AS theatre_city
    FROM shows s
    JOIN movies m   ON m.id = s.movie_id
    JOIN screens sc ON sc.id = s.screen_id
    JOIN theatres th ON th.id = sc.theatre_id
    WHERE s.id = %s
"""

# database/queries.sql #5
SEATS_FOR_SHOW = """
    SELECT ss.show_id    AS show_id,
           ss.seat_id    AS seat_id,
           ss.status     AS status,
           ss.price      AS price,
           s.row_label   AS row_label,
           s.seat_number AS seat_number,
           s.seat_type   AS seat_type
    FROM show_seats ss
    JOIN seats s ON s.id = ss.seat_id
    WHERE ss.show_id = %s
    ORDER BY s.row_label, s.seat_number
"""

# database/queries.sql #7
SEAT_COUNTS = """
    SELECT COUNT(*) FILTER (WHERE ss.status = 'AVAILABLE') AS available_count,
           COUNT(*) FILTER (WHERE ss.status = 'HELD')      AS held_count,
           COUNT(*) FILTER (WHERE ss.status = 'BOOKED')    AS booked_count,
           COUNT(*)                                        AS total_count
    FROM show_seats ss
    WHERE ss.show_id = %s
"""


def _require_show(show_id: int) -> dict:
    show = db.fetch_one(SHOW_BY_ID, (show_id,))
    if show is None:
        raise ApiError(404, "NOT_FOUND", "Show not found.")
    return show


@catalog_bp.get("/movies")
def list_movies():
    """Every movie in the catalogue, ordered by id."""
    movies = db.fetch_all(LIST_MOVIES)
    return jsonify({"count": len(movies), "movies": movies})


@catalog_bp.get("/movies/<int:movie_id>")
def movie_detail(movie_id: int):
    """One movie plus its shows, optionally limited to one calendar date."""
    movie = db.fetch_one(MOVIE_BY_ID, (movie_id,))
    if movie is None:
        raise ApiError(404, "NOT_FOUND", "Movie not found.")

    day = validators.date_param(request.args.get("date"), "The date filter")
    shows = db.fetch_all(SHOWS_FOR_MOVIE, (movie_id, day, day, day))
    return jsonify({"movie": movie, "date": day.isoformat() if day else None, "shows": shows})


@catalog_bp.get("/shows/<int:show_id>")
def show_detail(show_id: int):
    """One show's schedule, venue and seat counters."""
    show = _require_show(show_id)
    counts = db.fetch_one(SEAT_COUNTS, (show_id,))
    return jsonify({"show": show, "counts": counts})


@catalog_bp.get("/shows/<int:show_id>/seats")
def show_seats(show_id: int):
    """The show's full seat map: every seat with its status and price."""
    _require_show(show_id)
    seats = db.fetch_all(SEATS_FOR_SHOW, (show_id,))
    counts = db.fetch_one(SEAT_COUNTS, (show_id,))
    return jsonify({"show_id": show_id, "counts": counts, "seats": seats})
