"""Blueprint registrations."""

from backend.routes.admin import admin_bp
from backend.routes.auth import auth_bp
from backend.routes.bookings import bookings_bp
from backend.routes.catalog import catalog_bp
from backend.routes.health import health_bp
from backend.routes.reports import reports_bp

__all__ = [
    "admin_bp",
    "auth_bp",
    "bookings_bp",
    "catalog_bp",
    "health_bp",
    "reports_bp",
]
