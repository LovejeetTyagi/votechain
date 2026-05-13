"""
Run this to test Gmail SMTP independently of Flask:
    python test_email.py
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")
TEST_SEND_TO = GMAIL_USER  # sends to yourself

print(f"GMAIL_USER        : {GMAIL_USER}")
print(f"GMAIL_APP_PASSWORD: {'*' * len(GMAIL_PASS) if GMAIL_PASS else 'NOT SET'}")
print(f"Password length   : {len(GMAIL_PASS) if GMAIL_PASS else 0} chars (should be 16)")
print()

if not GMAIL_USER or not GMAIL_PASS:
    print("❌ GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
    exit(1)

print(f"Sending test email to {TEST_SEND_TO} ...")

try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "VoteChain — SMTP Test"
    msg["From"]    = GMAIL_USER
    msg["To"]      = TEST_SEND_TO

    msg.attach(MIMEText("This is a test email from VoteChain SMTP setup.", "plain"))
    msg.attach(MIMEText("<h2>✅ VoteChain SMTP is working!</h2>", "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        print("Connecting to smtp.gmail.com:465 ...")
        server.login(GMAIL_USER, GMAIL_PASS)
        print("Login successful ✅")
        server.sendmail(GMAIL_USER, TEST_SEND_TO, msg.as_string())
        print(f"Email sent to {TEST_SEND_TO} ✅")
        print("Check your inbox (and spam folder)!")

except smtplib.SMTPAuthenticationError as e:
    print(f"❌ Authentication failed: {e}")
    print()
    print("Possible fixes:")
    print("  1. Make sure 2-Step Verification is ON at myaccount.google.com/security")
    print("  2. Generate App Password at myaccount.google.com/apppasswords")
    print("  3. Remove spaces from GMAIL_APP_PASSWORD in .env")
    print("  4. Make sure you're using App Password NOT your Gmail login password")

except smtplib.SMTPConnectError as e:
    print(f"❌ Could not connect to Gmail SMTP: {e}")
    print("Check your internet connection or firewall.")

except Exception as e:
    print(f"❌ Unexpected error: {e}")
