"""One error shape for the whole API.

Every failure leaves the service as ``{"error": "CODE", "message": "..."}`` with
the HTTP status from the mapping table in ``backend/README.md``. Database
signals are translated here and nowhere else, so routes never need to inspect
SQLSTATEs.
"""

from __future__ import annotations

from flask import Flask, jsonify
from psycopg2 import Error as PsycopgError
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """An error the route raised on purpose."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str):
    return jsonify({"error": code, "message": message}), status


# Raised by database/functions.sql as RAISE EXCEPTION ... USING MESSAGE.
_DB_SIGNALS = {
    "SEAT_UNAVAILABLE": (409, "SEAT_UNAVAILABLE",
                        "One or more of the selected seats are no longer available."),
    "INVALID_SEATS": (400, "INVALID_SEATS",
                      "The seat selection is empty or contains seats that do not belong to this show."),
    "SHOW_NOT_FOUND": (404, "NOT_FOUND", "Show not found."),
    "HOLD_EXPIRED": (409, "HOLD_EXPIRED",
                     "The seat hold has expired. Please choose seats again."),
    "INVALID_STATE": (409, "INVALID_STATE",
                      "This booking cannot move to the requested state."),
    "CANCELLATION_NOT_ALLOWED": (409, "CANCELLATION_NOT_ALLOWED",
                                 "Bookings can only be cancelled up to the configured hours before the show."),
    "FORBIDDEN": (403, "FORBIDDEN", "You do not have access to this booking."),
    "BOOKING_NOT_FOUND": (404, "NOT_FOUND", "Booking not found."),
    "MOVIE_NOT_FOUND": (404, "NOT_FOUND", "Movie not found."),
    "SCREEN_NOT_FOUND": (404, "NOT_FOUND", "Screen not found."),
    "SHOW_STARTED": (409, "SHOW_STARTED",
                     "That show has already started, so seats can no longer be held."),
    "SHOW_OVERLAP": (409, "SHOW_OVERLAP",
                     "Another show already occupies that screen during this time."),
    "INVALID_TIME_RANGE": (400, "VALIDATION_ERROR",
                           "The show must start in the future and end after it starts."),
    "INVALID_PRICE": (400, "VALIDATION_ERROR", "The base price must be zero or more."),
    "INVALID_SIMULATION": (400, "VALIDATION_ERROR",
                           "simulate must be 'success' or 'failure'."),
    "SCREEN_HAS_NO_SEATS": (400, "VALIDATION_ERROR",
                            "That screen has no seats yet, so no show can be scheduled on it."),
}

# Plain SQLSTATEs, for constraint failures the routes may still provoke.
_SQLSTATES = {
    "23505": (409, "CONFLICT", "That value is already taken."),
    "23503": (400, "INVALID_REFERENCE", "A referenced record does not exist."),
    "23502": (400, "VALIDATION_ERROR", "A required field is missing."),
    "23514": (400, "VALIDATION_ERROR", "The request violates a database constraint."),
    "23P01": (409, "CONFLICT", "That time slot overlaps an existing record."),
    "22P02": (400, "VALIDATION_ERROR", "A value has the wrong type or format."),
}

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    503: "SERVICE_UNAVAILABLE",
}


def _primary_message(exc: PsycopgError) -> str:
    try:
        return (exc.diag.message_primary or "").strip()
    except AttributeError:  # connection-level failures have no diag
        return ""


def map_database_error(exc: PsycopgError) -> tuple[int, str, str]:
    """Translate a psycopg2 failure into ``(status, code, message)``."""
    signal = _primary_message(exc)
    if signal in _DB_SIGNALS:
        return _DB_SIGNALS[signal]

    sqlstate = getattr(exc, "pgcode", None)
    if sqlstate in _SQLSTATES:
        return _SQLSTATES[sqlstate]

    if sqlstate == "P0001" and signal:
        # A RAISE from the database whose signal text is not in the table yet.
        return 409, "CONFLICT", signal

    return 500, "INTERNAL_ERROR", "An unexpected database error occurred."


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        return error_response(exc.status, exc.code, exc.message)

    @app.errorhandler(PsycopgError)
    def _handle_database_error(exc: PsycopgError):
        status, code, message = map_database_error(exc)
        if status >= 500:
            app.logger.exception("database error: sqlstate=%s", getattr(exc, "pgcode", "?"))
        else:
            app.logger.info(
                "database rejected request: sqlstate=%s signal=%s",
                getattr(exc, "pgcode", "?"),
                _primary_message(exc),
            )
        return error_response(status, code, message)

    @app.errorhandler(HTTPException)
    def _handle_http_error(exc: HTTPException):
        code = _HTTP_CODES.get(exc.code or 500, "HTTP_ERROR")
        return error_response(exc.code or 500, code, exc.description or code)

    @app.errorhandler(Exception)
    def _handle_unexpected_error(exc: Exception):
        # Never echo SQL, DSNs, credentials or tracebacks to the client.
        app.logger.exception("unhandled error")
        return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
