# account_module.py — Subconscious Mirror User Account System
# Provides: register, login, JWT auth, entitlements, orders, license management
import os
import re
import hashlib
import time
import uuid
import sqlite3
from functools import wraps
from contextlib import contextmanager
from flask import request, jsonify, make_response

DB_FILE = None  # set by init_account_tables via main.py's DB_FILE global
JWT_SECRET = os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026")
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 8760  # 1 year

PLAN_CONFIG = {
    "spark":     {"label": "Free",        "price": 0.0,  "reports": 0},
    "credits_3":  {"label": "Starter",     "price": 2.99, "reports": 3},
    "credits_10": {"label": "Popular",     "price": 6.99, "reports": 10},
    "credits_30": {"label": "Pro",         "price": 14.99,"reports": 30},
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
    """Return a raw DB connection for use outside context managers."""
    conn = sqlite3.connect(DB_FILE or "/data/mirror_data.db", timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _get_db():
    """Context manager for DB connections."""
    @contextmanager
    def mgr():
        conn = get_db_conn()
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
    """Create users, entitlements, and orders tables if they don't exist."""
    from contextlib import contextmanager
    global DB_FILE
    # Import DB_FILE from main module scope
    import sys
    main_mod = sys.modules.get("__main__") or sys.modules.get("main")
    if main_mod and hasattr(main_mod, "DB_FILE"):
        DB_FILE = main_mod.DB_FILE
    elif not DB_FILE:
        DB_FILE = os.environ.get("DB_FILE", "/data/mirror_data.db")

    with _get_db() as conn:
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
        
        # Migration: add missing columns to existing tables
        try:
            conn.execute("ALTER TABLE entitlements ADD COLUMN remaining INTEGER NOT NULL DEFAULT 0")
            print("[MIGRATION] Added 'remaining' column to entitlements table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass  # Column already exists
            else:
                raise
        
        try:
            conn.execute("ALTER TABLE entitlements ADD COLUMN is_expired INTEGER NOT NULL DEFAULT 0")
            print("[MIGRATION] Added 'is_expired' column to entitlements table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                raise
        
        try:
            conn.execute("ALTER TABLE entitlements ADD COLUMN expires_at TEXT")
            print("[MIGRATION] Added 'expires_at' column to entitlements table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                raise
        
        try:
            conn.execute("ALTER TABLE entitlements ADD COLUMN order_id TEXT")
            print("[MIGRATION] Added 'order_id' column to entitlements table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                raise
        
        # Also check users table for missing columns
        try:
            conn.execute("ALTER TABLE users ADD COLUMN google_sub TEXT DEFAULT ''")
            print("[MIGRATION] Added 'google_sub' column to users table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                raise
        
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT DEFAULT (datetime('now'))")
            print("[MIGRATION] Added 'last_login' column to users table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                raise
        
        conn.commit()
        print("[INFO] Account tables initialized")
        # Note: SQLite ALTER TABLE ADD COLUMN requires a CONSTANT default (no expressions).
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
                conn.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (row["id"],))
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
                        conn.execute("UPDATE users SET google_sub=?, last_login=datetime('now') WHERE id=?", (google_sub, user_id))
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
                ent = conn.execute("""
                    SELECT e.plan_type, e.total_count, e.remaining, e.is_expired, e.expires_at
                    FROM entitlements e
                    WHERE e.user_id = ? AND e.is_expired = 0
                    ORDER BY e.created_at DESC LIMIT 1
                """, (user_id,)).fetchone()

            if not ent:
                return jsonify({"premium": False})

            plan_type = ent["plan_type"]
            config = PLAN_CONFIG.get(plan_type, {})
            total = ent["total_count"]
            remaining = ent["remaining"]
            is_unlimited = total < 0

            result = {
                "premium": True,
                "plan_type": plan_type,
                "plan_label": config.get("label", plan_type.title()),
                "total": total,
                "remaining": remaining if not is_unlimited else -1,
            }

            # Check expiry
            if ent.get("expires_at"):
                import datetime
                try:
                    exp_dt = datetime.datetime.fromisoformat(ent["expires_at"])
                    if datetime.datetime.now() > exp_dt:
                        result["premium"] = False
                        result["is_expired"] = True
                except Exception:
                    pass

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
            # Deactivate previous entitlements of same type
            conn.execute(
                "UPDATE entitlements SET is_expired=1 WHERE user_id=? AND plan_type=? AND is_expired=0",
                (user_id, plan_type),
            )

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

            # Create entitlement
            ent_id = uuid.uuid4().hex
            conn.execute("""
                INSERT INTO entitlements (id, user_id, plan_type, total_count, remaining, order_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ent_id, user_id, plan_type, config["reports"], config["reports"], key))
            conn.execute("UPDATE orders SET status='paid' WHERE id=?", (key,))

        return jsonify({"status": "redeemed", "plan_type": plan_type, "entitlement_id": ent_id})


def activate_entitlement(email, plan_type="spark", order_id="", amount=0.0):
    """Convenience function: activate an entitlement for an email (used by PayPal/NOWPayments callbacks)."""
    with _get_db() as conn:
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if not user:
            return None

        user_id = user["id"]
        config = PLAN_CONFIG.get(plan_type, PLAN_CONFIG["spark"])

        # Deactivate previous
        conn.execute("UPDATE entitlements SET is_expired=1 WHERE user_id=? AND plan_type=? AND is_expired=0", (user_id, plan_type))

        ord_id = order_id or uuid.uuid4().hex
        ent_id = uuid.uuid4().hex
        conn.execute("""
            INSERT INTO entitlements (id, user_id, plan_type, total_count, remaining, order_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ent_id, user_id, plan_type, config["reports"], config["reports"], ord_id))

        # Record order if not exists
        existing_order = conn.execute("SELECT id FROM orders WHERE id=?", (ord_id,)).fetchone()
        if not existing_order:
            conn.execute("""
                INSERT INTO orders (id, user_id, plan_type, amount, currency, status, payment_provider)
                VALUES (?, ?, ?, ?, 'USD', 'paid', '')
            """, (ord_id, user_id, plan_type, amount))

        return ent_id
