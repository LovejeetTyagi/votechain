from functools import wraps
from flask import request, g
import jwt as pyjwt
from utils import decode_jwt, error


def _extract_token() -> str | None:
    """Pull Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return None


# ── @login_required ───────────────────────────────────────────────────────────

def login_required(f):
    """
    Protect a route: JWT must be present and valid.
    Sets g.user_id and g.role for downstream use.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return error("Missing authentication token", 401)
        try:
            payload   = decode_jwt(token)
            g.user_id = payload["sub"]
            g.role    = payload["role"]
        except pyjwt.ExpiredSignatureError:
            return error("Token has expired. Please log in again.", 401)
        except pyjwt.InvalidTokenError:
            return error("Invalid token.", 401)
        return f(*args, **kwargs)
    return decorated


# ── @admin_required ───────────────────────────────────────────────────────────

def admin_required(f):
    """
    Protect a route: JWT must be valid AND role must be 'admin'.
    Must be applied AFTER @login_required (or stacked on top).
    """
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.role != "admin":
            return error("Admin access required.", 403)
        return f(*args, **kwargs)
    return decorated


# ── @voter_required ───────────────────────────────────────────────────────────

def voter_required(f):
    """
    Protect a route: JWT must be valid AND role must be 'voter'.
    """
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.role not in ("voter", "admin"):
            return error("Voter access required.", 403)
        return f(*args, **kwargs)
    return decorated
