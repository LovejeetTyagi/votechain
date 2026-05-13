import os
import random
import string
import smtplib
import bcrypt
import jwt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from config import Config

load_dotenv()   # ← loads .env file so os.getenv() works


# ── OTP ──────────────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Return a random numeric OTP string."""
    return "".join(random.choices(string.digits, k=length))


def hash_otp(otp: str) -> str:
    """Bcrypt-hash an OTP for safe Firestore storage."""
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()


def verify_otp(plain: str, hashed: str) -> bool:
    """Verify a plain OTP against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def otp_expiry_iso() -> str:
    """Return an ISO timestamp N seconds from now (UTC)."""
    expires = datetime.now(timezone.utc) + timedelta(seconds=Config.OTP_EXPIRY_SECONDS)
    return expires.isoformat()


def is_otp_expired(expires_at_iso: str) -> bool:
    """Return True if the OTP expiry timestamp has passed."""
    expires = datetime.fromisoformat(expires_at_iso)
    return datetime.now(timezone.utc) > expires


# ── Email (Gmail SMTP) ────────────────────────────────────────────────────────

def send_otp_email(to_email: str, otp: str) -> bool:
    """
    Send OTP email via Gmail SMTP.
    Requires GMAIL_USER and GMAIL_APP_PASSWORD in .env
    Get App Password from:
      myaccount.google.com → Security → 2-Step Verification → App Passwords
    """
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")

    # Dev fallback — prints OTP to terminal if credentials not set
    if not gmail_user or not gmail_pass:
        print(f"[DEV] OTP for {to_email}: {otp}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your VoteChain OTP"
        msg["From"]    = gmail_user
        msg["To"]      = to_email

        html_body = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;
                    background:#0a0e1a;color:#f0f4ff;border-radius:12px;">
          <h2 style="color:#4f8ef7;margin-bottom:0.5rem">🗳️ VoteChain</h2>
          <p style="color:#8899bb;margin-bottom:1.5rem">
            Use the code below to verify your identity. It expires in
            {Config.OTP_EXPIRY_SECONDS // 60} minutes.
          </p>
          <div style="background:#141c2e;border:1px solid rgba(99,153,255,.3);
                      border-radius:10px;padding:1.5rem;text-align:center;
                      letter-spacing:10px;font-size:2.2rem;font-weight:700;
                      color:#f0f4ff;">
            {otp}
          </div>
          <p style="color:#4a5a7a;font-size:12px;margin-top:1.5rem;">
            If you didn't request this, you can safely ignore this email.
            Do not share this code with anyone.
          </p>
        </div>
        """

        text_body = f"Your VoteChain OTP is: {otp}\nValid for {Config.OTP_EXPIRY_SECONDS // 60} minutes."

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())

        print(f"[EMAIL] OTP sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[EMAIL ERROR] Gmail authentication failed. Check GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False
    except smtplib.SMTPRecipientsRefused:
        print(f"[EMAIL ERROR] Recipient refused: {to_email}")
        return False
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_jwt(user_id: str, role: str) -> str:
    """Mint a signed JWT containing user_id and role."""
    payload = {
        "sub":  user_id,
        "role": role,
        "iat":  datetime.now(timezone.utc),
        "exp":  datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    """
    Decode and verify a JWT.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])


# ── Response helpers ──────────────────────────────────────────────────────────

def success(data: dict = None, message: str = "OK", status: int = 200):
    """Standard success response helper."""
    resp = {"success": True, "message": message}
    if data is not None:
        resp["data"] = data
    return resp, status


def error(message: str, status: int = 400):
    """Standard error response helper."""
    return {"success": False, "message": message}, status

