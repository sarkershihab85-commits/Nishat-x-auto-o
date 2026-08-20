# main.py — অটো পোস্ট বটের অ্যাডমিন প্যানেল (সম্পূর্ণ বাংলা UI)
from dotenv import load_dotenv
load_dotenv()
import json
from config import DATA_DIR

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          filters, ContextTypes)

from config import BOT_TOKEN, ADMIN_IDS
from settings_store import load_settings, save_settings
from ai_client import answer_group_message

# ═══ স্টেট ও ডেটা ═══
settings = load_settings()
my_channels = {}
user_state = {}   # {user_id: {"step": ..., "type": ...}}

# ═══ ফাইল-ভিত্তিক স্টেট ও স্ট্যাটস (আসল, কাজ করে) ═══
def set_autopost(on: bool):
    settings["autopost"] = on
    save_settings(settings)

def read_stats():
    pub = skip = 0
    try:
        with open(DATA_DIR / "posts.log") as f:
            for line in f:
                if line.strip() == "published": pub += 1
                elif line.strip() == "skipped": skip += 1
    except FileNotFoundError:
        pass
    return pub, skip

# ═══ UI: মেনুগুলো ═══
def main_kb():
    return ReplyKeyboardMarkup([
        ["📡 চ্যানেল সেটিংস"],
        ["🛡️ প্রাইভেসি ফিল্টার"],
        ["📝 অটো পোস্ট", "📊 পরিসংখ্যান"],
        ["🤖 AI সেটিংস", "📩 User Messaging"],
        ["📢 Channel → Group"],
        ["⚙️ সেটিংস", "❓ সাহায্য"],
    ], resize_keyboard=True)

def channel_kb():
    return ReplyKeyboardMarkup([
        ["🏠 Destination", "📡 Source"],
        ["➕ Source যোগ", "➖ Source বাদ"],
        ["➕ Destination যোগ", "➖ Destination বাদ"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)

def privacy_kb():
    return ReplyKeyboardMarkup([
        ["👤 @username", "📞 ফোন"],
        ["✉️ ইমেইল", "🔗 t.me লিংক"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)

def autopost_kb():
    return ReplyKeyboardMarkup([
        ["🟢 চালু করুন", "🔴 বন্ধ করুন"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)

def settings_kb():
    return ReplyKeyboardMarkup([
        ["⏱️ ডিলে সেট", "📝 টেমপ্লেট"],
        ["🔁 Forward সেটিংস", "📇 Personal তথ্য"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def ai_kb():
    return ReplyKeyboardMarkup([
        ["🟢 AI Editing চালু", "🔴 AI Editing বন্ধ"],
        ["🎨 AI Style", "🧠 Custom Prompt"],
        ["📏 Post Length", "✨ AI Emoji ON/OFF"],
        ["🎭 AI পরিচয় সেটিংস"],
        ["👥 Group AI সেটিংস"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def ai_identity_kb():
    return ReplyKeyboardMarkup([
        ["🤖 AI-র নাম", "👑 Owner-এর নাম"],
        ["🚫 অতিরিক্ত Filter/নিষেধ"],
        ["📄 Master নির্দেশনা (Text/File)"],
        ["⬅️ AI সেটিংসে ফিরুন"],
    ], resize_keyboard=True)


def user_message_kb():
    return ReplyKeyboardMarkup([
        ["👥 User List", "➕ User যোগ"],
        ["📝 Common Message", "⏰ Schedule"],
        ["📩 এখন পাঠান", "🟢 Campaign চালু"],
        ["🔴 Campaign বন্ধ", "🗑️ User সরান"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def channel_group_kb():
    return ReplyKeyboardMarkup([
        ["➕ Group যোগ করুন", "👥 Group List"],
        ["🎯 Select Group"],
        ["⚙️ Forward Settings", "🔢 Forward Count"],
        ["⏱️ Delay", "📅 Schedule"],
        ["🤖 AI Editing", "🟢 C→G চালু"],
        ["🔴 C→G বন্ধ", "⏸️ Pause"],
        ["▶️ Resume", "📊 Status"],
        ["📝 History", "⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def selected_forward_group():
    forwarding = settings["channel_group_forwarding"]
    return forwarding["groups"].get(str(forwarding.get("selected_group", "")))


def read_forward_history():
    path = DATA_DIR / "channel_group_forward_history.jsonl"
    rows = []
    try:
        with path.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    rows.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return rows

def is_admin(uid): return uid in ADMIN_IDS


async def optin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    key = str(user.id)
    username_key = (user.username or "").lstrip("@")
    users = settings.setdefault("users", {})
    # যদি admin আগে থেকে @username দিয়ে pre-add করে রাখে, সেই পুরনো enable/status ধরে রেখে
    # numeric ID-তে merge করে দেওয়া হচ্ছে — send_message-এর জন্য numeric ID-ই আসল key।
    existing = users.pop(username_key, None) if username_key and username_key in users and username_key != key else None
    record = users.setdefault(key, existing or {})
    record.update({
        "id": user.id,
        "username": user.username or "",
        "name": user.full_name or "",
        "opted_in": True,
        "enabled": record.get("enabled", True),
        "status": "ready",
    })
    campaign_ids = settings.setdefault("user_campaign", {}).setdefault("user_ids", [])
    if username_key and username_key in campaign_ids:
        campaign_ids.remove(username_key)
    if key not in campaign_ids:
        campaign_ids.append(key)
    save_settings(settings)
    await update.message.reply_text("✅ আপনি opt-in করেছেন। এখন থেকে Admin-এর অনুমোদিত message পেতে পারেন।")


async def optout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record = settings.setdefault("users", {}).setdefault(str(user.id), {})
    record.update({"id": user.id, "opted_in": False, "enabled": False, "status": "opted_out"})
    save_settings(settings)
    await update.message.reply_text("✅ আপনি opt-out করেছেন। আর campaign message পাঠানো হবে না।")


async def manage_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ অনুমতি নেই।")
        return
    command = update.message.text.split()[0].lower()
    value = update.message.text.split(maxsplit=1)[1].strip().lstrip("@") if len(update.message.text.split()) > 1 else ""
    if not value:
        await update.message.reply_text("User ID বা @username দিন।")
        return
    record = settings.setdefault("users", {}).get(value)
    if not record:
        await update.message.reply_text("⚠️ User তালিকায় পাওয়া যায়নি।")
        return
    if command == "/useron":
        record["enabled"] = True
        record["status"] = "ready"
        message = "✅ User চালু হয়েছে।"
    elif command == "/useroff":
        record["enabled"] = False
        record["status"] = "disabled"
        message = "✅ User বন্ধ হয়েছে।"
    elif command == "/userremove":
        settings["users"].pop(value, None)
        settings["user_campaign"]["user_ids"] = [item for item in settings["user_campaign"]["user_ids"] if str(item) != value]
        message = "✅ User সরানো হয়েছে।"
    elif command == "/userstatus":
        message = f"User: {value}\nOpt-in: {record.get('opted_in', False)}\nEnabled: {record.get('enabled', False)}\nStatus: {record.get('status', 'unknown')}"
    elif command == "/retry":
        if not record.get("opted_in") or not record.get("enabled", True):
            message = "⚠️ User opt-in করেনি অথবা বন্ধ আছে।"
        else:
            try:
                await ctx.bot.send_message(chat_id=record.get("id", value), text=settings["user_campaign"]["message"])
                record["status"] = "sent"
                message = "✅ Retry সফল হয়েছে।"
            except Exception as error:
                record["status"] = f"failed: {str(error)[:80]}"
                message = "❌ Retry ব্যর্থ হয়েছে।"
    else:
        return
    save_settings(settings)
    await update.message.reply_text(message, reply_markup=user_message_kb())


async def handle_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text or not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    group = settings.setdefault("group_ai", {}).get(chat_id, {})
    if not group.get("enabled", False):
        return
    text = message.text.strip()
    mode = group.get("reply_mode", "question")
    mentioned = ctx.bot.username and f"@{ctx.bot.username.lower()}" in text.lower()
    replied_to_bot = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot)
    if mode == "mention" and not mentioned:
        return
    if mode == "reply" and not replied_to_bot:
        return
    if mode == "ask" and not text.lower().startswith("/ask"):
        return
    if mode == "question" and not (text.endswith(("?", "？")) or "?" in text):
        return
    if mode == "ask":
        text = text[4:].strip()
    identity = {
        "identity_name": settings.get("ai", {}).get("identity_name", ""),
        "owner_name": settings.get("ai", {}).get("owner_name", ""),
        "identity_filter": settings.get("ai", {}).get("identity_filter", ""),
        "master_instruction": settings.get("ai", {}).get("master_instruction", ""),
    }
    group_context = {**identity, **group}
    try:
        answer = await answer_group_message(text, group_context, "")
        await message.reply_text(answer[:4000], disable_web_page_preview=True)
    except Exception as error:
        print(f"⚠️ AI ERROR group={chat_id}: {repr(error)}", flush=True)
        await message.reply_text("⚠️ AI উত্তর দিতে পারেনি। কিছুক্ষণ পর আবার চেষ্টা করুন।")
        with open(DATA_DIR / "ai_errors.log", "a", encoding="utf-8") as file:
            file.write(f"group={chat_id} error={error}\n")


async def send_campaign(bot):
    campaign = settings.get("user_campaign", {})
    message = campaign.get("message", "").strip()
    if not message:
        return
    delay = max(0, int(campaign.get("delay_minutes", 0)))
    for value in campaign.get("user_ids", []):
        record = settings.get("users", {}).get(str(value), {})
        if not record.get("opted_in") or not record.get("enabled", True):
            continue
        try:
            await bot.send_message(chat_id=record.get("id", value), text=message)
            record["status"] = "sent"
        except Exception as error:
            record["status"] = f"failed: {str(error)[:80]}"
            with open(DATA_DIR / "message_errors.log", "a", encoding="utf-8") as file:
                file.write(f"user={value} error={error}\n")
        save_settings(settings)
        if delay:
            import asyncio
            await asyncio.sleep(delay * 60)


async def campaign_loop(application):
    import asyncio
    while True:
        await asyncio.sleep(60)
        if settings.get("user_campaign", {}).get("enabled"):
            await send_campaign(application.bot)
            settings["user_campaign"]["enabled"] = False
            save_settings(settings)


async def post_init(application):
    import asyncio
    asyncio.create_task(campaign_loop(application))

# ═══ হ্যান্ডলার ═══
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ অনুমতি নেই。"); return
    await update.message.reply_text(
        "👋 স্বাগতম! এটা আপনার **অটো পোস্ট বট**।\n\n"
        "নিচের বাটন থেকে যেকোনো মেনু খুলুন — সব ধাপে ধাপে পরিচালিত হবে।",
        reply_markup=main_kb())

async def handle_forward(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fwd = update.message.forward_from_chat
    state = user_state.get(update.effective_user.id, {})
    if not fwd or state.get("step") != "await_channel" or state.get("type") != "destination_add":
        await update.message.reply_text("💡 Destination যোগ করতে আগে '➕ Destination যোগ' চাপুন।")
        return
    if fwd.id not in settings["destinations"]:
        settings["destinations"].append(fwd.id)
    save_settings(settings)
    user_state.pop(update.effective_user.id, None)
    await update.message.reply_text(
        f"✅ Destination যোগ হয়েছে!\n\n📛 নাম: {fwd.title}\n🆔 ID: {fwd.id}",
        reply_markup=channel_kb())

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    if user_state.get(uid, {}).get("step") != "await_master_instruction":
        return
    doc = update.message.document
    if not doc:
        return
    if doc.file_size and doc.file_size > 200_000:
        await update.message.reply_text("⚠️ ফাইল খুব বড় (সর্বোচ্চ ~200KB)। ছোট .txt ফাইল পাঠান।")
        return
    try:
        file = await ctx.bot.get_file(doc.file_id)
        raw = await file.download_as_bytearray()
        content = bytes(raw).decode("utf-8", errors="replace").strip()
    except Exception as error:
        await update.message.reply_text(f"❌ ফাইল পড়তে সমস্যা হয়েছে: {error}")
        return
    if not content:
        await update.message.reply_text("⚠️ ফাইলটা খালি মনে হচ্ছে।")
        return
    settings["ai"]["master_instruction"] = content[:8000]
    save_settings(settings)
    user_state.pop(uid, None)
    await update.message.reply_text(
        f"✅ ফাইল থেকে Master নির্দেশনা সেভ হয়েছে ({len(content)} অক্ষর)। AI এখন থেকে এই নিয়ম মেনে চলবে।",
        reply_markup=ai_identity_kb())


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ অনুমতি নেই।"); return

    if uid in user_state and user_state[uid]["step"] == "await_campaign_message":
        settings["user_campaign"]["message"] = t
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Common message সেভ হয়েছে।", reply_markup=user_message_kb())
        return

    if uid in user_state and user_state[uid]["step"] == "await_campaign_delay":
        if not t.strip().isdigit():
            await update.message.reply_text("⚠️ শুধু মিনিট সংখ্যা লিখুন।")
            return
        settings["user_campaign"]["delay_minutes"] = int(t.strip())
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Schedule delay সেভ হয়েছে।", reply_markup=user_message_kb())
        return

    if uid in user_state and user_state[uid]["step"] in ("await_ai_style", "await_ai_prompt", "await_ai_length"):
        field = {"await_ai_style": "style", "await_ai_prompt": "custom_prompt", "await_ai_length": "length"}[user_state[uid]["step"]]
        settings["ai"][field] = "" if t.strip() in ("না", "-", "খালি") else t.strip()
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ AI সেটিংস সেভ হয়েছে।", reply_markup=ai_kb())
        return

    if uid in user_state and user_state[uid]["step"] in ("await_ai_identity_name", "await_ai_owner_name", "await_ai_identity_filter"):
        field = {
            "await_ai_identity_name": "identity_name",
            "await_ai_owner_name": "owner_name",
            "await_ai_identity_filter": "identity_filter",
        }[user_state[uid]["step"]]
        settings["ai"][field] = "" if t.strip() in ("না", "-", "খালি") else t.strip()
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ AI পরিচয় সেটিংস সেভ হয়েছে।", reply_markup=ai_identity_kb())
        return

    if uid in user_state and user_state[uid]["step"] == "await_master_instruction":
        if t.strip() in ("না", "-", "খালি"):
            settings["ai"]["master_instruction"] = ""
        else:
            settings["ai"]["master_instruction"] = t.strip()[:8000]
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text(
            "✅ Master নির্দেশনা সেভ হয়েছে। AI এখন থেকে এই নিয়ম মেনে সব জায়গায় কাজ করবে।",
            reply_markup=ai_identity_kb())
        return

    if uid in user_state and user_state[uid]["step"] == "await_users":
        values = [item.strip() for item in t.replace(",", "\n").splitlines() if item.strip()]
        for value in values:
            key = value.lstrip("@")
            if key not in settings["user_campaign"]["user_ids"]:
                settings["user_campaign"]["user_ids"].append(key)
            settings.setdefault("users", {}).setdefault(key, {
                "id": int(key) if key.isdigit() else key,
                "username": value if value.startswith("@") else "",
                "opted_in": False,
                "enabled": True,
                "status": "waiting for opt-in",
            })
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text(f"✅ {len(values)} জন user যোগ হয়েছে। শুধু /optin করা user-দের message যাবে।", reply_markup=user_message_kb())
        return

    if uid in user_state and user_state[uid]["step"] == "await_group_config":
        parts = t.strip().split(maxsplit=2)
        if len(parts) < 2:
            await update.message.reply_text("উদাহরণ: -100123456789 on mention")
            return
        chat_id, enabled = parts[0], parts[1].lower() in ("on", "চালু", "1", "true")
        settings["group_ai"][chat_id] = {
            "enabled": enabled,
            "reply_mode": parts[2] if len(parts) > 2 else "question",
            "style": "সহায়ক, ভদ্র ও সংক্ষিপ্ত",
            "answer_length": "মাঝারি",
            "context_enabled": True,
            "custom_prompt": "",
        }
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Group AI সেটিংস আপডেট হয়েছে।", reply_markup=ai_kb())
        return

    if uid in user_state and user_state[uid]["step"].startswith("await_cg_"):
        step = user_state[uid]["step"]
        value = t.strip()
        forwarding = settings["channel_group_forwarding"]
        if step == "await_cg_add":
            group = value if value.startswith("@") else (int(value) if value.lstrip("-").isdigit() else f"@{value}")
            key = str(group)
            forwarding["groups"].setdefault(key, {
                "enabled": True, "paused": False, "count": 1, "delay_seconds": 0,
                "ai_enabled": False, "schedule": {"enabled": False, "start": "00:00", "end": "23:59"},
                "status": "active",
            })
            forwarding["selected_group"] = key
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ Group যোগ হয়েছে এবং selected হয়েছে: {key}", reply_markup=channel_group_kb())
            return
        if step == "await_cg_select":
            key = value if value in forwarding["groups"] else (f"@{value}" if f"@{value}" in forwarding["groups"] else value)
            if key not in forwarding["groups"]:
                await update.message.reply_text("⚠️ এই Group list-এ নেই।", reply_markup=channel_group_kb())
                return
            forwarding["selected_group"] = key
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ Selected Group: {key}", reply_markup=channel_group_kb())
            return
        group = selected_forward_group()
        if not group:
            user_state.pop(uid, None)
            await update.message.reply_text("⚠️ আগে Group যোগ করে select করুন।", reply_markup=channel_group_kb())
            return
        if step == "await_cg_count" and value.isdigit():
            group["count"] = max(1, min(20, int(value)))
        elif step == "await_cg_delay" and value.isdigit():
            group["delay_seconds"] = max(0, int(value))
        elif step == "await_cg_schedule":
            parts = value.split()
            if len(parts) == 3 and parts[0].lower() in ("on", "off"):
                group["schedule"] = {"enabled": parts[0].lower() == "on", "start": parts[1], "end": parts[2]}
            else:
                await update.message.reply_text("Format: on 09:00 23:00 অথবা off 00:00 23:59")
                return
        else:
            await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
            return
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Group forwarding setting সেভ হয়েছে।", reply_markup=channel_group_kb())
        return

    # ── ধাপ: source/destination যোগ বা বাদ ──
    if uid in user_state and user_state[uid]["step"] == "await_channel":
        state_type = user_state[uid]["type"]
        if state_type.startswith("forward_group_"):
            action = state_type.rsplit("_", 1)[1]
            value = t.strip()
            try:
                value = int(value)
            except ValueError:
                value = value if value.startswith("@") else f"@{value}"
            groups = settings["forward_groups"]
            if action == "add":
                if value not in groups:
                    groups.append(value)
                message = "✅ Forward Group যোগ হয়েছে।"
            else:
                if value in groups:
                    groups.remove(value)
                    message = "✅ Forward Group বাদ দেওয়া হয়েছে।"
                else:
                    message = "⚠️ Group তালিকায় পাওয়া যায়নি।"
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(message, reply_markup=settings_kb())
            return
        if state_type == "source_remove" or state_type == "destination_remove":
            try:
                chat = await ctx.bot.get_chat(t.strip() if t.strip().startswith("@") else f"@{t.strip()}")
                value = chat.username and f"@{chat.username}" or chat.id
            except Exception:
                value = t.strip()
            target = settings["sources"] if state_type == "source_remove" else settings["destinations"]
            candidates = [value, str(value), value.lstrip("@") if isinstance(value, str) else value]
            removed = False
            for item in list(target):
                if item in candidates or str(item).lstrip("@") in candidates:
                    target.remove(item)
                    removed = True
            user_state.pop(uid, None)
            save_settings(settings)
            label = "Source" if state_type == "source_remove" else "Destination"
            await update.message.reply_text(
                f"{'✅ বাদ দেওয়া হয়েছে' if removed else '⚠️ তালিকায় পাওয়া যায়নি'}: {label}",
                reply_markup=channel_kb())
            return

        username = t.replace("https://t.me/", "").replace("@", "").split("/")[0]
        try:
            chat = await ctx.bot.get_chat(f"@{username}")
            if state_type == "source_add":
                source = f"@{chat.username}" if chat.username else str(chat.id)
                if source not in settings["sources"]:
                    settings["sources"].append(source)
                label = "Source"
            else:
                if chat.id not in settings["destinations"]:
                    settings["destinations"].append(chat.id)
                label = "Destination"
            save_settings(settings)
            user_state.pop(uid)
            await update.message.reply_text(
                f"✅ {label} যোগ হয়েছে!\n\n"
                f"📛 নাম: {chat.title}\n🆔 ID: {chat.id}", reply_markup=channel_kb())
        except Exception:
            await update.message.reply_text(
                "❌ চ্যানেল পাওয়া যায়নি。\n\n"
                "💡 ধাপ ১: বটকে ওই চ্যানেলে অ্যাডমিন বানান\n"
                "💡 ধাপ ২: আবার URL পাঠান", reply_markup=channel_kb())
        return

    # ── ধাপ: ডিলে ──
    if uid in user_state and user_state[uid]["step"] == "await_delay":
        if not t.strip().isdigit():
            await update.message.reply_text("⚠️ শুধু মিনিট সংখ্যা লিখুন (যেমন: 5)"); return
        settings["delay_minutes"] = int(t.strip())
        save_settings(settings)
        user_state.pop(uid)
        await update.message.reply_text(
            f"✅ ডিলে সেট হয়েছে: **{settings['delay_minutes']} মিনিট**。", reply_markup=settings_kb())
        return

    if uid in user_state and user_state[uid]["step"] == "await_forward_value":
        state = user_state[uid]
        value = t.strip()
        if state["field"] in ("repeat_count", "repeat_interval_minutes"):
            if not value.isdigit():
                await update.message.reply_text("⚠️ শুধু 0 বা ধনাত্মক সংখ্যা লিখুন।")
                return
            settings["forwarding"][state["field"]] = int(value)
        else:
            settings["forwarding"]["enabled"] = value.lower() in ("চালু", "on", "yes", "1")
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Forward সেটিংস আপডেট হয়েছে।", reply_markup=settings_kb())
        return

    if uid in user_state and user_state[uid]["step"] == "await_replacement":
        field = user_state[uid]["field"]
        settings["replacements"][field] = "" if t.strip() in ("না", "-", "খালি") else t.strip()
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Personal তথ্য সেভ হয়েছে।", reply_markup=settings_kb())
        return

    # ── ধাপ: টেমপ্লেট ──
    if uid in user_state and user_state[uid]["step"] in ("await_tmpl_header", "await_tmpl_footer"):
        step = user_state[uid]["step"]
        if step == "await_tmpl_header":
            settings["template"]["header"] = t
            save_settings(settings)
            user_state[uid]["step"] = "await_tmpl_footer"
            await update.message.reply_text("✅ হেডার সেভ হয়েছে!\n\n📝 এখন **ফুটার** লিখুন (না চাইলে 'না' লিখুন):")
        else:
            if t.lower() != "না":
                settings["template"]["footer"] = t
            save_settings(settings)
            user_state.pop(uid)
            await update.message.reply_text(
                f"✅ টেমপ্লেট সেভ হয়েছে!\n\n"
                f"📌 হেডার: {settings['template']['header'] or '(খালি)'}\n"
                f"📌 ফুটার: {settings['template']['footer'] or '(খালি)'}",
                reply_markup=settings_kb())
        return

    # ── মূল মেনু ──
    if t == "📡 চ্যানেল সেটিংস":
        await update.message.reply_text("📡 চ্যানেল সেটিংস\n\nকোন ধরনের চ্যানেল?", reply_markup=channel_kb())

    elif t == "🏠 Destination":
        lst = "\n".join(f"🟢 {channel}" for channel in settings["destinations"]) or "খালি"
        await update.message.reply_text(
            f"🏠 Destination channel:\n{lst}", reply_markup=channel_kb())

    elif t == "📡 Source":
        lst = "\n".join(f"📡 {s}" for s in settings["sources"]) or "খালি"
        await update.message.reply_text(
            f"📡 Source channel (যেগুলো userbot দেখবে):\n{lst}", reply_markup=channel_kb())

    elif t in ("➕ Source যোগ", "➖ Source বাদ", "➕ Destination যোগ", "➖ Destination বাদ"):
        is_source = "Source" in t
        is_add = "যোগ" in t
        kind = "source" if is_source else "destination"
        action = "add" if is_add else "remove"
        user_state[uid] = {"step": "await_channel", "type": f"{kind}_{action}"}
        if kind == "destination" and is_add:
            await update.message.reply_text(
                "Destination channel-এর একটি post forward করুন অথবা @username/লিংক পাঠান।",
                reply_markup=channel_kb())
        else:
            label = "Source" if is_source else "Destination"
            action_text = "যোগ" if is_add else "বাদ"
            await update.message.reply_text(
                f"{label} {action_text} করতে @username বা t.me লিংক পাঠান।",
                reply_markup=channel_kb())

    elif t == "🛡️ প্রাইভেসি ফিল্টার":
        await update.message.reply_text(
            "🛡️ প্রাইভেসি ফিল্টার\n\nযে তথ্য পোস্ট থেকে মুছে যাবে — চাপ দিয়ে ON/OFF করুন:",
            reply_markup=privacy_kb())

    elif t in ("👤 @username", "📞 ফোন", "✉️ ইমেইল", "🔗 t.me লিংক"):
        key = {"👤 @username": "username", "📞 ফোন": "phone",
               "✉️ ইমেইল": "email", "🔗 t.me লিংক": "tme_link"}[t]
        settings["privacy"][key]["on"] = not settings["privacy"][key]["on"]
        save_settings(settings)
        st = "🟢 চালু" if settings["privacy"][key]["on"] else "🔴 বন্ধ"
        await update.message.reply_text(
            f"✅ ফিল্টার আপডেট!\n\n🔍 {t}: {st}\n\n"
            f"⚠️ এই নিয়ম এখন থেকে সোর্স পোস্টে প্রযোজ্য।", reply_markup=privacy_kb())

    elif t == "📢 Channel → Group":
        forwarding = settings["channel_group_forwarding"]
        await update.message.reply_text(
            f"📢 Channel → Group Auto Forward\n\n"
            f"অবস্থা: {'🟢 চালু' if forwarding['enabled'] else '🔴 বন্ধ'}\n"
            f"Group: {len(forwarding['groups'])}\n"
            f"Selected: {forwarding.get('selected_group') or '(নেই)'}",
            reply_markup=channel_group_kb())

    elif t == "➕ Group যোগ করুন":
        user_state[uid] = {"step": "await_cg_add"}
        await update.message.reply_text("Group-এর numeric ID বা @username পাঠান।")

    elif t == "👥 Group List":
        rows = []
        for key, group in settings["channel_group_forwarding"]["groups"].items():
            state = "⏸️ paused" if group.get("paused") else ("🟢 active" if group.get("enabled") else "🔴 disabled")
            rows.append(f"{key} — {state} — count {group.get('count', 1)} — delay {group.get('delay_seconds', 0)}s")
        await update.message.reply_text("\n".join(rows) or "Group list খালি।", reply_markup=channel_group_kb())

    elif t == "🎯 Select Group":
        user_state[uid] = {"step": "await_cg_select"}
        await update.message.reply_text("যে Group configure করবেন তার ID/@username পাঠান।")

    elif t == "⚙️ Forward Settings":
        group = selected_forward_group()
        if not group:
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())
        else:
            await update.message.reply_text(
                f"Selected: {settings['channel_group_forwarding']['selected_group']}\n"
                f"Status: {'paused' if group.get('paused') else ('active' if group.get('enabled') else 'disabled')}\n"
                f"Count: {group.get('count', 1)}\nDelay: {group.get('delay_seconds', 0)} seconds\n"
                f"AI: {'ON' if group.get('ai_enabled') else 'OFF'}\n"
                f"Schedule: {group.get('schedule', {})}",
                reply_markup=channel_group_kb())

    elif t in ("🔢 Forward Count", "⏱️ Delay", "📅 Schedule"):
        steps = {"🔢 Forward Count": "await_cg_count", "⏱️ Delay": "await_cg_delay", "📅 Schedule": "await_cg_schedule"}
        if not selected_forward_group():
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())
        else:
            user_state[uid] = {"step": steps[t]}
            prompt = "Count দিন (1-20)।" if t == "🔢 Forward Count" else ("Delay seconds দিন।" if t == "⏱️ Delay" else "Format: on 09:00 23:00 অথবা off 00:00 23:59")
            await update.message.reply_text(prompt)

    elif t == "🤖 AI Editing":
        group = selected_forward_group()
        if group:
            group["ai_enabled"] = not group.get("ai_enabled", False)
            save_settings(settings)
            await update.message.reply_text(f"✅ Selected group AI: {'ON' if group['ai_enabled'] else 'OFF'}", reply_markup=channel_group_kb())
        else:
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())

    elif t in ("🟢 C→G চালু", "🔴 C→G বন্ধ", "⏸️ Pause", "▶️ Resume"):
        group = selected_forward_group()
        if group:
            if t == "🟢 C→G চালু":
                settings["channel_group_forwarding"]["enabled"] = True
                group["enabled"] = True
            elif t == "🔴 C→G বন্ধ":
                settings["channel_group_forwarding"]["enabled"] = False
            elif t == "⏸️ Pause":
                group["paused"] = True
            else:
                group["paused"] = False
            save_settings(settings)
            await update.message.reply_text("✅ Forward status আপডেট হয়েছে।", reply_markup=channel_group_kb())
        else:
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())

    elif t == "📊 Status":
        rows = read_forward_history()
        success = sum(1 for row in rows if row.get("status") == "success")
        failed = sum(1 for row in rows if row.get("status") == "error")
        await update.message.reply_text(
            f"📊 Forward Status\n\nTotal: {len(rows)}\nSuccessful: {success}\nFailed: {failed}\n"
            f"Pending: 0\nLast: {rows[-1].get('time') if rows else 'নেই'}",
            reply_markup=channel_group_kb())

    elif t == "📝 History":
        rows = read_forward_history()[-15:]
        text = "\n".join(f"{r.get('time')} | {r.get('group')} | post {r.get('source_message_id')} | {r.get('status')}" for r in rows)
        await update.message.reply_text(text or "History খালি।", reply_markup=channel_group_kb())

    elif t == "🤖 AI সেটিংস":
        ai = settings["ai"]
        await update.message.reply_text(
            f"🤖 GROQ AI Post Editing\n\n"
            f"অবস্থা: {'🟢 চালু' if ai['enabled'] else '🔴 বন্ধ'}\n"
            f"Style: {ai['style']}\nLength: {ai['length']}\n"
            f"Emoji: {'চালু' if ai['emoji'] else 'বন্ধ'}\n"
            f"Custom prompt: {ai['custom_prompt'] or '(খালি)'}",
            reply_markup=ai_kb())

    elif t in ("🟢 AI Editing চালু", "🔴 AI Editing বন্ধ"):
        settings["ai"]["enabled"] = t.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ AI Post Editing আপডেট হয়েছে।", reply_markup=ai_kb())

    elif t == "✨ AI Emoji ON/OFF":
        settings["ai"]["emoji"] = not settings["ai"].get("emoji", True)
        save_settings(settings)
        await update.message.reply_text("✅ AI Emoji সেটিংস আপডেট হয়েছে।", reply_markup=ai_kb())

    elif t in ("🎨 AI Style", "🧠 Custom Prompt", "📏 Post Length"):
        steps = {"🎨 AI Style": "await_ai_style", "🧠 Custom Prompt": "await_ai_prompt", "📏 Post Length": "await_ai_length"}
        user_state[uid] = {"step": steps[t]}
        await update.message.reply_text("নতুন মান লিখুন। খালি করতে 'না' লিখুন।")

    elif t == "👥 Group AI সেটিংস":
        user_state[uid] = {"step": "await_group_config"}
        await update.message.reply_text(
            "এক লাইনে লিখুন: <chat_id> <on/off> <mode>\n"
            "Mode: always / question / mention / reply / ask\n"
            "উদাহরণ: -100123456789 on mention", reply_markup=ai_kb())

    elif t in ("🎭 AI পরিচয় সেটিংস", "⬅️ AI সেটিংসে ফিরুন"):
        if t == "⬅️ AI সেটিংসে ফিরুন":
            await update.message.reply_text("🤖 AI সেটিংসে ফিরে গেলাম।", reply_markup=ai_kb())
        else:
            ai = settings["ai"]
            master = ai.get("master_instruction") or ""
            master_preview = (master[:200] + "...") if len(master) > 200 else (master or "(সেট করা নেই)")
            await update.message.reply_text(
                f"🎭 AI পরিচয় সেটিংস\n\n"
                f"AI-র নাম: {ai.get('identity_name') or '(সেট করা নেই — default AI পরিচয় দেবে)'}\n"
                f"Owner-এর নাম: {ai.get('owner_name') or '(সেট করা নেই — মালিকের প্রশ্ন এড়িয়ে যাবে)'}\n"
                f"Filter/নিষেধ: {ai.get('identity_filter') or '(খালি)'}\n"
                f"Master নির্দেশনা: {master_preview}\n\n"
                f"এই সেটিংস অনুযায়ী AI কখনো ChatGPT/OpenAI/Groq-এর নাম বলবে না, "
                f"বরং আপনার দেওয়া পরিচয়/মালিক-এর নাম বলবে এবং Master নির্দেশনা সবসময় মেনে চলবে।",
                reply_markup=ai_identity_kb())

    elif t in ("🤖 AI-র নাম", "👑 Owner-এর নাম", "🚫 অতিরিক্ত Filter/নিষেধ"):
        steps = {
            "🤖 AI-র নাম": "await_ai_identity_name",
            "👑 Owner-এর নাম": "await_ai_owner_name",
            "🚫 অতিরিক্ত Filter/নিষেধ": "await_ai_identity_filter",
        }
        prompts = {
            "🤖 AI-র নাম": "AI নিজেকে যে নামে পরিচয় দেবে সেটা লিখুন (উদাহরণ: Nishat X AI)। খালি করতে 'না' লিখুন।",
            "👑 Owner-এর নাম": "'তোমার মালিক কে' জিজ্ঞেস করলে AI যে নাম বলবে সেটা লিখুন। খালি করতে 'না' লিখুন।",
            "🚫 অতিরিক্ত Filter/নিষেধ": "AI যা যা বলতে পারবে না তা লিখুন (যেমন: ফোন নম্বর/ঠিকানা কখনো বলবে না)। খালি করতে 'না' লিখুন।",
        }
        user_state[uid] = {"step": steps[t]}
        await update.message.reply_text(prompts[t])

    elif t == "📄 Master নির্দেশনা (Text/File)":
        user_state[uid] = {"step": "await_master_instruction"}
        await update.message.reply_text(
            "AI কীভাবে আচরণ করবে, কী কী উত্তর দেবে/দেবে না — পুরো নিয়ম এখানে লিখে পাঠান, "
            "অথবা সরাসরি একটা .txt ফাইল পাঠান (ফাইলের ভেতরের লেখাটাই নির্দেশনা হিসেবে সেভ হবে)।\n"
            "খালি করতে 'না' লিখুন।")

    elif t == "📩 User Messaging":
        campaign = settings["user_campaign"]
        await update.message.reply_text(
            f"📩 Opt-in User Messaging\n\n"
            f"তালিকায় user: {len(campaign['user_ids'])}\n"
            f"Message: {'সেট করা আছে' if campaign['message'] else 'খালি'}\n"
            f"Delay: {campaign['delay_minutes']} মিনিট",
            reply_markup=user_message_kb())

    elif t == "👥 User List":
        rows = []
        for key in settings["user_campaign"]["user_ids"]:
            item = settings["users"].get(str(key), {})
            rows.append(f"{key} — {'🟢 opt-in' if item.get('opted_in') else '🔴 opt-in নেই'} — {item.get('status', 'unknown')}")
        await update.message.reply_text("\n".join(rows) or "User list খালি।", reply_markup=user_message_kb())

    elif t == "➕ User যোগ":
        user_state[uid] = {"step": "await_users"}
        await update.message.reply_text("User ID বা @username দিন। একাধিক হলে comma বা নতুন line ব্যবহার করুন।")

    elif t == "📝 Common Message":
        user_state[uid] = {"step": "await_campaign_message"}
        await update.message.reply_text("Common message লিখুন।")

    elif t == "⏰ Schedule":
        user_state[uid] = {"step": "await_campaign_delay"}
        await update.message.reply_text("প্রতিটি message-এর মাঝে কত মিনিট বিরতি থাকবে? 0 দিলে পরপর যাবে।")

    elif t == "📩 এখন পাঠান":
        await send_campaign(ctx.bot)
        await update.message.reply_text("✅ Campaign send complete। User List-এ status দেখুন।", reply_markup=user_message_kb())

    elif t in ("🟢 Campaign চালু", "🔴 Campaign বন্ধ"):
        settings["user_campaign"]["enabled"] = t.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ Campaign অবস্থা আপডেট হয়েছে।", reply_markup=user_message_kb())

    elif t == "📝 অটো পোস্ট":
        st = "🟢 চালু" if settings["autopost"] else "🔴 বন্ধ"
        await update.message.reply_text(
            f"📝 অটো পোস্ট\n\n📊 অবস্থা: {st}\n"
            f"📡 সোর্স: {len(settings['sources'])}টা\n"
            f"🏠 Destination: {len(settings['destinations'])}টা\n\n"
            f"চালু/বন্ধ করতে নিচের বাটন ব্যবহার করুন:", reply_markup=autopost_kb())

    elif t == "🟢 চালু করুন":
        settings["autopost"] = True
        set_autopost(True)
        await update.message.reply_text("✅ অটো পোস্ট চালু হয়েছে!", reply_markup=autopost_kb())

    elif t == "🔴 বন্ধ করুন":
        settings["autopost"] = False
        set_autopost(False)
        await update.message.reply_text("⏸️ অটো পোস্ট বন্ধ করা হয়েছে!", reply_markup=autopost_kb())

    elif t == "📊 পরিসংখ্যান":
        pub, skip = read_stats()
        await update.message.reply_text(
            f"📊 পরিসংখ্যান\n\n"
            f"✅ পাবলিশ: {pub}\n"
            f"⏭️ স্কিপ: {skip}\n"
            f"📡 সোর্স: {len(settings['sources'])}\n"
            f"🏠 Destination: {len(settings['destinations'])}", reply_markup=main_kb())

    elif t == "⚙️ সেটিংস":
        await update.message.reply_text(
            f"⚙️ সেটিংস\n\n"
            f"⏱️ ডিলে: {settings['delay_minutes']} মিনিট\n"
            f"📌 হেডার: {settings['template']['header'] or '(খালি)'}\n"
            f"📌 ফুটার: {settings['template']['footer'] or '(খালি)'}",
            reply_markup=settings_kb())

    elif t == "⏱️ ডিলে সেট":
        user_state[uid] = {"step": "await_delay"}
        await update.message.reply_text(
            "⏱️ ডিলে সেট\n\n"
            "**ধাপ ১:** কত মিনিট পরে পোস্ট হবে, সংখ্যায় লিখুন (যেমন: 5)\n"
            "**ধাপ ২:** ✅ নিশ্চিত মেসেজ পাবেন")

    elif t == "📝 টেমপ্লেট":
        user_state[uid] = {"step": "await_tmpl_header"}
        await update.message.reply_text(
            "📝 টেমপ্লেট\n\n"
            "**ধাপ ১:** হেডার লিখুন (যেমন: 📢 নতুন আপডেট)\n"
            "**ধাপ ২:** ফুটার লিখুন\n"
            "**ধাপ ৩:** ✅ সেভ হয়ে যাবে")

    elif t == "🔁 Forward সেটিংস":
        f = settings["forwarding"]
        await update.message.reply_text(
            "🔁 Channel-এর edited post Group-এ forward\n\n"
            f"অবস্থা: {'🟢 চালু' if f['enabled'] else '🔴 বন্ধ'}\n"
            f"বার: {f['repeat_count']}\n"
            f"Interval: {f['repeat_interval_minutes']} মিনিট\n"
            f"Group: {len(settings['forward_groups'])}টি\n\n"
            "নিচের অপশন বেছে নিন।",
            reply_markup=ReplyKeyboardMarkup([
                ["🟢 Forward চালু", "🔴 Forward বন্ধ"],
                ["🔢 Repeat সংখ্যা", "⏱️ Repeat interval"],
                ["➕ Forward Group", "➖ Forward Group"],
                ["⬅️ ফিরে যান"],
            ], resize_keyboard=True))

    elif t in ("🟢 Forward চালু", "🔴 Forward বন্ধ"):
        settings["forwarding"]["enabled"] = t.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ Forward অবস্থা আপডেট হয়েছে।", reply_markup=settings_kb())

    elif t in ("🔢 Repeat সংখ্যা", "⏱️ Repeat interval"):
        field = "repeat_count" if t.startswith("🔢") else "repeat_interval_minutes"
        user_state[uid] = {"step": "await_forward_value", "field": field}
        await update.message.reply_text(
            "সংখ্যা লিখুন। Repeat count কমপক্ষে 1 এবং interval মিনিটে দিতে হবে।")

    elif t in ("➕ Forward Group", "➖ Forward Group"):
        action = "add" if t.startswith("➕") else "remove"
        user_state[uid] = {"step": "await_channel", "type": f"forward_group_{action}"}
        await update.message.reply_text(
            "Group-এর @username বা numeric chat ID পাঠান।")

    elif t == "📇 Personal তথ্য":
        await update.message.reply_text(
            "যে তথ্যগুলো source post-এর বদলে বসবে:\n"
            f"Username: {settings['replacements']['username'] or '(খালি)'}\n"
            f"Phone: {settings['replacements']['phone'] or '(খালি)'}\n"
            f"Email: {settings['replacements']['email'] or '(খালি)'}\n"
            f"Telegram link: {settings['replacements']['tme_link'] or '(খালি)'}\n\n"
            "পরিবর্তন করতে নিচের অপশন বেছে নিন।",
            reply_markup=ReplyKeyboardMarkup([
                ["👤 Username", "📞 Phone"],
                ["✉️ Email", "🔗 Telegram link"],
                ["⬅️ ফিরে যান"],
            ], resize_keyboard=True))

    elif t in ("👤 Username", "📞 Phone", "✉️ Email", "🔗 Telegram link"):
        field = {
            "👤 Username": "username", "📞 Phone": "phone",
            "✉️ Email": "email", "🔗 Telegram link": "tme_link",
        }[t]
        user_state[uid] = {"step": "await_replacement", "field": field}
        await update.message.reply_text("নতুন তথ্য পাঠান। মুছে দিতে 'না' লিখুন।")

    elif t == "❓ সাহায্য":
        await update.message.reply_text(
            "❓ সাহায্য\n\n"
            "🤖 এই বট সোর্স চ্যানেলের পোস্ট নিয়ে আপনার চ্যানেলে পোস্ট করে।\n\n"
            "📌 প্রথমে:\n"
            "১. 📡 চ্যানেল সেটিংস → আপনার চ্যানেল যোগ করুন\n"
            "২. .env-এ সোর্স চ্যানেল বসান\n"
            "৩. 📝 অটো পোস্ট চালু রাখুন\n\n"
            "🛡️ প্রাইভেসি ফিল্টার থেকে ব্যক্তিগত তথ্য সরানোর নিয়ম ON/OFF করুন。",
            reply_markup=main_kb())

    elif t == "⬅️ ফিরে যান":
        await update.message.reply_text("🏠 মূল মেনুতে ফিরে এলাম।", reply_markup=main_kb())

    else:
        await update.message.reply_text("❌ চিনতে পারিনি। নিচের বাটন ব্যবহার করুন。", reply_markup=main_kb())

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("optin", optin))
    app.add_handler(CommandHandler("optout", optout))
    for command in ("useron", "useroff", "userremove", "userstatus", "retry"):
        app.add_handler(CommandHandler(command, manage_user))
    app.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, handle_forward))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle))
    print(r"""
⢀⡴⠦⢤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⡤⠤⡄
⢸⡇⠀⣀⡈⠙⠲⠴⠒⠚⢹⠉⣹⠉⣿⠓⠒⠦⠔⠚⠉⡀⠀⠀⡇
⠀⣧⠀⢹⣩⠗⠀⠀⠀⠀⠛⠀⠛⠀⠛⠀⠀⠀⠀⠰⣏⡟⠀⣸⠁
⠀⠸⡆⠀⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠁⢠⠇⠀
⠀⢠⠏⠀⠀⠀⣠⣴⣦⢄⡀⠀⠀⠀⠀⣠⣦⣦⣄⠀⠀⠀⠸⡄⠀
⠀⣸⠤⠄⠀⣼⣿⣿⣿⣇⢳⠀⠀⠀⣼⣟⠛⣿⣏⢳⠀⢠⣀⡇⠀
⠀⢹⠶⠆⠀⣿⣿⣿⣿⣿⢸⠀⠀⠀⣿⣷⣶⣿⣿⢸⠀⠰⠤⡗⠀
⠀⢸⡚⠂⠀⢹⣿⣿⣿⢇⡞⠠⣤⠀⢻⣿⣿⣿⢏⡞⠃⠰⢒⡇⠀
⠀⠀⢷⡀⠀⠀⠙⠛⠓⠋⠀⠰⠵⠆⠀⠙⠛⠛⠋⠀⠀⢀⡞⠀⠀
⠀⠀⠀⠙⢧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡴⠋⠀⠀⠀
⠀⠀⠀⠀⠀⠉⠓⠶⠤⣤⣀⣀⣀⣀⣀⣤⠤⠶⠚⠉⠀⠀⠀⠀⠀
🟢 Nishat X System Online
""")
    app.run_polling()

if __name__ == "__main__":
    main()
