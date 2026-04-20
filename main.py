import os
import json
import telebot
import google.generativeai as genai
from datetime import datetime
import threading
import schedule
import time
import sys
import fcntl  # Unix-only process lock — works on Railway

# ============== CONFIG ==============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)

# ============== PROCESS LOCK (prevents 409 on Railway redeploy) ==============
LOCK_FILE = "/tmp/dsa_coach_bot.lock"

def acquire_lock():
    """Ensure only one instance runs. Exits immediately if another is running."""
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.write(str(os.getpid()))
        lock.flush()
        return lock  # Keep reference alive so lock holds
    except BlockingIOError:
        print("❌ Another bot instance is running. Exiting.")
        sys.exit(1)

# ============== YOUR FULL DETAILED PLAN ==============
YOUR_FULL_PLAN = """PHASE 1 — DSA Foundation (Weeks 1–8)
Week 1 — Arrays, Strings, HashMaps: Day 1-2 Frequency counting with hashmaps, Day 3-4 Two pointers (opposite ends), Day 5 Prefix sums
Week 2 — Binary Search: Day 1 Classic, Day 2-3 Binary search on answer space, Day 4-5 Boundary finding
Week 3 — Trees (Binary + BST): Day 1-2 DFS return-value, Day 3 BFS, Day 4 BST, Day 5 Path problems
Week 4 — Graphs (BFS + DFS): Day 1 BFS shortest path, Day 2 DFS components, Day 3 Cycle + Topological, Day 4 Union-Find, Day 5 Mixed
Week 5 — Heaps + Priority Queues: Day 1-2 Top-K, Day 3 Merge K, Day 4 Two-heap median, Day 5 Sliding window max/min
Week 6 — Sliding Window: Day 1 Fixed-size, Day 2-3 Longest valid, Day 4-5 Shortest valid
Week 7 — DP (1D): Day 1 Linear, Day 2 Choice, Day 3 String, Day 4 Kadane, Day 5 Space optimization
Week 8 — DP (2D) + Phase 1 Exit Test
PHASE 2 — Weeks 9-13 (Monotonic Stack, Intervals+Greedy, Backtracking, Advanced Graphs, Full Review)
After Phase 2: Maintenance mode (3 problems/week mixed)"""

PROGRESS_FILE = "progress.json"

# ============== PROGRESS ==============
def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except:
        return {"solves": [], "logs": [], "start_date": "2026-04-21"}

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ============== GEMINI ==============
def get_personalized_recommendation(progress):
    today = datetime.now().strftime("%Y-%m-%d")
    start = datetime.strptime(progress.get("start_date", "2026-04-21"), "%Y-%m-%d")
    days_elapsed = (datetime.now() - start).days
    week_num = (days_elapsed // 7) + 1
    day_num = (days_elapsed % 7) + 1

    recent_solves = [s["problem"] for s in progress["solves"][-10:]]
    recent_logs = [log["note"] for log in progress["logs"][-5:]]

    prompt = f"""You are my personal strict but motivating SDE-1 DSA coach.
My exact plan: {YOUR_FULL_PLAN}

Today: {today} (Week {week_num}, Day {day_num} of my plan)
Recent solves: {recent_solves}
Recent logs: {recent_logs}

Give EXACTLY this format (nothing else, no extra text):

PROBLEM: [LeetCode number + title] - https://leetcode.com/problems/[slug]/

WHY THIS ONE: (1 sentence why it fits Week {week_num} Day {day_num} + my recent activity)

SONG: [Song name - Artist] → https://youtu.be/[real-video-id] (high-energy grind song, Kanye/Tyler/Travis/Future/Kendrick style)

Keep it Medium difficulty."""

    response = model.generate_content(prompt)
    return response.text.strip()

# ============== DAILY MESSAGE ==============
def send_daily_message():
    try:
        progress = load_progress()
        rec = get_personalized_recommendation(progress)
        message = (
            f"🌅 *Good Morning Champion!*\n\n"
            f"{rec}\n\n"
            f"Reply with:\n"
            f"`/solved 238` — mark solved\n"
            f"`/log your note` — log a thought\n"
            f"`/skip` — skip today\n"
            f"`/extra` — get another problem\n"
            f"`/status` — see your stats"
        )
        bot.send_message(CHAT_ID, message, parse_mode="Markdown")
        print(f"✅ Daily message sent at {datetime.now()}")
    except Exception as e:
        print(f"❌ Failed to send daily message: {e}")

# ============== COMMANDS ==============
@bot.message_handler(commands=['start', 'status'])
def status(message):
    progress = load_progress()
    start = datetime.strptime(progress.get("start_date", "2026-04-21"), "%Y-%m-%d")
    days_elapsed = (datetime.now() - start).days
    week_num = (days_elapsed // 7) + 1
    bot.reply_to(
        message,
        f"✅ *DSA Coach is alive*\n\n"
        f"📅 Week {week_num} of your plan\n"
        f"🔥 Total solves: {len(progress['solves'])}\n"
        f"📝 Total logs: {len(progress['logs'])}\n\n"
        f"Type /extra for an instant problem",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['solved'])
def solved(message):
    try:
        prob = message.text.split(maxsplit=1)[1].strip()
        progress = load_progress()
        progress["solves"].append({
            "problem": prob,
            "date": datetime.now().strftime("%Y-%m-%d")
        })
        save_progress(progress)
        bot.reply_to(message, f"✅ Marked *{prob}* as solved 🔥 Keep grinding!", parse_mode="Markdown")
    except IndexError:
        bot.reply_to(message, "Usage: `/solved 238` or `/solved Two Sum`", parse_mode="Markdown")

@bot.message_handler(commands=['log'])
def log_cmd(message):
    try:
        note = message.text.split(maxsplit=1)[1].strip()
        progress = load_progress()
        progress["logs"].append({
            "note": note,
            "date": datetime.now().strftime("%Y-%m-%d")
        })
        save_progress(progress)
        bot.reply_to(message, "📝 Logged! Tomorrow's recommendation will factor this in.")
    except IndexError:
        bot.reply_to(message, "Usage: `/log struggled with sliding window today`", parse_mode="Markdown")

@bot.message_handler(commands=['skip'])
def skip(message):
    bot.reply_to(message, "⏭️ Today skipped. Rest well, come back stronger tomorrow 💪")

@bot.message_handler(commands=['break'])
def take_break(message):
    bot.reply_to(message, "🛑 Break noted. Type /start when you're back. Consistency > intensity.")

@bot.message_handler(commands=['extra'])
def extra(message):
    bot.reply_to(message, "⏳ Fetching your next problem...")
    progress = load_progress()
    rec = get_personalized_recommendation(progress)
    bot.reply_to(message, f"🔥 *Extra problem:*\n\n{rec}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def general(message):
    if message.text and message.text.startswith('/'):
        return
    bot.reply_to(
        message,
        "👋 Hey! I'm your DSA Coach.\n\nCommands:\n"
        "/status — see your progress\n"
        "/extra — get a problem now\n"
        "/solved 238 — log a solve\n"
        "/log your note — log thoughts\n"
        "/skip — skip today\n"
        "/break — pause messages"
    )

# ============== SCHEDULER (7:30 AM IST = 02:00 UTC) ==============
def run_scheduler():
    schedule.every().day.at("02:00").do(send_daily_message)
    print("⏰ Scheduler running — daily message at 02:00 UTC (7:30 AM IST)")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ============== MAIN ==============
if __name__ == "__main__":
    lock = acquire_lock()  # Die fast if another instance is running

    threading.Thread(target=run_scheduler, daemon=True).start()
    print("🚀 DSA Coach Bot started — Gemini 2.5 Flash active")

    # drop_pending_updates=True clears any queued messages from while bot was offline
    # This also prevents 409 race on redeploy by dropping stale poll sessions
    bot.infinity_polling(
        timeout=20,
        long_polling_timeout=15,
        allowed_updates=["message"],
        drop_pending_updates=True,
        restart_on_change=False,
        logger_level=None,  # Suppress telebot's noisy internal logging
    )
