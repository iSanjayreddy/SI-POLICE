import os, json, logging, threading, schedule, time, random
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from google import genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TOKEN      = os.environ["TELEGRAM_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CHAT_ID    = int(os.environ["CHAT_ID"])
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT       = int(os.getenv("PORT", 8080))
START_DATE = os.getenv("START_DATE", "2026-04-21")
DATA_FILE  = "progress.json"

gemini_client = genai.Client(api_key=GEMINI_KEY)
MODEL = "gemini-2.0-flash"
bot   = telebot.TeleBot(TOKEN, threaded=False)
app   = Flask(__name__)

_lock = threading.Lock()

def load():
    with _lock:
        try:
            return json.load(open(DATA_FILE))
        except:
            return {"solves": [], "logs": [], "skips": [],
                    "streaks": {"current": 0, "best": 0, "last_solve_date": ""},
                    "used_songs": [], "start_date": START_DATE,
                    "paused": False, "pause_until": ""}

def save(d):
    with _lock:
        json.dump(d, open(DATA_FILE, "w"), indent=2)

def week_day(d):
    start   = datetime.strptime(d.get("start_date", START_DATE), "%Y-%m-%d")
    elapsed = (datetime.now() - start).days
    return (elapsed // 7) + 1, (elapsed % 7) + 1

TOPICS = {1:"Arrays & HashMaps", 2:"Binary Search", 3:"Trees", 4:"Graphs",
          5:"Heaps", 6:"Sliding Window", 7:"DP 1D", 8:"DP 2D",
          9:"Monotonic Stack", 10:"Intervals & Greedy", 11:"Backtracking",
          12:"Advanced Graphs", 13:"Full Review"}

def topic(w): return TOPICS.get(w, "Mixed Review")

def update_streak(d):
    today = datetime.now().strftime("%Y-%m-%d")
    last  = d["streaks"].get("last_solve_date", "")
    yest  = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if last == today: return
    d["streaks"]["current"] = d["streaks"]["current"] + 1 if last == yest else 1
    d["streaks"]["last_solve_date"] = today
    if d["streaks"]["current"] > d["streaks"]["best"]:
        d["streaks"]["best"] = d["streaks"]["current"]

SONGS = [
    ("POWER - Kanye West",          "https://youtu.be/L53gjP-TtGE"),
    ("Sicko Mode - Travis Scott",   "https://youtu.be/6ONRf7h3Mdk"),
    ("Humble - Kendrick Lamar",     "https://youtu.be/tvTRZJ-4EyI"),
    ("DNA - Kendrick Lamar",        "https://youtu.be/NLYBE8eFWts"),
    ("Mask Off - Future",           "https://youtu.be/xvZqHgFz51I"),
    ("Goosebumps - Travis Scott",   "https://youtu.be/Dst9gZkq1a8"),
    ("God's Plan - Drake",          "https://youtu.be/xpVfcZ0ZcFM"),
    ("m.A.A.d city - Kendrick",     "https://youtu.be/xFFUkxBdCfQ"),
    ("Started From Bottom - Drake", "https://youtu.be/RubBzkZzpUA"),
    ("Bad and Boujee - Migos",      "https://youtu.be/P9mh7zHtPMY"),
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

def ask(prompt):
    try:
        return gemini_client.models.generate_content(model=MODEL, contents=prompt).text.strip()
    except Exception as e:
        log.error(f"Gemini: {e}")
        return f"Gemini error: {e}"

def get_problem(d):
    w, day = week_day(d)
    song   = pick_song(d)
    save(d)
    return ask(f"""Strict SDE-1 DSA coach. Week {w} Day {day}, topic: {topic(w)}.
Recent solves: {[s['problem'] for s in d['solves'][-10:]] or 'none'}
My notes: {[l['note'] for l in d['logs'][-3:]] or 'none'}
Pick ONE Medium LeetCode problem. Do NOT repeat recent solves.
Reply EXACTLY:
PROBLEM: [number]. [title]
LINK: https://leetcode.com/problems/[slug]/
PATTERN: [pattern]
WHY: [1 sentence]
HINT: [1 line nudge, not the solution]
SONG: {song[0]} -> {song[1]}""")

def coach_reply(text, d):
    w, day = week_day(d)
    return ask(f"""DSA coach on Telegram. Max 3 sentences. Week {w} Day {day}, topic: {topic(w)}.
Recent: {[s['problem'] for s in d['solves'][-5:]]}.
User: "{text}"
Be helpful, direct, real.""")

def send_daily():
    d = load()
    if d.get("paused") and datetime.now().strftime("%Y-%m-%d") <= d.get("pause_until", ""):
        return
    w, day = week_day(d)
    rec = get_problem(d)
    try:
        bot.send_message(CHAT_ID,
            f"Good morning!\nWeek {w} Day {day} - {topic(w)}\n"
            f"Streak: {d['streaks']['current']} days | Solved: {len(d['solves'])}\n\n"
            f"{rec}\n\n/solved 238 | /extra | /status",
            disable_web_page_preview=True)
        log.info("Daily sent")
    except Exception as e:
        log.error(f"Daily failed: {e}")

def run_scheduler():
    schedule.every().day.at("02:00").do(send_daily)
    while True:
        schedule.run_pending()
        time.sleep(30)

@bot.message_handler(commands=["start", "status"])
def cmd_status(m):
    d = load(); w, day = week_day(d); s = d["streaks"]
    recent = "\n".join(f"  {x['problem']}" for x in d["solves"][-5:]) or "  None yet"
    bot.reply_to(m,
        f"DSA Coach\nWeek {w} Day {day} - {topic(w)}\n"
        f"Solves: {len(d['solves'])} | Streak: {s['current']} days (best: {s['best']})\n\n"
        f"Recent:\n{recent}")

@bot.message_handler(commands=["extra"])
def cmd_extra(m):
    bot.reply_to(m, "Fetching problem...")
    d = load()
    bot.reply_to(m, get_problem(d), disable_web_page_preview=True)

@bot.message_handler(commands=["solved"])
def cmd_solved(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /solved 238"); return
    d = load()
    d["solves"].append({"problem": parts[1].strip(), "date": datetime.now().strftime("%Y-%m-%d")})
    update_streak(d); save(d)
    bot.reply_to(m, f"Logged {parts[1].strip()}! Streak: {d['streaks']['current']} days")

@bot.message_handler(commands=["log"])
def cmd_log(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /log struggled with trees"); return
    d = load()
    d["logs"].append({"note": parts[1].strip(), "date": datetime.now().strftime("%Y-%m-%d")})
    save(d); bot.reply_to(m, "Logged!")

@bot.message_handler(commands=["skip"])
def cmd_skip(m):
    d = load(); d["skips"].append({"date": datetime.now().strftime("%Y-%m-%d")}); save(d)
    bot.reply_to(m, "Skipped today. Come back tomorrow.")

@bot.message_handler(commands=["break"])
def cmd_break(m):
    parts = m.text.split()
    days  = int(parts[1]) if len(parts) > 1 else 1
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    d = load(); d["paused"] = True; d["pause_until"] = until; save(d)
    bot.reply_to(m, f"Paused for {days} days. /resume when back.")

@bot.message_handler(commands=["resume"])
def cmd_resume(m):
    d = load(); d["paused"] = False; d["pause_until"] = ""; save(d)
    bot.reply_to(m, "Resumed!")

@bot.message_handler(commands=["ping"])
def cmd_ping(m):
    bot.reply_to(m, f"Alive! {datetime.now().strftime('%H:%M UTC')}")

@bot.message_handler(func=lambda m: True, content_types=["text"])
def cmd_chat(m):
    if m.text and m.text.startswith("/"):
        bot.reply_to(m, "Unknown command. Try /start"); return
    d = load()
    bot.send_chat_action(m.chat.id, "typing")
    bot.reply_to(m, coach_reply(m.text, d))

# Simple /webhook path — no token in URL so no special character issues
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.content_type != "application/json":
        abort(403)
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data(as_text=True))])
    return "ok", 200

@app.route("/", methods=["GET"])
def health():
    return "DSA Coach Bot running", 200

if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    log.info("Bot running")
    app.run(host="0.0.0.0", port=PORT)
