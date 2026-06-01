"""Print chat IDs the bot can see. Message the bot first, then run this.

Usage:
    TELEGRAM_BOT_TOKEN=... python scripts/get_chat_id.py
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    print("Set TELEGRAM_BOT_TOKEN (env or .env) first", file=sys.stderr)
    raise SystemExit(2)

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
resp.raise_for_status()
updates = resp.json().get("result", [])
if not updates:
    print("No updates. Send any message to your bot in Telegram, then re-run.")
    raise SystemExit(0)

seen = {}
for u in updates:
    msg = u.get("message") or u.get("channel_post") or {}
    chat = msg.get("chat", {})
    if chat.get("id") is not None:
        seen[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name", "")
for cid, name in seen.items():
    print(f"chat_id={cid}  ({name})")
