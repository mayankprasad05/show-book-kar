"""Request parsing shared by every route.

Validation lives here so routes read as "check the shape, call the database".
None of these functions touch the database, and every failure is an
``ApiError`` with the envelope from :mod:`backend.errors`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import request

from backend.errors import ApiError


def json_body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_BODY", "Send a JSON object body.")
    return body


def positive_int(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ApiError(400, "VALIDATION_ERROR", f"{field} must be a positive integer.")
    return value


def required_text(data: dict, field: str, *, label: str | None = None,
                  max_length: int = 200) -> str:
    label = label or field
    value = data.get(field)
    if not isinstance(value, str) or value.strip() == "":
        raise ApiError(400, "VALIDATION_ERROR", f"{label} is required.")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(
            400, "VALIDATION_ERROR", f"{label} must be at most {max_length} characters."
        )
    return value


def optional_text(data: dict, field: str, *, label: str | None = None,
                  max_length: int = 200) -> str | None:
    if field not in data or data[field] is None:
        return None
    return required_text(data, field, label=label, max_length=max_length)


def money(value, field: str) -> Decimal:
    """Accept a JSON number or a numeric string; reject booleans and negatives."""
    if isinstance(value, bool) or value is None:
        raise ApiError(400, "VALIDATION_ERROR", f"{field} must be a number.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ApiError(400, "VALIDATION_ERROR", f"{field} must be a number.") from None
    if not amount.is_finite() or amount < 0:
        raise ApiError(400, "VALIDATION_ERROR", f"{field} must be zero or more.")
    return amount.quantize(Decimal("0.01"))


def iso_datetime(value, field: str) -> datetime:
    """Parse an ISO-8601 timestamp that carries an offset."""
    if not isinstance(value, str) or value.strip() == "":
        raise ApiError(
            400, "VALIDATION_ERROR", f"{field} must be an ISO-8601 timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(
            400, "VALIDATION_ERROR",
            f"{field} must be an ISO-8601 timestamp such as 2026-12-02T10:00:00+05:30.",
        ) from None
    if parsed.tzinfo is None:
        raise ApiError(
            400, "VALIDATION_ERROR", f"{field} must include a UTC offset."
        )
    return parsed


def date_param(raw: str | None, field: str = "date") -> date | None:
    """``?from=YYYY-MM-DD`` style filter; empty or absent means "no bound"."""
    if raw is None or raw.strip() == "":
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(
            400, "INVALID_DATE", f"{field} must use the YYYY-MM-DD format."
        ) from None


def date_range() -> tuple[date | None, date | None]:
    """Read ``?from=&to=``, rejecting a reversed range."""
    start = date_param(request.args.get("from"), "from")
    end = date_param(request.args.get("to"), "to")
    if start and end and start > end:
        raise ApiError(400, "INVALID_DATE", "from must be on or before to.")
    return start, end


def choice(value, allowed: tuple[str, ...], field: str, *, default: str | None = None) -> str:
    if value is None and default is not None:
        return default
    if value not in allowed:
        options = ", ".join(repr(item) for item in allowed)
        raise ApiError(
            400, "VALIDATION_ERROR", f"{field} must be one of {options}."
        )
    return value
