import os
import json
import telebot
import google.generativeai as genai
from datetime import datetime, timedelta
import threading
import schedule
import time

# ============== CONFIG ==============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")  # your personal chat ID

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============== YOUR FULL PLAN (embedded) ==============
YOUR_FULL_PLAN = """PHASE 1 — DSA Foundation (Weeks 1–8)
Week 1: Arrays, Strings, HashMaps (Day 1-2 Frequency, Day 3-4 Two Pointers, Day 5 Prefix sums)
Week 2: Binary Search
Week 3: Trees (Binary + BST)
Week 4: Graphs (BFS + DFS)
Week 5: Heaps + Priority Queues
Week 6: Sliding Window
Week 7: DP 1D
Week 8: DP 2D + Phase 1 Exit Test
PHASE 2 — DSA Completion + System Design (Weeks 9–13)
Week 9: Monotonic Stack + Queue
Week 10: Intervals + Greedy
Week 11: Backtracking
Week 12: Advanced Graphs
Week 13: Full Review + Exit Test
After that: Maintenance mode (3 problems/week)"""

# ============== PROGRESS ==============
PROGRESS_FILE = "progress.json"

def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except:
        return {"solves": [], "logs": [], "last_date": None, "start_date": "2026-04-21"}

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ============== LLM PROMPT (this is where the magic happens) ==============
def get_personalized_recommendation(progress):
    today = datetime.now().strftime("%Y-%m-%d")
    recent_solves = [s["problem"] for s in progress["solves"][-10:]]
    recent_logs = progress["logs"][-5:]

    prompt = f"""You are my strict but motivating DSA coach for SDE-1 prep.
My exact plan: {YOUR_FULL_PLAN}

Today is {today}.
My recent solves: {recent_solves}
My recent logs: {recent_logs}

Give me EXACTLY this format (nothing else):

PROBLEM: [LeetCode number + title] - https://leetcode.com/problems/...

WHY THIS ONE: (1 sentence why it fits my current week/day + recent solves)

SONG: [Song name - Artist] → https://youtu.be/... (real YouTube link, high-energy grind/reel type, Kanye/Tyler/Travis/Future vibe)

KEEP IT MEDIUM DIFFICULTY for my level."""

    response = model.generate_content(prompt)
    return response.text.strip()

# ============== DAILY MESSAGE ==============
def send_daily_message():
    progress = load_progress()
    rec = get_personalized_recommendation(progress)
    
    message = f"🌅 Good Morning Champion!\n\n{rec}\n\nReply with:\n/solved 123\n/log your note here\n/skip\n/break 2\n/extra\n/status"
    
    try:
        bot.send_message(CHAT_ID, message)
        print("Daily message sent")
    except Exception as e:
        print("Error:", e)

# ============== COMMANDS ==============
@bot.message_handler(commands=['start', 'status'])
def status(message):
    progress = load_progress()
    bot.reply_to(message, f"✅ Bot alive\nSolved today: {len([s for s in progress['solves'] if s['date']==datetime.now().strftime('%Y-%m-%d')])}\nTotal solves: {len(progress['solves'])}")

@bot.message_handler(commands=['solved'])
def solved(message):
    try:
        prob = message.text.split(maxsplit=1)[1].strip()
        progress = load_progress()
        progress["solves"].append({"problem": prob, "date": datetime.now().strftime("%Y-%m-%d")})
        save_progress(progress)
        bot.reply_to(message, f"✅ Marked {prob} as solved. Great job!")
    except:
        bot.reply_to(message, "Usage: /solved 238")

@bot.message_handler(commands=['log'])
def log(message):
    note = message.text.split(maxsplit=1)[1].strip()
    progress = load_progress()
    progress["logs"].append({"note": note, "date": datetime.now().strftime("%Y-%m-%d")})
    save_progress(progress)
    bot.reply_to(message, "📝 Logged. I’ll remember this for tomorrow’s recommendation.")

@bot.message_handler(commands=['skip'])
def skip(message):
    bot.reply_to(message, "⏭️ Today skipped. Tomorrow’s recommendation will adjust.")

@bot.message_handler(commands=['break'])
def take_break(message):
    bot.reply_to(message, "🛑 Break noted. I’ll pause daily problems until you say /start again.")

@bot.message_handler(commands=['extra'])
def extra(message):
    progress = load_progress()
    rec = get_personalized_recommendation(progress)
    bot.reply_to(message, f"🔥 Extra problem:\n{rec}")

# ============== SCHEDULER (runs every day at 7:30 AM IST) ==============
def run_scheduler():
    schedule.every().day.at("02:00").do(send_daily_message)  # 7:30 AM IST = 02:00 UTC
    while True:
        schedule.run_pending()
        time.sleep(60)

# ============== START BOT ==============
if __name__ == "__main__":
    # Start daily scheduler in background
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    print("🚀 DSA Coach Bot started...")
    bot.infinity_polling()
