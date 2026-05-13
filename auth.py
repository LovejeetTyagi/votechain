from flask import Blueprint, request, g
from firebase_admin import firestore
from datetime import datetime, timezone
import os

from config import Collections
from models import User, OTPRecord
from utils import (
    generate_otp, hash_otp, verify_otp,
    otp_expiry_iso, is_otp_expired,
    send_otp_email, create_jwt,
    success, error,
)
from middleware import login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ADMIN_SECRET_CODE = os.getenv("ADMIN_SECRET_CODE", "")


def _db():
    return firestore.client()


# ── POST /api/auth/register/send-otp ─────────────────────────────────────────
@auth_bp.post("/register/send-otp")
def register_send_otp():
    """
    Step 1 of registration.
    Body: { name, email, role?, admin_code? }
    Public users always get role='voter'.
    role='admin' only allowed if correct ADMIN_SECRET_CODE is provided.
    """
    data  = request.get_json(silent=True) or {}
    name  = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    requested_role = (data.get("role") or "voter").strip()
    admin_code     = (data.get("admin_code") or "").strip()

    if not name:
        return error("Name is required.")
    if not email or "@" not in email:
        return error("A valid email is required.")

    # ── Role security gate ────────────────────────────────────────────────────
    if requested_role == "admin":
        if not ADMIN_SECRET_CODE or admin_code != ADMIN_SECRET_CODE:
            return error("Invalid admin code.", 403)
        role = "admin"
    else:
        role = "voter"   # everyone else is always a voter

    db = _db()

    # Check duplicate
    existing = db.collection(Collections.USERS).where(
        filter=firestore.FieldFilter("email", "==", email)
    ).limit(1).get()
    if existing:
        return error("An account with this email already exists.", 409)

    otp        = generate_otp()
    otp_record = OTPRecord(
        email      = email,
        otp_hash   = hash_otp(otp),
        expires_at = otp_expiry_iso(),
    )

    db.collection(Collections.OTPS).document(email).set({
        **otp_record.to_dict(),
        "pending_name": name,
        "pending_role": role,
    })
    
    send_otp_email(email, otp)
    return success(message="OTP sent. Check your inbox.")


# ── POST /api/auth/register/verify-otp ───────────────────────────────────────
@auth_bp.post("/register/verify-otp")
def register_verify_otp():
    """
    Step 2 of registration.
    Body: { email, otp }
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp") or "").strip()

    if not email or not otp:
        return error("Email and OTP are required.")

    db      = _db()
    otp_ref = db.collection(Collections.OTPS).document(email)
    otp_doc = otp_ref.get()

    if not otp_doc.exists:
        return error("No OTP found for this email. Request a new one.", 404)

    otp_data = otp_doc.to_dict()

    if otp_data.get("used"):
        return error("OTP already used. Request a new one.")
    if is_otp_expired(otp_data["expires_at"]):
        return error("OTP has expired. Request a new one.")
    if not verify_otp(otp, otp_data["otp_hash"]):
        return error("Invalid OTP.")

    otp_ref.update({"used": True})

    user = User(
        name  = otp_data.get("pending_name", "User"),
        email = email,
        role  = otp_data.get("pending_role", "voter"),
    )
    db.collection(Collections.USERS).document(user.id).set(user.to_dict())

    token = create_jwt(user.id, user.role)
    return success(
        data    = {"token": token, "user": user.public_dict()},
        message = "Registration successful.",
        status  = 201,
    )


# ── POST /api/auth/login/send-otp ────────────────────────────────────────────
@auth_bp.post("/login/send-otp")
def login_send_otp():
    """
    Step 1 of login.
    Body: { email }
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return error("A valid email is required.")

    db     = _db()
    user_q = db.collection(Collections.USERS).where(
        filter=firestore.FieldFilter("email", "==", email)
    ).limit(1).get()

    if not user_q:
        return error("No account found with this email.", 404)

    otp        = generate_otp()
    otp_record = OTPRecord(
        email      = email,
        otp_hash   = hash_otp(otp),
        expires_at = otp_expiry_iso(),
    )
    db.collection(Collections.OTPS).document(email).set(otp_record.to_dict())

    send_otp_email(email, otp)
    return success(message="OTP sent. Check your inbox.")


# ── POST /api/auth/login/verify-otp ──────────────────────────────────────────
@auth_bp.post("/login/verify-otp")
def login_verify_otp():
    """
    Step 2 of login.
    Body: { email, otp }
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp") or "").strip()

    if not email or not otp:
        return error("Email and OTP are required.")

    db      = _db()
    otp_ref = db.collection(Collections.OTPS).document(email)
    otp_doc = otp_ref.get()

    if not otp_doc.exists:
        return error("No OTP found. Request a new one.", 404)

    otp_data = otp_doc.to_dict()

    if otp_data.get("used"):
        return error("OTP already used.")
    if is_otp_expired(otp_data["expires_at"]):
        return error("OTP expired. Request a new one.")
    if not verify_otp(otp, otp_data["otp_hash"]):
        return error("Invalid OTP.")

    otp_ref.update({"used": True})

    user_docs = db.collection(Collections.USERS).where(
        filter=firestore.FieldFilter("email", "==", email)
    ).limit(1).get()
    user_data = user_docs[0].to_dict()
    user      = User.from_dict(user_data)

    token = create_jwt(user.id, user.role)
    return success(
        data    = {"token": token, "user": user.public_dict()},
        message = "Login successful.",
    )


# ── GET /api/auth/me ──────────────────────────────────────────────────────────
@auth_bp.get("/me")
@login_required
def me():
    """Return the currently authenticated user's profile."""
    db       = _db()
    user_doc = db.collection(Collections.USERS).document(g.user_id).get()
    if not user_doc.exists:
        return error("User not found.", 404)
    return success(data={"user": user_doc.to_dict()})

print("ADMIN_SECRET_CODE =", ADMIN_SECRET_CODE)
