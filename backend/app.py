"""Application factory for Show-book-kar.

Run it locally with::

    .venv/Scripts/python -m flask --app backend.app run --port 5000

The factory stays free of business rules: routes validate and delegate, the
database owns the rules, and :mod:`backend.errors` owns every failure shape.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal

from flask import Flask
from flask_cors import CORS

from backend import db  # noqa: F401 - imported for its load_dotenv() side effect
from backend.errors import register_error_handlers
from backend.routes import (
    admin_bp,
    auth_bp,
    bookings_bp,
    catalog_bp,
    health_bp,
    reports_bp,
)


def _json_default(value):
    """JSON types the database produces that json does not know natively."""
    if isinstance(value, Decimal):
        # Money is a string in the API: NUMERIC(10,2) -> "138.29", no float drift.
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        HOLD_DURATION_MINUTES=int(os.getenv("HOLD_DURATION_MINUTES", "5")),
        CANCELLATION_CUTOFF_HOURS=int(os.getenv("CANCELLATION_CUTOFF_HOURS", "2")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)

    app.json.default = _json_default
    app.json.sort_keys = False

    # The frontend runs on its own dev origin and sends the session cookie.
    CORS(
        app,
        supports_credentials=True,
        resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "*")}},
    )

    register_error_handlers(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    return app


app = create_app()
