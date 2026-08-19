"""Collect source posts, make minimal edits, publish, then forward from ours."""
import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telegram.ext import Application

from config import BOT_TOKEN, API_ID, API_HASH, SESSION, PHONE, DATA_DIR, EMOJI_EDITING
from editor import edit_post
from ai_client import edit_post_with_ai
from privacy import clean_personal, replace_personal
from settings_store import is_processed, load_settings, mark_processed

bot_app = Application.builder().token(BOT_TOKEN).build()
user_client = TelegramClient(SESSION, API_ID, API_HASH)
TEMP_DIR = DATA_DIR / "media_tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
FORWARD_HISTORY = DATA_DIR / "channel_group_forward_history.jsonl"


def log_post(status: str):
    with open(DATA_DIR / "posts.log", "a", encoding="utf-8") as file:
        file.write(status + "\n")


def forward_key(source_chat, message_id, group, repeat_index):
    return f"{source_chat}:{message_id}:{group}:{repeat_index}"


def forward_done(key: str) -> bool:
    try:
        with FORWARD_HISTORY.open(encoding="utf-8") as file:
            return any(json.loads(line).get("key") == key for line in file if line.strip())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False


def record_forward(key, source_chat, message_id, group, repeat_index, status, error=""):
    record = {
        "key": key,
        "source_chat": str(source_chat),
        "source_message_id": message_id,
        "group": str(group),
        "forward_number": repeat_index + 1,
        "time": datetime.utcnow().isoformat() + "Z",
        "status": status,
        "error": error[:300],
    }
    with FORWARD_HISTORY.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def schedule_wait_seconds(group_settings: dict) -> int:
    schedule = group_settings.get("schedule", {})
    if not schedule.get("enabled"):
        return 0
    now = datetime.now()
    try:
        start = datetime.strptime(schedule.get("start", "00:00"), "%H:%M").time()
        end = datetime.strptime(schedule.get("end", "23:59"), "%H:%M").time()
    except ValueError:
        return 0
    inside = start <= now.time() <= end if start <= end else now.time() >= start or now.time() <= end
    if inside:
        return 0
    next_start = datetime.combine(now.date(), start)
    if next_start <= now:
        next_start += timedelta(days=1)
    return max(0, int((next_start - now).total_seconds()))


async def forward_channel_post(event, settings):
    config = settings.get("channel_group_forwarding", {})
    if not config.get("enabled"):
        return
    groups = config.get("groups", {})
    if not groups:
        return
    source_chat = event.chat_id
    for group, group_settings in groups.items():
        if not group_settings.get("enabled", True) or group_settings.get("paused"):
            continue
        count = max(1, min(20, int(group_settings.get("count", 1))))
        delay = max(0, int(group_settings.get("delay_seconds", 0)))
        wait_for_schedule = schedule_wait_seconds(group_settings)
        if wait_for_schedule:
            await asyncio.sleep(wait_for_schedule)
        for repeat_index in range(count):
            key = forward_key(source_chat, event.id, group, repeat_index)
            if forward_done(key) or not settings.get("channel_group_forwarding", {}).get("enabled"):
                continue
            if repeat_index and delay:
                await asyncio.sleep(delay)
            try:
                if group_settings.get("ai_enabled") and (event.message.text or event.message.message):
                    ai_settings = dict(settings.get("ai", {}))
                    ai_settings.update(group_settings.get("ai", {}))
                    edited = await edit_post_with_ai(event.message.text or event.message.message or "", {"ai": ai_settings})
                    sent = await send_message(group, event.message, edited)
                    _ = sent
                else:
                    await bot_app.bot.forward_message(
                        chat_id=group,
                        from_chat_id=source_chat,
                        message_id=event.id,
                    )
                record_forward(key, source_chat, event.id, group, repeat_index, "success")
            except Exception as error:
                record_forward(key, source_chat, event.id, group, repeat_index, "error", str(error))
                print(f"⚠️ Channel → Group failed for {group}: {error}")


def apply_template(text: str, template: dict) -> str:
    parts = []
    if template.get("header"):
        parts.append(template["header"])
    if text:
        parts.append(text)
    if template.get("footer"):
        parts.append(template["footer"])
    return "\n\n".join(parts)


async def prepare_text(text: str, settings: dict) -> str:
    text = clean_personal(
        text,
        settings.get("privacy"),
        settings.get("replacements"),
    )
    ai = settings.get("ai", {})
    if ai.get("enabled") and text:
        try:
            text = await edit_post_with_ai(text, settings)
        except Exception as error:
            print(f"⚠️ AI editing failed, original cleaned text used: {error}")
    text = edit_post(text, settings.get("emoji_editing", EMOJI_EDITING))
    return apply_template(text, settings.get("template", {}))


async def send_message(destination, message, text: str):
    """Send text or media through the bot, preserving the original media type."""
    if not message.media:
        return await bot_app.bot.send_message(destination, text)

    media_path = await message.download_media(file=str(TEMP_DIR))
    if not media_path:
        return await bot_app.bot.send_message(destination, text)
    path = Path(media_path)
    try:
        with path.open("rb") as media:
            if message.photo:
                return await bot_app.bot.send_photo(destination, media, caption=text)
            if message.video:
                return await bot_app.bot.send_video(destination, media, caption=text)
            if message.animation:
                return await bot_app.bot.send_animation(destination, media, caption=text)
            if message.audio:
                return await bot_app.bot.send_audio(destination, media, caption=text)
            if message.voice:
                return await bot_app.bot.send_voice(destination, media, caption=text)
            return await bot_app.bot.send_document(destination, media, caption=text)
    finally:
        try:
            path.unlink()
        except OSError:
            pass


async def forward_repeatedly(source_chat, message_id, groups, forwarding):
    """Forward the edited message from the user's channel, never re-compose it."""
    if not forwarding.get("enabled") or not groups:
        return
    count = max(1, int(forwarding.get("repeat_count", 1)))
    interval = max(0, int(forwarding.get("repeat_interval_minutes", 0))) * 60
    for repeat_index in range(count):
        if repeat_index and interval:
            await asyncio.sleep(interval)
        for group in groups:
            try:
                await bot_app.bot.forward_message(
                    chat_id=group,
                    from_chat_id=source_chat,
                    message_id=message_id,
                )
            except Exception as error:
                print(f"⚠️ Forward failed for {group}: {error}")


@user_client.on(events.NewMessage())
async def on_destination_post(event):
    settings = load_settings()
    destination_values = {str(item).lstrip("@").lower() for item in settings.get("destinations", [])}
    chat = await event.get_chat()
    chat_id = str(event.chat_id)
    username = str(getattr(chat, "username", "") or "").lstrip("@").lower()
    if chat_id not in destination_values and (not username or username not in destination_values):
        return
    asyncio.create_task(forward_channel_post(event, settings))


@user_client.on(events.NewMessage())
async def on_new_post(event):
    settings = load_settings()
    chat = await event.get_chat()
    source_values = {str(item).lstrip("@").lower() for item in settings["sources"]}
    chat_id = str(event.chat_id)
    chat_username = str(getattr(chat, "username", "") or "").lstrip("@").lower()
    if chat_id not in source_values and (not chat_username or chat_username not in source_values):
        return

    post_key = f"{event.chat_id}:{event.id}"
    if is_processed(post_key) or not settings["autopost"]:
        return

    message = event.message
    raw_text = message.text or message.message or ""
    final_text = await prepare_text(raw_text, settings)
    if not final_text and not message.media:
        log_post("skipped")
        mark_processed(post_key)
        return

    delay_minutes = max(0, int(settings.get("delay_minutes", 0)))
    if delay_minutes:
        await asyncio.sleep(delay_minutes * 60)

    destinations = settings["destinations"]
    if not destinations:
        print("❌ destination channel সেট করা নেই — স্কিপ")
        log_post("skipped")
        return

    for destination in destinations:
        try:
            sent = await send_message(destination, message, final_text)
            # Option B: forward the edited message from our destination channel.
            asyncio.create_task(
                forward_repeatedly(
                    destination,
                    sent.message_id,
                    settings.get("forward_groups", []),
                    settings.get("forwarding", {}),
                )
            )
        except Exception as error:
            print(f"⚠️ Publish failed for {destination}: {error}")
            log_post("failed")
            return

    mark_processed(post_key)
    log_post("published")
    print(f"✅ Edited post published and forwarding scheduled: {final_text[:50]}...")


async def main():
    await bot_app.initialize()
    await bot_app.start()
    await user_client.connect()
    if not await user_client.is_user_authorized():
        await user_client.send_code_request(PHONE)
        print("📲 Telegram OTP পাঠানো হয়েছে। TELEGRAM_CODE সেট করে workflow আবার চালু করুন।", flush=True)
        code = os.getenv("TELEGRAM_CODE", "").strip()
        if not code:
            raise RuntimeError("TELEGRAM_CODE পাওয়া যায়নি")
        try:
            await user_client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            password = os.getenv("TELEGRAM_2FA_PASSWORD", "")
            if not password:
                raise RuntimeError("TELEGRAM_2FA_PASSWORD পাওয়া যায়নি")
            await user_client.sign_in(password=password)
    print("👀 settings.json-এর সব source channel দেখা হচ্ছে...")
    await user_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())