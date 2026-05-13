import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# ── App config ──────────────────────────────────────────────────────────────
class Config:
    SECRET_KEY         = os.getenv("SECRET_KEY", "dev-secret-change-me")
    RESEND_API_KEY     = os.getenv("RESEND_API_KEY", "")
    EMAIL_FROM         = os.getenv("EMAIL_FROM", "noreply@example.com")
    OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))
    JWT_EXPIRY_HOURS   = int(os.getenv("JWT_EXPIRY_HOURS", 24))
    FIREBASE_CRED_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")


# ── Firebase init (singleton) ────────────────────────────────────────────────
def init_firebase():
    """Initialise Firebase Admin SDK (call once at startup)."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(Config.FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()


# ── Firestore collections ────────────────────────────────────────────────────
class Collections:
    USERS  = "users"
    POLLS  = "polls"
    VOTES  = "votes"
    OTPS   = "otps"
