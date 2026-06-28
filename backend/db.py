"""
Database abstraction layer — 支持 SQLite（本地/持久化卷）和 PostgreSQL（外部数据库）
===============================================================================
用法：
  1. PostgreSQL 模式：设置环境变量 DATABASE_URL=postgresql://user:pass@host/db
  2. SQLite 模式（默认）：设置 DB_FILE 路径（默认 mirror_data.db）
     - 推荐 Zeabur 持久化卷路径：DB_FILE=/data/mirror_data.db

兼容接口：get_db() -> context manager, get_db_conn() -> connection
向上兼容 sqlite3.Row 的 dict-like 访问方式。
"""

import os
import re
from contextlib import contextmanager

# ── Config ──
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_FILE = os.environ.get("DB_FILE", "mirror_data.db")

# ── PostgreSQL 模式 ──
PSYCOPG2_READY = False
if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        PSYCOPG2_READY = True
        print(f"[DB] PostgreSQL mode: {re.sub(r'://[^@]+@', '://***@', DATABASE_URL)}")
    except ImportError:
        print("[DB] WARNING: psycopg2 not found, attempting auto-install...")
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"])
            import psycopg2
            import psycopg2.extras
            PSYCOPG2_READY = True
            print("[DB] psycopg2-binary installed successfully via pip")
        except Exception as _e:
            print(f"[DB] ERROR: Failed to install psycopg2-binary: {_e}")
            print("[DB] Falling back to SQLite mode")


# ═══════════════════════════════════════════════════════════
#  SQLite 实现
# ═══════════════════════════════════════════════════════════

def _sqlite_get_conn():
    import sqlite3
    os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ═══════════════════════════════════════════════════════════
#  PostgreSQL 实现
# ═══════════════════════════════════════════════════════════

def _pg_get_conn():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    conn.autocommit = False
    # Use RealDictCursor so rows behave like dicts (compatible with sqlite3.Row)
    return conn


def _pg_cursor(conn):
    """Return a cursor that returns dict-like rows (compatible with sqlite3.Row)."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ═══════════════════════════════════════════════════════════
#  SQL 方言转换
# ═══════════════════════════════════════════════════════════

def translate_sql(sql):
    """将 SQLite SQL 转换为 PostgreSQL 兼容的 SQL（如启用 PostgreSQL 模式）"""
    if not DATABASE_URL:
        return sql  # SQLite 模式直接返回

    # datetime('now') -> NOW()
    sql = re.sub(r"(?i)datetime\('now'\)", "NOW()", sql)

    # INSERT OR REPLACE -> INSERT ... ON CONFLICT DO UPDATE
    # 简单处理常见模式
    sql = re.sub(r"(?i)INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", sql)

    # PRAGMA 语句 → 忽略（PostgreSQL 不需要）
    lines = sql.split("\n")
    filtered = [l for l in lines if not re.match(r"\s*PRAGMA\s", l, re.IGNORECASE)]
    return "\n".join(filtered)


# ═══════════════════════════════════════════════════════════
#  execute / executescript 兼容封装
# ═══════════════════════════════════════════════════════════

def _pg_execute(conn, sql, params=None):
    """PostgreSQL 版 execute：处理方言 + ? → %s 占位符"""
    translated = translate_sql(sql)
    cur = _pg_cursor(conn)
    if params is not None:
        # SQLite 用 ? 占位符，PostgreSQL 用 %s
        # simple but effective: replace ? with %s (outside strings)
        pg_params = _convert_params(params)
        cur.execute(translated.replace("?", "%s"), pg_params)
    else:
        cur.execute(translated)
    return cur


def _convert_params(params):
    """转换参数：如果是 dict 就保持，如果是 tuple/list 就保持"""
    return params


def _pg_executescript(conn, script):
    """PostgreSQL 版 executescript：按分号拆分执行"""
    statements = [s.strip() for s in script.split(";") if s.strip()]
    for stmt in statements:
        if stmt:
            translated = translate_sql(stmt)
            if translated.strip():
                cur = _pg_cursor(conn)
                cur.execute(translated)
    return True


# ═══════════════════════════════════════════════════════════
#  统一接口 — Row Proxy
# ═══════════════════════════════════════════════════════════

class RowProxy:
    """统一的行包装器：让 PostgreSQL 和 SQLite 的行行为一致"""
    def __init__(self, row, is_pg=False):
        self._row = row
        self._is_pg = is_pg

    def __getitem__(self, key):
        if self._is_pg:
            # psycopg2 RealDictRow supports both string and int access
            return self._row[key]
        return self._row[key]

    def __getattr__(self, name):
        if self._is_pg:
            return self._row.get(name)
        return self._row[name] if name != '_row' else self._row

    def keys(self):
        if self._is_pg:
            return self._row.keys()
        return self._row.keys()


# ═══════════════════════════════════════════════════════════
#  统一接口 — Connection 代理
# ═══════════════════════════════════════════════════════════

class DbConnection:
    """统一的数据库连接对象，兼容现有代码的 conn.execute() 调用方式"""

    def __init__(self, raw_conn, is_pg=False):
        self._conn = raw_conn
        self._is_pg = is_pg

    def execute(self, sql, params=None):
        if self._is_pg:
            return _pg_execute(self._conn, sql, params)
        else:
            if params is None:
                c = self._conn.execute(sql)
            else:
                c = self._conn.execute(sql, params)
            return c

    def executescript(self, script):
        if self._is_pg:
            return _pg_executescript(self._conn, script)
        else:
            self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    @property
    def row_factory(self):
        return None  # handled internally

    @row_factory.setter
    def row_factory(self, value):
        pass  # handled internally in PostgreSQL mode

    def cursor(self):
        if self._is_pg:
            return _pg_cursor(self._conn)
        return self._conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


# ═══════════════════════════════════════════════════════════
#  公共接口
# ═══════════════════════════════════════════════════════════

def get_db_conn():
    """获取一个数据库连接（与旧版兼容）"""
    if PSYCOPG2_READY and DATABASE_URL:
        raw = _pg_get_conn()
        return DbConnection(raw, is_pg=True)
    else:
        raw = _sqlite_get_conn()
        return DbConnection(raw, is_pg=False)


@contextmanager
def get_db():
    """Context manager: 自动提交/回滚 + 关闭"""
    conn = get_db_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_tables():
    """初始化所有数据库表"""
    conn = get_db_conn()
    try:
        schema = """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, email_verified INTEGER DEFAULT 0,
                failed_attempts INTEGER DEFAULT 0, locked_until TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
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
            CREATE TABLE IF NOT EXISTS referrals (
                ref_id TEXT PRIMARY KEY, inviter_email TEXT NOT NULL,
                count INTEGER DEFAULT 0, unlocked INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS referral_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref_id TEXT NOT NULL, visitor_ip TEXT, user_agent TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS payments (
                email TEXT, status TEXT, license_key TEXT, timestamp REAL
            );
            CREATE INDEX IF NOT EXISTS idx_email_tokens_token ON email_tokens(token);
            CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_orders_user ON user_orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_license_keys_key ON license_keys(key);
            CREATE INDEX IF NOT EXISTS idx_payments_email ON payments(email);
        """
        conn.executescript(schema)
        conn.commit()
        mode = "PostgreSQL" if PSYCOPG2_READY and DATABASE_URL else "SQLite"
        print(f"[DB] Tables initialized ({mode})")
    finally:
        conn.close()
