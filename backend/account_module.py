"""
Subconscious Mirror — User Account Module
集成到现有 Flask 后 main.py 中

功能：邮箱注册/登录/JWT认证/权益管理/兑换码
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
# Fixed default secret — MUST be overridden via JWT_SECRET env var in production
JWT_SECRET = os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SITE_URL = os.environ.get("BASE_URL", "https://mirror.api-tokenmaster.com")
DB_FILE = os.environ.get("DB_FILE", "mirror_data.db")

# SMTP
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

# Plan definitions
PLAN_CONFIG = {
    "spark":  {"price": 4.99,  "total_count": 1,  "expires_days": None,  "label": "The Spark"},
    "seeker": {"price": 12.99, "total_count": 5,  "expires_days": None,  "label": "The Seeker"},
    "oracle": {"price": 29.99, "total_count": -1, "expires_days": 30,    "label": "The Oracle"},
}


# ── Database Init ────────────────────────────────────────
def init_account_tables():
    """Create user account tables if not exist. Call from main.py init_db()."""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email_verified INTEGER DEFAULT 0,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS email_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS entitlements (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            total_count INTEGER NOT NULL,
            used_count INTEGER DEFAULT 0,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS user_orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            paypal_order_id TEXT,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            plan_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS license_keys (
            id TEXT PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            plan_type TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by_user_id TEXT,
            used_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_email_tokens_token ON email_tokens(token);
        CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_orders_user ON user_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_license_keys_key ON license_keys(key);
    """)
    conn.commit()
    conn.close()


# ── Helpers ──────────────────────────────────────────────
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_jwt(user_id, email=None, email_verified=False):
    payload = {
        "sub": user_id,
        "email": email or "",
        "ev": int(bool(email_verified)),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_db_conn():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def send_email(to, subject, body):
    if not SMTP_HOST or not SMTP_USER:
        print(f"[EMAIL] To: {to} | Subject: {subject}")
        return True
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def require_auth(f):
    """Decorator: require JWT token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"detail": "Missing or invalid Authorization header"}), 401
        token = auth_header[7:]
        try:
            payload = decode_jwt(token)
            user_id = payload["sub"]
            # Read user info directly from JWT to avoid cross-worker DB issues
            kwargs['current_user_id'] = user_id
            kwargs['current_user_email'] = payload.get("email", "")
            kwargs['current_user_verified'] = payload.get("ev", 0)
            kwargs['current_user_created'] = ""
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"detail": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"detail": "Invalid token"}), 401
        except Exception as e:
            import traceback
            print(f"[AUTH ERROR] {e}\n{traceback.format_exc()}")
            return jsonify({"detail": f"Auth error: {str(e)}"}), 500
    return decorated


def activate_entitlement(conn, user_id, plan_type):
    """Create entitlement record for a user."""
    config = PLAN_CONFIG.get(plan_type)
    if not config:
        return
    total_count = config["total_count"]
    expires_at = None
    if config["expires_days"]:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=config["expires_days"])).isoformat()
    conn.execute(
        "INSERT INTO entitlements (id, user_id, plan_type, total_count, expires_at) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), user_id, plan_type, total_count, expires_at),
    )


def cors_response(data, status=200):
    """Return a CORS-enabled JSON response."""
    resp = make_response(jsonify(data), status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


# ── Route Handlers (to be registered in main.py) ────────

def handle_options():
    """Handle CORS preflight."""
    return cors_response({"status": "ok"})


# --- AUTH ---

def auth_register():
    if request.method == "OPTIONS":
        return handle_options()
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if len(password) < 8:
        return cors_response({"detail": "Password must be at least 8 characters"}, 400)
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return cors_response({"detail": "Invalid email format"}, 400)

    conn = get_db_conn()
    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        conn.close()
        return cors_response({"detail": "This email is already registered. Please log in or reset your password."}, 409)

    user_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?,?,?)",
        (user_id, email, hash_password(password)),
    )

    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    conn.execute(
        "INSERT INTO email_tokens (id, user_id, token, purpose, expires_at) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), user_id, token, "verify_email", expires),
    )
    conn.commit()
    conn.close()

    verify_link = f"{SITE_URL}/verify-email?token={token}"
    send_email(email, "Verify your email - Subconscious Mirror",
               f"<p>Welcome to Subconscious Mirror!</p>"
               f"<p>Click the link below to verify your email:</p>"
               f"<p><a href='{verify_link}'>{verify_link}</a></p>"
               f"<p>This link expires in 24 hours.</p>")

    return cors_response({"message": "Registration successful. Please check your email to verify your account."})


def auth_verify_email():
    if request.method == "OPTIONS":
        return handle_options()
    data = request.get_json()
    token = data.get("token", "")

    conn = get_db_conn()
    row = conn.execute(
        "SELECT id, user_id, used, expires_at FROM email_tokens WHERE token=? AND purpose='verify_email'",
        (token,),
    ).fetchone()
    if not row:
        conn.close()
        return cors_response({"detail": "Invalid verification token"}, 400)
    if row["used"]:
        conn.close()
        return cors_response({"detail": "Token already used"}, 400)
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        conn.close()
        return cors_response({"detail": "Token expired"}, 400)

    conn.execute("UPDATE email_tokens SET used=1 WHERE id=?", (row["id"],))
    conn.execute("UPDATE users SET email_verified=1, updated_at=datetime('now') WHERE id=?", (row["user_id"],))
    conn.commit()
    conn.close()
    return cors_response({"message": "Email verified successfully"})


def auth_login():
    if request.method == "OPTIONS":
        return handle_options()
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    conn = get_db_conn()
    user = conn.execute(
        "SELECT id, email, password_hash, email_verified, failed_attempts, locked_until FROM users WHERE email=?",
        (email,),
    ).fetchone()

    if not user:
        conn.close()
        return cors_response({"detail": "Invalid email or password"}, 401)

    if user["locked_until"]:
        locked_until = datetime.fromisoformat(user["locked_until"])
        if locked_until > datetime.now(timezone.utc):
            conn.close()
            remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            return cors_response({"detail": f"Account locked. Try again in {remaining} minutes."}, 423)

    if not verify_password(password, user["password_hash"]):
        failed = user["failed_attempts"] + 1
        if failed >= MAX_LOGIN_ATTEMPTS:
            locked = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            conn.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?", (failed, locked, user["id"]))
        else:
            conn.execute("UPDATE users SET failed_attempts=? WHERE id=?", (failed, user["id"]))
        conn.commit()
        conn.close()
        return cors_response({"detail": "Invalid email or password"}, 401)

    conn.execute("UPDATE users SET failed_attempts=0, locked_until=NULL, updated_at=datetime('now') WHERE id=?", (user["id"],))
    conn.commit()
    token = create_jwt(user["id"], user["email"], user["email_verified"])
    conn.close()

    return cors_response({
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "email_verified": bool(user["email_verified"]),
        },
    })


def auth_forgot_password():
    if request.method == "OPTIONS":
        return handle_options()
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()

    conn = get_db_conn()
    user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if user:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        conn.execute(
            "INSERT INTO email_tokens (id, user_id, token, purpose, expires_at) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), user["id"], token, "reset_password", expires),
        )
        conn.commit()
        reset_link = f"{SITE_URL}/reset-password?token={token}"
        send_email(email, "Reset your password - Subconscious Mirror",
                   f"<p>Click the link below to reset your password:</p>"
                   f"<p><a href='{reset_link}'>{reset_link}</a></p>"
                   f"<p>This link expires in 1 hour.</p>")
    conn.close()
    return cors_response({"message": "If the email exists, a reset link has been sent."})


def auth_reset_password():
    if request.method == "OPTIONS":
        return handle_options()
    data = request.get_json()
    token = data.get("token", "")
    password = data.get("password", "")

    if len(password) < 8:
        return cors_response({"detail": "Password must be at least 8 characters"}, 400)

    conn = get_db_conn()
    row = conn.execute(
        "SELECT id, user_id, used, expires_at FROM email_tokens WHERE token=? AND purpose='reset_password'",
        (token,),
    ).fetchone()
    if not row:
        conn.close()
        return cors_response({"detail": "Invalid reset token"}, 400)
    if row["used"]:
        conn.close()
        return cors_response({"detail": "Token already used"}, 400)
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        conn.close()
        return cors_response({"detail": "Token expired"}, 400)

    conn.execute("UPDATE email_tokens SET used=1 WHERE id=?", (row["id"],))
    conn.execute("UPDATE users SET password_hash=?, failed_attempts=0, locked_until=NULL, updated_at=datetime('now') WHERE id=?",
                 (hash_password(password), row["user_id"]))
    conn.commit()
    conn.close()
    return cors_response({"message": "Password reset successfully"})


# --- USER ---

def user_me(current_user_id=None, current_user_email=None, current_user_verified=None, current_user_created=None):
    if request.method == "OPTIONS":
        return handle_options()
    try:
        # Use data passed from require_auth decorator to avoid cross-worker DB issues
        return cors_response({
            "id": current_user_id,
            "email": current_user_email or "",
            "email_verified": bool(current_user_verified),
            "created_at": current_user_created or "",
        })
    except Exception as e:
        import traceback
        print(f"[user_me ERROR] {e}\n{traceback.format_exc()}")
        return cors_response({"detail": f"Server error: {str(e)}"}, 500)


def user_entitlements(current_user_id=None):
    if request.method == "OPTIONS":
        return handle_options()
    user_id = current_user_id
    conn = get_db_conn()
    rows = conn.execute(
        "SELECT id, plan_type, total_count, used_count, expires_at, created_at FROM entitlements WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        item = dict(r)
        item["is_expired"] = False
        if item["expires_at"]:
            item["is_expired"] = datetime.fromisoformat(item["expires_at"]) < datetime.now(timezone.utc)
        item["remaining"] = item["total_count"] - item["used_count"] if item["total_count"] > 0 else -1
        result.append(item)
    return cors_response({"entitlements": result})


def user_orders(current_user_id=None):
    if request.method == "OPTIONS":
        return handle_options()
    user_id = current_user_id
    conn = get_db_conn()
    rows = conn.execute(
        "SELECT id, paypal_order_id, amount, currency, plan_type, status, created_at FROM user_orders WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return cors_response({"orders": [dict(r) for r in rows]})


def user_premium_status(current_user_id=None):
    if request.method == "OPTIONS":
        return handle_options()
    try:
        user_id = current_user_id
        conn = get_db_conn()
        rows = conn.execute(
            "SELECT plan_type, total_count, used_count, expires_at FROM entitlements WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        conn.close()

        for r in rows:
            is_expired = False
            if r["expires_at"]:
                is_expired = datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc)
            if is_expired:
                continue
            remaining = r["total_count"] - r["used_count"] if r["total_count"] > 0 else -1
            return cors_response({
                "premium": True,
                "plan_type": r["plan_type"],
                "plan_label": PLAN_CONFIG.get(r["plan_type"], {}).get("label", ""),
                "remaining": remaining,
                "total": r["total_count"],
            })
        return cors_response({"premium": False, "plan_type": None, "remaining": 0, "total": 0})
    except Exception as e:
        import traceback
        print(f"[premium_status ERROR] {e}\n{traceback.format_exc()}")
        return cors_response({"detail": f"Server error: {str(e)}"}, 500)


# --- LICENSE ---

def license_verify():
    if request.method == "OPTIONS":
        return handle_options()
    data = request.get_json()
    key = data.get("key", "")
    if not key:
        return cors_response({"detail": "License key is required"}, 400)

    conn = get_db_conn()
    row = conn.execute("SELECT plan_type, is_used FROM license_keys WHERE key=?", (key,)).fetchone()
    conn.close()
    if not row:
        return cors_response({"detail": "Invalid license key"}, 400)
    if row["is_used"]:
        return cors_response({"detail": "License key has already been used"}, 400)
    return cors_response({"valid": True, "plan_type": row["plan_type"], "plan_label": PLAN_CONFIG.get(row["plan_type"], {}).get("label", "")})


def license_redeem(current_user_id=None):
    if request.method == "OPTIONS":
        return handle_options()
    user_id = current_user_id
    data = request.get_json()
    key = data.get("key", "")
    if not key:
        return cors_response({"detail": "License key is required"}, 400)

    conn = get_db_conn()
    row = conn.execute("SELECT id, plan_type, is_used FROM license_keys WHERE key=?", (key,)).fetchone()
    if not row:
        conn.close()
        return cors_response({"detail": "Invalid license key"}, 400)
    if row["is_used"]:
        conn.close()
        return cors_response({"detail": "License key has already been used"}, 400)

    conn.execute(
        "UPDATE license_keys SET is_used=1, used_by_user_id=?, used_at=datetime('now') WHERE id=?",
        (user_id, row["id"]),
    )
    activate_entitlement(conn, user_id, row["plan_type"])
    conn.commit()
    conn.close()
    return cors_response({
        "message": f"License redeemed successfully. {PLAN_CONFIG.get(row['plan_type'], {}).get('label', '')} activated.",
        "plan_type": row["plan_type"],
    })


def admin_generate_license_keys():
    plan_type = request.args.get("plan_type", "")
    count = min(int(request.args.get("count", 10)), 1000)
    if plan_type not in PLAN_CONFIG:
        return cors_response({"detail": "Invalid plan type"}, 400)

    conn = get_db_conn()
    keys = []
    for _ in range(count):
        key = f"SM-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        conn.execute(
            "INSERT INTO license_keys (id, key, plan_type) VALUES (?,?,?)",
            (str(uuid.uuid4()), key, plan_type),
        )
        keys.append(key)
    conn.commit()
    conn.close()
    return cors_response({"generated": len(keys), "plan_type": plan_type, "keys": keys})


# --- ENTITLEMENT CONSUMPTION ---

def entitlements_consume(current_user_id=None):
    if request.method == "OPTIONS":
        return handle_options()
    user_id = current_user_id
    conn = get_db_conn()
    rows = conn.execute(
        "SELECT id, plan_type, total_count, used_count, expires_at FROM entitlements WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()

    for r in rows:
        is_expired = False
        if r["expires_at"]:
            is_expired = datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc)
        if is_expired:
            continue

        if r["total_count"] > 0 and r["used_count"] >= r["total_count"]:
            conn.close()
            return cors_response({"detail": "No remaining interpretations. Please upgrade your plan."}, 403)

        if r["total_count"] > 0:
            conn.execute("UPDATE entitlements SET used_count=used_count+1 WHERE id=?", (r["id"],))
        conn.commit()
        conn.close()
        remaining = r["total_count"] - r["used_count"] - 1 if r["total_count"] > 0 else -1
        return cors_response({"success": True, "remaining": remaining, "plan_type": r["plan_type"]})

    conn.close()
    return cors_response({"detail": "No active entitlement. Please purchase a plan."}, 403)


def entitlements_activate(current_user_id=None):
    """Activate entitlement after payment success. Called by frontend after PayPal capture."""
    if request.method == "OPTIONS":
        return handle_options()
    user_id = current_user_id
    data = request.get_json()
    plan_type = data.get("plan_type", "")
    order_id = data.get("order_id", "")

    if plan_type not in PLAN_CONFIG:
        return cors_response({"detail": "Invalid plan type"}, 400)

    conn = get_db_conn()

    # Check if already activated (idempotent)
    existing = conn.execute(
        "SELECT id FROM user_orders WHERE paypal_order_id=? AND status='completed'",
        (order_id,),
    ).fetchone()
    if existing:
        conn.close()
        return cors_response({"message": "Already activated", "plan_type": plan_type})

    # Record order
    config = PLAN_CONFIG[plan_type]
    conn.execute(
        "INSERT INTO user_orders (id, user_id, paypal_order_id, amount, plan_type, status) VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), user_id, order_id, config["price"], plan_type, "completed"),
    )

    # Activate entitlement
    activate_entitlement(conn, user_id, plan_type)
    conn.commit()
    conn.close()

    return cors_response({
        "message": f"{config['label']} activated successfully",
        "plan_type": plan_type,
        "plan_label": config["label"],
    })


# ── Registration Helper (call from main.py) ─────────────

def register_account_routes(app):
    """Register all account-related routes on the Flask app."""
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
