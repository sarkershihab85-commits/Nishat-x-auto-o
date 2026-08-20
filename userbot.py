# userbot.py — Personal Account Control & Auto-Forward Engine
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_ID, API_HASH, SESSION_STRING
from settings_store import load_settings, save_settings
from ai_client import edit_post_with_ai, answer_group_message, notify_admin_error

# User Client Initialization
if SESSION_STRING:
    user_client = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    user_client = Client("user_session", api_id=API_ID, api_hash=API_HASH)


def is_monitored_source(chat_id_or_username, settings: dict) -> bool:
    """পোস্টটি কি মনিটর করা কোনো সোর্স চ্যানেল থেকে এসেছে তা চেক করার লজিক"""
    sources = settings.get("sources", [])
    target = str(chat_id_or_username).lower()
    for s in sources:
        if str(s).lower() in [target, f"@{target}"]:
            return True
    return False


@user_client.on_message(filters.channel)
async def auto_post_listener(client: Client, message: Message):
    """সোর্স চ্যানেলে নতুন পোস্ট আসলে তা ক্যাচ করে AI এডিট এবং ডেস্টিনেশন চ্যানেলে অটো পোস্ট করার হ্যান্ডলার"""
    settings = load_settings()
    
    # অটো পোস্ট অপশন চালু না থাকলে স্কিপ করবে
    if not settings.get("autopost", True):
        return

    chat_identifier = message.chat.username or str(message.chat.id)
    if not is_monitored_source(chat_identifier, settings):
        return

    destinations = settings.get("destinations", [])
    if not destinations:
        return

    post_text = message.text or message.caption or ""

    # AI Process and Privacy Clean
    if post_text:
        processed_text = await edit_post_with_ai(post_text, settings)
    else:
        processed_text = ""

    # Destination Channels-এ পোস্ট পাঠানো
    for dest in destinations:
        try:
            if message.media:
                await user_client.copy_message(
                    chat_id=dest,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                    caption=processed_text
                )
            else:
                await user_client.send_message(chat_id=dest, text=processed_text)
            
            # Post Log Save
            log_post_status("published")

        except Exception as err:
            log_post_status("skipped")
            print(f"⚠️ Channel Post Error ({dest}): {err}")


@user_client.on_message(filters.group & ~filters.me)
async def group_auto_reply_listener(client: Client, message: Message):
    """গ্রুপের অটো-রিপ্লাই (AI Group Assistant) হ্যান্ডলার"""
    settings = load_settings()
    group_config = settings.get("channel_group_forwarding", {}).get("groups", {})
    
    chat_id = str(message.chat.id)
    if chat_id in group_config and group_config[chat_id].get("ai_enabled", False):
        if message.text:
            reply_text = await answer_group_message(message.text, settings)
            if reply_text:
                await message.reply_text(reply_text)


def log_post_status(status: str):
    """পোস্ট পাবলিশ বা স্কিপের হিসাব ফাইল এ লগ করার ফাংশন"""
    from config import DATA_DIR
    try:
        with open(DATA_DIR / "posts.log", "a", encoding="utf-8") as f:
            f.write(f"{status}\n")
    except Exception:
        pass
