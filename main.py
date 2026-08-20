# main.py — অটো পোস্ট বটের অ্যাডমিন প্যানেল (সম্পূর্ণ বাংলা UI)
from dotenv import load_dotenv
load_dotenv()

import json
import asyncio
from config import DATA_DIR, BOT_TOKEN, ADMIN_IDS
from settings_store import load_settings, save_settings
from ai_client import answer_group_message

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          filters, ContextTypes)

# ═══ স্টেট ও ডেটা ═══
settings = load_settings()
user_state = {}

# ═══ অটোপোস্ট toggle ═══
def set_autopost(on: bool):
    settings["autopost"] = on
    save_settings(settings)

# ═══ পারমিশন চেক ═══
def is_admin(uid):
    return uid in ADMIN_IDS

# ═══ UI: মেনুগুলো ═══
def main_kb():
    return ReplyKeyboardMarkup([
        ["📡 চ্যানেল সেটিংস"],
        ["🛡️ প্রাইভেসি ফিল্টার"],
        ["📝 অটো পোস্ট", "📊 পরিসংখ্যান"],
        ["🤖 AI সেটিংস"],
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
        ["🔁 Forward সেটিংস"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)

def ai_kb():
    return ReplyKeyboardMarkup([
        ["🟢 AI Editing চালু", "🔴 AI Editing বন্ধ"],
        ["🎨 AI Style", "🧠 Custom Prompt"],
        ["📏 Post Length", "✨ AI Emoji ON/OFF"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)

def channel_group_kb():
    return ReplyKeyboardMarkup([
        ["➕ Group যোগ", "👥 Group List"],
        ["🎯 Select Group"],
        ["⚙️ Forward Settings", "🔢 Forward Count"],
        ["⏱️ Delay", "📅 Schedule"],
        ["🤖 AI Editing", "🟢 C→G চালু"],
        ["🔴 C→G বন্ধ", "📊 Status"],
        ["📝 History", "⬅️ ফিরে যান"],
    ], resize_keyboard=True)

# ═══ Channel→Group helpers ═══
def selected_forward_group():
    fwd = settings["channel_group_forwarding"]
    return fwd["groups"].get(str(fwd.get("selected_group", "")))

def read_forward_history():
    path = DATA_DIR / "channel_group_forward_history.jsonl"
    rows = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return rows

# ═══ Campaign Loop ═══
async def campaign_loop(application):
    while True:
        await asyncio.sleep(60)
        if settings.get("user_campaign", {}).get("enabled"):
            campaign = settings["user_campaign"]
            message = campaign.get("message", "").strip()
            if message:
                for uid_str in campaign.get("user_ids", []):
                    record = settings.get("users", {}).get(str(uid_str), {})
                    if not record.get("opted_in") or not record.get("enabled", True):
                        continue
                    try:
                        await application.bot.send_message(chat_id=record.get("id", uid_str), text=message)
                        record["status"] = "sent"
                    except Exception as e:
                        record["status"] = f"failed: {str(e)[:80]}"
                    save_settings(settings)
            campaign["enabled"] = False
            save_settings(settings)

async def post_init(application):
    application.create_task(campaign_loop(application))

# ═══ হ্যান্ডলার ═══
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ অনুমতি নেই।")
        return
    await update.message.reply_text(
        "👋 স্বাগতম! এটা আপনার **অটো পোস্ট বট**।\n\n"
        "নিচের বাটন থেকে যেকোনো মেনু খুলুন — সব ধাপে ধাপে পরিচালিত হবে।",
        reply_markup=main_kb())

async def optin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record = settings.setdefault("users", {}).setdefault(str(user.id), {})
    record.update({
        "id": user.id,
        "username": user.username or "",
        "name": user.full_name or "",
        "opted_in": True,
        "enabled": True,
        "status": "ready",
    })
    save_settings(settings)
    await update.message.reply_text("✅ আপনি opt-in করেছেন। এখন থেকে Admin-এর অনুমোদিত message পেতে পারেন।")

async def optout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record = settings.setdefault("users", {}).setdefault(str(user.id), {})
    record.update({"id": user.id, "opted_in": False, "enabled": False, "status": "opted_out"})
    save_settings(settings)
    await update.message.reply_text("✅ আপনি opt-out করেছেন। আর campaign message পাঠানো হবে না।")

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
    try:
        answer = await answer_group_message(text, group, "")
        await message.reply_text(answer[:4000], disable_web_page_preview=True)
    except Exception as error:
        await message.reply_text("⚠️ AI উত্তর দিতে পারেনি। কিছুক্ষণ পর আবার চেষ্টা করুন।")

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ অনুমতি নেই।")
        return

    # ── স্টেট চেক ──
    if uid in user_state:
        step = user_state[uid]["step"]

        if step == "await_channel":
            state_type = user_state[uid]["type"]
            try:
                username = t.replace("https://t.me/", "").replace("@", "").split("/")[0]
                chat = await ctx.bot.get_chat(f"@{username}")
                if state_type == "source_add":
                    source = f"@{chat.username}" if chat.username else str(chat.id)
                    if source not in settings["sources"]:
                        settings["sources"].append(source)
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text(
                        f"✅ Source যোগ হয়েছে!\n\n📛 {chat.title}\n🆔 {chat.id}",
                        reply_markup=channel_kb())
                elif state_type == "destination_add":
                    if chat.id not in settings["destinations"]:
                        settings["destinations"].append(chat.id)
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text(
                        f"✅ Destination যোগ হয়েছে!\n\n📛 {chat.title}\n🆔 {chat.id}",
                        reply_markup=channel_kb())
                elif state_type == "source_remove":
                    target = settings["sources"]
                    found = False
                    for item in list(target):
                        if str(item).replace("@", "") == username or str(item) == t.strip():
                            target.remove(item)
                            found = True
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text(
                        f"{'✅ বাদ হয়েছে' if found else '⚠️ পাওয়া যায়নি'}: Source",
                        reply_markup=channel_kb())
                elif state_type == "destination_remove":
                    target = settings["destinations"]
                    found = False
                    for item in list(target):
                        if str(item) == t.strip() or str(item) == str(chat.id):
                            target.remove(item)
                            found = True
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text(
                        f"{'✅ বাদ হয়েছে' if found else '⚠️ পাওয়া যায়নি'}: Destination",
                        reply_markup=channel_kb())
            except Exception:
                await update.message.reply_text(
                    "❌ চ্যানেল পাওয়া যায়নি।\n\n"
                    "💡 বটকে চ্যানেলে অ্যাডমিন বানান।",
                    reply_markup=channel_kb())
            return

        if step == "await_delay":
            if not t.strip().isdigit():
                await update.message.reply_text("⚠️ শুধু সংখ্যা লিখুন।")
                return
            settings["delay_minutes"] = int(t.strip())
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ ডিলে: {t.strip()} মিনিট", reply_markup=settings_kb())
            return

        if step in ("await_tmpl_header", "await_tmpl_footer"):
            if step == "await_tmpl_header":
                settings["template"]["header"] = t
                save_settings(settings)
                user_state[uid]["step"] = "await_tmpl_footer"
                await update.message.reply_text("✅ হেডার সেভ!\n\n📝 এখন **ফুটার** লিখুন (না চাইলে 'না'):")
            else:
                if t.lower() != "না":
                    settings["template"]["footer"] = t
                save_settings(settings)
                user_state.pop(uid, None)
                await update.message.reply_text(
                    f"✅ টেমপ্লেট সেভ!\n\n📌 হেডার: {settings['template']['header'] or 'খালি'}\n"
                    f"📌 ফুটার: {settings['template']['footer'] or 'খালি'}",
                    reply_markup=settings_kb())
            return

        if step in ("await_ai_style", "await_ai_prompt", "await_ai_length"):
            field = {"await_ai_style": "style", "await_ai_prompt": "custom_prompt", "await_ai_length": "length"}[step]
            settings["ai"][field] = "" if t.strip() in ("না", "-", "খালি") else t.strip()
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text("✅ AI সেটিংস সেভ!", reply_markup=ai_kb())
            return

        if step == "await_users":
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
            await update.message.reply_text(f"✅ {len(values)} জন user যোগ হয়েছে।", reply_markup=user_message_kb())
            return

        if step == "await_campaign_message":
            settings["user_campaign"]["message"] = t
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text("✅ Message সেভ!", reply_markup=user_message_kb())
            return

        if step == "await_cg_add":
            group_id = t.strip()
            forwarding = settings["channel_group_forwarding"]
            forwarding["groups"].setdefault(group_id, {
                "enabled": True, "paused": False, "count": 1, "delay_seconds": 0,
                "ai_enabled": False, "schedule": {"enabled": False, "start": "00:00", "end": "23:59"},
                "status": "active",
            })
            forwarding["selected_group"] = group_id
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ Group যোগ + selected: {group_id}", reply_markup=channel_group_kb())
            return

        if step == "await_cg_select":
            key = t.strip()
            forwarding = settings["channel_group_forwarding"]
            if key not in forwarding["groups"]:
                await update.message.reply_text("⚠️ Group পাওয়া যায়নি।", reply_markup=channel_group_kb())
                return
            forwarding["selected_group"] = key
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ Selected: {key}", reply_markup=channel_group_kb())
            return

        if step == "await_cg_count":
            group = selected_forward_group()
            if group and t.strip().isdigit():
                group["count"] = max(1, min(20, int(t.strip())))
                save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text("✅ Count সেভ!", reply_markup=channel_group_kb())
            return

        if step == "await_cg_delay":
            group = selected_forward_group()
            if group and t.strip().isdigit():
                group["delay_seconds"] = max(0, int(t.strip()))
                save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text("✅ Delay সেভ!", reply_markup=channel_group_kb())
            return

    # ── মূল মেনু ──
    if t == "📡 চ্যানেল সেটিংস":
        await update.message.reply_text("📡 চ্যানেল সেটিংস", reply_markup=channel_kb())

    elif t == "🏠 Destination":
        lst = "\n".join(f"🟢 {ch}" for ch in settings["destinations"]) or "খালি"
        await update.message.reply_text(f"🏠 Destination:\n{lst}", reply_markup=channel_kb())

    elif t == "📡 Source":
        lst = "\n".join(f"📡 {s}" for s in settings["sources"]) or "খালি"
        await update.message.reply_text(f"📡 Source:\n{lst}", reply_markup=channel_kb())

    elif t in ("➕ Source যোগ", "➕ Destination যোগ"):
        is_src = "Source" in t
        user_state[uid] = {"step": "await_channel", "type": "source_add" if is_src else "destination_add"}
        label = "Source" if is_src else "Destination"
        await update.message.reply_text(f"{label} যোগ: @username বা t.me লিংক পাঠান।", reply_markup=channel_kb())

    elif t in ("➖ Source বাদ", "➖ Destination বাদ"):
        is_src = "Source" in t
        user_state[uid] = {"step": "await_channel", "type": "source_remove" if is_src else "destination_remove"}
        label = "Source" if is_src else "Destination"
        await update.message.reply_text(f"{label} বাদ: @username লিখুন।", reply_markup=channel_kb())

    elif t == "🛡️ প্রাইভেসি ফিল্টার":
        await update.message.reply_text("🛡️ প্রাইভেসি ফিল্টার — চাপ দিয়ে ON/OFF:", reply_markup=privacy_kb())

    elif t in ("👤 @username", "📞 ফোন", "✉️ ইমেইল", "🔗 t.me লিংক"):
        key = {"👤 @username": "username", "📞 ফোন": "phone", "✉️ ইমেইল": "email", "🔗 t.me লিংক": "tme_link"}[t]
        settings["privacy"][key]["on"] = not settings["privacy"][key]["on"]
        save_settings(settings)
        st = "🟢 চালু" if settings["privacy"][key]["on"] else "🔴 বন্ধ"
        await update.message.reply_text(f"✅ {t}: {st}", reply_markup=privacy_kb())

    elif t == "📝 অটো পোস্ট":
        st = "🟢 চালু" if settings.get("autopost") else "🔴 বন্ধ"
        await update.message.reply_text(f"📝 অটো পোস্ট: {st}", reply_markup=autopost_kb())

    elif t == "🟢 চালু করুন":
        set_autopost(True)
        await update.message.reply_text("✅ অটো পোস্ট চালু হয়েছে!", reply_markup=autopost_kb())

    elif t == "🔴 বন্ধ করুন":
        set_autopost(False)
        await update.message.reply_text("✅ অটো পোস্ট বন্ধ!", reply_markup=autopost_kb())

    elif t == "📊 পরিসংখ্যান":
        pub, skip = 0, 0
        try:
            with open(DATA_DIR / "posts.log") as f:
                for line in f:
                    if line.strip() == "published": pub += 1
                    elif line.strip() == "skipped": skip += 1
        except FileNotFoundError:
            pass
        await update.message.reply_text(
            f"📊 পরিসংখ্যান\n\n✅ পাবলিশ: {pub}\n⏭️ স্কিপ: {skip}\n📡 সোর্স: {len(settings['sources'])}\n"
            f"🏠 ডেস্টিনেশন: {len(settings['destinations'])}", reply_markup=main_kb())

    elif t == "⚙️ সেটিংস":
        await update.message.reply_text("⚙️ সেটিংস", reply_markup=settings_kb())

    elif t == "⏱️ ডিলে সেট":
        user_state[uid] = {"step": "await_delay"}
        await update.message.reply_text(f"বর্তমান ডিলে: {settings.get('delay_minutes', 0)} মিনিট\n\nনতুন মান লিখুন।")

    elif t == "📝 টেমপ্লেট":
        user_state[uid] = {"step": "await_tmpl_header"}
        await update.message.reply_text("📝 টেমপ্লেট হেডার লিখুন (না চাইলে 'না'):")

    elif t == "🔁 Forward সেটিংস":
        fwd = settings.get("forwarding", {})
        await update.message.reply_text(
            f"🔁 Forward\n\nON/OFF: {'চালু' if fwd.get('enabled') else 'বন্ধ'}\n"
            f"Repeat: {fwd.get('repeat_count', 1)} | Interval: {fwd.get('repeat_interval_minutes', 0)} মিনিট",
            reply_markup=settings_kb())

    elif t == "🤖 AI সেটিংস":
        ai = settings["ai"]
        await update.message.reply_text(
            f"🤖 AI\n\nঅবস্থা: {'🟢 চালু' if ai['enabled'] else '🔴 বন্ধ'}\n"
            f"Style: {ai['style']}\nLength: {ai['length']}\nEmoji: {'ON' if ai['emoji'] else 'OFF'}",
            reply_markup=ai_kb())

    elif t in ("🟢 AI Editing চালু", "🔴 AI Editing বন্ধ"):
        settings["ai"]["enabled"] = t.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ AI আপডেট!", reply_markup=ai_kb())

    elif t == "✨ AI Emoji ON/OFF":
        settings["ai"]["emoji"] = not settings["ai"].get("emoji", True)
        save_settings(settings)
        await update.message.reply_text("✅ Emoji আপডেট!", reply_markup=ai_kb())

    elif t in ("🎨 AI Style", "🧠 Custom Prompt", "📏 Post Length"):
        steps = {"🎨 AI Style": "await_ai_style", "🧠 Custom Prompt": "await_ai_prompt", "📏 Post Length": "await_ai_length"}
        user_state[uid] = {"step": steps[t]}
        await update.message.reply_text("নতুন মান লিখুন। খালি করতে 'না'।")

    elif t == "📢 Channel → Group":
        fwd = settings["channel_group_forwarding"]
        await update.message.reply_text(
            f"📢 Channel → Group\n\n{'🟢 চালু' if fwd['enabled'] else '🔴 বন্ধ'}\n"
            f"Groups: {len(fwd['groups'])}", reply_markup=channel_group_kb())

    elif t == "➕ Group যোগ":
        user_state[uid] = {"step": "await_cg_add"}
        await update.message.reply_text("Group ID বা @username পাঠান।")

    elif t == "👥 Group List":
        rows = []
        for key, g in settings["channel_group_forwarding"]["groups"].items():
            st = "⏸️" if g.get("paused") else ("🟢" if g.get("enabled") else "🔴")
            rows.append(f"{st} {key}")
        await update.message.reply_text("\n".join(rows) or "খালি।", reply_markup=channel_group_kb())

    elif t == "🎯 Select Group":
        user_state[uid] = {"step": "await_cg_select"}
        await update.message.reply_text("Group ID লিখুন।")

    elif t == "⚙️ Forward Settings":
        g = selected_forward_group()
        if g:
            await update.message.reply_text(f"Status: {g.get('enabled')}\nCount: {g.get('count', 1)}\nDelay: {g.get('delay_seconds', 0)}s", reply_markup=channel_group_kb())
        else:
            await update.message.reply_text("⚠️ আগে Group select করুন।", reply_markup=channel_group_kb())

    elif t == "🔢 Forward Count":
        user_state[uid] = {"step": "await_cg_count"}
        await update.message.reply_text("Count (1-20):")

    elif t == "⏱️ Delay":
        user_state[uid] = {"step": "await_cg_delay"}
        await update.message.reply_text("Delay seconds:")

    elif t == "🤖 AI Editing":
        g = selected_forward_group()
        if g:
            g["ai_enabled"] = not g.get("ai_enabled", False)
            save_settings(settings)
            await update.message.reply_text(f"✅ AI: {'ON' if g['ai_enabled'] else 'OFF'}", reply_markup=channel_group_kb())

    elif t in ("🟢 C→G চালু", "🔴 C→G বন্ধ"):
        g = selected_forward_group()
        if g:
            settings["channel_group_forwarding"]["enabled"] = t.startswith("🟢")
            g["enabled"] = t.startswith("🟢")
            save_settings(settings)
            await update.message.reply_text("✅ আপডেট!", reply_markup=channel_group_kb())

    elif t == "📊 Status":
        await update.message.reply_text(f"📊 Status\n\nসোর্স: {len(settings['sources'])}\nডেস্টি: {len(settings['destinations'])}\nAutopost: {settings.get('autopost')}", reply_markup=channel_group_kb())

    elif t == "📝 History":
        rows = read_forward_history()[-10:]
        text = "\n".join(f"{r.get('time','')} | {r.get('group','')} | {r.get('status','')}" for r in rows)
        await update.message.reply_text(text or "খালি।", reply_markup=channel_group_kb())

    elif t == "❓ সাহায্য":
        await update.message.reply_text(
            "❓ সাহায্য\n\n"
            "📡 চ্যানেল সেটিংস → Source/Destination যোগ\n"
            "📝 অটো পোস্ট → চালু/বন্ধ\n"
            "🛡️ প্রাইভেসি → ব্যক্তিগত তথ্য মুছুন\n"
            "🤖 AI → পোস্ট এডিটিং\n"
            "📢 Channel → Group → গ্রুপে ফরোয়ার্ড",
        reply_markup=main_kb())

    elif t == "➕ User যোগ":
        user_state[uid] = {"step": "await_users"}
        await update.message.reply_text("User ID বা @username দিন।")

    elif t == "📝 Common Message":
        user_state[uid] = {"step": "await_campaign_message"}
        await update.message.reply_text("পাঠানো মেসেজ লিখুন।")

    elif t == "📋 Queue":
        await update.message.reply_text("📋 Queue: এখন খালি", reply_markup=main_kb())

    else:
        await update.message.reply_text("💡 বাটন চাপুন বা /start লিখুন।", reply_markup=main_kb())


async def handle_forward(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fwd = update.message.forward_from_chat
    state = user_state.get(update.effective_user.id, {})
    if not fwd or state.get("step") != "await_channel":
        return
    uid = update.effective_user.id
    state_type = state.get("type", "")
    if state_type == "destination_add":
        if fwd.id not in settings["destinations"]:
            settings["destinations"].append(fwd.id)
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text(f"✅ Destination: {fwd.title} ({fwd.id})", reply_markup=channel_kb())


# ═══ Main ═══
async def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("optin", optin))
    app.add_handler(CommandHandler("optout", optout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.FORWARD, handle_forward))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, handle_group))

    print("🤖 অ্যাডমিন বট চালু হয়েছে!")

    # userbot চেষ্টা
    try:
        from userbot import user_client
        if user_client:
            await user_client.start(phone=PHONE)
            me = await user_client.get_me()
            print(f"👀 Userbot: {me.first_name} ({me.id})")
    except Exception as e:
        print(f"⚠️ Userbot চালু হচ্ছে না: {e}")

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
