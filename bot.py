"""
DSA Coach Bot — Fully Optimized
- Gemini 2.5 Flash for problem recs + dynamic replies
- Curated song bank + Gemini song picker
- Smart week/day tracking
- Full command suite
- Railway-safe (no 409 conflicts)
"""

import os
import json
import logging
import threading
import schedule
import time
import sys
import fcntl
import random
from datetime import datetime, timedelta

import telebot
from telebot import types
import google.generativeai as genai

# ============================================================
# LOGGING — See everything in Railway logs
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))  # MUST be int
START_DATE = os.getenv("START_DATE", "2026-04-21")
PROGRESS_FILE = os.getenv("PROGRESS_FILE", "progress.json")
LOCK_FILE = "/tmp/dsa_coach.lock"

if not TELEGRAM_TOKEN or not GEMINI_API_KEY or not CHAT_ID:
    log.error("Missing env vars: TELEGRAM_TOKEN, GEMINI_API_KEY, CHAT_ID — exiting")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True, num_threads=4)

# ============================================================
# PROCESS LOCK — prevents Railway 409 on redeploy
# ============================================================
def acquire_lock():
    lf = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lf.write(str(os.getpid()))
        lf.flush()
        log.info(f"Process lock acquired (PID {os.getpid()})")
        return lf
    except BlockingIOError:
        log.error("Another instance is running — exiting to avoid 409")
        sys.exit(1)

# ============================================================
# YOUR PLAN
# ============================================================
YOUR_FULL_PLAN = """
PHASE 1 — DSA Foundation (Weeks 1–8)
Week 1 — Arrays, Strings, HashMaps:
  Day 1-2: Frequency counting with hashmaps
  Day 3-4: Two pointers (opposite ends)
  Day 5: Prefix sums

Week 2 — Binary Search:
  Day 1: Classic binary search
  Day 2-3: Binary search on answer space
  Day 4-5: Boundary finding

Week 3 — Trees (Binary + BST):
  Day 1-2: DFS with return-value patterns
  Day 3: BFS level-order traversal
  Day 4: BST operations
  Day 5: Path problems

Week 4 — Graphs (BFS + DFS):
  Day 1: BFS shortest path
  Day 2: DFS connected components
  Day 3: Cycle detection + Topological sort
  Day 4: Union-Find (DSU)
  Day 5: Mixed graph problems

Week 5 — Heaps + Priority Queues:
  Day 1-2: Top-K problems
  Day 3: Merge K sorted lists
  Day 4: Two-heap median trick
  Day 5: Sliding window max/min

Week 6 — Sliding Window:
  Day 1: Fixed-size window
  Day 2-3: Longest valid window
  Day 4-5: Shortest valid window

Week 7 — DP (1D):
  Day 1: Linear DP
  Day 2: Choice DP (house robber style)
  Day 3: String DP
  Day 4: Kadane's algorithm
  Day 5: Space optimization

Week 8 — DP (2D) + Phase 1 Exit Test

PHASE 2 — Weeks 9–13:
  Week 9: Monotonic Stack
  Week 10: Intervals + Greedy
  Week 11: Backtracking
  Week 12: Advanced Graphs (Dijkstra, Bellman-Ford, Prim)
  Week 13: Full review + mock interviews

After Phase 2: Maintenance mode (3 problems/week, mixed)
"""

# ============================================================
# SONG BANK — High-energy grind anthems
# ============================================================
SONG_BANK = [
    {"title": "POWER - Kanye West", "url": "https://youtu.be/L53gjP-TtGE"},
    {"title": "Jumpman - Drake & Future", "url": "https://youtu.be/NyP-PjNOaH8"},
    {"title": "Mask Off - Future", "url": "https://youtu.be/xvZqHgFz51I"},
    {"title": "Goosebumps - Travis Scott", "url": "https://youtu.be/Dst9gZkq1a8"},
    {"title": "Sicko Mode - Travis Scott", "url": "https://youtu.be/6ONRf7h3Mdk"},
    {"title": "m.A.A.d city - Kendrick Lamar", "url": "https://youtu.be/xFFUkxBdCfQ"},
    {"title": "Money Trees - Kendrick Lamar", "url": "https://youtu.be/ekwjmjHDiKI"},
    {"title": "Alright - Kendrick Lamar", "url": "https://youtu.be/Z-48u_uWMHY"},
    {"title": "NEW MAGIC WAND - Tyler the Creator", "url": "https://youtu.be/9-RMcwVLBqQ"},
    {"title": "EARFQUAKE - Tyler the Creator", "url": "https://youtu.be/m57hMdHD-oI"},
    {"title": "Essence - Wizkid", "url": "https://youtu.be/IKMOh9HRTDA"},
    {"title": "F**kin Problems - ASAP Rocky", "url": "https://youtu.be/cQ5jRUsHosc"},
    {"title": "Work - Rihanna", "url": "https://youtu.be/HL1UzIK-flA"},
    {"title": "Bad and Boujee - Migos", "url": "https://youtu.be/P9mh7zHtPMY"},
    {"title": "Tunnel Vision - Kodak Black", "url": "https://youtu.be/3t0OUQM9xIU"},
    {"title": "God's Plan - Drake", "url": "https://youtu.be/xpVfcZ0ZcFM"},
    {"title": "Started From the Bottom - Drake", "url": "https://youtu.be/RubBzkZzpUA"},
    {"title": "Clique - Kanye West", "url": "https://youtu.be/vCFa3pGPKyY"},
    {"title": "Black Skinhead - Kanye West", "url": "https://youtu.be/NkRkBDQ7fR0"},
    {"title": "All Falls Down - Kanye West", "url": "https://youtu.be/8kyWDhB_QeI"},
    {"title": "Humble - Kendrick Lamar", "url": "https://youtu.be/tvTRZJ-4EyI"},
    {"title": "DNA - Kendrick Lamar", "url": "https://youtu.be/NLYBE8eFWts"},
    {"title": "Pick Up the Phone - Young Thug", "url": "https://youtu.be/bHScFtQKIl0"},
    {"title": "Way 2 Sexy - Drake", "url": "https://youtu.be/OlegueILrMQ"},
    {"title": "Father Stretch My Hands - Kanye West", "url": "https://youtu.be/uYzUOM73bB0"},
]

def pick_song_smart(progress):
    """Pick a song Gemini hasn't picked recently (track in progress)."""
    used = set(progress.get("used_songs", []))
    fresh = [s for s in SONG_BANK if s["title"] not in used]
    if not fresh:
        # Reset cycle
        fresh = SONG_BANK
        progress["used_songs"] = []
    song = random.choice(fresh)
    progress.setdefault("used_songs", []).append(song["title"])
    return song

# ============================================================
# PROGRESS
# ============================================================
_lock = threading.Lock()

def load_progress():
    with _lock:
        try:
            with open(PROGRESS_FILE) as f:
                return json.load(f)
        except Exception:
            return {
                "solves": [],
                "logs": [],
                "skips": [],
                "streaks": {"current": 0, "best": 0, "last_solve_date": ""},
                "start_date": START_DATE,
                "used_songs": [],
                "paused": False,
                "pause_until": "",
            }

def save_progress(data):
    with _lock:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(data, f, indent=2)

def update_streak(progress):
    today = datetime.now().strftime("%Y-%m-%d")
    last = progress["streaks"].get("last_solve_date", "")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if last == today:
        return  # Already updated today
    if last == yesterday:
        progress["streaks"]["current"] += 1
    elif last != today:
        progress["streaks"]["current"] = 1
    progress["streaks"]["last_solve_date"] = today
    if progress["streaks"]["current"] > progress["streaks"]["best"]:
        progress["streaks"]["best"] = progress["streaks"]["current"]

def get_week_day(progress):
    start = datetime.strptime(progress.get("start_date", START_DATE), "%Y-%m-%d")
    elapsed = (datetime.now() - start).days
    week = (elapsed // 7) + 1
    day = (elapsed % 7) + 1
    return week, day

def get_topic_for_week(week):
    topics = {
        1: "Arrays, Strings, HashMaps",
        2: "Binary Search",
        3: "Trees (Binary + BST)",
        4: "Graphs (BFS + DFS)",
        5: "Heaps + Priority Queues",
        6: "Sliding Window",
        7: "Dynamic Programming 1D",
        8: "Dynamic Programming 2D",
        9: "Monotonic Stack",
        10: "Intervals + Greedy",
        11: "Backtracking",
        12: "Advanced Graphs",
        13: "Full Review + Mock Interviews",
    }
    return topics.get(week, "Mixed Review")

# ============================================================
# GEMINI CALLS
# ============================================================
def gemini_get_problem(progress):
    week, day = get_week_day(progress)
    topic = get_topic_for_week(week)
    recent_solves = [s["problem"] for s in progress["solves"][-15:]]
    recent_logs = [l["note"] for l in progress["logs"][-5:]]
    streak = progress["streaks"]["current"]
    song = pick_song_smart(progress)

    prompt = f"""You are a strict but motivating SDE-1 DSA interview coach. No fluff, pure signal.

My plan:
{YOUR_FULL_PLAN}

Context:
- Today: {datetime.now().strftime("%Y-%m-%d")} (Week {week}, Day {day})
- Current topic: {topic}
- Recent solves: {recent_solves if recent_solves else "None yet"}
- My notes/struggles: {recent_logs if recent_logs else "None yet"}
- Current streak: {streak} days

Pick ONE Medium LeetCode problem perfectly suited for Week {week} Day {day} of my plan.
Do NOT repeat any of these: {recent_solves}

Reply in EXACTLY this format, nothing else before or after:

PROBLEM: [number]. [title]
LINK: https://leetcode.com/problems/[slug]/
PATTERN: [1-2 word pattern name, e.g. "Two Pointers", "Sliding Window"]
WHY: [1 sharp sentence: why this fits Week {week} Day {day} + my recent activity]
HINT: [1 line conceptual nudge — not the solution, just the key insight to unlock it]
SONG: {song['title']} → {song['url']}"""

    try:
        response = gemini.generate_content(prompt)
        save_progress(progress)  # Save updated used_songs
        return response.text.strip()
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return f"⚠️ Gemini error: {e}\n\nTry /extra again in a moment."

def gemini_reply(user_message, progress):
    """Dynamic conversational reply for freeform messages."""
    week, day = get_week_day(progress)
    topic = get_topic_for_week(week)
    recent_solves = [s["problem"] for s in progress["solves"][-10:]]
    recent_logs = [l["note"] for l in progress["logs"][-5:]]

    prompt = f"""You are a strict but encouraging SDE-1 DSA coach on Telegram. Be concise — max 4 sentences. No markdown headers. Use emojis sparingly.

My context:
- Week {week}, Day {day} of my DSA plan
- Current topic: {topic}
- Recent solves: {recent_solves}
- My logs: {recent_logs}

User message: "{user_message}"

Respond helpfully. If they ask about a problem/concept, explain it briefly and precisely.
If they're venting or frustrated, be real and motivating — not cheesy.
If they ask something unrelated to DSA, gently redirect."""

    try:
        response = gemini.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        log.error(f"Gemini chat error: {e}")
        return "⚠️ Couldn't reach Gemini right now. Try again in a sec."

def gemini_review_solution(problem, approach, progress):
    """Review a solution approach the user describes."""
    week, day = get_week_day(progress)
    prompt = f"""You are a strict SDE-1 DSA interview coach. Review this solution approach concisely.

Problem: {problem}
User's approach: {approach}

Give:
1. VERDICT: Correct / Partially correct / Wrong
2. TIME: O(?) complexity
3. SPACE: O(?) complexity  
4. FEEDBACK: 2 sentences max — what's good + what to improve
5. OPTIMAL: Is there a better approach? One line if yes.

Be direct. No fluff."""

    try:
        response = gemini.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Gemini error: {e}"

# ============================================================
# DAILY MESSAGE
# ============================================================
def send_daily_message():
    progress = load_progress()
    if progress.get("paused"):
        pause_until = progress.get("pause_until", "")
        if pause_until and datetime.now().strftime("%Y-%m-%d") <= pause_until:
            log.info(f"Bot paused until {pause_until}, skipping daily message")
            return
        else:
            progress["paused"] = False
            save_progress(progress)

    week, day = get_week_day(progress)
    topic = get_topic_for_week(week)
    streak = progress["streaks"]["current"]
    total = len(progress["solves"])

    streak_msg = f"🔥 {streak} day streak!" if streak > 1 else "Day 1 — let's build that streak"

    try:
        rec = gemini_get_problem(progress)
        message = (
            f"🌅 *Good morning, Champion!*\n"
            f"_{streak_msg} | Week {week} · Day {day} · {topic}_\n"
            f"_{total} problems solved total_\n\n"
            f"{rec}\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"*Commands:*\n"
            f"`/solved 238` — log a solve\n"
            f"`/review 238 your approach` — get feedback\n"
            f"`/log note` — save a thought\n"
            f"`/extra` — get another problem\n"
            f"`/skip` — skip today\n"
            f"`/status` — see your stats"
        )
        bot.send_message(CHAT_ID, message, parse_mode="Markdown", disable_web_page_preview=True)
        log.info(f"Daily message sent — Week {week} Day {day}")
    except Exception as e:
        log.error(f"Failed to send daily message: {e}")
        bot.send_message(CHAT_ID, f"⚠️ Daily message failed: {e}")

# ============================================================
# REPLY HELPER
# ============================================================
def safe_reply(message, text, **kwargs):
    try:
        bot.reply_to(message, text, **kwargs)
        log.info(f"Replied to @{message.from_user.username}: {text[:60]}")
    except Exception as e:
        log.error(f"Failed to reply: {e}")
        try:
            bot.send_message(message.chat.id, text, **kwargs)
        except Exception as e2:
            log.error(f"send_message also failed: {e2}")

# ============================================================
# COMMANDS
# ============================================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    log.info(f"/start from {message.from_user.id}")
    progress = load_progress()
    week, day = get_week_day(progress)
    topic = get_topic_for_week(week)
    safe_reply(
        message,
        f"🚀 *DSA Coach Bot is LIVE*\n\n"
        f"📅 You're on *Week {week}, Day {day}*\n"
        f"📚 Topic: _{topic}_\n"
        f"🔥 Streak: {progress['streaks']['current']} days\n"
        f"✅ Total solves: {len(progress['solves'])}\n\n"
        f"I'll ping you every morning at *7:30 AM IST* with a problem + song.\n\n"
        f"Commands:\n"
        f"`/extra` — problem right now\n"
        f"`/solved 238` — log a solve\n"
        f"`/review 238 approach` — solution review\n"
        f"`/log note` — save a thought\n"
        f"`/status` — full stats\n"
        f"`/skip` — skip today\n"
        f"`/break 3` — pause for N days\n"
        f"`/resume` — unpause\n"
        f"`/ping` — test bot is alive",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["status"])
def cmd_status(message):
    log.info(f"/status from {message.from_user.id}")
    progress = load_progress()
    week, day = get_week_day(progress)
    topic = get_topic_for_week(week)
    streak = progress["streaks"]
    solves = progress["solves"]
    logs = progress["logs"]

    # Last 5 solves
    recent = "\n".join([f"  • {s['problem']} ({s['date']})" for s in solves[-5:]]) or "  None yet"

    paused_info = ""
    if progress.get("paused"):
        paused_info = f"\n⏸️ *Paused until:* {progress.get('pause_until', '?')}"

    safe_reply(
        message,
        f"📊 *Your DSA Progress*\n\n"
        f"📅 Week {week} · Day {day} · _{topic}_\n"
        f"✅ Total solves: *{len(solves)}*\n"
        f"📝 Total logs: *{len(logs)}*\n"
        f"🔥 Current streak: *{streak['current']} days*\n"
        f"🏆 Best streak: *{streak['best']} days*\n"
        f"{paused_info}\n\n"
        f"*Last 5 solves:*\n{recent}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["solved"])
def cmd_solved(message):
    log.info(f"/solved from {message.from_user.id}: {message.text}")
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError("missing problem")
        prob = parts[1].strip()
        progress = load_progress()
        today = datetime.now().strftime("%Y-%m-%d")
        progress["solves"].append({"problem": prob, "date": today})
        update_streak(progress)
        save_progress(progress)
        streak = progress["streaks"]["current"]
        streak_emoji = "🔥" * min(streak, 5)
        safe_reply(
            message,
            f"✅ *{prob}* logged!\n\n"
            f"{streak_emoji} Streak: *{streak} days*\n"
            f"Total: *{len(progress['solves'])} problems solved*\n\n"
            f"Keep grinding. Every problem rewires your brain 🧠",
            parse_mode="Markdown"
        )
    except Exception as e:
        log.warning(f"/solved parse error: {e}")
        safe_reply(message, "Usage: `/solved 238` or `/solved Product of Array Except Self`", parse_mode="Markdown")

@bot.message_handler(commands=["review"])
def cmd_review(message):
    log.info(f"/review from {message.from_user.id}")
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError()
        problem = parts[1].strip()
        approach = parts[2].strip()
        safe_reply(message, "🔍 Reviewing your approach...")
        progress = load_progress()
        feedback = gemini_review_solution(problem, approach, progress)
        safe_reply(message, f"*Solution Review — Problem {problem}*\n\n{feedback}", parse_mode="Markdown")
    except Exception:
        safe_reply(
            message,
            "Usage: `/review 238 I used a prefix product array, left pass then right pass`",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=["log"])
def cmd_log(message):
    log.info(f"/log from {message.from_user.id}")
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError()
        note = parts[1].strip()
        progress = load_progress()
        progress["logs"].append({"note": note, "date": datetime.now().strftime("%Y-%m-%d")})
        save_progress(progress)
        safe_reply(message, f"📝 *Logged:* _{note}_\n\nGemini will use this for tomorrow's recommendation.", parse_mode="Markdown")
    except Exception:
        safe_reply(message, "Usage: `/log struggled with two pointers today`", parse_mode="Markdown")

@bot.message_handler(commands=["extra"])
def cmd_extra(message):
    log.info(f"/extra from {message.from_user.id}")
    safe_reply(message, "⏳ Fetching your next problem from Gemini...")
    progress = load_progress()
    rec = gemini_get_problem(progress)
    week, day = get_week_day(progress)
    safe_reply(
        message,
        f"🔥 *Extra Problem — Week {week} Day {day}*\n\n{rec}",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@bot.message_handler(commands=["skip"])
def cmd_skip(message):
    log.info(f"/skip from {message.from_user.id}")
    progress = load_progress()
    today = datetime.now().strftime("%Y-%m-%d")
    progress["skips"].append({"date": today})
    save_progress(progress)
    skips = len(progress["skips"])
    safe_reply(
        message,
        f"⏭️ Today skipped.\n\n"
        f"Total skips: {skips}. Skipping is okay — quitting isn't. See you tomorrow 💪"
    )

@bot.message_handler(commands=["break"])
def cmd_break(message):
    log.info(f"/break from {message.from_user.id}")
    try:
        parts = message.text.split()
        days = int(parts[1]) if len(parts) > 1 else 1
        days = max(1, min(days, 30))
        until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        progress = load_progress()
        progress["paused"] = True
        progress["pause_until"] = until
        save_progress(progress)
        safe_reply(
            message,
            f"🛑 *Break mode ON* — paused for {days} day(s) until {until}.\n\n"
            f"Rest. Recover. Type /resume when you're back.",
            parse_mode="Markdown"
        )
    except Exception:
        safe_reply(message, "Usage: `/break 3` (pause for 3 days)", parse_mode="Markdown")

@bot.message_handler(commands=["resume"])
def cmd_resume(message):
    log.info(f"/resume from {message.from_user.id}")
    progress = load_progress()
    progress["paused"] = False
    progress["pause_until"] = ""
    save_progress(progress)
    safe_reply(message, "✅ *Back in the game!* Daily messages resumed. Let's get it 🔥", parse_mode="Markdown")

@bot.message_handler(commands=["ping"])
def cmd_ping(message):
    log.info(f"/ping from {message.from_user.id}")
    safe_reply(message, f"🏓 Pong! Bot is alive.\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

@bot.message_handler(commands=["song"])
def cmd_song(message):
    log.info(f"/song from {message.from_user.id}")
    progress = load_progress()
    song = pick_song_smart(progress)
    save_progress(progress)
    safe_reply(
        message,
        f"🎵 *Grind Song:*\n{song['title']}\n{song['url']}\n\nNow go solve something.",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@bot.message_handler(commands=["week"])
def cmd_week(message):
    log.info(f"/week from {message.from_user.id}")
    progress = load_progress()
    week, day = get_week_day(progress)
    topic = get_topic_for_week(week)

    # Extract week-specific info from plan
    week_lines = [l.strip() for l in YOUR_FULL_PLAN.splitlines() if f"Week {week}" in l or f"Day" in l]

    safe_reply(
        message,
        f"📅 *Week {week} · Day {day}*\n"
        f"📚 Topic: _{topic}_\n\n"
        f"Focus on mastering the core patterns for this topic. "
        f"Quality > quantity. One well-understood problem beats five shallow ones.\n\n"
        f"Type /extra to get today's problem.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["reset"])
def cmd_reset(message):
    log.info(f"/reset from {message.from_user.id}")
    # Require confirmation
    safe_reply(
        message,
        "⚠️ *Are you sure you want to reset all progress?*\n\n"
        "Type `/confirm_reset` to wipe everything and start fresh.\n"
        "This cannot be undone.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["confirm_reset"])
def cmd_confirm_reset(message):
    progress = {
        "solves": [],
        "logs": [],
        "skips": [],
        "streaks": {"current": 0, "best": 0, "last_solve_date": ""},
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "used_songs": [],
        "paused": False,
        "pause_until": "",
    }
    save_progress(progress)
    safe_reply(message, "🔄 Progress reset. Fresh start from today. Let's go 🚀")

# ============================================================
# DYNAMIC REPLY (catch-all free text → Gemini)
# ============================================================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    text = message.text or ""
    if text.startswith("/"):
        safe_reply(message, "❓ Unknown command. Try /start to see all commands.")
        return

    log.info(f"Free text from {message.from_user.id}: {text[:80]}")
    bot.send_chat_action(message.chat.id, "typing")
    progress = load_progress()
    reply = gemini_reply(text, progress)
    safe_reply(message, reply)

# ============================================================
# SCHEDULER — 7:30 AM IST = 02:00 UTC
# ============================================================
def run_scheduler():
    schedule.every().day.at("02:00").do(send_daily_message)
    log.info("⏰ Scheduler started — daily message at 02:00 UTC (7:30 AM IST)")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    lock = acquire_lock()

    # Verify bot token works before doing anything else
    try:
        me = bot.get_me()
        log.info(f"✅ Bot verified: @{me.username} (ID: {me.id})")
    except Exception as e:
        log.error(f"❌ Bot token invalid or Telegram unreachable: {e}")
        sys.exit(1)

    threading.Thread(target=run_scheduler, daemon=True).start()

    log.info("🚀 DSA Coach Bot fully started — Gemini 2.5 Flash active")

    # Manually drop pending updates before polling starts (avoids 409 + stale messages)
    try:
        updates = bot.get_updates(offset=-1, timeout=1)
        if updates:
            bot.get_updates(offset=updates[-1].update_id + 1, timeout=1)
        log.info("✅ Pending updates cleared")
    except Exception as e:
        log.warning(f"Could not clear pending updates: {e}")

    bot.infinity_polling(
        timeout=20,
        long_polling_timeout=15,
        allowed_updates=["message"],
        logger_level=logging.WARNING,
    )
