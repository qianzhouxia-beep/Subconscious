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
import tempfile
import threading
import zhconv
from flask import Flask, request, jsonify, make_response, send_file
from flask_cors import CORS

# Add backend directory to path for email templates
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from email_templates import send_order_confirmation, send_dream_report, send_inactive_reengagement_email
except ImportError:
    send_order_confirmation = None
    send_dream_report = None
    send_inactive_reengagement_email = None
    print("[Warning] email_templates not found, email features disabled")

app = Flask(__name__)
app.url_map.strict_slashes = False
CORS(app, supports_credentials=True)

# --- CONFIGURATION (ENV DRIVEN) ---
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.environ.get("PAYPAL_SECRET", "")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
WHISPER_API_BASE = os.environ.get("WHISPER_API_BASE", "https://api-tokenmaster.com/v1/audio/transcriptions")
WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
# faster-whisper local model (lazy init)
_whisper_model = None
_whisper_lock = threading.Lock()
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")  # base=145MB, faster & more accurate than tiny
HTML_FILE = "index.html"
DB_FILE = "mirror_data.db"

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")


# --- DATABASE LAYER ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        ref_id TEXT PRIMARY KEY,
                        inviter_email TEXT,
                        count INTEGER DEFAULT 0,
                        unlocked INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS referral_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ref_id TEXT,
                        visitor_ip TEXT,
                        user_agent TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(ref_id, visitor_ip, user_agent))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        status TEXT,
                        license_key TEXT,
                        timestamp REAL)''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_email ON payments(email)')
    conn.commit()
    conn.close()

init_db()

@app.route('/api/session/init', methods=['GET', 'POST', 'OPTIONS'])
def session_init():
    if request.method == 'OPTIONS': return _cors(make_response())
    new_sid = uuid.uuid4().hex
    is_premium = False
    auth_token = request.cookies.get('sm_auth_token')
    if auth_token:
        conn = get_db_connection()
        row = conn.execute("SELECT status FROM payments WHERE email = ?", (auth_token,)).fetchone()
        conn.close()
        if row and row['status'] == 'paid': is_premium = True
    res = make_response(jsonify({"sessionId": new_sid, "premium": is_premium, "status": "active"}))
    return _cors(res)

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"error": str(e), "type": type(e).__name__}), 500, {"Access-Control-Allow-Origin": "*"}

def _cors(res, status=200):
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return res, status

@app.route('/')
def index():
    if os.path.exists(HTML_FILE):
        return send_file(HTML_FILE)
    return "<h1>Mirror Sanctum Error: HTML File Missing</h1>", 404

@app.route('/api/referral/init', methods=['POST', 'OPTIONS'])
def init_ref():
    if request.method == 'OPTIONS': return _cors(make_response())
    inviter_email = request.json.get('email', '')
    ref_id = f"ref_{int(time.time())}_{os.urandom(2).hex()}"
    conn = get_db_connection()
    conn.execute("INSERT INTO referrals (ref_id, inviter_email, count) VALUES (?, ?, 0)", (ref_id, inviter_email))
    conn.commit()
    conn.close()
    return _cors(jsonify({"status": "ready", "refId": ref_id}))


@app.route('/api/referral/status', methods=['GET'])
def referral_status():
    ref_id = request.args.get('refId')
    conn = get_db_connection()
    row = conn.execute("SELECT count, unlocked FROM referrals WHERE ref_id = ?", (ref_id,)).fetchone()
    conn.close()
    return _cors(jsonify({"count": row["count"] if row else 0, "unlocked": row["unlocked"] if row else 0}))

@app.route('/api/referral/click', methods=['POST'])
def referral_click():
    inviter_id = request.json.get('refBy')
    visitor_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'unknown')
    if not inviter_id: return _cors(jsonify({"status": "ignored"}))
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO referral_logs (ref_id, visitor_ip, user_agent) VALUES (?, ?, ?)", 
                     (inviter_id, visitor_ip, user_agent))
        conn.execute("UPDATE referrals SET count = count + 1 WHERE ref_id = ?", (inviter_id,))
        conn.commit()
        row = conn.execute("SELECT count, inviter_email, unlocked FROM referrals WHERE ref_id = ?", (inviter_id,)).fetchone()
        if row and row['count'] >= 2 and row['unlocked'] == 0 and row['inviter_email']:
            conn.execute("INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', 'referral-unlock', ?)",
                         (row['inviter_email'], time.time()))
            conn.execute("UPDATE referrals SET unlocked = 1 WHERE ref_id = ?", (inviter_id,))
            conn.commit()
        return _cors(jsonify({"status": "counted", "count": row["count"] if row else 0}))
    except sqlite3.IntegrityError:
        return _cors(jsonify({"status": "ignored"}))
    finally:
        conn.close()

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS': return _cors(make_response())
    req_data = request.json
    messages = req_data.get('messages', [])
    lang = req_data.get('lang', 'zh')
    user_email = req_data.get('email')
    is_premium = False
    if user_email:
        conn = get_db_connection()
        row = conn.execute("SELECT status FROM payments WHERE email = ?", (user_email,)).fetchone()
        conn.close()
        if row and row['status'] == 'paid': is_premium = True
    user_msg_count = len([m for m in messages if m['role'] == 'user'])
    
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
        "The user has already provided their sleep environment data (Moon phase, pre-sleep state, "
        "sleep quality, dream mood, dream type, stress level) in the '[Environment:]' section. "
        "NEVER ask about these details — they are already known.\n\n"
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
            "=== EXAMPLES OF GOOD QUESTIONS ===\n"
            "✅ \"The red door only appeared after you counted to three — did the act of counting feel protective, like a ritual, or did the number itself matter?\"\n"
            "✅ \"Your childhood home had no furniture, but you knew exactly where everything should be — was the emptiness comforting or accusing?\"\n"
            "✅ \"The dog with human eyes followed you through every room but never barked — what did its silence tell you?\"\n\n"
            "Always mirror the user's language (if they wrote in Chinese, respond in Chinese; if English, respond in English)."
        )
    else:
        system_content += (
            "Rule: Deliver a detailed destiny report in TWO PARTS. "
            "Separate with '[PROPHECY_DIVIDER]'.\n\n"
            "PART 1 (free — must be substantial, 4-6 paragraphs):\n"
            "1. [DREAM NARRATIVE] Restate the user's dream in a poetic, refined way.\n"
            "2. [PSYCHOLOGICAL ANALYSIS] Deep analysis from Jungian/analytical psychology perspective. "
            "Identify archetypes, shadow elements, anima/animus, and collective unconscious patterns.\n"
            "3. [SYMBOL DECODING] Break down 2-3 key symbols from the dream — "
            "what they represent personally, culturally, and archetypally.\n"
            "4. [EMOTIONAL LANDSCAPE] Map the emotional journey through the dream — "
            "where emotions shifted, what triggered them, what they reveal.\n\n"
            "PART 2 (paid — 3-5 paragraphs, must deliver clear value):\n"
            "5. [TAROT GUIDANCE] Based on the dream's core energy, select the most fitting Major Arcana tarot card. "
            "Explain WHY this card matches the dream, its upright/reversed meaning, "
            "and what guidance it offers the dreamer. "
            "CRITICAL: Include the card's name AND number in the heading — e.g. '**节制牌（XIV）解读**' so the oracle can later reference it precisely.\n"
            "6. [REAL-LIFE MIRROR] Connect the dream patterns to the user's waking life — "
            "what unresolved situations, relationships, or inner conflicts may be surfacing.\n"
            "7. [ACTIONABLE WISDOM] Provide 3-5 concrete, personalized actions the dreamer can take.\n"
            "8. [PROPHECY] A single, cryptic, poetic closing line — like an oracle's final word. "
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
            "Format: Each section should have a bold header (e.g. '**Psychological Analysis**'). "
            "Write in the same language the user has been using. "
            "Make PART 1 satisfying on its own but leave PART 2 feeling essential."
        )
    try:
        response = requests.post(DEEPSEEK_API_BASE, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "system", "content": system_content}] + messages, "temperature": 0.5, "max_tokens": 4096}, timeout=120)
        res_json = response.json()
        ai_msg = res_json['choices'][0]['message']
        text = ai_msg.get('content') or ai_msg.get('reasoning_content') or ""
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
            return _cors(jsonify({"mode": "report", "status": "full" if is_premium else "partial", "data": {"free_part": free, "paid_part": paid}}))
    except Exception as e: return _cors(jsonify({"error": str(e)}), 500)

@app.route('/api/symbol-lookup', methods=['POST', 'OPTIONS'])
def symbol_lookup():
    if request.method == 'OPTIONS': return _cors(make_response())
    req_data = request.json
    symbol = req_data.get('symbol', '').strip()
    lang = req_data.get('lang', 'en')
    if not symbol: return _cors(jsonify({"error": "Symbol is required"}), 400)
    system_content = f"You are a dream symbol oracle. The user asks about the dream symbol '{symbol}'. Provide a concise but insightful interpretation (2-4 paragraphs) covering: common psychological meaning, archetypal/cultural significance, and what this symbol may reveal about the dreamer's inner state. Do NOT ask follow-up questions. Respond in {'Chinese' if lang == 'zh' else 'English'}."
    try:
        response = requests.post(DEEPSEEK_API_BASE, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "system", "content": system_content}], "temperature": 0.7}, timeout=60)
        res_json = response.json()
        ai_msg = res_json['choices'][0]['message']
        text = ai_msg.get('content') or ai_msg.get('reasoning_content') or ""
        return _cors(jsonify({"symbol": symbol, "interpretation": text}))
    except Exception as e: return _cors(jsonify({"error": str(e)}), 500)

@app.route('/api/clean-text', methods=['POST', 'OPTIONS'])
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
        response = requests.post(DEEPSEEK_API_BASE,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text}
            ], "temperature": 0.1, "max_tokens": 2048},
            timeout=30)
        res_json = response.json()
        ai_msg = res_json['choices'][0]['message']
        cleaned = (ai_msg.get('content') or ai_msg.get('reasoning_content') or raw_text).strip()
        # Safety: if the AI returned something weird or empty, fall back to raw
        if not cleaned or len(cleaned) < len(raw_text) * 0.3:
            cleaned = raw_text
        return _cors(jsonify({"cleaned": cleaned, "raw": raw_text}))
    except Exception as e:
        # On any error, return the raw text so the user isn't blocked
        return _cors(jsonify({"cleaned": raw_text, "raw": raw_text, "error": str(e)}))

# --- Filler-word removal patterns (Chinese speech fillers) ---
# Filler word sets (characters and phrases common in Chinese speech fillers)
_FILLER_CHARS = frozenset('啊哦呃嗯嘛呢吧啦呀哟嘿诶嘶哈呵咳呣噢喔呗吖嘞啰')
_FILLER_PHRASES = frozenset({'就是说', '反正', '怎么说呢', '这样子', '对不对', '是吧', '那个', '然后呢', '那啥', '怎么说'})

def _post_process_whisper_text(text, lang='zh'):
    """Local post-processing: T2S + filler removal. LLM polish handles punctuation."""
    if not text: return text
    # 1. Traditional → Simplified Chinese
    if lang == 'zh':
        try:
            text = zhconv.convert(text, 'zh-cn')
        except Exception:
            pass
    # 2. Replace multi-char filler phrases as substrings (handle adjacency like "那怎么说呢")
    for phrase in sorted(_FILLER_PHRASES, key=len, reverse=True):
        text = text.replace(phrase, ' ')
    # 3. Collapse all delimiters to spaces, split into word tokens
    text = re.sub(r'[\s,，。．！？…、；;：:]+', ' ', text).strip()
    words = text.split()
    # 4. Filter out standalone filler characters
    clean = [w for w in words if w not in _FILLER_CHARS]
    return ' '.join(clean)

def _polish_via_llm(text, lang='zh'):
    """Use DeepSeek to add punctuation, correct errors, and clean up fillers."""
    if lang != 'zh' or not DEEPSEEK_API_KEY or not text:
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
        response = requests.post(DEEPSEEK_API_BASE,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ], "temperature": 0.1, "max_tokens": 1024},
            timeout=8)
        res_json = response.json()
        polished = (res_json['choices'][0]['message'].get('content') or text).strip()
        polished = polished.strip('"\'').strip()
        return polished if polished else text
    except Exception as e:
        print(f"[Post-process] LLM polish failed: {e}")
        return text


# --- WHISPER TRANSCRIPTION (audio → text, with post-processing pipeline) ---
@app.route('/api/transcribe', methods=['POST', 'OPTIONS'])
def transcribe():
    """Transcribe audio: local faster-whisper → post-process (T2S + fillers → LLM polish)."""
    if request.method == 'OPTIONS': return _cors(make_response())
    if 'audio' not in request.files:
        return _cors(jsonify({"error": "No audio file"}), 400)
    audio_file = request.files['audio']
    lang = request.form.get('lang', 'zh')
    whisper_lang = 'zh' if lang == 'zh' else 'en'
    tmp_path = None
    try:
        # Step 1: Save audio to temp file
        suffix = '.webm' if audio_file.filename and audio_file.filename.endswith('.webm') else '.ogg'
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(tmp_fd)
        audio_file.save(tmp_path)

        # Step 2: Local faster-whisper transcription
        model = _get_whisper_model()
        segments, info = model.transcribe(
            tmp_path, language=whisper_lang,
            beam_size=5, best_of=5, temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True
        )
        raw_text = ' '.join(seg.text.strip() for seg in segments).strip()
        print(f"[Whisper] Raw ({whisper_lang}): {raw_text[:120] if raw_text else '(empty)'}")

        if not raw_text:
            return _cors(jsonify({"text": ""}))

        # Step 3: Local post-processing (T2S + filler removal)
        cleaned = _post_process_whisper_text(raw_text, whisper_lang)
        print(f"[Whisper] Cleaned: {cleaned[:120]}")

        # Step 4: LLM polish (punctuation + error correction)
        polished = _polish_via_llm(cleaned, whisper_lang)
        print(f"[Whisper] Polished: {polished[:120]}")

        return _cors(jsonify({"text": polished}))
    except Exception as e:
        print(f"[Whisper] Error: {e}")
        import traceback; traceback.print_exc()
        return _cors(jsonify({"error": str(e)}), 500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except: pass


def _get_whisper_model():
    """Lazy-init faster-whisper model (thread-safe)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        from faster_whisper import WhisperModel
        print(f"[Whisper-local] Loading model '{WHISPER_MODEL_SIZE}' from {MODEL_DIR}...")
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE, device='cpu', compute_type='int8',
            download_root=MODEL_DIR
        )
        print("[Whisper-local] Model loaded OK")
        return _whisper_model

@app.route('/api/verify-license', methods=['POST', 'OPTIONS'])
def verify_license():
    if request.method == 'OPTIONS': return _cors(make_response())
    data = request.json
    license_key = data.get('license_key')
    # Test mode: use TEST-MIRROR-2026 to unlock full report without payment
    if license_key == 'TEST-MIRROR-2026':
        email = data.get('email') or 'test@mirror.local'
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, ?, ?, ?)", (email, 'paid', license_key, time.time()))
        conn.commit()
        conn.close()
        return _cors(jsonify({"status": "unlocked", "email": email}))
    try:
        res = requests.post("https://api.gumroad.com/v2/licenses/verify", data={"product_permalink": "subconscious-mirror", "license_key": license_key}, timeout=10)
        res_data = res.json()
        if res_data.get('success') is True:
            email = res_data['purchase']['email']
            conn = get_db_connection()
            conn.execute("INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, ?, ?, ?)", (email, 'paid', license_key, time.time()))
            conn.commit()
            conn.close()
            return _cors(jsonify({"status": "unlocked", "email": email}))
        return _cors(jsonify({"status": "failed", "message": "Invalid license key"}), 400)
    except Exception as e: return _cors(jsonify({"error": str(e)}), 500)

@app.route('/api/check-premium', methods=['GET'])
def check_premium():
    email = request.args.get('email')
    conn = get_db_connection()
    row = conn.execute("SELECT status FROM payments WHERE email = ?", (email,)).fetchone()
    conn.close()
    if row and row['status'] == 'paid': return _cors(jsonify({"status": "unlocked"}))
    return _cors(jsonify({"status": "locked"}))

# --- PAYPAL WEBHOOK ---
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
                conn = get_db_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', ?, ?)",
                    (payer_email, f"paypal-{capture_id}", time.time())
                )
                conn.commit()
                conn.close()
                print(f"[PayPal] Payment captured for {payer_email}, amount: ${amount}")
                
                # Send order confirmation email
                if send_order_confirmation:
                    try:
                        order_data = {
                            'customer_name': 'Seeker',
                            'product_name': 'Subconscious Mirror PRO STABLE (Lifetime)',
                            'order_id': capture_id,
                            'amount': f'${amount}',
                            'date': time.strftime('%Y-%m-%d %H:%M UTC'),
                            'status': 'PAID / SUCCESS',
                            'cta_link': 'https://mirror.api-tokenmaster.com'
                        }
                        success, error = send_order_confirmation(payer_email, order_data, 'en')
                        if success:
                            print(f"[Email] Order confirmation sent to {payer_email}")
                        else:
                            print(f"[Email] Failed to send: {error}")
                    except Exception as e:
                        print(f"[Email] Error sending confirmation: {e}")
                
                return jsonify({"status": "success"}), 200
        
        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        print(f"[PayPal Webhook Error] {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/paypal/debug', methods=['GET'])
def paypal_debug():
    """Debug endpoint: check PayPal env vars and connectivity"""
    info = {
        "paypal_client_id_set": bool(PAYPAL_CLIENT_ID),
        "paypal_client_id_prefix": PAYPAL_CLIENT_ID[:8] if PAYPAL_CLIENT_ID else '(empty)',
        "paypal_secret_set": bool(PAYPAL_SECRET),
        "paypal_secret_len": len(PAYPAL_SECRET) if PAYPAL_SECRET else 0,
        "base_url": os.environ.get('BASE_URL', '(not set)'),
        "paypal_reachable": False,
        "paypal_auth_status": None,
    }
    # Test PayPal connectivity
    try:
        test_res = requests.get('https://api-m.paypal.com/v1/oauth2/token', timeout=10)
        info["paypal_reachable"] = True
        info["paypal_auth_status"] = f"HTTP {test_res.status_code}"
    except Exception as e:
        info["paypal_auth_status"] = str(e)
    return _cors(jsonify(info))


@app.route('/api/paypal/config', methods=['GET'])
def paypal_config():
    """Return PayPal client ID for frontend SDK initialization"""
    return _cors(jsonify({
        "clientId": PAYPAL_CLIENT_ID,
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
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return _cors(jsonify({"error": "PayPal credentials not configured"}), 503)
    
    try:
        # Get access token
        auth_res = requests.post(
            'https://api-m.paypal.com/v1/oauth2/token',
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            headers={'Accept': 'application/json', 'Accept-Language': 'en_US'},
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        auth_res.raise_for_status()
        access_token = auth_res.json()['access_token']
        
        # Capture the order
        capture_res = requests.post(
            f'https://api-m.paypal.com/v2/checkout/orders/{order_id}/capture',
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
            conn = get_db_connection()
            conn.execute(
                "INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', ?, ?)",
                (payer_email, f'paypal-sdk-{capture_id}', time.time())
            )
            conn.commit()
            conn.close()
            print(f'[PayPal SDK] Captured ${amount} from {payer_email}')
            
            # Send confirmation email
            if send_order_confirmation:
                try:
                    order_data = {
                        'customer_name': payer_name,
                        'product_name': 'Subconscious Mirror PRO (Lifetime)',
                        'order_id': capture_id,
                        'amount': f'${amount}',
                        'date': time.strftime('%Y-%m-%d %H:%M UTC'),
                        'status': 'PAID',
                        'cta_link': 'https://mirror.api-tokenmaster.com'
                    }
                    send_order_confirmation(payer_email, order_data, 'en')
                except Exception as e:
                    print(f'[Email] Error: {e}')
        
        return _cors(jsonify({
            "status": "captured",
            "email": payer_email,
            "amount": amount,
            "captureId": capture_id
        }))
    
    except Exception as e:
        import traceback
        print(f'[PayPal Capture Error] {e}\n{traceback.format_exc()}')
        return _cors(jsonify({"error": str(e)}), 500)


@app.route('/api/paypal/create-order', methods=['POST'])
def paypal_create_order():
    """Create PayPal order for client-side checkout (LIVE)"""
    data = request.get_json()
    amount = data.get('amount', '4.99')
    
    # Quick sanity check
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return _cors(jsonify({"error": "PayPal credentials not configured on server", "code": "MISSING_CREDS"}), 503)
    
    try:
        # Get access token from PayPal LIVE API
        auth_res = requests.post(
            'https://api-m.paypal.com/v1/oauth2/token',
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            headers={'Accept': 'application/json', 'Accept-Language': 'en_US'},
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        auth_res.raise_for_status()
        access_token = auth_res.json()['access_token']
        
        # Create order with application_context for redirect URLs
        base_url = os.environ.get('BASE_URL', 'https://mirror.api-tokenmaster.com').rstrip('/')
        order_res = requests.post(
            'https://api-m.paypal.com/v2/checkout/orders',
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
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[PayPal Create Order Error] {e}\n{tb}")
        return _cors(jsonify({"error": str(e), "traceback": tb}), 500)

@app.route('/api/paypal/return', methods=['GET'])
def paypal_return():
    """Handle PayPal redirect after payment (success or cancel)"""
    status = request.args.get('status', 'unknown')
    token = request.args.get('token', '')  # PayPal order token
    payer_email = ''
    
    if status == 'success' and token:
        # Capture the order server-side (optional: webhook also handles this)
        try:
            auth_res = requests.post(
                'https://api-m.paypal.com/v1/oauth2/token',
                auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
                headers={'Accept': 'application/json'},
                data={'grant_type': 'client_credentials'},
                timeout=15
            )
            access_token = auth_res.json().get('access_token')
            
            if access_token:
                capture_res = requests.post(
                    f'https://api-m.paypal.com/v2/checkout/orders/{token}/capture',
                    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'},
                    timeout=15
                )
                if capture_res.status_code == 201 or capture_res.status_code == 200:
                    cap_data = capture_res.json()
                    payer_email = cap_data.get('payer', {}).get('email_address')
                    amount = cap_data.get('purchase_units', [{}])[0].get('payments', {}).get('captures', [{}])[0].get('amount', {}).get('value')
                    capture_id = cap_data.get('id')
                    
                    if payer_email:
                        conn = get_db_connection()
                        conn.execute(
                            "INSERT OR REPLACE INTO payments (email, status, license_key, timestamp) VALUES (?, 'paid', ?, ?)",
                            (payer_email, f'paypal-{capture_id}', time.time())
                        )
                        conn.commit()
                        conn.close()
                        print(f'[PayPal Return] Captured payment for {payer_email}, ${amount}')
        except Exception as e:
            print(f'[PayPal Return] Capture error (webhook may still handle): {e}')
        
        # Redirect to frontend with success indicator
        base_url = os.environ.get('BASE_URL', 'https://mirror.api-tokenmaster.com').rstrip('/')
        from flask import redirect as flask_redirect
        return flask_redirect(f'{base_url}/?payment=success&email={payer_email}')
    
    # Cancel or other status - redirect to home
    base_url = os.environ.get('BASE_URL', 'https://mirror.api-tokenmaster.com').rstrip('/')
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
    session_url = data.get('session_url', 'https://mirror.api-tokenmaster.com')
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
    except Exception as e:
        return _cors(jsonify({"ok": False, "error": str(e)}), 500)

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
        return _cors(jsonify({"ok": False, "error": str(e)}), 500)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
