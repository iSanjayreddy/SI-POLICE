"""
DSA Coach Bot — Webhook mode (no 409, Railway-safe)
"""
import os, json, logging, threading, schedule, time, sys, random
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from google import genai

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────
TOKEN       = os.environ["TELEGRAM_TOKEN"]
GEMINI_KEY  = os.environ["GEMINI_API_KEY"]
CHAT_ID     = int(os.environ["CHAT_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]   # e.g. https://your-app.up.railway.app
START_DATE  = os.getenv("START_DATE", "2026-04-21")
DATA_FILE   = "progress.json"
PORT        = int(os.getenv("PORT", 8080))

gemini_client = genai.Client(api_key=GEMINI_KEY)
MODEL         = "gemini-2.0-flash"          # stable free-tier model
bot           = telebot.TeleBot(TOKEN, threaded=False)
app           = Flask(__name__)

# ── Data ─────────────────────────────────────────────────────
_lock = threading.Lock()

def load():
    with _lock:
        try:
            return json.load(open(DATA_FILE))
        except Exception:
            return {"solves":[], "logs":[], "skips":[], "used_songs":[],
                    "streaks":{"current":0,"best":0,"last_solve_date":""},
                    "start_date": START_DATE, "paused": False, "pause_until":""}

def save(d):
    with _lock:
        json.dump(d, open(DATA_FILE,"w"), indent=2)

def week_day(d):
    start   = datetime.strptime(d.get("start_date", START_DATE), "%Y-%m-%d")
    elapsed = (datetime.now() - start).days
    return (elapsed // 7) + 1, (elapsed % 7) + 1

TOPICS = {1:"Arrays & HashMaps", 2:"Binary Search", 3:"Trees",
          4:"Graphs", 5:"Heaps", 6:"Sliding Window",
          7:"DP 1D", 8:"DP 2D", 9:"Monotonic Stack",
          10:"Intervals & Greedy", 11:"Backtracking",
          12:"Advanced Graphs", 13:"Full Review"}

def topic(w): return TOPICS.get(w, "Mixed Review")

def update_streak(d):
    today = datetime.now().strftime("%Y-%m-%d")
    last  = d["streaks"].get("last_solve_date","")
    yest  = (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
    if last == today: return
    d["streaks"]["current"] = d["streaks"]["current"]+1 if last==yest else 1
    d["streaks"]["last_solve_date"] = today
    if d["streaks"]["current"] > d["streaks"]["best"]:
        d["streaks"]["best"] = d["streaks"]["current"]

# ── Songs ─────────────────────────────────────────────────────
SONGS = [
    ("POWER - Kanye West",            "https://youtu.be/L53gjP-TtGE"),
    ("Jumpman - Drake & Future",       "https://youtu.be/NyP-PjNOaH8"),
    ("Sicko Mode - Travis Scott",      "https://youtu.be/6ONRf7h3Mdk"),
    ("Mask Off - Future",              "https://youtu.be/xvZqHgFz51I"),
    ("Humble - Kendrick Lamar",        "https://youtu.be/tvTRZJ-4EyI"),
    ("DNA - Kendrick Lamar",           "https://youtu.be/NLYBE8eFWts"),
    ("m.A.A.d city - Kendrick Lamar",  "https://youtu.be/xFFUkxBdCfQ"),
    ("Goosebumps - Travis Scott",      "https://youtu.be/Dst9gZkq1a8"),
    ("Black Skinhead - Kanye West",    "https://youtu.be/NkRkBDQ7fR0"),
    ("Alright - Kendrick Lamar",       "https://youtu.be/Z-48u_uWMHY"),
    ("Started From Bottom - Drake",    "https://youtu.be/RubBzkZzpUA"),
    ("God's Plan - Drake",             "https://youtu.be/xpVfcZ0ZcFM"),
    ("NEW MAGIC WAND - Tyler",         "https://youtu.be/9-RMcwVLBqQ"),
    ("F**kin Problems - ASAP Rocky",   "https://youtu.be/cQ5jRUsHosc"),
    ("Bad and Boujee - Migos",         "https://youtu.be/P9mh7zHtPMY"),
]

def pick_song(d):
    used  = set(d.get("used_songs", []))
    fresh = [s for s in SONGS if s[0] not in used]
    if not fresh:
        d["used_songs"] = []
        fresh = SONGS
    s = random.choice(fresh)
    d.setdefault("used_songs", []).append(s[0])
    return s

# ── Gemini ────────────────────────────────────────────────────
def ask_gemini(prompt):
    try:
        r = gemini_client.models.generate_content(model=MODEL, contents=prompt)
        return r.text.strip()
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return f"⚠️ Gemini unavailable: {e}"

def get_problem(d):
    w, day = week_day(d)
    t      = topic(w)
    recent = [s["problem"] for s in d["solves"][-10:]]
    notes  = [l["note"] for l in d["logs"][-3:]]
    song   = pick_song(d)
    save(d)

    prompt = f"""You are a strict SDE-1 DSA coach. No fluff.

Plan context: Week {w} Day {day} — Topic: {t}
Recent solves: {recent or 'none yet'}
My notes: {notes or 'none'}

Pick ONE Medium LeetCode problem for Week {w} Day {day}.
Do NOT repeat: {recent}

Reply in EXACTLY this format:
PROBLEM: [number]. [title]
LINK: https://leetcode.com/problems/[slug]/
PATTERN: [pattern name]
WHY: [1 sentence why this fits today]
HINT: [1 line conceptual nudge, not the solution]
SONG: {song[0]} → {song[1]}"""

    return ask_gemini(prompt)

def coach_reply(text, d):
    w, day = week_day(d)
    prompt = f"""You are a DSA coach on Telegram. Be concise — 3 sentences max. No markdown headers.
Week {w} Day {day}, topic: {topic(w)}.
Recent solves: {[s['problem'] for s in d['solves'][-5:]]}
User: "{text}"
Reply helpfully. If frustrated, be real. If off-topic, redirect gently."""
    return ask_gemini(prompt)

def review_solution(problem, approach):
    prompt = f"""DSA coach reviewing a solution. Be direct.
Problem: {problem}
Approach: {approach}

Reply:
VERDICT: Correct / Partial / Wrong
TIME: O(?)
SPACE: O(?)
FEEDBACK: 2 sentences
BETTER: one line if a better approach exists"""
    return ask_gemini(prompt)

# ── Daily message ─────────────────────────────────────────────
def send_daily():
    d = load()
    if d.get("paused"):
        if datetime.now().strftime("%Y-%m-%d") <= d.get("pause_until",""):
            log.info("Paused, skipping daily"); return
        d["paused"] = False; save(d)

    w, day = week_day(d)
    streak = d["streaks"]["current"]
    rec    = get_problem(d)
    msg = (f"🌅 *Good morning!*\n"
           f"_Week {w} · Day {day} · {topic(w)}_\n"
           f"🔥 Streak: {streak} days · ✅ {len(d['solves'])} solved\n\n"
           f"{rec}\n\n"
           f"`/solved 238` · `/extra` · `/review 238 approach` · `/status`")
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown", disable_web_page_preview=True)
        log.info("Daily message sent")
    except Exception as e:
        log.error(f"Daily send failed: {e}")

# ── Scheduler ─────────────────────────────────────────────────
def run_scheduler():
    schedule.every().day.at("02:00").do(send_daily)   # 7:30 AM IST
    log.info("Scheduler running — 02:00 UTC daily")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ── Bot handlers ──────────────────────────────────────────────
@bot.message_handler(commands=["start", "status"])
def cmd_status(m):
    d = load(); w, day = week_day(d); s = d["streaks"]
    recent = "\n".join(f"  • {x['problem']}" for x in d["solves"][-5:]) or "  None yet"
    bot.reply_to(m,
        f"📊 *DSA Coach*\n\n"
        f"Week {w} · Day {day} · _{topic(w)}_\n"
        f"✅ Solves: *{len(d['solves'])}*\n"
        f"🔥 Streak: *{s['current']}* (best: {s['best']})\n\n"
        f"*Recent:*\n{recent}",
        parse_mode="Markdown")

@bot.message_handler(commands=["extra"])
def cmd_extra(m):
    bot.reply_to(m, "⏳ Fetching problem...")
    d = load()
    bot.reply_to(m, get_problem(d), parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=["solved"])
def cmd_solved(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: `/solved 238`", parse_mode="Markdown"); return
    prob = parts[1].strip(); d = load()
    d["solves"].append({"problem": prob, "date": datetime.now().strftime("%Y-%m-%d")})
    update_streak(d); save(d)
    streak = d["streaks"]["current"]
    bot.reply_to(m, f"✅ *{prob}* logged!\n🔥 Streak: {streak} days · {len(d['solves'])} total", parse_mode="Markdown")

@bot.message_handler(commands=["review"])
def cmd_review(m):
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(m, "Usage: `/review 238 I used a hashmap`", parse_mode="Markdown"); return
    bot.reply_to(m, "🔍 Reviewing...")
    bot.reply_to(m, review_solution(parts[1], parts[2]), parse_mode="Markdown")

@bot.message_handler(commands=["log"])
def cmd_log(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: `/log struggled with two pointers`", parse_mode="Markdown"); return
    d = load()
    d["logs"].append({"note": parts[1].strip(), "date": datetime.now().strftime("%Y-%m-%d")})
    save(d); bot.reply_to(m, "📝 Logged! Gemini will use this tomorrow.")

@bot.message_handler(commands=["skip"])
def cmd_skip(m):
    d = load(); d["skips"].append({"date": datetime.now().strftime("%Y-%m-%d")}); save(d)
    bot.reply_to(m, f"⏭️ Skipped. {len(d['skips'])} total skips. Rest well 💪")

@bot.message_handler(commands=["break"])
def cmd_break(m):
    parts = m.text.split(); days = int(parts[1]) if len(parts)>1 else 1
    until = (datetime.now()+timedelta(days=days)).strftime("%Y-%m-%d")
    d = load(); d["paused"]=True; d["pause_until"]=until; save(d)
    bot.reply_to(m, f"🛑 Paused for {days} day(s) until {until}.\nType /resume when back.", parse_mode="Markdown")

@bot.message_handler(commands=["resume"])
def cmd_resume(m):
    d = load(); d["paused"]=False; d["pause_until"]=""; save(d)
    bot.reply_to(m, "✅ Resumed! Daily messages are back. Let's go 🔥")

@bot.message_handler(commands=["song"])
def cmd_song(m):
    d = load(); s = pick_song(d); save(d)
    bot.reply_to(m, f"🎵 *{s[0]}*\n{s[1]}", parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=["ping"])
def cmd_ping(m):
    bot.reply_to(m, f"🏓 Alive! {datetime.now().strftime('%H:%M:%S UTC')}")

@bot.message_handler(func=lambda m: True, content_types=["text"])
def cmd_chat(m):
    if m.text and m.text.startswith("/"): 
        bot.reply_to(m, "❓ Unknown command. Try /start"); return
    d = load()
    bot.send_chat_action(m.chat.id, "typing")
    bot.reply_to(m, coach_reply(m.text, d))

# ── Webhook endpoint ──────────────────────────────────────────
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") != "application/json":
        abort(403)
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data(as_text=True))])
    return "ok", 200

@app.route("/", methods=["GET"])
def health():
    return "DSA Coach Bot is running ✅", 200

# ── Start ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # Set webhook — Telegram will POST updates to your Railway URL
    webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/{TOKEN}"
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=webhook_endpoint)
    log.info(f"✅ Webhook set: {webhook_endpoint}")

    threading.Thread(target=run_scheduler, daemon=True).start()
    log.info("🚀 DSA Coach Bot running on webhook mode")

    app.run(host="0.0.0.0", port=PORT, debug=False)
