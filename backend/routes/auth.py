"""Registration, sign-in, sign-out and "who am I".

The session cookie is the only source of identity for the rest of the API.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend import auth, db
from backend.errors import ApiError

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Deliberately identical for "unknown email" and "wrong password" so the
# endpoint does not confirm which addresses exist.
_INVALID_CREDENTIALS = "Email or password is incorrect."


def _json_body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_BODY", "Send a JSON object body.")
    return body


def _required_text(body: dict, key: str, *, label: str, max_length: int = 200) -> str:
    value = body.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise ApiError(400, "VALIDATION_ERROR", f"{label} is required.")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(
            400, "VALIDATION_ERROR", f"{label} must be at most {max_length} characters."
        )
    return value


@auth_bp.post("/register")
def register():
    body = _json_body()

    name = _required_text(body, "name", label="Name")
    email = _required_text(body, "email", label="Email").lower()
    password = body.get("password")

    if not auth.EMAIL_PATTERN.match(email):
        raise ApiError(400, "VALIDATION_ERROR", "Email is not a valid address.")
    if not isinstance(password, str) or password == "":
        raise ApiError(400, "VALIDATION_ERROR", "Password is required.")
    if len(password) < auth.MIN_PASSWORD_LENGTH:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            f"Password must be at least {auth.MIN_PASSWORD_LENGTH} characters.",
        )
    if len(password.encode("utf-8")) > auth.MAX_PASSWORD_BYTES:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            f"Password must be at most {auth.MAX_PASSWORD_BYTES} bytes.",
        )

    if auth.find_user_by_email(email) is not None:
        raise ApiError(409, "EMAIL_TAKEN", "That email is already registered.")

    # Registration always creates a customer; the role column is never taken
    # from the request body.
    user = db.fetch_one(
        """
        INSERT INTO users (email, password_hash, name, role)
        VALUES (%s, %s, %s, 'customer')
        RETURNING id, email, name, role, created_at
        """,
        (email, auth.hash_password(password), name),
    )

    auth.login_user(user)
    return jsonify({"user": user}), 201


@auth_bp.post("/login")
def login():
    body = _json_body()
    email = body.get("email")
    password = body.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        raise ApiError(400, "VALIDATION_ERROR", "Email and password are required.")

    user = auth.find_user_by_email(email.strip().lower())
    if user is None or not auth.verify_password(password, user["password_hash"]):
        raise ApiError(401, "INVALID_CREDENTIALS", _INVALID_CREDENTIALS)

    auth.login_user(user)
    user.pop("password_hash", None)
    return jsonify({"user": user})


@auth_bp.post("/logout")
def logout():
    auth.logout_user()
    return jsonify({"status": "signed_out"})


@auth_bp.get("/me")
def me():
    return jsonify({"user": auth.require_user()})
