"""
auth.py — JWT authentication helpers
=====================================
Provides:
  - generate_token(user)   → signed JWT string
  - decode_token(token)    → payload dict or None
  - require_auth           → route decorator; injects `g.current_user`
  - require_role(*roles)   → route decorator; checks role after require_auth

Token lifecycle
---------------
Tokens are issued as httpOnly, SameSite=Lax cookies named 'aegis_token'.
The cookie is set on POST /api/login and cleared on POST /api/logout.
Every protected endpoint reads the cookie server-side — the frontend
never needs to read or attach the token manually.

JWT payload schema
------------------
{
    "sub":   <int user_id>,
    "email": <str>,
    "role":  "senior" | "caregiver",
    "exp":   <unix timestamp — 8 hours from issue>
}
"""

import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, jsonify, g

# ── Configuration ─────────────────────────────────────────────────────────────

# Read from environment; hard-coded fallback only for local dev.
# In production, always set JWT_SECRET_KEY as an env var.
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "aegis-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME_HOURS = 8
COOKIE_NAME = "aegis_token"


# ── Token generation & decoding ───────────────────────────────────────────────

def generate_token(user: dict) -> str:
    """
    Create a signed JWT for the given user dict.
    user must contain: user_id, email, role.
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub":   str(user["user_id"]),   # PyJWT 2.13+ requires sub to be a string
        "email": user.get("email"),
        "role":  user["role"],
        "iat":   now,
        "exp":   now + timedelta(hours=TOKEN_LIFETIME_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """
    Decode and validate a JWT.  Returns the payload dict on success,
    None if the token is missing, malformed, or expired.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _extract_token() -> str | None:
    """Pull the JWT from the httpOnly cookie."""
    return request.cookies.get(COOKIE_NAME)


# ── Decorators ────────────────────────────────────────────────────────────────

def require_auth(f):
    """
    Route decorator that requires a valid JWT cookie.

    On success: sets g.current_user = {user_id, email, role} and calls f().
    On failure: returns 401 JSON.

    Usage:
        @app.route("/api/something")
        @require_auth
        def something():
            user_id = g.current_user["user_id"]
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required"}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired session — please log in again"}), 401

        g.current_user = {
            "user_id": int(payload["sub"]),  # sub is stored as str; cast back to int
            "email":   payload.get("email"),
            "role":    payload["role"],
        }
        return f(*args, **kwargs)
    return decorated


def require_role(*allowed_roles):
    """
    Route decorator that requires the authenticated user to have one of
    the specified roles.  Must be stacked AFTER @require_auth.

    Usage:
        @app.route("/api/resolve/<int:tx_id>", methods=["POST"])
        @require_auth
        @require_role("caregiver")
        def resolve(tx_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "Authentication required"}), 401
            if user["role"] not in allowed_roles:
                return jsonify({"error": "Access denied — wrong role for this endpoint"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# Read from env — production needs Secure=True, SameSite=None for cross-domain cookies
_COOKIE_SECURE   = os.getenv("COOKIE_SECURE",   "false").strip().lower() == "true"
_COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax").strip()


def set_auth_cookie(response, token: str):
    """Attach the JWT as an httpOnly cookie.
    Local:      Secure=False, SameSite=Lax  (same-origin).
    Production: set COOKIE_SECURE=true, COOKIE_SAMESITE=None via Render env vars.
    """
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_COOKIE_SECURE,
        max_age=TOKEN_LIFETIME_HOURS * 3600,
        path="/",
    )
    return response


def clear_auth_cookie(response):
    """Expire the auth cookie (used on logout)."""
    response.set_cookie(
        COOKIE_NAME,
        "",
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_COOKIE_SECURE,
        max_age=0,
        path="/",
    )
    return response
