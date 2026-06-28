# main.py - Version: v34.0.0 (PRO STABLE)
# Optimized by Backend Architect Specialist
import os
import re
from dotenv import load_dotenv
load_dotenv()
import sys
import sqlite3
import requests
import time
import uuid
import zhconv
from flask import Flask, request, jsonify, make_response, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Add backend directory to path for email templates
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from email_templates import send_order_confirmation, send_dream_report, send_inactive_reengagement_email
except ImportError:
    send_order_confirmation = None
    send_dream_report = None
    send_inactive_reengagement_email = None
    print("[Warning] email_templates not found, email features disabled")

# ── User Account System ──────────────────────────────────
try:
    from account_module import init_account_tables, register_account_routes, activate_entitlement, get_db_conn, PLAN_CONFIG
    ACCOUNT_SYSTEM_READY = True
except ImportError as e:
    print(f"[Warning] account_module not found, user account features disabled: {e}")
    ACCOUNT_SYSTEM_READY = False

app = Flask(__name__)
app.url_map.strict_slashes = False
CORS(app, supports_credentials=True)

# ── Persistent Storage: Sync tarot images to /data/tarot/ on startup ──
# Zeabur Volume is mounted at /data — this survives container restarts.
# On first deploy (or after image changes), copy static/tarot/ → /data/tarot/
import shutil as _shutil
_TAROT_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'tarot')
_TAROT_DST = '/data/tarot'
try:
    if os.path.isdir(_TAROT_SRC):
        os.makedirs(_TAROT_DST, exist_ok=True)
        _synced = 0
        for _f in os.listdir(_TAROT_SRC):
            if _f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                _src_f = os.path.join(_TAROT_SRC, _f)
                _dst_f = os.path.join(_TAROT_DST, _f)
                # Only copy if destination missing or source is newer
                if (not os.path.exists(_dst_f) or
                    os.path.getmtime(_src_f) > os.path.getmtime(_dst_f)):
                    _shutil.copy2(_src_f, _dst_f)
                    _synced += 1
        if _synced:
            print(f"[Storage] Synced {_synced} tarot images → {_TAROT_DST} (persistent volume)")
        else:
            print(f"[Storage] Tarot images already up-to-date in {_TAROT_DST}")
    else:
        print(f"[Warning] Source tarot dir not found: {_TAROT_SRC}")
except Exception as _e:
    print(f"[Warning] Failed to sync tarot images: {_e}")

# --- RATE LIMITER ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# --- CONFIGURATION (ENV DRIVEN) ---
import logging
import json
from datetime import datetime, timezone

# 结构化 JSON 日志
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            import traceback
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("subconscious-mirror")

DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# --- DeepSeek V4 模型命名（2026/07/24 旧模型 deepseek-chat / deepseek-reasoner 将到期） ---
# deepseek-chat → deepseek-v4-flash (non-thinking, 快速低成本的通用模型)
# deepseek-reasoner → deepseek-v4-pro + thinking (链式推理, 适合深度分析)
DEEPSEEK_CHAT_MODEL = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash")
DEEPSEEK_REPORT_MODEL = os.environ.get("DEEPSEEK_REPORT_MODEL", "deepseek-v4-pro")

# --- 备用 AI 模型（OpenAI 兼容 API） ---
# 主模型（DeepSeek）不可用时，自动降级到备选模型，防止服务中断
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# 第二备用（通用 OpenAI 兼容 API — 可接入 Moonshot/Kimi/Qwen/GLM 等任意服务）
FALLBACK_API_KEY = os.environ.get("FALLBACK_API_KEY", "")
FALLBACK_API_BASE = os.environ.get("FALLBACK_API_BASE", "")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "")

# 模型供应商注册表（按优先级排序）
AI_PROVIDERS = [
    {
        "name": "deepseek",
        "api_key": DEEPSEEK_API_KEY,
        "api_base": DEEPSEEK_API_BASE,
        "chat_model": DEEPSEEK_CHAT_MODEL,
        "report_model": DEEPSEEK_REPORT_MODEL,
    },
    {"name": "openai",   "api_key": OPENAI_API_KEY,   "api_base": OPENAI_API_BASE,   "default_model": OPENAI_MODEL},
    {"name": "fallback", "api_key": FALLBACK_API_KEY, "api_base": FALLBACK_API_BASE, "default_model": FALLBACK_MODEL},
]

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.environ.get("PAYPAL_SECRET", "")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
PAYPAL_SANDBOX = os.environ.get("PAYPAL_SANDBOX", "false") == "true"
PAYPAL_API_BASE = "https://api-m.sandbox.paypal.com" if PAYPAL_SANDBOX else "https://api-m.paypal.com"
# Sandbox credentials (used when PAYPAL_SANDBOX=true)
SANDBOX_PAYPAL_CLIENT_ID = os.environ.get("SANDBOX_PAYPAL_CLIENT_ID", PAYPAL_CLIENT_ID)
SANDBOX_PAYPAL_SECRET = os.environ.get("SANDBOX_PAYPAL_SECRET", PAYPAL_SECRET)
WHISPER_API_BASE = os.environ.get("WHISPER_API_BASE", "https://api-tokenmaster.com/v1/audio/transcriptions")
WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
HTML_FILE = "index.html"
BRAND_URL = os.environ.get("BASE_URL", "https://mirror.api-tokenmaster.com")
GUMROAD_PERMALINK = os.environ.get("GUMROAD_PERMALINK", "subconscious-mirror")
ENABLE_TEST_MODE = os.environ.get("ENABLE_TEST_MODE", "0") == "1"
TEST_LICENSE_KEY = os.environ.get("TEST_LICENSE_KEY", "TEST-MIRROR-2026") if ENABLE_TEST_MODE else None
PRICE_USD = os.environ.get("PRICE_USD", "4.99")

# 兼容性：如果只配了 DeepSeek，不强制要求其它 API Key
if not DEEPSEEK_API_KEY and not OPENAI_API_KEY:
    raise ValueError("At least one of DEEPSEEK_API_KEY or OPENAI_API_KEY is required")

# --- ERROR CLASSIFICATION ---
class ServiceUnavailableError(Exception):
    """外部服务不可用（AI API、支付网关等）"""
    pass

class ExternalAPIError(Exception):
    """外部 API 返回错误"""
    pass

def classify_request_error(err, context=""):
    """将 requests 异常分类为 HTTP 状态码和用户可读消息"""
    if isinstance(err, requests.Timeout):
        return 503, f"Service timeout: {context}"
    if isinstance(err, requests.ConnectionError):
        return 502, f"Cannot reach external service: {context}"
    if isinstance(err, requests.HTTPError):
        status = err.response.status_code if hasattr(err, 'response') else 500
        if status == 429:
            return 429, "AI service is busy, please try again in a moment"
        elif status == 401:
            return 500, "API authentication failed — please check server configuration"
        elif status >= 500:
            return 502, f"External service error: {context}"
        return 502, f"External API error: {context}"
    if isinstance(err, (sqlite3.OperationalError, sqlite3.DatabaseError)):
        return 503, "Database temporarily unavailable"
    if isinstance(err, (json.JSONDecodeError, KeyError, IndexError)):
        return 502, f"Unexpected API response format: {context}"
    if isinstance(err, ValueError):
        return 400, str(err)
    return 500, f"Internal error: {context}"


# --- MULTI-MODEL FALLBACK CHAIN ---
def _call_llm_with_fallback(payload_builder, timeout=120, mode='chat', report_mode=False):
    """
    按优先级依次尝试各 AI 供应商，实现自动故障转移。
    
    Args:
        payload_builder: 接收 (provider_config, model_override) 返回 (payload_dict, model_name) 的回调
        timeout: 请求超时秒数（主模型用完整超时，降级模型减半）
        mode: 用于日志标记 ('chat', 'symbol', 'clean', 'polish')
        report_mode: 是否为报告模式（控制 deepseek-v4-pro+thinking vs deepseek-v4-flash）
    
    Returns:
        (response_json, provider_name) — 成功即返回
    
    Raises:
        所有供应商都失败后抛出最后一个异常
    """
    last_error = None
    providers_tried = []
    
    for provider in AI_PROVIDERS:
        api_key = provider.get("api_key", "")
        api_base = provider.get("api_base", "")
        # 跳过未配置的供应商
        if not api_key or not api_base:
            continue
        
        # 降级模型超时减半（已有一个失败，快速失败优于长时间等待）
        actual_timeout = timeout if not providers_tried else max(timeout // 2, 30)
        
        # 决定模型名（DeepSeek V4 新命名体系）
        # 旧模型 deepseek-chat / deepseek-reasoner 将于 2026/07/24 到期
        if provider["name"] == "deepseek":
            model_override = provider.get("report_model", "deepseek-v4-pro") if report_mode else provider.get("chat_model", "deepseek-v4-flash")
        else:
            model_override = provider.get("default_model", "")
        
        try:
            payload = payload_builder(provider, model_override)
            logger.info(f"llm_call_{mode}", extra={
                "provider": provider["name"],
                "model": model_override,
                "timeout": actual_timeout,
                "retry": len(providers_tried),
            })
            
            resp = requests.post(
                api_base,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=actual_timeout,
            )
            resp.raise_for_status()
            res_json = resp.json()
            
            # 验证响应结构
            if 'choices' not in res_json or not res_json['choices']:
                raise ValueError(f"Empty choices in response from {provider['name']}")
            
            logger.info(f"llm_ok_{mode}", extra={"provider": provider["name"], "model": model_override})
            return res_json, provider["name"]
            
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError,
                json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = e
            providers_tried.append(provider["name"])
            logger.warning(f"llm_fallback_{mode}", extra={
                "provider": provider["name"],
                "error": str(e)[:200],
                "type": type(e).__name__,
                "next_try": True,
            })
            continue  # 尝试下一个供应商
        except Exception as e:
            last_error = e
            providers_tried.append(provider["name"])
            logger.error(f"llm_unexpected_{mode}", extra={
                "provider": provider["name"],
                "error": str(e)[:200],
            })
            continue
    
    # 所有供应商都失败
    logger.critical(f"llm_all_failed_{mode}", extra={
        "providers_tried": ",".join(providers_tried),
        "last_error": str(last_error)[:300] if last_error else "unknown",
    })
    raise last_error or RuntimeError(f"All AI providers failed for {mode}")



# --- DATABASE LAYER ---
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
# Persistent volume path (Zeabur mounts /data as persistent disk)
# This MUST point to the volume, otherwise data is lost on container restart
_DATA_DIR = os.environ.get("DATA_DIR", "/data")
DB_FILE = os.environ.get("DB_FILE", os.path.join(_DATA_DIR, "mirror_data.db"))
# Ensure data directory exists
os.makedirs(os.path.dirname(DB_FILE) if os.path.dirname(DB_FILE) else ".", exist_ok=True)

if DATABASE_URL:
    from backend.db import get_db as _pg_get_db, get_db_conn as _pg_get_conn
    from backend.db import init_tables as _pg_init_tables
    def get_db(): return _pg_get_db()
    def get_db_connection(): return _pg_get_conn()
    def init_db(): _pg_init_tables()
else:
    # DB_FILE already set above to /data/mirror_data.db (persistent volume)
    # Do NOT override with local path here!
    @contextmanager
    def get_db():
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_db_connection():
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                                ref_id TEXT PRIMARY KEY,
                                inviter_email TEXT,
                                count INTEGER DEFAULT 0,
                                unlocked INTEGER DEFAULT 0)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS referral_logs (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                ref_id TEXT NOT NULL,
                                visitor_ip TEXT,
                                user_agent TEXT,
                                created_at TEXT DEFAULT (datetime('now')))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
                                email TEXT,
                                status TEXT,
                                license_key TEXT,
                                timestamp REAL)''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_email ON payments(email)')
            cursor.execute('''CREATE TABLE IF NOT EXISTS chat_sessions (
                                id TEXT PRIMARY KEY,
                                user_id TEXT,
                                session_id TEXT NOT NULL,
                                dream_text TEXT DEFAULT '',
                                turn_count INTEGER DEFAULT 0,
                                status TEXT DEFAULT 'active',
                                created_at TEXT DEFAULT (datetime(\'now\')),
                                updated_at TEXT DEFAULT (datetime(\'now\')))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
                                id TEXT PRIMARY KEY,
                                session_id TEXT NOT NULL,
                                role TEXT NOT NULL,
                                content TEXT NOT NULL,
                                turn INTEGER DEFAULT 0,
                                created_at TEXT DEFAULT (datetime(\'now\')))''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)')
            cursor.execute('''CREATE TABLE IF NOT EXISTS dream_reports (
                                id TEXT PRIMARY KEY,
                                session_id TEXT NOT NULL,
                                free_content TEXT,
                                paid_content TEXT,
                                tarot_index INTEGER DEFAULT -1,
                                is_paid INTEGER DEFAULT 0,
                                created_at TEXT DEFAULT (datetime(\'now\')))''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_dream_reports_session ON dream_reports(session_id)')
        try:
            from backend.account_module import init_account_tables
            init_account_tables()
        except ImportError:
            pass

init_db()

# ── Initialize User Account System ───────────────────────
if ACCOUNT_SYSTEM_READY:
    init_account_tables()
    register_account_routes(app)
    print("[INFO] User account system initialized — /api/auth/* /api/user/* /api/license/* registered")

# --- REQUEST LOGGING MIDDLEWARE ---
@app.before_request
def log_request():
    request._start_time = time.time()

@app.after_request
def log_response(response):
    elapsed_ms = int((time.time() - getattr(request, '_start_time', time.time())) * 1000)
    logger.info("request", extra={
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "elapsed_ms": elapsed_ms,
        "ip": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", "")[:100],
    })
    return response

@app.route('/api/session/init', methods=['GET', 'POST', 'OPTIONS'])
def session_init():
    if request.method == 'OPTIONS': return _cors(make_response())
    new_sid = uuid.uuid4().hex
    is_premium = False
    auth_token = request.cookies.get('sm_auth_token')
    if auth_token:
        with get_db() as conn:
            row = conn.execute("SELECT status FROM payments WHERE email = ?", (auth_token,)).fetchone()
            if row and row['status'] == 'paid': is_premium = True
    res = make_response(jsonify({"sessionId": new_sid, "premium": is_premium, "status": "active"}))
    return _cors(res)

# ─── Chat Session Management API ───

@app.route('/api/chat/session', methods=['POST', 'OPTIONS'])
def chat_session_create():
    if request.method == 'OPTIONS': return _cors(make_response())
    import uuid as _uuid
    sid = _uuid.uuid4().hex
    sess_id = _uuid.uuid4().hex
    auth_token = request.cookies.get('sm_auth_token', '')
    user_id = ''
    if auth_token:
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(auth_token, os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026"), algorithms=["HS256"])
            user_id = payload.get("sub", "")
        except: pass
    with get_db() as conn:
        conn.execute("INSERT INTO chat_sessions (id, user_id, session_id) VALUES (?, ?, ?)",
                     (sid, user_id, sess_id))
    return _cors(jsonify({"sessionId": sess_id, "id": sid}))

@app.route('/api/chat/sessions', methods=['GET', 'OPTIONS'])
def chat_sessions_list():
    if request.method == 'OPTIONS': return _cors(make_response())
    auth_token = request.cookies.get('sm_auth_token', '')
    user_id = ''
    if auth_token:
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(auth_token, os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026"), algorithms=["HS256"])
            user_id = payload.get("sub", "")
        except: pass
    with get_db() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT id, session_id, dream_text, turn_count, status, created_at FROM chat_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (user_id,)
            ).fetchall()
        else:
            rows = []
    return _cors(jsonify({"sessions": [dict(r) for r in rows]}))

@app.route('/api/chat/session/<session_id>', methods=['GET', 'DELETE', 'OPTIONS'])
def chat_session_detail(session_id):
    if request.method == 'OPTIONS': return _cors(make_response())
    if request.method == 'DELETE':
        with get_db() as conn:
            conn.execute("UPDATE chat_sessions SET status='deleted' WHERE session_id=?", (session_id,))
        return _cors(jsonify({"status": "deleted"}))
    with get_db() as conn:
        session = conn.execute("SELECT * FROM chat_sessions WHERE session_id=?", (session_id,)).fetchone()
        if not session:
            return _cors(jsonify({"error": "session not found"}), 404)
        messages = conn.execute("SELECT role, content, turn, created_at FROM chat_messages WHERE session_id=? ORDER BY turn ASC", (session_id,)).fetchall()
        report = conn.execute("SELECT * FROM dream_reports WHERE session_id=? ORDER BY created_at DESC LIMIT 1", (session_id,)).fetchone()
    return _cors(jsonify({
        "session": dict(session),
        "messages": [dict(m) for m in messages],
        "report": dict(report) if report else None
    }))

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"error": str(e), "type": type(e).__name__}), 500, {"Access-Control-Allow-Origin": "*"}

# --- CORS CONFIGURATION ---
ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else None

def _cors(res, status=200):
    origin = request.headers.get("Origin", "")
    # 如果配置了白名单，使用白名单；否则允许常见域名（比 * 安全）
    if ALLOWED_ORIGINS:
        if origin in ALLOWED_ORIGINS:
            res.headers["Access-Control-Allow-Origin"] = origin
    elif origin and ("api-tokenmaster.com" in origin or "localhost" in origin or "127.0.0.1" in origin):
        res.headers["Access-Control-Allow-Origin"] = origin
    else:
        res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    res.headers["Vary"] = "Origin"
    return res, status

@app.route('/')
def index():
    if os.path.exists(HTML_FILE):
        return send_file(HTML_FILE)
    return "<h1>Mirror Sanctum Error: HTML File Missing</h1>", 404

# --- HEALTH CHECK ---
@app.route('/health')
def health():
    """健康检查端点 — 用于负载均衡器和监控系统"""
    import time as _time
    health_data = {
        "status": "ok",
        "service": "subconscious-mirror",
        "version": "v34.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # 检查数据库连接
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        health_data["database"] = "ok"
    except Exception as e:
        health_data["database"] = f"error: {e}"
        health_data["status"] = "degraded"
    # 检查各 AI 供应商连通性
    ai_providers_status = {}
    for provider in AI_PROVIDERS:
        api_key = provider.get("api_key", "")
        api_base = provider.get("api_base", "")
        if not api_key or not api_base:
            continue
        try:
            base_url = api_base.replace("/chat/completions", "").rstrip("/")
            resp = requests.get(base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
            ai_providers_status[provider["name"]] = "ok" if resp.status_code < 500 else f"HTTP {resp.status_code}"
        except Exception as e:
            ai_providers_status[provider["name"]] = f"unreachable: {str(e)[:80]}"
    health_data["ai_providers"] = ai_providers_status
    # 整体 AI 状态：至少有一个可用即算 ok
    healthy_providers = [k for k, v in ai_providers_status.items() if v == "ok"]
    health_data["ai_api"] = "ok" if healthy_providers else ai_providers_status.get("deepseek", "unreachable")
    return _cors(jsonify(health_data))

@app.route('/api/referral/init', methods=['POST', 'OPTIONS'])
def init_ref():
    if request.method == 'OPTIONS': return _cors(make_response())
    inviter_email = request.json.get('email', '')
    ref_id = f"ref_{int(time.time())}_{os.urandom(2).hex()}"
    with get_db() as conn:
        conn.execute("INSERT INTO referrals (ref_id, inviter_email, count) VALUES (?, ?, 0)", (ref_id, inviter_email))
    return _cors(jsonify({"status": "ready", "refId": ref_id}))


@app.route('/api/referral/status', methods=['GET'])
def referral_status():
    ref_id = request.args.get('refId')
    with get_db() as conn:
        row = conn.execute("SELECT count, unlocked FROM referrals WHERE ref_id = ?", (ref_id,)).fetchone()
    return _cors(jsonify({"count": row["count"] if row else 0, "unlocked": row["unlocked"] if row else 0}))

@app.route('/api/referral/click', methods=['POST'])
def referral_click():
    inviter_id = request.json.get('refBy')
    visitor_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'unknown')
    if not inviter_id: return _cors(jsonify({"status": "ignored"}))
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO referral_logs (ref_id, visitor_ip, user_agent) VALUES (?, ?, ?)", 
                         (inviter_id, visitor_ip, user_agent))
            conn.execute("UPDATE referrals SET count = count + 1 WHERE ref_id = ?", (inviter_id,))
            row = conn.execute("SELECT count, inviter_email, unlocked FROM referrals WHERE ref_id = ?", (inviter_id,)).fetchone()
            if row and row['count'] >= 2 and row['unlocked'] == 0 and row['inviter_email']:
                conn.execute("INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', 'referral-unlock', ?)",
                             (row['inviter_email'], time.time()))
                conn.execute("UPDATE referrals SET unlocked = 1 WHERE ref_id = ?", (inviter_id,))
        return _cors(jsonify({"status": "counted", "count": row["count"] if row else 0}))
    except sqlite3.IntegrityError:
        return _cors(jsonify({"status": "ignored"}))

# ─── Tarot AI Reading ──────────────────────────────────────────────────────────
TAROT_CARDS = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World"
]

@app.route('/api/tarot/reading', methods=['POST', 'OPTIONS'])
@limiter.limit("20 per minute")
def tarot_reading():
    if request.method == 'OPTIONS':
        return _cors(make_response())
    req_data = request.json or {}
    card_indices = req_data.get('cards', [])
    topic = req_data.get('topic', '')
    lang = req_data.get('lang', 'zh')
    
    if not card_indices or len(card_indices) != 3:
        return _cors(jsonify({"error": "Need exactly 3 card indices"}), 400)
    if any(i < 0 or i > 21 for i in card_indices):
        return _cors(jsonify({"error": "Card indices must be 0-21"}), 400)
    
    card_names_en = [TAROT_CARDS[i] for i in card_indices]
    
    if lang == 'zh':
        system_content = (
            "你是一位融合东西方智慧的资深塔罗解读师。你的风格专业、富有洞察力，"
            "善于将古老的塔罗智慧与现代生活相结合，给出有建设性的指引。\n\n"
            "用户抽取了一个三牌阵（过去-现在-未来），请你根据这三张牌的组合，"
            "以及用户提出的问题/主题，给出完整且有深度的解读。\n\n"
            "解读要求：\n"
            "1. 先针对「过去」位置的第一张牌进行解读，解释它的能量如何影响了当前处境\n"
            "2. 再针对「现在」位置的第二张牌进行解读，分析当下的课题与机遇\n"
            "3. 再针对「未来」位置的第三张牌进行解读，揭示可能的发展方向\n"
            "4. 最后给出这三张牌组合在一起的整体叙事——它们讲述了一个怎样的故事？\n"
            "5. 结尾给出一句有启发性的建议或箴言\n\n"
            "格式要求：使用自然段落，每部分用 **加粗标题** 区分。语言温暖但不浮夸，"
            "保持专业塔罗解读的风格。每个段落控制在3-5句。\n\n"
            "不要提及「作为AI」或「作为语言模型」，直接以塔罗解读师的身份回应。"
        )
        user_msg = f"问题/主题：{topic or '个人成长'}\n三张牌：{card_names_en[0]}（过去）、{card_names_en[1]}（现在）、{card_names_en[2]}（未来）\n\n请给出完整解读。"
    else:
        system_content = (
            "You are a professional tarot reader blending Eastern and Western wisdom. "
            "Your style is insightful, professional, and practical. "
            "You give constructive guidance based on the cards.\n\n"
            "The user has drawn a 3-card spread (Past-Present-Future). "
            "Give a complete, meaningful interpretation.\n\n"
            "Structure:\n"
            "1. Interpret the first card (Past) and its influence\n"
            "2. Interpret the second card (Present) — current challenges and opportunities\n"
            "3. Interpret the third card (Future) — potential direction\n"
            "4. Overall narrative — what story do these three cards tell together?\n"
            "5. End with an inspiring suggestion or advice\n\n"
            "Format: Use natural paragraphs with **bold headers**. "
            "Keep each section to 3-5 sentences. Be warm but professional.\n"
            "Do not mention being an AI. Speak as a tarot reader directly."
        )
        user_msg = f"Question/Topic: {topic or 'personal growth'}\nThree cards: {card_names_en[0]} (Past), {card_names_en[1]} (Present), {card_names_en[2]} (Future)\n\nPlease provide the complete reading."
    
    try:
        def _build_tarot_payload(provider, model_override):
            payload = {
                "model": model_override,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_msg}
                ],
                "max_tokens": 2048,
            }
            if provider["name"] == "deepseek":
                payload["thinking"] = {"type": "disabled"}
                payload["temperature"] = 0.7
            else:
                payload["temperature"] = 0.7
            return payload
        
        res_json, used_provider = _call_llm_with_fallback(
            _build_tarot_payload, timeout=45, mode='tarot', report_mode=False
        )
        ai_msg = res_json['choices'][0]['message']
        text = ai_msg.get('content') or ai_msg.get('reasoning_content') or ""
        return _cors(jsonify({"reading": text, "cards": card_names_en}))
    except Exception as e:
        app.logger.error(f"[Tarot] AI call failed: {e}")
        # Fallback to template-based reading
        return _cors(jsonify({"error": str(e)}), 500)


@app.route('/api/chat', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def chat():
    if request.method == 'OPTIONS': return _cors(make_response())
    req_data = request.json
    messages = req_data.get('messages', [])
    lang = req_data.get('lang', 'zh')
    user_email = req_data.get('email')
    sm_token = req_data.get('token', '')
    session_id = req_data.get('session_id', '')
    is_premium = False

    # Check SMAuth JWT token for premium status
    if sm_token:
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(sm_token, os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026"), algorithms=["HS256"])
            user_id = payload.get("sub", "")
            if user_id:
                with get_db() as conn:
                    rows = conn.execute(
                        "SELECT total_count, used_count, expires_at FROM entitlements WHERE user_id=? ORDER BY created_at DESC",
                        (user_id,)
                    ).fetchall()
                    for r in rows:
                        if r["expires_at"] and datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc):
                            continue
                        if r["total_count"] < 0 or r["used_count"] < r["total_count"]:
                            is_premium = True
                            break
        except Exception as e:
            print(f"[Chat] JWT check failed: {e}")

    # Fallback: check old payments table by email
    if not is_premium and user_email:
        with get_db() as conn:
            row = conn.execute("SELECT status FROM payments WHERE email = ?", (user_email,)).fetchone()
            if row and row['status'] == 'paid': is_premium = True
    user_msg_count = len([m for m in messages if m['role'] == 'user'])
    
    # ─── Auto-save messages to DB if session_id provided ───
    def _save_chat_msg(role, content, turn_num):
        if not session_id: return
        try:
            import uuid as _uuid
            with get_db() as conn:
                conn.execute("INSERT INTO chat_messages (id, session_id, role, content, turn) VALUES (?, ?, ?, ?, ?)",
                             (_uuid.uuid4().hex, session_id, role, content, turn_num))
                conn.execute("UPDATE chat_sessions SET turn_count=?, updated_at=datetime('now') WHERE session_id=?",
                             (max(turn_num, 0), session_id))
        except Exception as e:
            print(f"[Chat] Save msg failed: {e}")
    
    def _save_dream_report(free_part, paid_part, tarot_idx):
        if not session_id: return
        try:
            import uuid as _uuid
            with get_db() as conn:
                conn.execute("INSERT INTO dream_reports (id, session_id, free_content, paid_content, tarot_index, is_paid) VALUES (?, ?, ?, ?, ?, ?)",
                             (_uuid.uuid4().hex, session_id, free_part, paid_part, tarot_idx, 1 if is_premium else 0))
        except Exception as e:
            print(f"[Chat] Save report failed: {e}")
    
    def _update_session_dream(text):
        if not session_id or not text: return
        try:
            with get_db() as conn:
                conn.execute("UPDATE chat_sessions SET dream_text=? WHERE session_id=?", (text[:500], session_id))
        except Exception as e:
            print(f"[Chat] Update dream_text failed: {e}")
    
    # --- Input validation: reject meaningless / garbage input ---
    if messages and messages[-1]['role'] == 'user':
        raw_input = messages[-1]['content'].strip()
        # Extract only the dream description: strip "Dream: " prefix and remove [...] sections
        dream_core = raw_input
        if dream_core.startswith('Dream:'):
            dream_core = dream_core[6:].strip()
        # Remove all [bracketed sections] (Atmosphere, Environment, Symbols)
        import re as _re
        dream_core = _re.sub(r'\[.*?\]', '', dream_core).strip()
        # Remove all common punctuation and whitespace for pattern detection
        cleaned = ''.join(c for c in dream_core if c.isalnum() or '\u4e00' <= c <= '\u9fff')
        # Rule 1: too short after cleaning
        if len(cleaned) < 3:
            return _cors(jsonify({"mode": "question", "content":
                "请描述一个真实的梦境，哪怕只是片段。" if lang == 'zh' else
                "Please describe an actual dream, even just a fragment."
            }))
        # Rule 2: all same character repeated (e.g. "11111", "啊啊啊啊")
        if len(set(cleaned)) == 1:
            return _cors(jsonify({"mode": "question", "content":
                "这看起来不像是真实的梦境内容。请分享你梦到的场景、人物或感受。" if lang == 'zh' else
                "This doesn't look like a real dream. Please share a scene, character, or feeling from your dream."
            }))
        # Rule 3: only numbers
        if cleaned.isdigit():
            return _cors(jsonify({"mode": "question", "content":
                "数字本身不是梦境。请描述你梦中的画面、故事或感受。" if lang == 'zh' else
                "Numbers alone aren't a dream. Please describe the images, story, or feelings from your dream."
            }))
        # Rule 4: only punctuation / emoji / whitespace
        if len(cleaned) == 0 and len(dream_core) < 6:
            return _cors(jsonify({"mode": "question", "content":
                "请用文字描述你的梦境。" if lang == 'zh' else
                "Please describe your dream in words."
            }))
    
    mode = 'question' if user_msg_count < 5 else 'report'
    system_content = (
        "You are a Mysterious Dream Oracle — a fusion of Carl Jung's analytical psychology, "
        "the Hall/Van de Castle dream coding system, and Eastern symbolic wisdom. "
        "Your tone: poetic, precise, mildly cryptic — never vague or generic.\n\n"
        "The user may provide structured context in their message — "
        "you MUST USE this data when present:\n"
        "1. [Atmosphere:] — Lucidity level of the dream. Use this to calibrate how aware the dreamer was.\n"
        "2. [DreamType:] — Type of dream (e.g. ordinary, lucid, nightmare, repeating). "
        "Adjust your analysis framework accordingly.\n"
        "3. [Stress:] — User's current stress level. Use this to contextualize dream tension "
        "and connect to waking-life pressure points.\n"
        "4. [Symbols:] — Keywords the user explicitly associated with the dream. "
        "Use these as your starting point for symbol decoding — they are the user's own signposts.\n"
        "NEVER ask the user to clarify these details — they are already provided and must be incorporated "
        "into your analysis directly.\n\n"
        "IMPORTANT — The user's dream text may come from voice input and lacks punctuation. "
        "You MUST infer sentence boundaries, tone shifts, and emotional transitions from the text flow.\n\n"
    )
    if mode == 'question':
        system_content += (
            "Rule: Ask exactly ONE short, sharp question that targets a specific, unexplored dimension of the dream.\n\n"
            "=== QUESTIONING FRAMEWORK (pick ONE dimension per turn, rotate through them) ===\n"
            "1. SENSORY ANCHOR: Ask about one specific sensory detail the user mentioned (\"You said the walls were wet — did it feel like sweat, condensation, or something else?\") — NOT \"What did you feel?\"\n"
            "2. EMOTIONAL TURNING POINT: Ask about the moment the emotion changed (\"You went from calm to terrified when the figure appeared — what exactly shifted in that second?\") — NOT \"How did you feel?\"\n"
            "3. CHARACTER RELATIONSHIP: Ask about a person/creature and its felt connection (\"The old woman in the doorway — did she feel familiar, like someone you know, or was she a stranger with your mother's eyes?\") — NOT \"Who was that?\"\n"
            "4. ENVIRONMENTAL METAPHOR: Ask about the setting's symbolic resonance (\"The endless staircase — did it feel like it was going somewhere or just repeating? Like a maze or a ritual?\") — NOT \"What did the place look like?\"\n"
            "5. UNRESOLVED TENSION: Ask about the dream's unresolved core (\"You woke up just as you reached for the door — what did you expect to find on the other side in that instant before waking?\") — NOT \"What happened next?\"\n\n"
            "=== FORBIDDEN QUESTION PATTERNS (NEVER use these) ===\n"
            "- \"Can you tell me more about...\" ❌ (too vague)\n"
            "- \"What did that mean to you?\" ❌ (lazy, puts work on user)\n"
            "- \"How did that make you feel?\" ❌ (user already provided mood data)\n"
            "- \"Could you describe...\" ❌ (user already described it)\n"
            "- Any question that could be answered with \"yes\" or \"no\" ❌\n\n"
            "=== USING STRUCTURED DATA FOR BETTER QUESTIONS ===\n"
            "The [Atmosphere:], [DreamType:], [Stress:], and [Symbols:] sections contain rich data. Use them:\n"
            "- If [Symbols:] mentions 'water' or 'ocean', ask about the quality of the water, not whether there was water.\n"
            "- If [Atmosphere:] shows high lucidity, ask about what the user chose to do — they were aware they were dreaming.\n"
            "- If [Stress:] is high, connect the dream's tension to waking-life pressure points.\n"
            "- If [DreamType:] is 'repeating', explore what might be unresolved.\n\n"
            "=== EXAMPLES OF GOOD QUESTIONS ===\n"
            "✅ \"The red door only appeared after you counted to three — did the act of counting feel protective, like a ritual, or did the number itself matter?\"\n"
            "✅ \"Your childhood home had no furniture, but you knew exactly where everything should be — was the emptiness comforting or accusing?\"\n"
            "✅ \"The dog with human eyes followed you through every room but never barked — what did its silence tell you?\"\n\n"
            "Always mirror the user's language (if they wrote in Chinese, respond in Chinese; if English, respond in English)."
        )
    else:
        system_content += (
            "🔴 LANGUAGE IS NON-NEGOTIABLE: Detect the user's language from their FIRST message. "
            "If the user writes in CHINESE (any dialect), EVERYTHING in your report — "
            "including ALL section headers, ALL body text, the tarot card name, and the prophecy — MUST be in Chinese. "
            "ZERO English words allowed in section headers. Use these EXACT Chinese headers: "
            "**心理学分析**, **符号解码**, **情感地图**, **塔罗指引**, **现实映照**, **行动智慧**, **预言**. "
            "If the user writes in ENGLISH, use English headers: "
            "**Psychological Analysis**, **Symbol Decoding**, **Emotional Landscape**, **Tarot Guidance**, "
            "**Real-Life Mirror**, **Actionable Wisdom**, **Prophecy**. "
            "NEVER mix languages. This is the #1 quality requirement.\n\n"
            "Rule: Deliver a destiny report in TWO PARTS. "
            "Separate with '[PROPHECY_DIVIDER]'.\n\n"
            "PART 1 (free — concise preview, 1-2 paragraphs only):\n"
            "1. [DREAM NARRATIVE] Restate the user's dream in a poetic, refined way — "
            "incorporate the [Atmosphere:] lucidity data into the narrative tone. "
            "KEEP THIS SHORT — just one vivid paragraph that hints at deeper analysis to come. "
            "End with a teaser line like 'The full psychological analysis, symbol decoding, and emotional landscape are revealed in the complete report.'\n\n"
            "PART 2 (paid — comprehensive full analysis, 7-10 paragraphs, MUST deliver clear value):\n"
            "2. [PSYCHOLOGICAL ANALYSIS / 心理学分析] Deep analysis from Jungian/analytical psychology perspective. "
            "Identify archetypes, shadow elements, anima/animus, and collective unconscious patterns. "
            "Use the [Stress:] and [DreamType:] data to contextualize why "
            "this dream is emerging now in the user's life. "
            "⚠️ Section header MUST be '**心理学分析**' if user input is Chinese, or '**Psychological Analysis**' if English.\n"
            "3. [SYMBOL DECODING / 符号解码] Break down 2-3 key symbols from the dream — "
            "what they represent personally, culturally, and archetypally. "
            "ALWAYS start with the [Symbols:] keywords as your primary reference, then expand beyond them. "
            "⚠️ Section header MUST be '**符号解码**' if Chinese, or '**Symbol Decoding**' if English.\n"
            "4. [EMOTIONAL LANDSCAPE / 情感地图] Map the emotional journey through the dream — "
            "where emotions shifted, what triggered them, what they reveal. "
            "Cross-reference the user's [Atmosphere:] lucidity rating with "
            "the actual dream narrative to identify discrepancies the user may not have noticed. "
            "⚠️ Section header MUST be '**情感地图**' if Chinese, or '**Emotional Landscape**' if English.\n"
            "5. [TAROT GUIDANCE / 塔罗指引] Based on the dream's core energy, select the most fitting Major Arcana tarot card. "
            "Explain WHY this card matches the dream, its upright/reversed meaning, "
            "and what guidance it offers the dreamer. "
            "CRITICAL: Include the card's name AND number in the heading — e.g. '**塔罗指引：愚者（The Fool, 00）**' so the oracle can later reference it precisely. "
            "⚠️ Section header MUST contain '塔罗' if Chinese, or 'Tarot Guidance' if English.\n"
            "6. [REAL-LIFE MIRROR / 现实映照] Connect the dream patterns to the user's waking life — "
            "what unresolved situations, relationships, or inner conflicts may be surfacing. "
            "Use the [Stress:] level and [DreamType:] to ground this connection "
            "in the user's actual life context rather than generic advice. "
            "⚠️ Section header MUST be '**现实映照**' if Chinese, or '**Real-Life Mirror**' if English.\n"
            "7. [ACTIONABLE WISDOM / 行动智慧] Provide 3-5 concrete, personalized actions the dreamer can take. "
            "⚠️ Section header MUST be '**行动智慧**' if Chinese, or '**Actionable Wisdom**' if English.\n"
            "8. [PROPHECY / 预言] A single, cryptic, poetic closing line — like an oracle's final word. "
            "The prophecy MUST distill the ESSENCE of the specific Tarot card you selected. "
            "It must NOT be generic. It must directly embody the card's core theme, symbolic imagery, and wisdom. "
            "Examples of card-specific prophecies: "
            "The Fool — 'The edge greets you not as a warning, but as a wing.' | "
            "Temperance — 'The cup tilted, and the river learned to walk.' | "
            "Death — 'The door you mourn was never a door — only the absence of one.' | "
            "The Star — 'You poured sorrow into the well; the well remembered your name.' | "
            "The Tower — 'Lightning doesn't destroy the tower — it reveals the sky the tower was hiding.'\n\n"
            "IMPORTANT — After PART 2, on a new line by itself, output the tarot card number "
            "in this exact format: [TAROT: N] where N is the number of the Major Arcana card "
            "(00-21) you selected for the user. For example: [TAROT: 12] for The Hanged Man. "
            "This is used to display the correct tarot card image, so it must be accurate.\n\n"
            "CRITICAL LANGUAGE RULE: You MUST write the ENTIRE report in the SAME language as the user's input. "
            "If the user writes in Chinese, ALL section headers and content MUST be in Chinese — "
            "e.g. '**心理学分析**' NOT '**Psychological Analysis**', "
            "'**符号解码**' NOT '**Symbol Decoding**', "
            "'**情感地图**' NOT '**Emotional Landscape**', "
            "'**塔罗指引**' NOT '**Tarot Guidance**', "
            "'**现实映照**' NOT '**Real-Life Mirror**', "
            "'**行动智慧**' NOT '**Actionable Wisdom**', "
            "'**预言**' NOT '**Prophecy**'. "
            "Do NOT mix languages. The report must feel native to the user. "
            "Format: Each section should have a bold header in the user's language. "
            "PART 1 should feel like a tempting preview — just enough to intrigue. "
            "PART 2 should feel like the full feast — deep, detailed, and clearly worth paying for."
        )
    try:
        report_mode = (mode == 'report')
        timeout_secs = 180 if report_mode else 120
        
        def _build_chat_payload(provider, model_override):
            payload = {
                "model": model_override,
                "messages": [{"role": "system", "content": system_content}] + messages,
                "max_tokens": 4096,
            }
            # DeepSeek V4 Thinking 控制
            if provider["name"] == "deepseek":
                if report_mode:
                    # 报告模式：用 deepseek-v4-pro + thinking 做深度推理
                    payload["thinking"] = {"type": "enabled"}
                    payload["reasoning_effort"] = "high"
                    # Thinking 模式不支持 temperature
                else:
                    # 问答模式：deepseek-v4-flash，关闭 thinking 节省成本加速
                    payload["thinking"] = {"type": "disabled"}
                    payload["temperature"] = 0.5
            else:
                # 非 DeepSeek 降级模型
                payload["temperature"] = 0.7
            return payload
        
        res_json, used_provider = _call_llm_with_fallback(
            _build_chat_payload, timeout=timeout_secs, mode='chat', report_mode=report_mode
        )
        
        ai_msg = res_json['choices'][0]['message']
        text = ai_msg.get('content') or ai_msg.get('reasoning_content') or ""
        # Save messages to DB
        if messages and messages[-1]['role'] == 'user':
            _save_chat_msg('user', messages[-1]['content'], user_msg_count - 1)
            if user_msg_count == 1:
                _update_session_dream(messages[-1]['content'])
        _save_chat_msg('ai', text, user_msg_count)
        if mode == 'question': return _cors(jsonify({"mode": "question", "content": text}))
        else:
            # 支持多种分隔符格式（AI 有时会把 --- 理解成 Markdown 语法变体）
            sep_match = re.split(
                r'\[PROPHECY_DIVIDER\]|\*{1,3}PROPHECY_START\*{1,3}|-{2,}PROPHECY_START-{2,}',
                text, maxsplit=1
            )
            free = sep_match[0].strip()
            if len(sep_match) > 1 and sep_match[1].strip():
                paid = sep_match[1].strip()
            else:
                paid = (
                    "解锁完整命运报告，获取塔罗指引、现实映照、行动建议与命运预言。" if lang == 'zh'
                    else "Unlock the full destiny report for Tarot guidance, real-life reflections, action steps, and your personal prophecy."
                )
            # If premium user generated a report, consume one entitlement
            if is_premium and sm_token:
                try:
                    import jwt as pyjwt
                    payload = pyjwt.decode(sm_token, os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026"), algorithms=["HS256"])
                    uid = payload.get("sub", "")
                    if uid:
                        with get_db() as conn:
                            rows = conn.execute(
                                "SELECT id, total_count, used_count FROM entitlements WHERE user_id=? ORDER BY created_at DESC",
                                (uid,)
                            ).fetchall()
                            for r in rows:
                                if r["total_count"] > 0 and r["used_count"] < r["total_count"]:
                                    conn.execute("UPDATE entitlements SET used_count=used_count+1 WHERE id=?", (r["id"],))
                                    conn.commit()
                                    break
                except Exception as e:
                    print(f"[Chat] Entitlement consume failed: {e}")

            # Save report to DB
            tarot_match = re.search(r'\[TAROT:\s*(\d+)\]', paid)
            tarot_idx = int(tarot_match.group(1)) if tarot_match else -1
            _save_dream_report(free, paid, tarot_idx)

            return _cors(jsonify({"mode": "report", "status": "full" if is_premium else "partial", "data": {"free_part": free, "paid_part": paid}}))
    except requests.Timeout:
        logger.error("chat_all_timeout", extra={"user_msgs": user_msg_count, "lang": lang})
        return _cors(jsonify({"error": "All AI services are overloaded. Please try again."}), 503)
    except (requests.ConnectionError, requests.HTTPError) as e:
        logger.error("chat_all_unreachable", extra={"error": str(e)[:200]})
        return _cors(jsonify({"error": "All AI services are unreachable. Please try again shortly."}), 502)
    except Exception as e:
        logger.error("chat_all_failed", extra={"error": str(e)[:300], "type": type(e).__name__})
        return _cors(jsonify({"error": "All AI services are currently unavailable. Please try again later."}), 500)

@app.route('/api/symbol-lookup', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def symbol_lookup():
    if request.method == 'OPTIONS': return _cors(make_response())
    req_data = request.json
    symbol = req_data.get('symbol', '').strip()
    lang = req_data.get('lang', 'en')
    if not symbol: return _cors(jsonify({"error": "Symbol is required"}), 400)
    system_content = f"You are a dream symbol oracle. The user asks about the dream symbol '{symbol}'. Provide a concise but insightful interpretation (2-4 paragraphs) covering: common psychological meaning, archetypal/cultural significance, and what this symbol may reveal about the dreamer's inner state. IMPORTANT: Use a blank line (double newline) between each paragraph to separate them clearly. Do NOT ask follow-up questions. Respond in {'Chinese' if lang == 'zh' else 'English'}."
    try:
        def _build_symbol_payload(provider, model_override):
            payload = {
                "model": model_override,
                "messages": [{"role": "system", "content": system_content}],
                "max_tokens": 1024,
            }
            if provider["name"] == "deepseek":
                payload["thinking"] = {"type": "disabled"}  # 符号查询不需要链式推理
                payload["temperature"] = 0.7
            else:
                payload["temperature"] = 0.7
            return payload
        res_json, used_provider = _call_llm_with_fallback(
            _build_symbol_payload, timeout=60, mode='symbol'
        )
        ai_msg = res_json['choices'][0]['message']
        text = ai_msg.get('content') or ai_msg.get('reasoning_content') or ""
        return _cors(jsonify({"symbol": symbol, "interpretation": text}))
    except Exception as e:
        logger.error("symbol_lookup_error", extra={"symbol": symbol, "error": str(e)})
        return _cors(jsonify({"error": "Symbol lookup failed. All AI services unavailable."}), 500)

@app.route('/api/clean-text', methods=['POST', 'OPTIONS'])
@limiter.limit("20 per minute")
def clean_text():
    """AI-powered voice transcript cleanup — removes filler words, adds punctuation, fixes flow."""
    if request.method == 'OPTIONS': return _cors(make_response())
    req_data = request.json
    raw_text = req_data.get('text', '').strip()
    lang = req_data.get('lang', 'zh')
    if not raw_text: return _cors(jsonify({"cleaned": ""}))
    if len(raw_text) < 3: return _cors(jsonify({"cleaned": raw_text}))

    if lang == 'zh':
        system_prompt = (
            "你是一个语音整理助手。把用户口语化的语音转文字整理成通顺、逻辑清楚的文本。\n\n"
            "规则：\n"
            "1. 删除语气词：嗯、呃、那个、这个、就是说、反正、怎么说呢、之类的\n"
            "2. 删除重复词：\"我我我\" → \"我\"\n"
            "3. 加标点：。？！，根据语气加上\n"
            "4. 如果句子太乱，适当调整语序让逻辑清楚\n"
            "5. 保持原意，不要添加额外内容，不要分析评论\n"
            "6. 直接输出整理后的文本，不要加任何前缀/后缀\n"
        )
    else:
        system_prompt = (
            "You are a speech cleaner. Clean up spoken transcriptions into fluent, logically clear text.\n\n"
            "Rules:\n"
            "1. Remove filler words: um, uh, like, you know, I mean, sort of, actually, basically, literally\n"
            "2. Remove word repetitions: \"I I I went\" → \"I went\"\n"
            "3. Add proper punctuation: . ! ? based on tone\n"
            "4. If sentences are jumbled, adjust the order to make logic clear\n"
            "5. Keep original meaning — no added commentary\n"
            "6. Output ONLY the cleaned text — no prefixes or suffixes\n"
        )

    try:
        def _build_clean_payload(provider, model_override):
            payload = {
                "model": model_override,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text}
                ],
                "max_tokens": 2048,
            }
            if provider["name"] == "deepseek":
                payload["thinking"] = {"type": "disabled"}  # 语音清理不需要链式推理
                payload["temperature"] = 0.1
            else:
                payload["temperature"] = 0.1
            return payload
        res_json, used_provider = _call_llm_with_fallback(
            _build_clean_payload, timeout=30, mode='clean'
        )
        ai_msg = res_json['choices'][0]['message']
        cleaned = (ai_msg.get('content') or ai_msg.get('reasoning_content') or raw_text).strip()
        # Safety: if the AI returned something weird or empty, fall back to raw
        if not cleaned or len(cleaned) < len(raw_text) * 0.3:
            cleaned = raw_text
        return _cors(jsonify({"cleaned": cleaned, "raw": raw_text}))
    except Exception as e:
        logger.error("clean_text_error", extra={"error": str(e)})
        # On any error, return the raw text so the user isn't blocked
        return _cors(jsonify({"cleaned": raw_text, "raw": raw_text, "error": str(e)}))

# --- Filler-word removal patterns (Chinese speech fillers) ---
# Filler word sets (characters and phrases common in Chinese speech fillers)
_FILLER_CHARS = frozenset('啊哦呃嗯嘛呢吧啦呀哟嘿诶嘶哈呵咳呣噢喔呗吖嘞啰')
_FILLER_PHRASES = frozenset({'就是说', '反正', '怎么说呢', '这样子', '对不对', '是吧', '那个', '然后呢', '那啥', '怎么说'})

def _polish_via_llm(text, lang='zh'):
    """Use AI to add punctuation, correct errors, and clean up fillers. Auto-fallback on failure."""
    if lang != 'zh' or not text:
        return text
    # 检查是否至少有一个 AI 供应商可用来做后处理（否则跳过）
    has_provider = any(
        p.get("api_key") and p.get("api_base")
        for p in AI_PROVIDERS
    )
    if not has_provider:
        return text
    system_prompt = (
        "你是中文语音识别后处理助手。给你一段没有标点符号的语音转文字结果，请做以下处理：\n"
        "1. 添加正确的标点符号（句号、逗号、问号、感叹号等）\n"
        "2. 删除无意义的语气词和口语填充词（啊、哦、呃、嗯、嘛、呢、吧、啦、呀 等，但保留有语法功能的句尾语气词如'吗'、'呢'表疑问）\n"
        "3. 修正明显的同音字/错别字错误\n"
        "4. 保持原意不变，不要添加、删除或改写任何实质性内容\n"
        "5. 只返回处理后的文本，不要任何前缀、后缀或解释\n"
    )
    try:
        def _build_polish_payload(provider, model_override):
            payload = {
                "model": model_override,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "max_tokens": 1024,
            }
            if provider["name"] == "deepseek":
                payload["thinking"] = {"type": "disabled"}
                payload["temperature"] = 0.1
            else:
                payload["temperature"] = 0.1
            return payload
        res_json, used_provider = _call_llm_with_fallback(
            _build_polish_payload, timeout=8, mode='polish'
        )
        polished = (res_json['choices'][0]['message'].get('content') or text).strip()
        polished = polished.strip('"\'').strip()
        return polished if polished else text
    except Exception as e:
        logger.warning(f"_polish_via_llm all providers failed: {e}")
        return text


# --- WHISPER TRANSCRIPTION (audio → text via WHISPER_API_BASE) ---
@app.route('/api/transcribe', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def transcribe():
    """Transcribe audio via WHISPER_API_BASE endpoint."""
    if request.method == 'OPTIONS': return _cors(make_response())
    if 'audio' not in request.files:
        return _cors(jsonify({"error": "No audio file"}), 400)
    audio_file = request.files['audio']
    lang = request.form.get('lang', 'zh')

    # Fallback: if WHISPER_API_BASE not configured, return empty gracefully
    if not WHISPER_API_BASE:
        return _cors(jsonify({"text": ""}))

    try:
        # Send audio directly to Whisper API
        files = {'file': (audio_file.filename or 'audio.webm', audio_file.read(), audio_file.content_type or 'audio/webm')}
        headers = {'Authorization': f'Bearer {WHISPER_API_KEY}'}
        data = {'model': 'whisper-1', 'language': lang}

        resp = requests.post(WHISPER_API_BASE, headers=headers, files=files, data=data, timeout=30)
        resp.raise_for_status()
        res_json = resp.json()
        raw_text = res_json.get('text', '').strip()
        print(f"[Whisper API] Raw ({lang}): {raw_text[:120] if raw_text else '(empty)'}")

        if not raw_text:
            return _cors(jsonify({"text": ""}))

        # Polish via LLM (add punctuation, fix errors)
        polished = _polish_via_llm(raw_text, lang)
        print(f"[Whisper API] Polished: {polished[:120]}")

        return _cors(jsonify({"text": polished}))
    except requests.Timeout:
        logger.error("whisper_timeout")
        return _cors(jsonify({"error": "Voice transcription timed out. Please try again or type your dream."}), 503)
    except requests.ConnectionError:
        logger.error("whisper_connection_error")
        return _cors(jsonify({"error": "Voice service unreachable. Please type your dream instead."}), 502)
    except requests.HTTPError as e:
        logger.error("whisper_http_error", extra={"status": e.response.status_code if hasattr(e, 'response') else 'unknown'})
        return _cors(jsonify({"error": "Voice transcription failed. Please type your dream instead."}), 502)
    except Exception as e:
        logger.error("whisper_unexpected_error", extra={"error": str(e)})
        import traceback; traceback.print_exc()
        return _cors(jsonify({"error": "Voice processing error. Please type your dream."}), 500)

@app.route('/api/verify-license', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def verify_license():
    if request.method == 'OPTIONS': return _cors(make_response())
    data = request.json
    license_key = data.get('license_key')
    # Test mode: only enabled when ENABLE_TEST_MODE=1
    if TEST_LICENSE_KEY and license_key == TEST_LICENSE_KEY:
        email = data.get('email') or 'test@mirror.local'
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, ?, ?, ?)", (email, 'paid', license_key, time.time()))
        return _cors(jsonify({"status": "unlocked", "email": email}))
    try:
        res = requests.post("https://api.gumroad.com/v2/licenses/verify", data={"product_permalink": GUMROAD_PERMALINK, "license_key": license_key}, timeout=10)
        res_data = res.json()
        if res_data.get('success') is True:
            email = res_data['purchase']['email']
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, ?, ?, ?)", (email, 'paid', license_key, time.time()))
            return _cors(jsonify({"status": "unlocked", "email": email}))
        return _cors(jsonify({"status": "failed", "message": "Invalid license key"}), 400)
    except requests.Timeout:
        return _cors(jsonify({"error": "License verification timed out. Please try again."}), 503)
    except requests.ConnectionError:
        return _cors(jsonify({"error": "Cannot reach license server. Please try again later."}), 502)
    except (json.JSONDecodeError, KeyError):
        return _cors(jsonify({"error": "License verification returned unexpected data."}), 502)
    except Exception as e:
        logger.error("verify_license_error", extra={"error": str(e)})
        return _cors(jsonify({"error": "License verification failed. Please try again."}), 500)

@app.route('/api/check-premium', methods=['GET'])
def check_premium():
    email = request.args.get('email')
    with get_db() as conn:
        row = conn.execute("SELECT status FROM payments WHERE email = ?", (email,)).fetchone()
    if row and row['status'] == 'paid': return _cors(jsonify({"status": "unlocked"}))
    return _cors(jsonify({"status": "locked"}))

# --- PAYPAL WEBHOOK ---

def _send_email_with_retry(send_func, email, data, lang='en', max_retries=3, backoff=2):
    """
    带重试的邮件发送。
    send_func: callable(email, data, lang) → (success: bool, error: str)
    返回: (success: bool, error: str)
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            success, error = send_func(email, data, lang)
            if success:
                return True, None
            last_error = error
        except Exception as e:
            last_error = str(e)
        if attempt < max_retries - 1:
            time.sleep(backoff * (attempt + 1))
    return False, last_error

@app.route('/paypal/webhook', methods=['POST'])
def paypal_webhook():
    """Handle PayPal payment capture completed webhook"""
    # Verify webhook signature (production should validate)
    payload = request.get_data()
    headers = request.headers
    
    try:
        data = request.get_json()
        event_type = data.get('event_type')
        
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            resource = data.get('resource', {})
            payer_email = resource.get('payer', {}).get('email_address')
            amount = resource.get('amount', {}).get('value')
            capture_id = resource.get('id')
            
            if payer_email:
                with get_db() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', ?, ?)",
                        (payer_email, f"paypal-{capture_id}", time.time())
                    )
                print(f"[PayPal] Payment captured for {payer_email}, amount: ${amount}")
                
                # Send order confirmation email (with retry)
                if send_order_confirmation:
                    try:
                        order_data = {
                            'customer_name': 'Seeker',
                            'product_name': 'Subconscious Mirror PRO STABLE (Lifetime)',
                            'order_id': capture_id,
                            'amount': f'${amount}',
                            'date': time.strftime('%Y-%m-%d %H:%M UTC'),
                            'status': 'PAID / SUCCESS',
                            'cta_link': BRAND_URL
                        }
                        success, error = _send_email_with_retry(
                            send_order_confirmation, payer_email, order_data, 'en'
                        )
                        if success:
                            logger.info("email_order_confirmation_sent", extra={"email": payer_email})
                        else:
                            logger.error("email_order_confirmation_failed", extra={"email": payer_email, "error": error})
                    except Exception as e:
                        logger.error("email_order_confirmation_exception", extra={"email": payer_email, "error": str(e)})
                
                return jsonify({"status": "success"}), 200
        
        return jsonify({"status": "ignored"}), 200
    except json.JSONDecodeError:
        logger.warning("paypal_webhook_invalid_json")
        return jsonify({"error": "Invalid JSON"}), 400
    except Exception as e:
        logger.error("paypal_webhook_error", extra={"error": str(e)})
        return jsonify({"error": "Webhook processing error"}), 500

@app.route('/api/paypal/debug', methods=['GET'])
def paypal_debug():
    """Debug endpoint: check PayPal connectivity only (no secrets exposed).
    Only available when FLASK_ENV is not 'production'."""
    if os.environ.get("FLASK_ENV", "production") == "production":
        return _cors(jsonify({"error": "Not available in production"}), 403)
    info = {
        "paypal_client_configured": bool(PAYPAL_CLIENT_ID),
        "paypal_secret_configured": bool(PAYPAL_SECRET),
        "paypal_reachable": False,
        "paypal_status": None,
    }
    try:
        test_res = requests.get(f'{PAYPAL_API_BASE}/v1/oauth2/token', timeout=10)
        info["paypal_reachable"] = True
        info["paypal_status"] = f"HTTP {test_res.status_code}"
    except requests.Timeout:
        info["paypal_status"] = "timeout"
    except requests.ConnectionError:
        info["paypal_status"] = "unreachable"
    except Exception as e:
        info["paypal_status"] = f"error: {e}"
    return _cors(jsonify(info))


@app.route('/api/paypal/config', methods=['GET'])
def paypal_config():
    """Return PayPal client ID for frontend SDK initialization"""
    cid = SANDBOX_PAYPAL_CLIENT_ID if PAYPAL_SANDBOX else PAYPAL_CLIENT_ID
    return _cors(jsonify({
        "clientId": cid,
        "intent": "capture",
        "currency": "USD"
    }))


@app.route('/api/paypal/capture-order', methods=['POST'])
def paypal_capture_order():
    """Capture a PayPal order after buyer approval (called by frontend SDK onApprove)"""
    data = request.get_json()
    order_id = data.get('orderID')
    
    if not order_id:
        return _cors(jsonify({"error": "Missing orderID"}), 400)
    cid = SANDBOX_PAYPAL_CLIENT_ID if PAYPAL_SANDBOX else PAYPAL_CLIENT_ID
    secret = SANDBOX_PAYPAL_SECRET if PAYPAL_SANDBOX else PAYPAL_SECRET
    if not cid or not secret:
        return _cors(jsonify({"error": "PayPal credentials not configured"}), 503)
    
    try:
        # Get access token
        auth_res = requests.post(
            f'{PAYPAL_API_BASE}/v1/oauth2/token',
            auth=(cid, secret),
            headers={'Accept': 'application/json', 'Accept-Language': 'en_US'},
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        auth_res.raise_for_status()
        access_token = auth_res.json()['access_token']
        
        # Capture the order
        capture_res = requests.post(
            f'{PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}'
            },
            timeout=15
        )
        
        if capture_res.status_code not in (200, 201):
            return _cors(jsonify({"error": "Capture failed", "details": capture_res.text}), 500)
        
        cap_data = capture_res.json()
        payer = cap_data.get('payer', {})
        payer_email = payer.get('email_address', '')
        amount_obj = (cap_data.get('purchase_units', [{}])[0]
                      .get('payments', {})
                      .get('captures', [{}])[0]
                      .get('amount', {}))
        amount = amount_obj.get('value', '0')
        capture_id = cap_data.get('id', '')
        payer_name = payer.get('name', {}).get('given_name', 'Seeker')
        
        # Store payment
        if payer_email:
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', ?, ?)",
                    (payer_email, f'paypal-sdk-{capture_id}', time.time())
                )
            print(f'[PayPal SDK] Captured ${amount} from {payer_email}')
            
            # Send confirmation email (with retry)
            if send_order_confirmation:
                try:
                    order_data = {
                        'customer_name': payer_name,
                        'product_name': 'Subconscious Mirror PRO (Lifetime)',
                        'order_id': capture_id,
                        'amount': f'${amount}',
                        'date': time.strftime('%Y-%m-%d %H:%M UTC'),
                        'status': 'PAID',
                        'cta_link': BRAND_URL
                    }
                    success, error = _send_email_with_retry(
                        send_order_confirmation, payer_email, order_data, 'en'
                    )
                    if success:
                        logger.info("email_sdk_order_confirmation_sent", extra={"email": payer_email})
                    else:
                        logger.error("email_sdk_order_confirmation_failed", extra={"email": payer_email, "error": error})
                except Exception as e:
                    logger.error("email_sdk_order_confirmation_exception", extra={"email": payer_email, "error": str(e)})
        
        return _cors(jsonify({
            "status": "captured",
            "email": payer_email,
            "amount": amount,
            "captureId": capture_id
        }))
    
    except requests.Timeout:
        logger.error("paypal_capture_timeout", extra={"order_id": order_id})
        return _cors(jsonify({"error": "PayPal is taking too long. Your payment may still process — please check your email."}), 503)
    except requests.ConnectionError:
        logger.error("paypal_capture_connection_error")
        return _cors(jsonify({"error": "Cannot reach PayPal. Please try again."}), 502)
    except requests.HTTPError as e:
        logger.error("paypal_capture_http_error", extra={"status": e.response.status_code if hasattr(e, 'response') else 'unknown'})
        return _cors(jsonify({"error": "PayPal returned an error. Please try again."}), 502)
    except Exception as e:
        import traceback
        logger.error("paypal_capture_error", extra={"error": str(e), "traceback": traceback.format_exc()})
        return _cors(jsonify({"error": "Payment processing error. Please contact support if charged."}), 500)


@app.route('/api/paypal/create-order', methods=['POST'])
def paypal_create_order():
    """Create PayPal order for client-side checkout (LIVE)"""
    data = request.get_json()
    amount = data.get('amount', '4.99')
    
    # Quick sanity check
    cid = SANDBOX_PAYPAL_CLIENT_ID if PAYPAL_SANDBOX else PAYPAL_CLIENT_ID
    secret = SANDBOX_PAYPAL_SECRET if PAYPAL_SANDBOX else PAYPAL_SECRET
    if not cid or not secret:
        return _cors(jsonify({"error": "PayPal credentials not configured on server", "code": "MISSING_CREDS"}), 503)
    
    try:
        # Get access token from PayPal API
        auth_res = requests.post(
            f'{PAYPAL_API_BASE}/v1/oauth2/token',
            auth=(cid, secret),
            headers={'Accept': 'application/json', 'Accept-Language': 'en_US'},
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        auth_res.raise_for_status()
        access_token = auth_res.json()['access_token']
        
        # Create order with application_context for redirect URLs
        base_url = BRAND_URL.rstrip('/')
        order_res = requests.post(
            f'{PAYPAL_API_BASE}/v2/checkout/orders',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}'
            },
            json={
                'intent': 'CAPTURE',
                'application_context': {
                    'brand_name': 'Subconscious Mirror',
                    'landing_page': 'BILLING',
                    'user_action': 'PAY_NOW',
                    'return_url': f'{base_url}/api/paypal/return?status=success',
                    'cancel_url': f'{base_url}/api/paypal/return?status=cancel'
                },
                'purchase_units': [{
                    'amount': {
                        'currency_code': 'USD',
                        'value': amount
                    }
                }]
            },
            timeout=15
        )
        order_res.raise_for_status()
        return _cors(jsonify(order_res.json()))
    except requests.Timeout:
        logger.error("paypal_create_order_timeout")
        return _cors(jsonify({"error": "PayPal is taking too long. Please try again."}), 503)
    except requests.ConnectionError:
        logger.error("paypal_create_order_connection_error")
        return _cors(jsonify({"error": "Cannot reach PayPal. Please try again."}), 502)
    except requests.HTTPError as e:
        logger.error("paypal_create_order_http_error", extra={"status": e.response.status_code if hasattr(e, 'response') else 'unknown'})
        return _cors(jsonify({"error": "PayPal returned an error. Please try again."}), 502)
    except Exception as e:
        import traceback
        logger.error("paypal_create_order_error", extra={"error": str(e), "traceback": traceback.format_exc()})
        return _cors(jsonify({"error": "Payment setup failed. Please try again."}), 500)

@app.route('/api/paypal/return', methods=['GET'])
def paypal_return():
    """Handle PayPal redirect after payment (success or cancel)"""
    status = request.args.get('status', 'unknown')
    token = request.args.get('token', '')  # PayPal order token
    payer_email = ''
    
    cid = SANDBOX_PAYPAL_CLIENT_ID if PAYPAL_SANDBOX else PAYPAL_CLIENT_ID
    secret = SANDBOX_PAYPAL_SECRET if PAYPAL_SANDBOX else PAYPAL_SECRET

    if status == 'success' and token:
        # Capture the order server-side (optional: webhook also handles this)
        try:
            auth_res = requests.post(
                f'{PAYPAL_API_BASE}/v1/oauth2/token',
                auth=(cid, secret),
                headers={'Accept': 'application/json'},
                data={'grant_type': 'client_credentials'},
                timeout=15
            )
            access_token = auth_res.json().get('access_token')
            
            if access_token:
                capture_res = requests.post(
                    f'{PAYPAL_API_BASE}/v2/checkout/orders/{token}/capture',
                    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'},
                    timeout=15
                )
                if capture_res.status_code == 201 or capture_res.status_code == 200:
                    cap_data = capture_res.json()
                    payer_email = cap_data.get('payer', {}).get('email_address')
                    amount = cap_data.get('purchase_units', [{}])[0].get('payments', {}).get('captures', [{}])[0].get('amount', {}).get('value')
                    capture_id = cap_data.get('id')
                    
                    if payer_email:
                        with get_db() as conn:
                            conn.execute(
                                "INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', ?, ?)",
                                (payer_email, f'paypal-{capture_id}', time.time())
                            )
                        print(f'[PayPal Return] Captured payment for {payer_email}, ${amount}')
        except requests.Timeout:
            logger.warning("paypal_return_timeout")
        except requests.ConnectionError:
            logger.warning("paypal_return_connection_error")
        except Exception as e:
            logger.error("paypal_return_capture_error", extra={"error": str(e)})
        
        # Redirect to frontend with success indicator
        base_url = BRAND_URL.rstrip('/')
        from flask import redirect as flask_redirect
        return flask_redirect(f'{base_url}/?payment=success&email={payer_email}')
    
    # Cancel or other status - redirect to home
    base_url = BRAND_URL.rstrip('/')
    from flask import redirect as flask_redirect
    return flask_redirect(f'{base_url}/?payment=cancel')

@app.route('/api/send-report', methods=['POST', 'OPTIONS'])
def send_report():
    """Send dream report via email — supports both HTML and template modes"""
    if request.method == 'OPTIONS': return _cors(make_response())
    
    data = request.get_json()
    email = data.get('email')
    html_body = data.get('html', '')       # 完整 HTML 报告
    dream_title = data.get('dream_title', 'Your Dream Analysis')
    report_preview = data.get('preview', '')
    session_url = data.get('session_url', BRAND_URL)
    lang = data.get('lang', 'zh')
    
    if not email:
        return _cors(jsonify({"ok": False, "error": "Email required"}), 400)
    
    try:
        if html_body:
            # 加载并压缩 Logo 用于邮件头部（邮件不适合太大体积）
            import base64
            from PIL import Image
            import io
            logo_b64 = ""
            # Fetch logo from GitHub Raw CDN (not in Zeabur build)
            logo_url = os.environ.get('LOGO_URL', 'https://raw.githubusercontent.com/qianzhouxia-beep/Subconscious/main/static/logo.png')
            try:
                logo_res = requests.get(logo_url, timeout=10)
                logo_res.raise_for_status()
                img = Image.open(io.BytesIO(logo_res.content))
                # 邮件头像缩小到 128x128 以内
                max_size = 128
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                logo_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
                print(f"[Email] Logo embedded: {len(logo_b64)} chars (resized to {img.size})")
            except Exception as e:
                print(f"[Email] Logo fetch failed: {e}")
                logo_b64 = ""

            # 将报告内容包裹在专业邮件模板中发送
            from backend.email_templates import send_report_content_email
            report_email_data = {
                'customer_name': data.get('customer_name', 'Seeker'),
                'dream_title': dream_title,
                'session_url': session_url,
                'cta_link': session_url,
                'header_logo_b64': logo_b64,
                'order_data': data.get('order_data', None),  # 订单确认板块数据（可选）
            }
            success, error = send_report_content_email(email, report_email_data, html_body, lang)
        elif send_dream_report:
            report_data = {
                'dream_title': dream_title,
                'session_url': session_url,
                'report_preview': report_preview
            }
            success, error = send_dream_report(email, report_data, lang)
        else:
            return _cors(jsonify({"ok": False, "error": "Email service not configured"}), 503)
        
        if success:
            return _cors(jsonify({"ok": True}))
        else:
            return _cors(jsonify({"ok": False, "error": error or "Unknown error"}), 500)
    except requests.Timeout:
        return _cors(jsonify({"ok": False, "error": "Email service timeout. Your report is still available on the website."}), 503)
    except Exception as e:
        logger.error("send_report_error", extra={"email": email, "error": str(e)})
        return _cors(jsonify({"ok": False, "error": "Failed to send report. Your report is still available on the website."}), 500)

@app.route('/api/send-3day-reminder', methods=['POST', 'OPTIONS'])
def send_3day_reminder():
    """Send 3-day inactive re-engagement email to a user."""
    if request.method == 'OPTIONS':
        return _cors(jsonify({}), 200)
    try:
        data = request.get_json()
        email = data.get('email', '')
        if not email:
            return _cors(jsonify({"ok": False, "error": "Missing email"}), 400)
        send_data = {
            'customer_name': data.get('customer_name', 'Seeker'),
            'last_dream_date': data.get('last_dream_date', 'a few days ago'),
            'session_url': data.get('session_url', BRAND_URL),
            'cta_link': data.get('cta_link', BRAND_URL),
        }
        lang = data.get('lang', 'en')
        if send_inactive_reengagement_email:
            success, error = send_inactive_reengagement_email(email, send_data, lang)
            if success:
                return _cors(jsonify({"ok": True}))
            else:
                return _cors(jsonify({"ok": False, "error": error}), 500)
        else:
            return _cors(jsonify({"ok": False, "error": "Email service not available"}), 503)
    except Exception as e:
        logger.error("send_3day_reminder_error", extra={"email": email, "error": str(e)})
        return _cors(jsonify({"ok": False, "error": "Failed to send reminder."}), 500)


# ═══ Report Download (PDF) ════════════════════════════════════

@app.route('/api/report/download', methods=['POST', 'OPTIONS'])
def report_download():
    """Generate a PDF report from submission data."""
    if request.method == 'OPTIONS': return _cors(make_response())
    data = request.get_json()
    html_content = data.get('html', '')
    lang = data.get('lang', 'zh')
    
    if not html_content:
        return _cors(jsonify({"error": "No report content"}), 400)
    
    # Wrap the HTML in a full document with styles
    # Use inline styles + web-safe CJK fonts for reliable rendering
    full_html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<style>
  @page {{ margin: 1.5cm; size: A4; }}
  body {{ font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", "WenQuanYi Micro Hei", sans-serif; color: #1a1a1a; line-height: 1.7; padding: 20px; background: #fff; }}
  h2 {{ color: #7c5cff; font-size: 18px; margin-top: 24px; margin-bottom: 8px; border-bottom: 2px solid rgba(124,92,255,0.3); padding-bottom: 4px; }}
  h4 {{ font-size: 14px; margin-top: 20px; margin-bottom: 6px; }}
  p {{ font-size: 12px; margin-bottom: 12px; color: #333; line-height: 1.8; text-align: justify; }}
  strong {{ color: #111; }}
  .pcard {{ background: linear-gradient(135deg, rgba(255,213,79,0.06), rgba(255,213,79,0.02)); border: 1px solid rgba(255,213,79,0.15); border-radius: 12px; padding: 18px; margin-bottom: 14px; }}
  .header {{ text-align: center; margin-bottom: 30px; }}
  .header h1 {{ color: #7c5cff; font-size: 24px; margin-bottom: 4px; }}
  .header p {{ color: #888; font-size: 11px; }}
  .footer {{ text-align: center; margin-top: 40px; color: #aaa; font-size: 10px; border-top: 1px solid #eee; padding-top: 15px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>Subconscious Mirror</h1>
    <p>{'AI 解梦报告' if lang == 'zh' else 'Dream Analysis Report'}</p>
  </div>
  {html_content}
  <div class="footer">
    <p>Generated by Subconscious Mirror — AI-Powered Dream Oracle</p>
    <p>https://mirror.api-tokenmaster.com</p>
  </div>
</body>
</html>"""
    
    pdf_bytes = None
    
    # Method 1: weasyprint (best quality, needs system libs)
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=full_html).write_pdf()
    except Exception as e:
        logger.warning(f"weasyprint failed: {e}, trying fallback...")
    
    # Method 2: fallback — fpdf2 (no system deps, simpler)
    if pdf_bytes is None:
        try:
            from fpdf import FPDF
            import re as _pr
            import os as _os

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            # Try to add CJK font from common system paths
            cjk_font_paths = [
                "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/dejavu/DejavuSans.ttf",
            ]
            font_added = False
            for fp in cjk_font_paths:
                if _os.path.exists(fp):
                    try:
                        pdf.add_font("CJK", "", fp, uni=True)
                        font_added = True
                        break
                    except:
                        continue

            # Strip HTML tags for plain text fallback
            text = _pr.sub(r'<[^>]+>', '', full_html)
            text = _pr.sub(r'&[a-z]+;', '', text)
            text = _pr.sub(r'\s+', ' ', text).strip()

            if font_added:
                pdf.set_font("CJK", size=10)
            else:
                pdf.set_font("Helvetica", size=9)

            for line in text.split('\n'):
                line = line.strip()
                if not line: continue
                try:
                    pdf.multi_cell(0, 6, line)
                except Exception:
                    # Last resort: encode non-ASCII as replacement chars
                    safe = line.encode('latin-1', 'replace').decode('latin-1')
                    pdf.multi_cell(0, 5, safe)

            pdf_bytes = pdf.output()
        except Exception as e2:
            logger.error(f"fpdf2 fallback also failed: {e2}")
            return _cors(jsonify({"error": "Failed to generate PDF. PDF libraries unavailable on server."}), 500)
    
    try:
        from io import BytesIO
        pdf_io = BytesIO(pdf_bytes)
        return send_file(
            pdf_io,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='subconscious-mirror-report.pdf'
        )
    except Exception as e:
        logger.error(f"PDF send_file error: {e}")
        return _cors(jsonify({"error": "Failed to send PDF"}), 500)


# ═══ Tarot Wallpaper ═══════════════════════════════════════

@app.route('/api/tarot/wallpaper', methods=['POST', 'OPTIONS'])
def tarot_wallpaper():
    """Generate a phone wallpaper with tarot card and dream info."""
    if request.method == 'OPTIONS': return _cors(make_response())
    data = request.get_json()
    card_index = data.get('card_index', 0)
    card_name = data.get('card_name', 'The Fool')
    dream_text = data.get('dream_text', '')
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io, textwrap

        # 9:16 wallpaper dimensions
        W, H = 1080, 1920

        # Create dark background — use RGB (not RGBA) to avoid black-screen issues
        # The original bug: 'alpha' variable (0-30) was used as R/G/B component,
        # making the entire background nearly black (rgb=15-45).
        img = Image.new('RGB', (W, H), (10, 10, 20))
        draw = ImageDraw.Draw(img)

        # Subtle vertical gradient: dark purple at bottom → slightly lighter at top
        for y in range(H):
            ratio = 1 - y / H          # 1.0 at top, 0.0 at bottom
            r = int(10 + 20 * ratio)   # 30 at top, 10 at bottom
            g = int(10 + 15 * ratio)   # 25 at top, 10 at bottom
            b = int(20 + 35 * ratio)   # 55 at top, 20 at bottom (purple tint)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Try to load fonts — safe fallback chain
        font_large = font_med = font_small = None
        font_paths = [
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52),
        ]
        for fp, sz in font_paths:
            try:
                font_large = ImageFont.truetype(fp, sz)
                font_med   = ImageFont.truetype(fp.replace('Bold', ''), 28) if 'Bold' in fp else ImageFont.truetype(fp, 28)
                font_small  = ImageFont.truetype(fp.replace('Bold', ''), 22) if 'Bold' in fp else ImageFont.truetype(fp, 22)
                break
            except Exception:
                continue
        if font_large is None:
            # Fallback: use default (bitmap) font — never crashes
            font_def = ImageFont.load_default()
            font_large = font_def
            font_med   = font_def
            font_small  = font_def

        # Load tarot card image — search in order: persistent volume → static dir → GitHub
        # FIX: Use a fixed filename list indexed by card_index.
        # The old code built `fn` from card_name (which may be Chinese),
        # producing filenames like "00-愚者.png" that don't match the actual
        # English-named files (00-fool.png, 01-magician.png, etc.).
        _tarot_filenames = [
            "00-fool.png", "01-magician.png", "02-high-priestess.png",
            "03-empress.png", "04-emperor.png", "05-hierophant.png",
            "06-lovers.png", "07-chariot.png", "08-strength.png",
            "09-hermit.png", "10-wheel-of-fortune.png", "11-justice.png",
            "12-hanged-man.png", "13-death.png", "14-temperance.png",
            "15-devil.png", "16-tower.png", "17-star.png",
            "18-moon.png", "19-sun.png", "20-judgement.png", "21-world.png",
        ]
        fn = _tarot_filenames[card_index] if 0 <= card_index < len(_tarot_filenames) else _tarot_filenames[0]
        card_asset = None
        # 1. Persistent volume (/data/tarot/) — survives container restarts
        _search_paths = [
            os.path.join(_TAROT_DST, fn),          # /data/tarot/ (Zeabur Volume)
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'tarot', fn),  # static/tarot/
        ]
        for attempt_path in _search_paths:
            try:
                if os.path.exists(attempt_path):
                    card_asset = Image.open(attempt_path).convert('RGBA')
                    logger.info(f"[Wallpaper] Loaded tarot image from local file: {attempt_path}")
                    break
            except Exception as _e:
                logger.warning(f"[Wallpaper] Failed to load {attempt_path}: {_e}")
                continue
        # 2. Fallback: download from GitHub raw (no local file needed)
        if card_asset is None:
            card_img_url = (
                f"https://raw.githubusercontent.com/qianzhouxia-beep/Subconscious/"
                f"main/static/tarot/{fn}"
            )
            try:
                import requests as _img_req
                logger.info(f"[Wallpaper] Downloading tarot image from GitHub: {card_img_url}")
                resp = _img_req.get(card_img_url, timeout=15)
                if resp.status_code == 200:
                    card_asset = Image.open(io.BytesIO(resp.content)).convert('RGBA')
                    logger.info(f"[Wallpaper] Downloaded {fn} from GitHub ({len(resp.content)} bytes)")
                    # Cache to persistent volume for next time
                    try:
                        os.makedirs(_TAROT_DST, exist_ok=True)
                        with open(os.path.join(_TAROT_DST, fn), 'wb') as _f:
                            _f.write(resp.content)
                        logger.info(f"[Wallpaper] Cached {fn} → {_TAROT_DST}")
                    except Exception as _save_e:
                        logger.warning(f"[Wallpaper] Failed to cache image: {_save_e}")
            except Exception as _e:
                logger.warning(f"[Wallpaper] GitHub download failed: {_e}")

        # 3. Final fallback: draw a placeholder card with Pillow so the wallpaper is never blank
        if card_asset is None:
            logger.warning(f"[Wallpaper] All sources failed for {fn}, drawing placeholder card")
            ph_w, ph_h = 300, 500
            card_asset = Image.new('RGBA', (ph_w, ph_h), (124, 92, 255, 80))  # purple translucent
            ph_draw = ImageDraw.Draw(card_asset)
            # Border
            ph_draw.rectangle([4, 4, ph_w-4, ph_h-4], outline=(124, 92, 255, 200), width=3)
            # Card index number (large)
            try:
                _font_ph = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
            except Exception:
                _font_ph = ImageFont.load_default()
            _label = f"[{card_index}]"
            _bb = ph_draw.textbbox((0, 0), _label, font=_font_ph)
            _tw = _bb[2] - _bb[0]; _th = _bb[3] - _bb[1]
            ph_draw.text(((ph_w - _tw) // 2, (ph_h - _th) // 2 - 40), _label, fill=(255, 255, 255, 220), font=_font_ph)
            # Card name below number
            try:
                _font_ph2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except Exception:
                _font_ph2 = ImageFont.load_default()
            _name_text = card_name[:30]
            _bb2 = ph_draw.textbbox((0, 0), _name_text, font=_font_ph2)
            _tw2 = _bb2[2] - _bb2[0]
            ph_draw.text(((ph_w - _tw2) // 2, (ph_h - _th) // 2 + 50), _name_text, fill=(200, 200, 255, 200), font=_font_ph2)
            logger.info(f"[Wallpaper] Using drawn placeholder for card_index={card_index}")

        y_text = 180
        if card_asset:
            # Resize card image to fixed height, keep aspect ratio
            card_h = 500
            card_w = int(card_asset.width * card_h / card_asset.height)
            card_asset = card_asset.resize((card_w, card_h), Image.LANCZOS)
            x_off = (W - card_w) // 2
            y_off = 160
            # Paste with alpha mask (correct way)
            alpha_mask = card_asset.split()[-1]   # alpha channel
            img.paste(card_asset, (x_off, y_off), mask=alpha_mask)
            y_text = y_off + card_h + 30

        # Draw text — use purple accent color
        # PIL ImageDraw.fill accepts RGB tuple or color name string
        PURPLE = (124, 92, 255)    # #7c5cff
        GRAY_MID = (136, 136, 136)  # #888
        GRAY_DIM = (102, 102, 102)  # #666
        GRAY_LT  = (170, 170, 170)  # #aaa

        # Card name
        draw.text((W // 2, y_text), card_name, fill=PURPLE, font=font_large, anchor='mt')
        y_text += 60

        # Subtitle
        draw.text((W // 2, y_text), "Your Dream Tarot", fill=GRAY_MID, font=font_med, anchor='mt')
        y_text += 80

        # Dream text (wrapped)
        if dream_text:
            wrapper = textwrap.TextWrapper(width=28)
            lines = wrapper.wrap(dream_text[:180])
            for line in lines:
                draw.text((W // 2, y_text), line, fill=GRAY_LT, font=font_small, anchor='mt')
                y_text += 34

        # Branding
        draw.text((W // 2, H - 80), "Subconscious Mirror", fill=PURPLE, font=font_med, anchor='mt')
        draw.text((W // 2, H - 45), "AI-Powered Dream Oracle", fill=GRAY_DIM, font=font_small, anchor='mt')

        # Save to bytes — RGB mode, no alpha issues
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        from flask import send_file
        safe_name = card_name.lower().replace(' ', '-').replace('/', '-')
        return send_file(
            buf,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'tarot-{safe_name}-wallpaper.png'
        )
    except Exception as e:
        logger.error(f"Wallpaper generation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return _cors(jsonify({"error": "Failed to generate wallpaper"}), 500)


# ── Google OAuth ───────────────────────────────────────
from urllib.parse import urlencode as _urlenc

@app.route('/api/auth/social/<provider>')
def social_login(provider):
    if provider == 'google':
        # Try using account_module's helper if available
        _helper = app.config.get("_social_google_auth_url")
        if _helper:
            auth_url, err = _helper()
            if err:
                return jsonify({'detail': err}), 500
            return jsonify({'auth_url': auth_url})

        # Fallback: inline implementation with CORRECT env var names
        client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '')
        if not client_id:
            return jsonify({'detail': 'Google OAuth not configured (missing GOOGLE_OAUTH_CLIENT_ID)'}), 500
        auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + _urlenc({
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'online',
            'prompt': 'select_account',
        })
        return jsonify({'auth_url': auth_url})
    else:
        return jsonify({'detail': provider + ' login is being configured. Please use email.'}), 501

# Callback path MUST match GOOGLE_OAUTH_REDIRECT_URI in Zeabur env vars
@app.route('/api/auth/social/google/callback')
def google_callback():
    code = request.args.get('code', '')
    if not code:
        return redirect('/?oauth_error=authorization_code_missing')

    # Try using account_module's helper if available
    _callback_helper = app.config.get("_handle_google_callback")
    # DEBUG: Force inline OAuth to isolate account_module issues
    _callback_helper = None
    if _callback_helper:
        try:
            token, email, err = _callback_helper(code)
            if err:
                return redirect('/?oauth_error=' + err)
            if not token or not email:
                return redirect('/?oauth_error=token_generation_failed')
            resp = make_response(redirect('/?oauth_token=' + email))
            resp.set_cookie('sm_auth_token', token, max_age=31536000, httponly=True, samesite='Lax')
            return resp
        except Exception as e:
            logger.error("account_module_callback_error", extra={"err": str(e)})
            # Fall through to inline implementation
            pass

    # Fallback: inline implementation with CORRECT env var names
    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
    redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '')

    if not all([client_id, client_secret, code]):
        return redirect('/?oauth_error=google_oauth_misconfigured')

    try:
        token_res = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=15,
        )
        if not token_res.ok:
            logger.error("google_token_error", extra={"status": token_res.status_code, "body": token_res.text[:200]})
            return redirect('/?oauth_error=token_exchange_failed')

        access_token = token_res.json().get('access_token', '')
        if not access_token:
            return redirect('/?oauth_error=no_access_token')

        userinfo_res = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': 'Bearer ' + access_token},
            timeout=10,
        )
        if not userinfo_res.ok:
            return redirect('/?oauth_error=userinfo_failed')

        userinfo = userinfo_res.json()
        email = userinfo.get('email', '')
        if not email:
            return redirect('/?oauth_error=no_email_from_google')

        # Generate JWT token for the user
        import hashlib as _hashlib, uuid as _uuid, time as _time
        try:
            import jwt as _jwt
            # Find or create user in DB
            with get_db() as conn:
                row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                if row:
                    user_id = row["id"]
                    # best-effort last_login update; tolerate legacy DBs without this column
                    try:
                        conn.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user_id,))
                    except Exception:
                        pass
                else:
                    user_id = _uuid.uuid4().hex
                    pwd_hash = _hashlib.sha256(os.urandom(24).hex().encode()).hexdigest()
                    google_sub = userinfo.get("id", "")
                    # Tolerate legacy DBs without google_sub column
                    try:
                        conn.execute("INSERT INTO users (id,email,password_hash,google_sub) VALUES(?,?,?,?)",
                                     (user_id, email, pwd_hash, google_sub))
                    except Exception:
                        # Fallback: insert without google_sub
                        conn.execute("INSERT INTO users (id,email,password_hash) VALUES(?,?,?)",
                                     (user_id, email, pwd_hash))
            jwt_token = _jwt.encode({
                "sub": user_id, "email": email,
                "iat": int(_time.time()),
                "exp": int(_time.time()) + 8760*3600,
            }, os.environ.get("JWT_SECRET", "smirror_fixed_secret_v1_7f3a9e2b8c1d4a6f_2026"), algorithm="HS256")
        except Exception as e:
            logger.error("google_jwt_error", extra={"err": str(e)})
            jwt_token = email  # fallback: use raw email as token

        resp = make_response(redirect('/?oauth_token=' + jwt_token))
        resp.set_cookie('sm_auth_token', jwt_token, max_age=31536000, httponly=True, samesite='Lax')
        return resp
    except Exception as e:
        logger.error("google_callback_error", extra={"err": str(e)})
        return redirect('/?oauth_error=internal_error')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    # 生产环境严禁开启 debug=True（会导致内存泄漏和任意代码执行风险）
    is_production = os.environ.get("FLASK_ENV", "production") == "production"
    app.run(host='0.0.0.0', port=port, debug=not is_production)
