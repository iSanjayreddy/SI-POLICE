import os
import random
from datetime import datetime

# Get secrets
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Your list of problems (add as many as you want from your Week 1 plan)
problems = [
    "124. Binary Tree Maximum Path Sum - https://leetcode.com/problems/binary-tree-maximum-path-sum/",
    "15. 3Sum - https://leetcode.com/problems/3sum/",
    "238. Product of Array Except Self - https://leetcode.com/problems/product-of-array-except-self/",
    "11. Container With Most Water - https://leetcode.com/problems/container-with-most-water/",
    "3. Longest Substring Without Repeating Characters - https://leetcode.com/problems/longest-substring-without-repeating-characters/",
    "53. Maximum Subarray - https://leetcode.com/problems/maximum-subarray/",
    "209. Minimum Size Subarray Sum - https://leetcode.com/problems/minimum-size-subarray-sum/",
    "167. Two Sum II - Input Array Is Sorted - https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/",
    # Add 20-30+ problems here (especially from Arrays, HashMaps, Two Pointers)
]

def send_telegram_message():
    problem = random.choice(problems)
    
    message = f"""🌅 Good Morning!

Today's DSA Problem:

{problem}

Solve it today! 💪
Reply here with your approach or time taken.

Keep grinding for SDE-1!"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    response = __import__('requests').post(url, json=data)
    
    if response.status_code == 200:
        print(f"✅ Message sent successfully at {datetime.now()}")
    else:
        print(f"❌ Failed: {response.text}")

if __name__ == "__main__":
    send_telegram_message()
