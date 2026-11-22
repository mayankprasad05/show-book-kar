"""Liveness and readiness.

``GET /api/health`` is the one route that must work even when everything else is
broken, so it is kept free of session, auth and business logic.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from backend import db

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    try:
        info = db.check_connection()
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
        current_app.logger.warning("health check failed: %s", exc)
        return (
            jsonify(
                {
                    "status": "error",
                    "database": "unavailable",
                    "message": "The service cannot reach PostgreSQL.",
                }
            ),
            503,
        )

    return jsonify(
        {
            "status": "ok",
            "database": "ok",
            "database_name": info["database_name"],
            "server_version": info["server_version"],
            "server_time": info["server_time"],
            "schema_loaded": info["schema_loaded"],
        }
    )
