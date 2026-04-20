import os
import json
import telebot
import google.generativeai as genai
from datetime import datetime
import threading
import schedule
import time

# ============== CONFIG ==============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

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

def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except:
        return {"solves": [], "logs": [], "start_date": "2026-04-21"}

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_personalized_recommendation(progress):
    today = datetime.now().strftime("%Y-%m-%d")
    recent_solves = [s["problem"] for s in progress["solves"][-10:]]
    recent_logs = [log["note"] for log in progress["logs"][-5:]]

    prompt = f"""You are my personal strict but motivating SDE-1 DSA coach.
My exact plan: {YOUR_FULL_PLAN}

Today: {today}
Recent solves: {recent_solves}
Recent logs: {recent_logs}

Give EXACTLY this format (nothing else):

PROBLEM: [LeetCode number + title] - https://leetcode.com/problems/...

WHY THIS ONE: (1 sentence why it fits my current week/day + recent solves/logs)

SONG: [Song name - Artist] → https://youtu.be/... (real high-energy grind/reel motivational song, Kanye/Tyler/Travis/Future style)

Keep it Medium difficulty for my current level."""

    response = model.generate_content(prompt)
    return response.text.strip()

def send_daily_message():
    progress = load_progress()
    rec = get_personalized_recommendation(progress)
    message = f"🌅 Good Morning Champion!\n\n{rec}\n\nReply with:\n/solved 238\n/log your note here\n/skip\n/break 2\n/extra\n/status"
    bot.send_message(CHAT_ID, message)

# ============== COMMANDS ==============
@bot.message_handler(commands=['start', 'status'])
def status(message):
    progress = load_progress()
    bot.reply_to(message, f"✅ Coach is alive\nTotal solves: {len(progress['solves'])}\nType /extra for instant problem")

@bot.message_handler(commands=['solved'])
def solved(message):
    try:
        prob = message.text.split(maxsplit=1)[1].strip()
        progress = load_progress()
        progress["solves"].append({"problem": prob, "date": datetime.now().strftime("%Y-%m-%d")})
        save_progress(progress)
        bot.reply_to(message, f"✅ Marked {prob} as solved 🔥")
    except:
        bot.reply_to(message, "Usage: /solved 238")

@bot.message_handler(commands=['log'])
def log_cmd(message):
    note = message.text.split(maxsplit=1)[1].strip()
    progress = load_progress()
    progress["logs"].append({"note": note, "date": datetime.now().strftime("%Y-%m-%d")})
    save_progress(progress)
    bot.reply_to(message, "📝 Logged. Tomorrow’s recommendation will use this.")

@bot.message_handler(commands=['skip'])
def skip(message):
    bot.reply_to(message, "⏭️ Today skipped.")

@bot.message_handler(commands=['break'])
def take_break(message):
    bot.reply_to(message, "🛑 Break noted. Daily messages paused until you type /start again.")

@bot.message_handler(commands=['extra'])
def extra(message):
    progress = load_progress()
    rec = get_personalized_recommendation(progress)
    bot.reply_to(message, f"🔥 Extra problem right now:\n{rec}")

@bot.message_handler(func=lambda m: True)
def general(message):
    if message.text.startswith('/'): return
    bot.reply_to(message, "👋 Hey! I'm your DSA coach.\nSend /start or any command above.")

# ============== SCHEDULER (7:30 AM IST = 02:00 UTC) ==============
def run_scheduler():
    schedule.every().day.at("02:00").do(send_daily_message)   # Tomorrow morning 7:30 AM IST
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("🚀 DSA Coach Bot started - Gemini is active")
    bot.infinity_polling()
