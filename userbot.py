# userbot.py — সোর্স চ্যানেল থেকে পোস্ট পড়ে আপনার ডেস্টিনেশনে পাঠায়
from dotenv import load_dotenv
load_dotenv()

import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import API_ID, API_HASH, SESSION, PHONE
from settings_store import load_settings, save_settings
from privacy import clean_personal
from editor import format_post
from ai_client import ai_rewrite

# ═══ Settings লোড ═══
settings = load_settings()

# ═══ Userbot ক্লায়েন্ট ═══
if API_ID and API_HASH and SESSION:
    user_client = TelegramClient(StringSession(), API_ID, API_HASH)
else:
    user_client = None
    print("⚠️ userbot চালু হবে না — TELEGRAM_API_ID / API_HASH / SESSION সেট করুন।")

# ═══ Rate Limit / Flood Control ═══
_last_post_time = {}
MIN_GAP = 2  # পোস্টের মধ্যে ন্যূনতম ২ সেকেন্ড গ্যাপ


def log_post(status: str, detail: str = ""):
    """পোস্টের লগ লেখা"""
    from config import DATA_DIR
    log_file = DATA_DIR / "posts.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{status}\n")
    except Exception:
        pass


def is_bot_post(event) -> bool:
    """Bot নিজের পোস্ট চেনা — anti-loop"""
    sender = event.sender
    if sender and getattr(sender, "bot", False):
        return True
    return False


def is_destination_channel(chat_id: int) -> bool:
    """ডেস্টিনেশন চ্যানেলের পোস্ট ignore"""
    return chat_id in settings.get("destinations", [])


def is_duplicate(event) -> bool:
    """ডুপ্লিকেট পোস্ট চেক"""
    post_id = event.message.id
    chat_id = event.chat_id
    unique_key = f"{chat_id}_{post_id}"
    duplicates = settings.setdefault("duplicate_check", [])
    if unique_key in duplicates:
        return True
    duplicates.append(unique_key)
    # শুধু শেষ ১০০০০ টা রাখো
    if len(duplicates) > 10000:
        settings["duplicate_check"] = duplicates[-10000:]
    save_settings(settings)
    return False


def is_rate_limited() -> bool:
    """রেট লিমিট চেক"""
    global _last_post_time
    now = time.time()
    last = _last_post_time.get("last", 0)
    if now - last < MIN_GAP:
        return True
    return False


def mark_posted():
    global _last_post_time
    _last_post_time["last"] = time.time()


# ═══ মূল হ্যান্ডলার: সোর্স চ্যানেলে নতুন পোস্ট ═══
async def on_new_post(event):
    try:
        chat_id = event.chat_id
        sources = settings.get("sources", [])
        destinations = settings.get("destinations", [])
        autopost_on = settings.get("autopost", False)

        # ১. Autopost চালু আছে কিনা
        if not autopost_on:
            return

        # ২. এটা সোর্স চ্যানেল কিনা
        if str(chat_id) not in [str(s) for s in sources]:
            return

        # ৩. Bot পোস্ট? (Anti-loop)
        if is_bot_post(event):
            return

        # ৪. ডেস্টিনেশন চ্যানেল? (Anti-loop)
        if is_destination_channel(chat_id):
            return

        # ৫. ডুপ্লিকেট?
        if is_duplicate(event):
            log_post("duplicate")
            return

        # ৬. রেট লিমিট?
        if is_rate_limited():
            await asyncio.sleep(MIN_GAP)

        # ৭. টেক্সট সংগ্রহ
        text = event.message.text or ""
        if not text or not text.strip():
            log_post("skipped", "no text")
            return

        post_text = text.strip()

        # ৮. প্রাইভেসি ফিল্টার
        privacy = settings.get("privacy", {})
        contact = settings.get("replacements", {}).get("contact", "@FastOTP_Nishat")
        post_text = clean_personal(post_text, privacy, contact)

        # ৯. AI রিরাইট (চালু থাকলে)
        ai = settings.get("ai", {})
        if ai.get("enabled", False) and ai.get("custom_prompt") != "off":
            try:
                post_text = ai_rewrite(post_text, {
                    "style": ai.get("style", "সহায়ক, ভদ্র ও সংক্ষিপ্ত"),
                    "length": ai.get("length", "মাঝারি"),
                    "emoji": ai.get("emoji", True),
                    "custom_prompt": ai.get("custom_prompt", ""),
                    "contact": contact,
                })
            except Exception as e:
                print(f"⚠️ AI এরর, মূল পোস্টই যাবে: {e}")

        # ১০. এডিটর (ক্লিন + টেমপ্লেট)
        post_text = format_post(post_text, settings)

        # ১১. ডিলে
        delay = settings.get("delay_minutes", 0)
        if delay > 0:
            await asyncio.sleep(delay * 60)

        # ১২. পাবলিশ (সব ডেস্টিনেশনে)
        for dest in destinations:
            try:
                if user_client and user_client.is_connected():
                    await user_client.send_message(dest, post_text)
                else:
                    print(f"⚠️ userbot কানেক্টেড নেই: {dest}")
                    continue
                mark_posted()
                log_post("published")
                print(f"✅ পোস্ট পাবলিশ: {dest}")
            except Exception as e:
                log_post("failed", str(e)[:200])
                print(f"❌ পাবলিশ এরর ({dest}): {e}")

    except Exception as e:
        log_post("error", str(e)[:200])
        print(f"❌ on_new_post এরর: {e}")


# ═══ Userbot চালু ═══
async def main():
    if not user_client:
        print("❌ userbot: API/Session সেট আছে না — চালু হচ্ছে না।")
        return

    await user_client.start(phone=PHONE)
    me = await user_client.get_me()
    print(f"👀 Userbot চালু: {me.first_name} (ID: {me.id})")

    # সোর্স চ্যানেল মনিটর
    sources = settings.get("sources", [])
    print(f"👀 {len(sources)} সোর্স চ্যানেল দেখা হচ্ছে...")
    for src in sources:
        print(f"   📡 {src}")

    print(f"🏠 {len(settings.get('destinations', []))} ডেস্টিনেশন")

    # নতুন পোস্ট ইভেন্ট
    @user_client.on(events.NewMessage)
    async def handler(event):
        await on_new_post(event)

    print("🟢 সোর্স মনিটরিং চালু — নতুন পোস্টের জন্য অপেক্ষা...")
    await user_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
