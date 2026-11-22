"""Session auth: bcrypt hashing, the signed-in user, and the route guards.

The browser never tells us who it is. Identity comes from Flask's signed session
cookie, which only ever stores ``user_id`` and ``role``; every request re-reads
the user row so a deleted or demoted account loses access immediately.

Passwords are bcrypt digests (``users.password_hash``), never plaintext, and are
never returned by any endpoint.
"""

from __future__ import annotations

import functools
import re

import bcrypt
from flask import g, session

from backend import db
from backend.errors import ApiError

BCRYPT_ROUNDS = 10
MIN_PASSWORD_LENGTH = 8
# bcrypt only reads the first 72 bytes of a password; reject longer input
# instead of silently truncating it.
MAX_PASSWORD_BYTES = 72

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PUBLIC_USER_COLUMNS = "id, email, name, role, created_at"


# ---------------------------------------------------------------------------
# Password handling
# ---------------------------------------------------------------------------
def _password_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:MAX_PASSWORD_BYTES]


def hash_password(plain: str) -> str:
    """Return a bcrypt digest for ``plain``."""
    return bcrypt.hashpw(
        _password_bytes(plain), bcrypt.gensalt(rounds=BCRYPT_ROUNDS, prefix=b"2b")
    ).decode("utf-8")


def verify_password(plain: str, stored_hash: str) -> bool:
    """Constant-time check; a malformed stored hash is a failed login, not a 500."""
    if not plain or not stored_hash:
        return False
    try:
        return bcrypt.checkpw(_password_bytes(plain), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
def login_user(user: dict) -> None:
    """Start a fresh session for ``user`` (clears any previous one)."""
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]


def logout_user() -> None:
    session.clear()


def find_user_by_email(email: str):
    return db.fetch_one(
        f"SELECT {PUBLIC_USER_COLUMNS}, password_hash FROM users WHERE email = %s",
        (email,),
    )


def find_user_by_id(user_id: int):
    return db.fetch_one(
        f"SELECT {PUBLIC_USER_COLUMNS} FROM users WHERE id = %s", (user_id,)
    )


def current_user():
    """The signed-in user for this request, or ``None``. Cached on ``g``."""
    if "_current_user" in g:
        return g._current_user

    user = None
    if session.get("user_id") is not None:
        user = find_user_by_id(session["user_id"])
        if user is None:
            # The account disappeared under a live cookie.
            session.clear()

    g._current_user = user
    return user


def require_user() -> dict:
    user = current_user()
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Sign in to continue.")
    return user


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        require_user()
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        user = require_user()
        if user["role"] != "admin":
            raise ApiError(403, "FORBIDDEN", "Administrator access is required.")
        return view(*args, **kwargs)

    return wrapper
