"""Telegram Bot API admin panel. Personal user messaging is handled by userbot.py."""
import json
import os
from datetime import datetime

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ai_client import answer_group_message
from config import ADMIN_IDS, BOT_TOKEN, DATA_DIR, SESSION, SUPER_OWNER_ID
from notifier import configure, notify
from settings_store import load_settings, save_settings

settings = load_settings()
states = {}
chat_history = {}


def is_admin(uid):
    item = settings.get("admins", {}).get(str(uid), {})
    return uid in ADMIN_IDS or (item.get("enabled") and item.get("role") in {"admin", "super_owner"})


def can(uid, permission):
    item = settings.get("admins", {}).get(str(uid), {})
    return uid == SUPER_OWNER_ID or uid in ADMIN_IDS or "*" in item.get("permissions", []) or permission in item.get("permissions", [])


def main_kb():
    return ReplyKeyboardMarkup([
        ["📡 চ্যানেল সেটিংস", "📝 অটো পোস্ট"],
        ["🤖 AI সেটিংস", "📩 User Messaging"],
        ["📢 Channel → Group", "👥 Admin Settings"],
        ["📊 পরিসংখ্যান", "⚙️ সেটিংস"],
        ["❓ সাহায্য"],
    ], resize_keyboard=True)


def channel_kb():
    return ReplyKeyboardMarkup([
        ["🏠 Destination", "📡 Source"],
        ["➕ Source যোগ", "➖ Source বাদ"],
        ["➕ Destination যোগ", "➖ Destination বাদ"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def ai_kb():
    return ReplyKeyboardMarkup([
        ["🟢 AI চালু", "🔴 AI বন্ধ"],
        ["🎨 AI Style", "🧠 Custom Prompt"],
        ["📚 All Data", "🧾 Format Template"],
        ["🖼️ Image ON/OFF", "📄 File ON/OFF"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def user_kb():
    return ReplyKeyboardMarkup([
        ["👥 User List", "➕ User যোগ"],
        ["📝 Common Message", "⏰ Schedule"],
        ["📩 এখন পাঠান", "🟢 Campaign চালু"],
        ["🔴 Campaign বন্ধ", "⬅️ ফিরে যান"],
    ], resize_keyboard=True)


def admin_kb():
    return ReplyKeyboardMarkup([["➕ Admin যোগ", "➖ Admin বাদ"], ["👥 Admin List"], ["⬅️ ফিরে যান"]], resize_keyboard=True)


def cg_kb():
    return ReplyKeyboardMarkup([
        ["➕ Group যোগ", "👥 Group List"], ["🎯 Select Group"],
        ["🟢 C→G চালু", "🔴 C→G বন্ধ"], ["⏸️ Pause", "▶️ Resume"],
        ["🔢 Count", "⏱️ Delay"], ["📅 Schedule", "📊 Status"],
        ["⬅️ ফিরে যান"],
    ], resize_keyboard=True)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "👋 স্বাগতম। এটি Telegram Auto Post & AI Bot।\n"
            "Admin না হলে সাধারণ AI chat চালু থাকলে message পাঠাতে পারবেন।"
        )
        return
    await update.message.reply_text(
        "👋 Nishat X Auto Post & AI Bot\n\n"
        "Source channel monitor, professional AI formatting, media forwarding, "
        "schedule, group forwarding এবং personal campaign messaging এখানে নিয়ন্ত্রণ করুন।\n\n"
        "/help — ব্যবহার নির্দেশনা\n/status — সব service-এর অবস্থা",
        reply_markup=main_kb(),
    )


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Help\n\n"
        "/start — মূল menu\n/help — এই নির্দেশনা\n/status — Bot/User Client/AI status\n"
        "/optin — campaign message অনুমতি\n/optout — campaign বন্ধ\n"
        "/useron ID, /useroff ID, /userremove ID, /userstatus ID, /retry ID\n"
        "/adminadd ID permission1,permission2\n/adminremove ID\n\n"
        "AI চালু থাকলে post publish/forward-এর আগে AI processing হবে। "
        "Media filter আলাদা করে Image/File ON/OFF করা যায়।"
    )


async def status_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ai = settings.get("ai", {})
    session_state = "🟢 Session file আছে" if os.path.exists(SESSION + ".session") or os.path.exists(SESSION) else "🟡 Session এখনো তৈরি হয়নি"
    await update.message.reply_text(
        "📊 Service Status\n\n"
        f"Bot API: {'🟢 configured' if BOT_TOKEN else '🔴 BOT_TOKEN missing'}\n"
        f"User Client: {session_state}\n"
        f"AI: {'🟢 ON' if ai.get('enabled') else '🔴 OFF'}\n"
        f"Sources: {len(settings.get('sources', []))}\n"
        f"Destinations: {len(settings.get('destinations', []))}\n"
        f"Multi-watch: {'🟢 ON' if settings.get('multi_watch', {}).get('enabled') else '🔴 OFF'}\n"
        f"Campaign: {'🟢 queued' if settings.get('user_campaign', {}).get('enabled') else '🔴 idle'}\n"
        f"Last checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=main_kb() if is_admin(update.effective_user.id) else None,
    )


async def optin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record = settings.setdefault("users", {}).setdefault(str(user.id), {})
    record.update({"id": user.id, "username": user.username or "", "name": user.full_name or "", "opted_in": True, "enabled": True, "status": "ready"})
    if str(user.id) not in settings["user_campaign"]["user_ids"]:
        settings["user_campaign"]["user_ids"].append(str(user.id))
    save_settings(settings)
    await update.message.reply_text("✅ Opt-in সম্পন্ন হয়েছে।")


async def optout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    record = settings.setdefault("users", {}).setdefault(str(update.effective_user.id), {})
    record.update({"id": update.effective_user.id, "opted_in": False, "enabled": False, "status": "opted_out"})
    save_settings(settings)
    await update.message.reply_text("✅ Opt-out সম্পন্ন হয়েছে।")


async def manage_user_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not can(update.effective_user.id, "user_control"):
        await update.message.reply_text("❌ অনুমতি নেই।")
        return
    parts = update.message.text.split(maxsplit=1)
    if len(parts) != 2:
        await update.message.reply_text("ব্যবহার: /useron ID")
        return
    key = parts[1].strip().lstrip("@")
    record = settings.setdefault("users", {}).get(key)
    if not record:
        await update.message.reply_text("⚠️ User তালিকায় নেই।")
        return
    command = parts[0].lower()
    if command == "/userremove":
        settings["users"].pop(key, None)
        settings["user_campaign"]["user_ids"] = [v for v in settings["user_campaign"]["user_ids"] if str(v) != key]
        result = "User সরানো হয়েছে।"
    elif command == "/userstatus":
        result = f"ID: {key}\nOpt-in: {record.get('opted_in')}\nEnabled: {record.get('enabled')}\nStatus: {record.get('status')}"
    else:
        record["enabled"] = command == "/useron"
        record["status"] = "ready" if record["enabled"] else "disabled"
        result = "✅ User status আপডেট হয়েছে।"
    save_settings(settings)
    await update.message.reply_text(result)


async def admin_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_OWNER_ID and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ শুধু Super Owner এই command ব্যবহার করতে পারবেন।")
        return
    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 2:
        await update.message.reply_text("ব্যবহার: /adminadd ID channel_manage,ai_settings")
        return
    key = parts[1].strip().lstrip("@")
    if parts[0].lower() == "/adminremove":
        settings["admins"].pop(key, None)
        save_settings(settings)
        await update.message.reply_text("✅ Admin সরানো হয়েছে।")
        return
    permissions = [x.strip() for x in (parts[2] if len(parts) > 2 else "user_control").split(",") if x.strip()]
    settings["admins"][key] = {"role": "admin", "permissions": permissions, "enabled": True}
    save_settings(settings)
    await update.message.reply_text("✅ Admin যোগ/আপডেট হয়েছে।")


async def send_campaign_trigger(update, ctx):
    settings["user_campaign"]["enabled"] = True
    save_settings(settings)
    await update.message.reply_text("✅ Campaign queue করা হয়েছে। Personal Telegram Account worker এটি পাঠাবে।", reply_markup=user_kb())


async def handle_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    group = settings.get("group_ai", {}).get(str(update.effective_chat.id), {})
    if not group.get("enabled"):
        return
    text = update.message.text or ""
    mode = group.get("reply_mode", "question")
    if mode == "question" and not text.endswith(("?", "？")):
        return
    if mode == "mention" and (ctx.bot.username or "").lower() not in text.lower():
        return
    try:
        answer = await answer_group_message(text, {**settings.get("ai", {}), **group})
        await update.message.reply_text(answer[:4000])
    except Exception as error:
        await notify("Group AI Error", error, "AI settings, API quota এবং group configuration যাচাই করুন.", f"group-ai:{update.effective_chat.id}")


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global settings
    settings = load_settings()
    uid, text = update.effective_user.id, (update.message.text or "").strip()
    if not is_admin(uid):
        if settings.get("live_chat", {}).get("enabled"):
            try:
                answer = await answer_group_message(text, settings.get("live_chat", {}), "\n".join(chat_history.get(uid, [])[-6:]))
                await update.message.reply_text(answer[:4000])
            except Exception as error:
                await notify("Live Chat AI Error", error, "AI configuration ও API quota যাচাই করুন.", f"live:{uid}")
        return

    state = states.get(uid)
    if state:
        if state["step"] == "source":
            settings["sources"].append(text if text.startswith("@") else text)
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ Source যোগ হয়েছে।", reply_markup=channel_kb())
            return
        if state["step"] == "destination":
            value = int(text) if text.lstrip("-").isdigit() else text
            settings["destinations"].append(value)
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ Destination যোগ হয়েছে।", reply_markup=channel_kb())
            return
        if state["step"] in {"ai_style", "ai_prompt", "knowledge"}:
            field = {"ai_style": "style", "ai_prompt": "custom_prompt", "knowledge": "private_knowledge"}[state["step"]]
            settings["ai"][field] = "" if text.lower() in {"না", "-", "খালি"} else text[:12000]
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ AI data সেভ হয়েছে।", reply_markup=ai_kb())
            return
        if state["step"] == "campaign_message":
            settings["user_campaign"]["message"] = text
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ Campaign message সেভ হয়েছে।", reply_markup=user_kb())
            return
        if state["step"] == "user_add":
            for value in text.replace(",", "\n").splitlines():
                value = value.strip().lstrip("@")
                if value:
                    settings["user_campaign"]["user_ids"].append(value) if value not in settings["user_campaign"]["user_ids"] else None
                    settings["users"].setdefault(value, {"id": int(value) if value.isdigit() else value, "opted_in": False, "enabled": True, "status": "waiting for opt-in"})
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ User list আপডেট হয়েছে।", reply_markup=user_kb())
            return
        if state["step"] == "admin_add":
            parts = text.split(maxsplit=1)
            if not parts:
                return
            key = parts[0].lstrip("@")
            permissions = (parts[1] if len(parts) > 1 else "user_control").split(",")
            settings["admins"][key] = {"role": "admin", "permissions": permissions, "enabled": True}
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ Admin যোগ হয়েছে।", reply_markup=admin_kb())
            return
        if state["step"] == "group_add":
            key = text
            settings["channel_group_forwarding"]["groups"].setdefault(key, {"enabled": True, "paused": False, "count": 1, "delay_seconds": 0, "schedule": {"enabled": False, "start": "00:00", "end": "23:59"}})
            settings["channel_group_forwarding"]["selected_group"] = key
            states.pop(uid)
            save_settings(settings)
            await update.message.reply_text("✅ Group যোগ হয়েছে।", reply_markup=cg_kb())
            return

    if text == "📡 চ্যানেল সেটিংস":
        await update.message.reply_text("📡 Channel settings", reply_markup=channel_kb())
    elif text == "➕ Source যোগ":
        states[uid] = {"step": "source"}
        await update.message.reply_text("@username বা channel ID পাঠান।")
    elif text == "➕ Destination যোগ":
        states[uid] = {"step": "destination"}
        await update.message.reply_text("Destination channel ID বা @username পাঠান।")
    elif text in {"🏠 Destination", "📡 Source"}:
        key = "destinations" if text.startswith("🏠") else "sources"
        await update.message.reply_text("\n".join(map(str, settings[key])) or "তালিকা খালি।", reply_markup=channel_kb())
    elif text == "📝 অটো পোস্ট":
        await update.message.reply_text(f"Auto Post: {'🟢 ON' if settings['autopost'] else '🔴 OFF'}\nMulti-watch: {'🟢 ON' if settings['multi_watch']['enabled'] else '🔴 OFF'}", reply_markup=main_kb())
    elif text == "🤖 AI সেটিংস":
        await update.message.reply_text(f"AI: {'🟢 ON' if settings['ai']['enabled'] else '🔴 OFF'}\nStyle: {settings['ai']['style']}", reply_markup=ai_kb())
    elif text in {"🟢 AI চালু", "🔴 AI বন্ধ"}:
        settings["ai"]["enabled"] = text.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ AI status আপডেট হয়েছে।", reply_markup=ai_kb())
    elif text in {"🎨 AI Style", "🧠 Custom Prompt", "📚 All Data"}:
        states[uid] = {"step": {"🎨 AI Style": "ai_style", "🧠 Custom Prompt": "ai_prompt", "📚 All Data": "knowledge"}[text]}
        await update.message.reply_text("নতুন তথ্য লিখুন। মুছতে 'না' লিখুন।")
    elif text == "🧾 Format Template":
        states[uid] = {"step": "ai_prompt"}
        await update.message.reply_text("Header/border/footer/contact সহ custom format লিখুন।")
    elif text in {"🖼️ Image ON/OFF", "📄 File ON/OFF"}:
        key = "image" if text.startswith("🖼️") else "file"
        settings["media_filter"][key] = not settings["media_filter"].get(key, True)
        save_settings(settings)
        await update.message.reply_text(f"✅ {key} filter: {'ON' if settings['media_filter'][key] else 'OFF'}", reply_markup=ai_kb())
    elif text == "📩 User Messaging":
        await update.message.reply_text(f"Users: {len(settings['users'])}\nMessage: {'সেট' if settings['user_campaign']['message'] else 'খালি'}", reply_markup=user_kb())
    elif text == "📝 Common Message":
        states[uid] = {"step": "campaign_message"}
        await update.message.reply_text("Personal account থেকে পাঠানোর message লিখুন।")
    elif text == "➕ User যোগ":
        states[uid] = {"step": "user_add"}
        await update.message.reply_text("User ID/@username দিন।")
    elif text == "👥 User List":
        await update.message.reply_text("\n".join(f"{k}: {v.get('status')}" for k, v in settings["users"].items()) or "খালি।", reply_markup=user_kb())
    elif text == "📩 এখন পাঠান" or text == "🟢 Campaign চালু":
        await send_campaign_trigger(update, ctx)
    elif text == "🔴 Campaign বন্ধ":
        settings["user_campaign"]["enabled"] = False
        save_settings(settings)
        await update.message.reply_text("✅ Campaign বন্ধ।", reply_markup=user_kb())
    elif text == "👥 Admin Settings":
        await update.message.reply_text("Admin management", reply_markup=admin_kb())
    elif text == "➕ Admin যোগ":
        states[uid] = {"step": "admin_add"}
        await update.message.reply_text("ID permissions লিখুন। উদাহরণ: 12345 channel_manage,ai_settings")
    elif text == "👥 Admin List":
        await update.message.reply_text(json.dumps(settings["admins"], ensure_ascii=False, indent=2), reply_markup=admin_kb())
    elif text == "➕ Group যোগ":
        states[uid] = {"step": "group_add"}
        await update.message.reply_text("Group ID বা @username পাঠান।")
    elif text == "📢 Channel → Group":
        await update.message.reply_text("Channel → Group settings", reply_markup=cg_kb())
    elif text == "🟢 C→G চালু":
        settings["channel_group_forwarding"]["enabled"] = True
        save_settings(settings)
        await update.message.reply_text("✅ Channel → Group চালু।", reply_markup=cg_kb())
    elif text == "🔴 C→G বন্ধ":
        settings["channel_group_forwarding"]["enabled"] = False
        save_settings(settings)
        await update.message.reply_text("✅ Channel → Group বন্ধ।", reply_markup=cg_kb())
    elif text == "📊 পরিসংখ্যান":
        await status_command(update, ctx)
    elif text == "❓ সাহায্য":
        await help_command(update, ctx)
    else:
        await update.message.reply_text("নিচের menu ব্যবহার করুন।", reply_markup=main_kb())


async def post_init(application):
    configure(application.bot)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN সেট করা নেই")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("optin", optin))
    app.add_handler(CommandHandler("optout", optout))
    for command in ("useron", "useroff", "userremove", "userstatus"):
        app.add_handler(CommandHandler(command, manage_user_command))
    app.add_handler(CommandHandler("adminadd", admin_command))
    app.add_handler(CommandHandler("adminremove", admin_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle))
    app.run_polling()


if __name__ == "__main__":
    main()
