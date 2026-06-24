"""
Subconscious Mirror — User Account Module v2
简化版：每个需要认证的函数自己解析 JWT，不依赖 decorator kwargs
"""

import os
import re
import time
import uuid
import secrets
import sqlite3
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from functools import wraps

import bcrypt
import jwt
from flask import request, jsonify, make_response

# ── Config ───────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SITE_URL = os.environ.get("BASE_URL", "https://mirror.api-tokenmaster.com")
DB_FILE = os.environ.get("DB_FILE", "mirror_data.db")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

PLAN_CONFIG = {
    "spark":  {"price": 4.99,  "total_count": 1,  "expires_days": None,  "label": "The Spark"},
    "seeker": {"price": 12.99, "total_count": 5,  "expires_days": None,  "label": "The Seeker"},
    "oracle": {"price": 29.99, "total_count": -1, "expires_days": 30,    "label": "The Oracle"},
}

# NOWPayments (crypto)
NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY", "")
NOWPAYMENTS_IPN_SECRET = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
NOWPAYMENTS_API_BASE = "https://api.nowpayments.io/v1"


# ── Database ─────────────────────────────────────────────
def init_account_tables():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, email_verified INTEGER DEFAULT 0,
            failed_attempts INTEGER DEFAULT 0, locked_until TEXT,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS email_tokens (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
            purpose TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS entitlements (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, plan_type TEXT NOT NULL,
            total_count INTEGER NOT NULL, used_count INTEGER DEFAULT 0,
            expires_at TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS user_orders (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, paypal_order_id TEXT,
            amount REAL NOT NULL, currency TEXT DEFAULT 'USD', plan_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending', created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS license_keys (
            id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, plan_type TEXT NOT NULL,
            is_used INTEGER DEFAULT 0, used_by_user_id TEXT, used_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS crypto_payments (
            id TEXT PRIMARY KEY, user_id TEXT, paypal_email TEXT,
            plan_type TEXT NOT NULL, amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD', crypto_currency TEXT,
            crypto_amount REAL, nowpayments_id TEXT,
            pay_address TEXT, status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_email_tokens_token ON email_tokens(token);
        CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_orders_user ON user_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_license_keys_key ON license_keys(key);
    """)
    conn.commit()
    conn.close()


def get_db_conn():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ── Auth Helpers ─────────────────────────────────────────
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_jwt(user_id, email="", email_verified=False):
    return jwt.encode({
        "sub": user_id, "email": email, "ev": int(bool(email_verified)),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

def get_user_from_token():
    """Extract user info from JWT in Authorization header. Returns dict or raises."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing Authorization header")
    payload = decode_jwt(auth_header[7:])
    return {
        "id": payload["sub"],
        "email": payload.get("email", ""),
        "email_verified": bool(payload.get("ev", 0)),
    }

def send_email(to, subject, body):
    if not SMTP_HOST or not SMTP_USER:
        print(f"[EMAIL] To: {to} | Subject: {subject}")
        return True
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject; msg["From"] = SMTP_USER; msg["To"] = to
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls(); s.login(SMTP_USER, SMTP_PASS); s.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}"); return False

def cors_response(data, status=200):
    resp = make_response(jsonify(data), status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

def handle_options():
    return cors_response({"status": "ok"})

def activate_entitlement(conn, user_id, plan_type):
    config = PLAN_CONFIG.get(plan_type)
    if not config: return
    total_count = config["total_count"]
    expires_at = None
    if config["expires_days"]:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=config["expires_days"])).isoformat()
    conn.execute(
        "INSERT INTO entitlements (id, user_id, plan_type, total_count, expires_at) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), user_id, plan_type, total_count, expires_at))


# ═══ AUTH ROUTES ═════════════════════════════════════════

def auth_register():
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    if len(password) < 8: return cors_response({"detail": "Password must be at least 8 characters"}, 400)
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email): return cors_response({"detail": "Invalid email format"}, 400)

    conn = get_db_conn()
    if conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        conn.close(); return cors_response({"detail": "This email is already registered."}, 409)

    user_id = str(uuid.uuid4())
    conn.execute("INSERT INTO users (id, email, password_hash) VALUES (?,?,?)", (user_id, email, hash_password(password)))
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    conn.execute("INSERT INTO email_tokens (id, user_id, token, purpose, expires_at) VALUES (?,?,?,?,?)",
                 (str(uuid.uuid4()), user_id, token, "verify_email", expires))
    conn.commit(); conn.close()

    verify_link = f"{SITE_URL}/verify-email?token={token}"
    send_email(email, "Verify your email - Subconscious Mirror",
               f"<p>Click to verify: <a href='{verify_link}'>{verify_link}</a></p>")
    return cors_response({"message": "Registration successful. Please check your email to verify your account."})


def auth_verify_email():
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json(); token = data.get("token", "")
    conn = get_db_conn()
    row = conn.execute("SELECT id, user_id, used, expires_at FROM email_tokens WHERE token=? AND purpose='verify_email'", (token,)).fetchone()
    if not row: conn.close(); return cors_response({"detail": "Invalid token"}, 400)
    if row["used"]: conn.close(); return cors_response({"detail": "Token already used"}, 400)
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc): conn.close(); return cors_response({"detail": "Token expired"}, 400)
    conn.execute("UPDATE email_tokens SET used=1 WHERE id=?", (row["id"],))
    conn.execute("UPDATE users SET email_verified=1 WHERE id=?", (row["user_id"],))
    conn.commit(); conn.close()
    return cors_response({"message": "Email verified successfully"})


def auth_login():
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    conn = get_db_conn()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user: conn.close(); return cors_response({"detail": "Invalid email or password"}, 401)

    if user["locked_until"]:
        locked_until = datetime.fromisoformat(user["locked_until"])
        if locked_until > datetime.now(timezone.utc):
            conn.close()
            return cors_response({"detail": f"Account locked. Try again in {int((locked_until - datetime.now(timezone.utc)).total_seconds()/60)} minutes."}, 423)

    if not verify_password(password, user["password_hash"]):
        failed = user["failed_attempts"] + 1
        if failed >= MAX_LOGIN_ATTEMPTS:
            conn.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                         (failed, (datetime.now(timezone.utc)+timedelta(minutes=LOCKOUT_MINUTES)).isoformat(), user["id"]))
        else:
            conn.execute("UPDATE users SET failed_attempts=? WHERE id=?", (failed, user["id"]))
        conn.commit(); conn.close()
        return cors_response({"detail": "Invalid email or password"}, 401)

    conn.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (user["id"],))
    conn.commit()
    token = create_jwt(user["id"], user["email"], user["email_verified"])
    conn.close()
    return cors_response({"token": token, "user": {"id": user["id"], "email": user["email"], "email_verified": bool(user["email_verified"])}})


def auth_forgot_password():
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    conn = get_db_conn()
    user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if user:
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO email_tokens (id, user_id, token, purpose, expires_at) VALUES (?,?,?,?,?)",
                     (str(uuid.uuid4()), user["id"], token, "reset_password", (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
        conn.commit()
        reset_link = f"{SITE_URL}/reset-password?token={token}"
        send_email(email, "Reset password - Subconscious Mirror", f"<p><a href='{reset_link}'>{reset_link}</a></p>")
    conn.close()
    return cors_response({"message": "If the email exists, a reset link has been sent."})


def auth_reset_password():
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json(); token = data.get("token", ""); password = data.get("password", "")
    if len(password) < 8: return cors_response({"detail": "Password must be at least 8 characters"}, 400)
    conn = get_db_conn()
    row = conn.execute("SELECT id, user_id, used, expires_at FROM email_tokens WHERE token=? AND purpose='reset_password'", (token,)).fetchone()
    if not row: conn.close(); return cors_response({"detail": "Invalid token"}, 400)
    if row["used"]: conn.close(); return cors_response({"detail": "Token already used"}, 400)
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc): conn.close(); return cors_response({"detail": "Token expired"}, 400)
    conn.execute("UPDATE email_tokens SET used=1 WHERE id=?", (row["id"],))
    conn.execute("UPDATE users SET password_hash=?, failed_attempts=0, locked_until=NULL WHERE id=?", (hash_password(password), row["user_id"]))
    conn.commit(); conn.close()
    return cors_response({"message": "Password reset successfully"})


# ═══ USER ROUTES (each parses JWT independently) ═════════

def user_me():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        return cors_response({"id": user["id"], "email": user["email"], "email_verified": user["email_verified"], "created_at": ""})
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def user_entitlements():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        conn = get_db_conn()
        rows = conn.execute("SELECT * FROM entitlements WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        conn.close()
        result = []
        for r in rows:
            item = dict(r)
            item["is_expired"] = bool(item.get("expires_at") and datetime.fromisoformat(item["expires_at"]) < datetime.now(timezone.utc))
            item["remaining"] = item["total_count"] - item["used_count"] if item["total_count"] > 0 else -1
            result.append(item)
        return cors_response({"entitlements": result})
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def user_orders():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        conn = get_db_conn()
        rows = conn.execute("SELECT * FROM user_orders WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        conn.close()
        return cors_response({"orders": [dict(r) for r in rows]})
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def user_premium_status():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        conn = get_db_conn()
        rows = conn.execute("SELECT plan_type, total_count, used_count, expires_at FROM entitlements WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        conn.close()
        for r in rows:
            if r["expires_at"] and datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc): continue
            remaining = r["total_count"] - r["used_count"] if r["total_count"] > 0 else -1
            return cors_response({"premium": True, "plan_type": r["plan_type"], "plan_label": PLAN_CONFIG.get(r["plan_type"],{}).get("label",""), "remaining": remaining, "total": r["total_count"]})
        return cors_response({"premium": False, "plan_type": None, "remaining": 0, "total": 0})
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def license_verify():
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json(); key = data.get("key", "")
    if not key: return cors_response({"detail": "License key required"}, 400)
    conn = get_db_conn()
    row = conn.execute("SELECT plan_type, is_used FROM license_keys WHERE key=?", (key,)).fetchone()
    conn.close()
    if not row: return cors_response({"detail": "Invalid license key"}, 400)
    if row["is_used"]: return cors_response({"detail": "License key already used"}, 400)
    return cors_response({"valid": True, "plan_type": row["plan_type"], "plan_label": PLAN_CONFIG.get(row["plan_type"],{}).get("label","")})


def license_redeem():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        data = request.get_json(); key = data.get("key", "")
        if not key: return cors_response({"detail": "License key required"}, 400)
        conn = get_db_conn()
        row = conn.execute("SELECT id, plan_type, is_used FROM license_keys WHERE key=?", (key,)).fetchone()
        if not row: conn.close(); return cors_response({"detail": "Invalid license key"}, 400)
        if row["is_used"]: conn.close(); return cors_response({"detail": "License key already used"}, 400)
        conn.execute("UPDATE license_keys SET is_used=1, used_by_user_id=?, used_at=datetime('now') WHERE id=?", (user["id"], row["id"]))
        activate_entitlement(conn, user["id"], row["plan_type"])
        conn.commit(); conn.close()
        return cors_response({"message": f"License redeemed. {PLAN_CONFIG.get(row['plan_type'],{}).get('label','')} activated.", "plan_type": row["plan_type"]})
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def entitlements_consume():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        conn = get_db_conn()
        rows = conn.execute("SELECT id, plan_type, total_count, used_count, expires_at FROM entitlements WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        for r in rows:
            if r["expires_at"] and datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc): continue
            if r["total_count"] > 0 and r["used_count"] >= r["total_count"]:
                conn.close(); return cors_response({"detail": "No remaining interpretations"}, 403)
            if r["total_count"] > 0:
                conn.execute("UPDATE entitlements SET used_count=used_count+1 WHERE id=?", (r["id"],))
            conn.commit(); conn.close()
            remaining = r["total_count"] - r["used_count"] - 1 if r["total_count"] > 0 else -1
            return cors_response({"success": True, "remaining": remaining, "plan_type": r["plan_type"]})
        conn.close()
        return cors_response({"detail": "No active entitlement"}, 403)
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def entitlements_activate():
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        data = request.get_json()
        plan_type = data.get("plan_type", ""); order_id = data.get("order_id", "")
        if plan_type not in PLAN_CONFIG: return cors_response({"detail": "Invalid plan type"}, 400)
        conn = get_db_conn()
        existing = conn.execute("SELECT id FROM user_orders WHERE paypal_order_id=? AND status='completed'", (order_id,)).fetchone()
        if existing: conn.close(); return cors_response({"message": "Already activated", "plan_type": plan_type})
        config = PLAN_CONFIG[plan_type]
        conn.execute("INSERT INTO user_orders (id, user_id, paypal_order_id, amount, plan_type, status) VALUES (?,?,?,?,?,?)",
                     (str(uuid.uuid4()), user["id"], order_id, config["price"], plan_type, "completed"))
        activate_entitlement(conn, user["id"], plan_type)
        conn.commit(); conn.close()
        return cors_response({"message": f"{config['label']} activated", "plan_type": plan_type, "plan_label": config["label"]})
    except Exception as e:
        return cors_response({"detail": str(e)}, 401)


def admin_generate_license_keys():
    plan_type = request.args.get("plan_type", "")
    count = min(int(request.args.get("count", 10)), 1000)
    if plan_type not in PLAN_CONFIG: return cors_response({"detail": "Invalid plan type"}, 400)
    conn = get_db_conn()
    keys = []
    for _ in range(count):
        key = f"SM-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        conn.execute("INSERT INTO license_keys (id, key, plan_type) VALUES (?,?,?)", (str(uuid.uuid4()), key, plan_type))
        keys.append(key)
    conn.commit(); conn.close()
    return cors_response({"generated": len(keys), "plan_type": plan_type, "keys": keys})


# ═══ NOWPAYMENTS (CRYPTO) ═══════════════════════════════

def nowpayments_create_payment():
    """Create a NOWPayments invoice for crypto payment."""
    if request.method == "OPTIONS": return handle_options()
    try:
        user = get_user_from_token()
        data = request.get_json()
        plan_type = data.get("plan_type", "")
        if plan_type not in PLAN_CONFIG: return cors_response({"detail": "Invalid plan type"}, 400)
        config = PLAN_CONFIG[plan_type]

        import requests as http_req
        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "price_amount": config["price"],
            "price_currency": "usd",
            "order_id": str(uuid.uuid4()),
            "order_description": f"Subconscious Mirror - {config['label']}",
            "ipn_callback_url": f"{SITE_URL}/api/nowpayments/webhook",
            "success_url": f"{SITE_URL}/payment/success?plan={plan_type}",
            "cancel_url": f"{SITE_URL}/payment/cancel",
            "is_fixed_rate": True,
            "is_fee_paid_by_user": True,
        }

        if not NOWPAYMENTS_API_KEY:
            return cors_response({"detail": "NOWPayments not configured (missing API key). Please contact support."}, 503)

        resp = http_req.post(f"{NOWPAYMENTS_API_BASE}/invoice", json=payload, headers=headers, timeout=15)
        if resp.status_code not in (200, 201):
            error_detail = resp.text[:300]
            print(f"[NOWPayments] API error {resp.status_code}: {error_detail}")
            return cors_response({"detail": f"Payment provider error. Please try again later."}, 502)

        result = resp.json()
        payment_id = result.get("id")
        invoice_url = result.get("invoice_url", "")

        # Store in DB
        conn = get_db_conn()
        conn.execute(
            "INSERT INTO crypto_payments (id, user_id, plan_type, amount, nowpayments_id, pay_address, status) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user["id"], plan_type, config["price"], str(payment_id), "", "pending"),
        )
        conn.commit(); conn.close()

        return cors_response({
            "payment_id": payment_id,
            "invoice_url": invoice_url,
            "amount": config["price"],
            "currency": "USD",
            "plan_type": plan_type,
            "plan_label": config["label"],
        })
    except Exception as e:
        return cors_response({"detail": str(e)}, 500)


def nowpayments_webhook():
    """Receive NOWPayments IPN (Instant Payment Notification)."""
    if request.method == "OPTIONS": return handle_options()
    data = request.get_json()
    payment_id = data.get("payment_id", "")
    payment_status = data.get("payment_status", "")
    order_id = data.get("order_id", "")
    pay_amount = data.get("pay_amount", 0)
    actually_paid = data.get("actually_paid", 0)

    # Verify IPN secret
    if NOWPAYMENTS_IPN_SECRET:
        received_secret = request.headers.get("x-nowpayments-sig", "")
        import hashlib
        expected = hashlib.sha256(f"{payment_id}:{pay_amount}:{NOWPAYMENTS_IPN_SECRET}".encode()).hexdigest()
        if received_secret and received_secret != expected:
            return cors_response({"status": "invalid_signature"}, 403)

    conn = get_db_conn()
    row = conn.execute("SELECT id, user_id, plan_type, status FROM crypto_payments WHERE nowpayments_id=?", (str(payment_id),)).fetchone()
    if not row:
        conn.close()
        return cors_response({"status": "payment_not_found"}, 404)

    if row["status"] == "finished":
        conn.close()
        return cors_response({"status": "already_processed"})

    if payment_status == "finished":
        conn.execute("UPDATE crypto_payments SET status='finished', crypto_amount=? WHERE id=?", (actually_paid, row["id"]))
        activate_entitlement(conn, row["user_id"], row["plan_type"])
        conn.commit()
        conn.close()
        return cors_response({"status": "activated"})

    conn.execute("UPDATE crypto_payments SET status=? WHERE id=?", (payment_status, row["id"]))
    conn.commit()
    conn.close()
    return cors_response({"status": "updated", "payment_status": payment_status})


def nowpayments_status(payment_id):
    """Check payment status by nowpayments payment ID."""
    if not NOWPAYMENTS_API_KEY:
        return cors_response({"detail": "NOWPayments not configured"}, 503)
    import requests as http_req
    try:
        resp = http_req.get(
            f"{NOWPAYMENTS_API_BASE}/payment/{payment_id}",
            headers={"x-api-key": NOWPAYMENTS_API_KEY},
            timeout=10,
        )
        if resp.status_code != 200:
            return cors_response({"detail": "Failed to get payment status"}, 502)
        return cors_response(resp.json())
    except Exception as e:
        return cors_response({"detail": str(e)}, 502)


# ═══ GOOGLE OAUTH ═══════════════════════════════════════

def auth_social_google():
    """Initiate Google OAuth login — redirect user to Google consent screen."""
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        return cors_response({"detail": "Google login not configured", "code": "NOT_CONFIGURED"}, 501)
    redirect_uri = f"{SITE_URL}/api/auth/social/google/callback"
    params = (
        f"client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
        f"&prompt=select_account"
    )
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    # Return auth_url so frontend can redirect (supports both popup and full redirect)
    return cors_response({"auth_url": auth_url})


def auth_social_google_callback():
    """
    Handle Google OAuth callback.
    Flow: Google redirects here with ?code=... → exchange code for tokens →
    fetch user info → create/log in user → redirect to frontend with JWT.
    """
    code = request.args.get("code", "")
    error = request.args.get("error", "")
    if error:
        print(f"[Google OAuth] User denied or error: {error}")
        from flask import redirect as flask_redirect
        return flask_redirect(f"{SITE_URL}/?oauth_error={error}")

    if not code:
        return cors_response({"detail": "Missing authorization code"}, 400)

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    redirect_uri = f"{SITE_URL}/api/auth/social/google/callback"

    if not client_id or not client_secret:
        return cors_response({"detail": "Google OAuth not fully configured"}, 500)

    import requests as http_req

    # Step 1: Exchange authorization code for tokens
    try:
        token_resp = http_req.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get("access_token", "")
        if not access_token:
            print(f"[Google OAuth] No access_token in response: {token_data}")
            return cors_response({"detail": "Failed to get access token"}, 502)
    except Exception as e:
        print(f"[Google OAuth] Token exchange failed: {e}")
        return cors_response({"detail": "Google token exchange failed"}, 502)

    # Step 2: Fetch user info from Google
    try:
        user_resp = http_req.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        user_resp.raise_for_status()
        google_user = user_resp.json()
        google_email = google_user.get("email", "").lower()
        google_name = google_user.get("name", google_email.split("@")[0])
        google_id = google_user.get("id", "")
        google_verified = google_user.get("verified_email", False)

        if not google_email:
            print(f"[Google OAuth] No email in user info: {google_user}")
            return cors_response({"detail": "Google account has no email"}, 400)
    except Exception as e:
        print(f"[Google OAuth] User info fetch failed: {e}")
        return cors_response({"detail": "Failed to fetch Google user info"}, 502)

    # Step 3: Find or create user
    conn = get_db_conn()
    user = conn.execute("SELECT * FROM users WHERE email=?", (google_email,)).fetchone()

    if user:
        # Existing user — log them in
        user_id = user["id"]
        conn.execute("UPDATE users SET updated_at=datetime('now') WHERE id=?", (user_id,))
    else:
        # New user — create account with a random password
        user_id = str(uuid.uuid4())
        random_password = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO users (id, email, password_hash, email_verified) VALUES (?,?,?,?)",
            (user_id, google_email, hash_password(random_password), 1 if google_verified else 0),
        )
        print(f"[Google OAuth] Created new user: {google_email}")

    conn.commit()
    conn.close()

    # Step 4: Generate JWT and redirect to frontend
    token = create_jwt(user_id, google_email, True)
    from flask import redirect as flask_redirect
    return flask_redirect(f"{SITE_URL}/?oauth_token={token}&email={google_email}")


# ── Apple OAuth Placeholder ─────────────────────────────

# ── Apple / GitHub Placeholder (removed, only Google active) ──


# ── Register Routes ──────────────────────────────────────
def register_account_routes(app):
    app.add_url_rule('/api/auth/register', 'auth_register', auth_register, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/auth/verify-email', 'auth_verify_email', auth_verify_email, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/auth/login', 'auth_login', auth_login, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/auth/forgot-password', 'auth_forgot_password', auth_forgot_password, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/auth/reset-password', 'auth_reset_password', auth_reset_password, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/user/me', 'user_me', user_me, methods=['GET', 'OPTIONS'])
    app.add_url_rule('/api/user/entitlements', 'user_entitlements', user_entitlements, methods=['GET', 'OPTIONS'])
    app.add_url_rule('/api/user/orders', 'user_orders', user_orders, methods=['GET', 'OPTIONS'])
    app.add_url_rule('/api/user/premium-status', 'user_premium_status', user_premium_status, methods=['GET', 'OPTIONS'])
    app.add_url_rule('/api/license/verify', 'license_verify', license_verify, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/license/redeem', 'license_redeem', license_redeem, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/entitlements/consume', 'entitlements_consume', entitlements_consume, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/entitlements/activate', 'entitlements_activate', entitlements_activate, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/admin/generate-license-keys', 'admin_generate_license_keys', admin_generate_license_keys, methods=['POST'])

    # NOWPayments
    app.add_url_rule('/api/nowpayments/create-payment', 'nowpayments_create_payment', nowpayments_create_payment, methods=['POST', 'OPTIONS'])
    app.add_url_rule('/api/nowpayments/webhook', 'nowpayments_webhook', nowpayments_webhook, methods=['POST', 'OPTIONS'])

    # Social auth
    app.add_url_rule('/api/auth/social/google', 'auth_social_google', auth_social_google, methods=['GET'])
    app.add_url_rule('/api/auth/social/google/callback', 'auth_social_google_callback', auth_social_google_callback, methods=['GET'])
