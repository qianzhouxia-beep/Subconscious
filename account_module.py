# account_module.py — Subconscious Mirror User Account System
# Provides: register, login, JWT auth, entitlements, orders, license management
import os
import re
import hashlib
import time
import uuid
from functools import wraps
from contextlib import contextmanager
from flask import request, jsonify, make_response

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
_DB_FILE = os.environ.get("DB_FILE", os.path.join(os.environ.get("DATA_DIR", "/data"), "mirror_data.db"))

DB_FILE = None  # set by init_account_tables via main.py's DB_FILE global
JWT_SECRET = os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026")
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 8760  # 1 year

PLAN_CONFIG = {
    "spark":      {"label": "Free",         "price": 0.0,  "reports": 0},
    "credits_3":  {"label": "Starter",      "price": 2.99, "reports": 3},
    "credits_10": {"label": "Popular",      "price": 6.99, "reports": 10},
    "credits_30": {"label": "Pro",          "price": 14.99,"reports": 30},
    # Tarot-only plans (purchased separately)
    "tarot_3":   {"label": "Tarot ×3",    "price": 1.99, "reports": 3},
    "tarot_10":  {"label": "Tarot ×10",   "price": 4.99, "reports": 10},
    "tarot_30":  {"label": "Tarot ×30",   "price": 9.99, "reports": 30},
}


def _hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _generate_token(user_id, email):
    try:
        import jwt
        payload = {
            "sub": user_id,
            "email": email,
            "iat": int(time.time()),
            "exp": int(time.time()) + (JWT_EXPIRY_HOURS * 3600),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    except ImportError:
        # Fallback: use a simple token (not ideal but works without PyJWT)
        token = hashlib.sha256(f"{user_id}:{email}:{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()
        return token


def _decode_token(token):
    try:
        import jwt
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload
    except ImportError:
        # Fallback lookup by token string in users table
        return None
    except Exception:
        return None


def get_db_conn():
    """Return a raw DB connection — uses backend.db abstraction for PG/SQLite compat."""
    if DATABASE_URL:
        try:
            from backend.db import get_db_conn as _pg_get_conn
            return _pg_get_conn()
        except Exception:
            pass  # fallback below
    # SQLite fallback
    import sqlite3
    conn = sqlite3.connect(DB_FILE or _DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _get_db():
    """Context manager for DB connections (works with both PG and SQLite)."""
    @contextmanager
    def mgr():
        conn = get_db_conn()
        is_pg = bool(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return mgr()


def token_required(f):
    """Decorator: require valid Bearer token. Sets request.user dict."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"detail": "Authentication required"}), 401
        token = auth_header[7:]
        print(f"[DEBUG] token_received: {token[:20]}...")
        payload = _decode_token(token)
        print(f"[DEBUG] payload: {payload}")
        if not payload:
            return jsonify({"detail": "Invalid or expired token"}), 401
        # Look up user
        try:
            with _get_db() as conn:
                row = conn.execute(
                    "SELECT id, email, created_at FROM users WHERE id = ?", (payload["sub"],)
                ).fetchone()
                if not row:
                    return jsonify({"detail": "User not found"}), 401
                request.user = dict(row)
                request.user_payload = payload
        except Exception as e:
            import traceback
            print(f"[ERROR] token_required db error: {e}")
            print(traceback.format_exc())
            return jsonify({"detail": f"DB error: {str(e)}"}), 500
        return f(*args, **kwargs)
    return decorated


def init_account_tables():
    """Create users, entitlements, and orders tables if they don't exist. Works with both PG and SQLite."""
    global DB_FILE
    # Import DB_FILE from main module scope
    import sys
    main_mod = sys.modules.get("__main__") or sys.modules.get("main")
    if main_mod and hasattr(main_mod, "DB_FILE"):
        DB_FILE = main_mod.DB_FILE
    elif not DB_FILE:
        DB_FILE = os.environ.get("DB_FILE", "/data/mirror_data.db")

    _is_pg = bool(DATABASE_URL)

    with _get_db() as conn:
        if _is_pg:
            # ── PostgreSQL path ──
            _pg_tables = [
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    google_sub TEXT DEFAULT '',
                    email_verified INTEGER DEFAULT 0,
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    last_login TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS entitlements (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_type TEXT NOT NULL DEFAULT 'spark',
                    total_count INTEGER NOT NULL DEFAULT 0,
                    remaining INTEGER NOT NULL DEFAULT 0,
                    is_expired INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT DEFAULT '',
                    order_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_type TEXT NOT NULL DEFAULT 'spark',
                    amount REAL NOT NULL DEFAULT 0,
                    currency TEXT DEFAULT 'USD',
                    status TEXT DEFAULT 'pending',
                    payment_provider TEXT DEFAULT '',
                    provider_order_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )""",
            ]
            for sql in _pg_tables:
                conn.execute(sql)
            # Indexes
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            ]:
                try:
                    conn.execute(idx_sql)
                except Exception:
                    pass
        else:
            # ── SQLite path (original) ──
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    google_sub TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS entitlements (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_type TEXT NOT NULL DEFAULT 'spark',
                    total_count INTEGER NOT NULL DEFAULT 0,
                    remaining INTEGER NOT NULL DEFAULT 0,
                    is_expired INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT,
                    order_id TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_type TEXT NOT NULL DEFAULT 'spark',
                    amount REAL NOT NULL DEFAULT 0,
                    currency TEXT DEFAULT 'USD',
                    status TEXT DEFAULT 'pending',
                    payment_provider TEXT DEFAULT '',
                    provider_order_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id);
                CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """)

        # Migration: add missing columns to existing tables (PG + SQLite compatible)
        _migration_cols = [
            ("entitlements", "remaining", "INTEGER NOT NULL DEFAULT 0"),
            ("entitlements", "is_expired", "INTEGER NOT NULL DEFAULT 0"),
            ("entitlements", "expires_at", "TEXT"),
            ("entitlements", "order_id", "TEXT"),
            ("users", "google_sub", "TEXT DEFAULT ''"),
        ]
        for table, col, col_def in _migration_cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                print(f"[MIGRATION] Added '{col}' column to {table} table")
            except Exception as e:
                _err = str(e).lower()
                if "duplicate" in _err or "already exists" in _err or "column" in _err:
                    pass  # Column already exists
                else:
                    raise

        # Check users table for missing columns
        if not _is_pg:
            # SQLite: use PRAGMA
            try:
                user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
                if "last_login" not in user_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT DEFAULT ''")
                    conn.execute("UPDATE users SET last_login = datetime('now') WHERE last_login IS NULL OR last_login = ''")
                    print("[account_module] Migrated: added users.last_login column")
                if "google_sub" not in user_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN google_sub TEXT DEFAULT ''")
                    print("[account_module] Migrated: added users.google_sub column")
            except Exception as e:
                print(f"[account_module] Migration check failed (non-fatal): {e}")
        else:
            # PostgreSQL: check columns via information_schema
            try:
                existing = {row[0] for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND table_schema='public'"
                ).fetchall()}
                for col_name in ["last_login", "google_sub"]:
                    if col_name not in existing:
                        conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} TEXT DEFAULT ''")
                        print(f"[account_module] PG migrated: added users.{col_name} column")
            except Exception as e:
                print(f"[account_module] PG migration check failed (non-fatal): {e}")

    print("[account_module] Tables initialized OK")


def register_account_routes(app):
    """Register all authentication and user API routes on the Flask app."""

    # ─── Auth Routes ────────────────────────────────────────

    @app.route("/api/auth/register", methods=["POST"])
    def auth_register():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")

        if not email or "@" not in email:
            return jsonify({"detail": "Valid email address required"}), 400
        if len(password) < 6:
            return jsonify({"detail": "Password must be at least 6 characters"}), 400

        with _get_db() as conn:
            # Check if email already exists
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                return jsonify({"detail": "An account with this email already exists"}), 409

            user_id = uuid.uuid4().hex
            pwd_hash = _hash_password(password)
            conn.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                (user_id, email, pwd_hash),
            )

        # Auto-login after registration
        token = _generate_token(user_id, email)
        return jsonify({
            "token": token,
            "user": {"id": user_id, "email": email},
        })

    @app.route("/api/auth/login", methods=["POST"])
    def auth_login():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"detail": "Email and password are required"}), 400

        with _get_db() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()

            if not row or row["password_hash"] != _hash_password(password):
                return jsonify({"detail": "Invalid email or password"}), 401

            # Update last login (best-effort: tolerate legacy DBs without this column)
            try:
                _now = __import__('datetime').datetime.now().isoformat()
                conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now, row["id"]))
            except Exception:
                pass

        token = _generate_token(row["id"], row["email"])
        return jsonify({
            "token": token,
            "user": {"id": row["id"], "email": row["email"]},
        })

    @app.route("/api/auth/forgot-password", methods=["POST"])
    def auth_forgot_password():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()

        if not email:
            return jsonify({"detail": "Email is required"}), 400

        # Always return success to prevent email enumeration
        # In production, send an actual reset email here
        return jsonify({"message": "If the email exists, a reset link has been sent."})

    # ─── Social Login (Google OAuth) ─────────────────────────
    # Note: These routes are defined in main.py directly since they need
    # the Flask app's url_for. The account_module provides helper functions
    # that those routes can call.

    def social_google_auth_url():
        """Generate Google OAuth authorization URL."""
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")
        if not client_id:
            return None, "Google OAuth not configured (missing GOOGLE_OAUTH_CLIENT_ID)"

        from urllib.parse import urlencode
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "prompt": "select_account",
        })
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
        return auth_url, None

    def handle_google_callback(code):
        """Exchange Google auth code for user info; create/find user; return token."""
        import requests as _req
        from urllib.parse import urlencode

        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
        redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")

        if not all([client_id, client_secret, code]):
            return None, None, "Google OAuth misconfigured"

        # Exchange code for access_token
        token_res = _req.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        if not token_res.ok:
            return None, None, "Google token exchange failed"

        access_token = token_res.json().get("access_token", "")
        if not access_token:
            return None, None, "No access_token from Google"

        # Fetch user info
        userinfo_res = _req.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": "Bearer " + access_token},
            timeout=10,
        )
        if not userinfo_res.ok:
            return None, None, "Failed to fetch Google user info"

        userinfo = userinfo_res.json()
        email = userinfo.get("email", "")
        google_sub = userinfo.get("id", "")

        if not email:
            return None, None, "Google did not return email"

        # Find or create user
        with _get_db() as conn:
            row = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                user_id = row["id"]
                # Update google_sub if missing (best-effort; tolerate legacy DBs without last_login)
                try:
                    cur = conn.execute("SELECT google_sub FROM users WHERE id = ?", (user_id,)).fetchone()
                    if cur and not cur["google_sub"]:
                        _now = __import__('datetime').datetime.now().isoformat()
                        conn.execute("UPDATE users SET google_sub=?, last_login=? WHERE id=?", (google_sub, _now, user_id))
                except Exception:
                    pass
            else:
                user_id = uuid.uuid4().hex
                pwd_hash = _hash_password(os.urandom(24).hex())  # random password for OAuth-only accounts
                # Tolerate legacy DBs without google_sub column
                try:
                    conn.execute(
                        "INSERT INTO users (id, email, password_hash, google_sub) VALUES (?, ?, ?, ?)",
                        (user_id, email, pwd_hash, google_sub or ""),
                    )
                except Exception:
                    # Fallback: insert without google_sub
                    conn.execute(
                        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                        (user_id, email, pwd_hash),
                    )

        token = _generate_token(user_id, email)
        return token, email, None

    # Store helpers on app for use by main.py routes
    app.config["_social_google_auth_url"] = social_google_auth_url
    app.config["_handle_google_callback"] = handle_google_callback

    # ─── User Routes ─────────────────────────────────────────

    @app.route("/api/user/me", methods=["GET"])
    @token_required
    def user_me():
        return jsonify(request.user)

    @app.route("/api/user/premium-status", methods=["GET"])
    @token_required
    def user_premium_status():
        try:
            user_id = request.user["id"]
            with _get_db() as conn:
                # 1. Dream credits (credits_* plans)
                dream_ent = conn.execute("""
                    SELECT e.plan_type, e.total_count, e.remaining, e.is_expired, e.expires_at
                    FROM entitlements e
                    WHERE e.user_id = ? AND e.plan_type LIKE 'credits_%' AND e.is_expired = 0
                    ORDER BY e.created_at DESC LIMIT 1
                """, (user_id,)).fetchone()

                # 2. Tarot credits (tarot_* plans)
                tarot_ent = conn.execute("""
                    SELECT e.plan_type, e.total_count, e.remaining, e.is_expired, e.expires_at
                    FROM entitlements e
                    WHERE e.user_id = ? AND e.plan_type LIKE 'tarot_%' AND e.is_expired = 0
                    ORDER BY e.created_at DESC LIMIT 1
                """, (user_id,)).fetchone()

            result = {"premium": False}

            # Dream credits
            if dream_ent:
                plan_type = dream_ent["plan_type"]
                config = PLAN_CONFIG.get(plan_type, {})
                total = dream_ent["total_count"]
                remaining = dream_ent["remaining"]
                is_unlimited = total < 0

                result["premium"] = True
                result["plan_type"] = plan_type
                result["plan_label"] = config.get("label", plan_type.title())
                result["total"] = total
                result["remaining"] = remaining if not is_unlimited else -1

                # Check expiry
                if dream_ent.get("expires_at"):
                    import datetime
                    try:
                        exp_dt = datetime.datetime.fromisoformat(dream_ent["expires_at"])
                        if datetime.datetime.now() > exp_dt:
                            result["premium"] = False
                            result["is_expired"] = True
                    except Exception:
                        pass

            # Tarot credits
            if tarot_ent:
                t_total = tarot_ent["total_count"]
                t_remaining = tarot_ent["remaining"]
                result["tarot_premium"] = True
                result["tarot_plan_type"] = tarot_ent["plan_type"]
                result["tarot_total"] = t_total
                result["tarot_remaining"] = t_remaining if t_total >= 0 else -1
            else:
                result["tarot_premium"] = False
                result["tarot_remaining"] = 0
                result["tarot_total"] = 0

            return jsonify(result)
        except Exception as e:
            import traceback
            print(f"[ERROR] premium-status failed: {e}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    @app.route("/api/user/entitlements", methods=["GET"])
    @token_required
    def user_entitlements():
        try:
            user_id = request.user["id"]
            with _get_db() as conn:
                rows = conn.execute("""
                    SELECT id, plan_type, total_count, remaining, is_expired, expires_at, order_id, created_at
                    FROM entitlements WHERE user_id = ? ORDER BY created_at DESC
                """, (user_id,)).fetchall()

            entitlements = []
            for r in rows:
                d = dict(r)
                d["total_count"] = d["total_count"]
                d["remaining"] = d["remaining"]
                entitlements.append(d)

            return jsonify({"entitlements": entitlements})
        except Exception as e:
            import traceback
            print(f"[ERROR] entitlements failed: {e}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    @app.route("/api/user/orders", methods=["GET"])
    @token_required
    def user_orders():
        user_id = request.user["id"]
        with _get_db() as conn:
            rows = conn.execute("""
                SELECT id, plan_type, amount, currency, status, payment_provider, created_at
                FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
            """, (user_id,)).fetchall()

        orders = []
        for r in rows:
            orders.append(dict(r))

        return jsonify({"orders": orders})

    # ─── Entitlement Routes ──────────────────────────────────

    @app.route("/api/entitlements/consume", methods=["POST"])
    @token_required
    def entitlement_consume():
        user_id = request.user["id"]
        with _get_db() as conn:
            ent = conn.execute("""
                SELECT id, remaining, total_count FROM entitlements
                WHERE user_id = ? AND is_expired = 0 AND (total_count < 0 OR remaining > 0)
                ORDER BY created_at DESC LIMIT 1
            """, (user_id,)).fetchone()

            if not ent:
                return jsonify({"detail": "No entitlements available. Please purchase a plan."}), 403

            if ent["total_count"] >= 0:
                new_remaining = ent["remaining"] - 1
                if new_remaining < 0:
                    return jsonify({"detail": "No reports remaining. Please upgrade your plan."}), 403
                conn.execute("UPDATE entitlements SET remaining=? WHERE id=?", (new_remaining, ent["id"]))
            else:
                new_remaining = -1  # unlimited

        return jsonify({"remaining": new_remaining, "total": ent["total_count"]})

    @app.route("/api/entitlements/activate", methods=["POST"])
    @token_required
    def entitlement_activate():
        data = request.get_json(silent=True) or {}
        plan_type = data.get("plan_type", "spark")
        order_id = data.get("order_id", "")
        user_id = request.user["id"]

        config = PLAN_CONFIG.get(plan_type, PLAN_CONFIG["spark"])

        with _get_db() as conn:
            # Check if user already has an active entitlement of this type
            existing = conn.execute(
                "SELECT id, remaining, total_count FROM entitlements WHERE user_id=? AND plan_type=? AND is_expired=0",
                (user_id, plan_type),
            ).fetchone()

            if existing:
                # Update existing entitlement: add new credits to remaining
                new_remaining = existing["remaining"] + config["reports"]
                new_total = existing["total_count"] + config["reports"]
                conn.execute(
                    "UPDATE entitlements SET remaining=?, total_count=? WHERE id=?",
                    (new_remaining, new_total, existing["id"]),
                )
                ent_id = existing["id"]
            else:
                # Create new entitlement
                ent_id = uuid.uuid4().hex
                conn.execute("""
                    INSERT INTO entitlements (id, user_id, plan_type, total_count, remaining, order_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ent_id, user_id, plan_type, config["reports"], config["reports"], order_id))

            # Record order as paid
            if order_id:
                conn.execute(
                    "UPDATE orders SET status='paid' WHERE id=? AND user_id=?",
                    (order_id, user_id),
                )

        return jsonify({"status": "activated", "plan_type": plan_type, "entitlement_id": ent_id})

    # ─── License Routes ──────────────────────────────────────

    @app.route("/api/license/verify", methods=["POST"])
    def license_verify():
        data = request.get_json(silent=True) or {}
        key = (data.get("key") or "").strip()
        if not key:
            return jsonify({"valid": False, "detail": "License key is required"})

        with _get_db() as conn:
            row = conn.execute("""
                SELECT e.id, e.plan_type, e.remaining, e.total_count, u.email
                FROM entitlements e JOIN users u ON e.user_id = u.id
                WHERE e.order_id = ? AND e.is_expired = 0
            """, (key,)).fetchone()

            if not row:
                return jsonify({"valid": False, "detail": "License key not found or expired"})

            return jsonify({
                "valid": True,
                "plan_type": row["plan_type"],
                "email": row["email"],
                "remaining": row["remaining"],
                "total": row["total_count"],
            })

    @app.route("/api/license/redeem", methods=["POST"])
    @token_required
    def license_redeem():
        data = request.get_json(silent=True) or {}
        key = (data.get("key") or "").strip()
        if not key:
            return jsonify({"detail": "License key is required"}), 400

        user_id = request.user["id"]

        with _get_db() as conn:
            # Check if already redeemed
            existing = conn.execute(
                "SELECT id FROM entitlements WHERE order_id=? AND user_id=?", (key, user_id)
            ).fetchone()
            if existing:
                return jsonify({"detail": "This license has already been redeemed"}), 409

            # Find the license (order)
            order = conn.execute("SELECT id, plan_type, amount, status FROM orders WHERE id=?", (key,)).fetchone()
            if not order:
                return jsonify({"detail": "License key not found"}), 404

            if order["status"] == "paid":
                return jsonify({"detail": "This license has already been used"}), 409

            plan_type = order["plan_type"] or "spark"
            config = PLAN_CONFIG.get(plan_type, PLAN_CONFIG["spark"])

            # Check if user already has an active entitlement of this type
            existing = conn.execute(
                "SELECT id, remaining, total_count FROM entitlements WHERE user_id=? AND plan_type=? AND is_expired=0",
                (user_id, plan_type),
            ).fetchone()

            if existing:
                # Update existing entitlement: add new credits
                new_remaining = existing["remaining"] + config["reports"]
                new_total = existing["total_count"] + config["reports"]
                conn.execute(
                    "UPDATE entitlements SET remaining=?, total_count=? WHERE id=?",
                    (new_remaining, new_total, existing["id"]),
                )
                ent_id = existing["id"]
            else:
                # Create new entitlement
                ent_id = uuid.uuid4().hex
                conn.execute("""
                    INSERT INTO entitlements (id, user_id, plan_type, total_count, remaining, order_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ent_id, user_id, plan_type, config["reports"], config["reports"], key))

            conn.execute("UPDATE orders SET status='paid' WHERE id=?", (key,))

        return jsonify({"status": "redeemed", "plan_type": plan_type, "entitlement_id": ent_id})


def activate_entitlement(email, plan_type="spark", order_id="", amount=0.0):
    """Convenience function: activate an entitlement for an email (used by PayPal/NOWPayments callbacks).
    If user already has an active entitlement of this type, add credits to it (accumulate).
    Also activates a tarot entitlement with the same credit count."""
    with _get_db() as conn:
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if not user:
            return None
        
        user_id = user["id"]
        config = PLAN_CONFIG.get(plan_type, PLAN_CONFIG["spark"])
        tarot_plan = "tarot_" + plan_type.split("_")[-1]  # e.g. "credits_10" → "tarot_10"
        tarot_config = PLAN_CONFIG.get(tarot_plan, PLAN_CONFIG["spark"])
        
        ord_id = order_id or uuid.uuid4().hex
        
        # --- Dream entitlement ---
        existing = conn.execute(
            "SELECT id, remaining, total_count FROM entitlements WHERE user_id=? AND plan_type=? AND is_expired=0",
            (user_id, plan_type),
        ).fetchone()
        
        if existing:
            new_remaining = existing["remaining"] + config["reports"]
            new_total = existing["total_count"] + config["reports"]
            conn.execute(
                "UPDATE entitlements SET remaining=?, total_count=? WHERE id=?",
                (new_remaining, new_total, existing["id"]),
            )
            ent_id = existing["id"]
        else:
            ent_id = uuid.uuid4().hex
            conn.execute("""
                INSERT INTO entitlements (id, user_id, plan_type, total_count, remaining, order_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ent_id, user_id, plan_type, config["reports"], config["reports"], ord_id))
        
        # --- Tarot entitlement (same credit count) ---
        tarot_existing = conn.execute(
            "SELECT id, remaining, total_count FROM entitlements WHERE user_id=? AND plan_type=? AND is_expired=0",
            (user_id, tarot_plan),
        ).fetchone()
        
        if tarot_existing:
            new_tarot_remaining = tarot_existing["remaining"] + tarot_config["reports"]
            new_tarot_total = tarot_existing["total_count"] + tarot_config["reports"]
            conn.execute(
                "UPDATE entitlements SET remaining=?, total_count=? WHERE id=?",
                (new_tarot_remaining, new_tarot_total, tarot_existing["id"]),
            )
        else:
            tarot_ent_id = uuid.uuid4().hex
            conn.execute("""
                INSERT INTO entitlements (id, user_id, plan_type, total_count, remaining, order_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tarot_ent_id, user_id, tarot_plan, tarot_config["reports"], tarot_config["reports"], ord_id))
        
        # Record order if not exists
        existing_order = conn.execute("SELECT id FROM orders WHERE id=?", (ord_id,)).fetchone()
        if not existing_order:
            conn.execute("""
                INSERT INTO orders (id, user_id, plan_type, amount, currency, status, payment_provider)
                VALUES (?, ?, ?, ?, 'USD', 'paid', '')
            """, (ord_id, user_id, plan_type, amount))
        
        return ent_id
