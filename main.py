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
            campaign = settings.get("user_campaign", {})
            message = campaign.get("message", "").strip()
            if message:
                for uid in campaign.get("user_ids", []):
                    record = settings.get("users", {}).get(str(uid), {})
                    if not record.get("opted_in") or not record.get("enabled", True):
                        continue
                    try:
                        await application.bot.send_message(chat_id=record.get("id", uid), text=message)
                        record["status"] = "sent"
                    except Exception as e:
                        record["status"] = f"failed: {str(e)[:80]}"
                    save_settings(settings)
            settings["user_campaign"]["enabled"] = False
            save_settings(settings)

# ═══ post_init: application start-এর পরে task চালু ═══
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

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ অনুমতি নেই।")
        return

    # ── স্টেট-ভিত্তিক ইনপুট ──
    state = user_state.get(uid)

    if state and state["step"] == "await_delay":
        if not t.strip().isdigit():
            await update.message.reply_text("⚠️ শুধু সংখ্যা লিখুন।")
            return
        settings["delay_minutes"] = int(t.strip())
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text(f"✅ ডিলে সেট: **{t.strip()} মিনিট**", reply_markup=settings_kb())
        return

    if state and state["step"] in ("await_tmpl_header", "await_tmpl_footer"):
        if state["step"] == "await_tmpl_header":
            settings["template"]["header"] = t
            save_settings(settings)
            user_state[uid]["step"] = "await_tmpl_footer"
            await update.message.reply_text("✅ হেডার সেভ!\n\n📝 এখন **ফুটার** লিখুন (না চাইলে 'না' লিখুন):")
            return
        else:
            if t.lower() != "না":
                settings["template"]["footer"] = t
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(
                f"✅ টেমপ্লেট সেভ!\n\n📌 হেডার: {settings['template']['header'] or '(খালি)'}\n📌 ফুটার: {settings['template']['footer'] or '(খালি)'}",
                reply_markup=settings_kb())
            return

    if state and state["step"] == "await_ai_style":
        settings["ai"]["style"] = "" if t.strip() in ("না", "-") else t.strip()
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ AI Style সেভ!", reply_markup=ai_kb())
        return

    if state and state["step"] == "await_ai_prompt":
        settings["ai"]["custom_prompt"] = "" if t.strip() in ("না", "-") else t.strip()
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Custom Prompt সেভ!", reply_markup=ai_kb())
        return

    if state and state["step"] == "await_ai_length":
        settings["ai"]["length"] = "" if t.strip() in ("না", "-") else t.strip()
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Post Length সেভ!", reply_markup=ai_kb())
        return

    if state and state["step"] == "await_channel":
        stype = state["type"]
        # Source Add / Remove
        if stype in ("source_add", "source_remove"):
            username = t.replace("https://t.me/", "").replace("https://t.me/", "").replace("@", "").split("/")[0].strip()
            try:
                chat = await ctx.bot.get_chat(f"@{username}")
                source = f"@{chat.username}" if chat.username else str(chat.id)
                if stype == "source_add":
                    if source not in settings["sources"]:
                        settings["sources"].append(source)
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text(
                        f"✅ Source যোগ হয়েছে!\n\n📛 {chat.title}\n🆔 {chat.id}",
                        reply_markup=channel_kb())
                else:
                    if source in settings["sources"]:
                        settings["sources"].remove(source)
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text("✅ Source বাদ দেওয়া হয়েছে।", reply_markup=channel_kb())
            except Exception:
                await update.message.reply_text(
                    "❌ চ্যানেল পাওয়া যায়নি।\n\n💡 বটকে চ্যানেলে অ্যাডমিন বানান, তারপর URL দিন।",
                    reply_markup=channel_kb())
            return

        # Destination Add / Remove
        if stype in ("destination_add", "destination_remove"):
            if stype == "destination_add":
                username = t.replace("https://t.me/", "").replace("@", "").split("/")[0].strip()
                try:
                    chat = await ctx.bot.get_chat(f"@{username}")
                    if chat.id not in settings["destinations"]:
                        settings["destinations"].append(chat.id)
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text(
                        f"✅ Destination যোগ হয়েছে!\n\n📛 {chat.title}\n🆔 {chat.id}",
                        reply_markup=channel_kb())
                except Exception:
                    await update.message.reply_text(
                        "❌ চ্যানেল পাওয়া যায়নি।\n\n💡 বটকে চ্যানেলে অ্যাডমিন বানান।",
                        reply_markup=channel_kb())
            else:
                value = t.strip()
                if value.isdigit() and int(value) in settings["destinations"]:
                    settings["destinations"].remove(int(value))
                    save_settings(settings)
                    user_state.pop(uid, None)
                    await update.message.reply_text("✅ Destination বাদ হয়েছে।", reply_markup=channel_kb())
                else:
                    await update.message.reply_text("⚠️ ID তালিকায় পাওয়া যায়নি।", reply_markup=channel_kb())
            return

    if state and state["step"] == "await_forward_value":
        field = state["field"]
        value = t.strip()
        if field in ("repeat_count", "repeat_interval_minutes"):
            if not value.isdigit():
                await update.message.reply_text("⚠️ শুধু সংখ্যা দিন।")
                return
            settings["forwarding"][field] = int(value)
        else:
            settings["forwarding"]["enabled"] = value.lower() in ("চালু", "on", "yes", "1")
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ Forward সেটিংস আপডেট!", reply_markup=settings_kb())
        return

    # Channel→Group states
    if state and state["step"] in ("await_cg_add", "await_cg_select", "await_cg_count",
                                    "await_cg_delay", "await_cg_schedule"):
        fwd = settings["channel_group_forwarding"]
        if state["step"] == "await_cg_add":
            value = t.strip()
            group = value if value.startswith("@") else (int(value) if value.lstrip("-").isdigit() else f"@{value}")
            key = str(group)
            fwd["groups"].setdefault(key, {
                "enabled": True, "paused": False, "count": 1, "delay_seconds": 0,
                "ai_enabled": False, "schedule": {"enabled": False, "start": "00:00", "end": "23:59"},
                "status": "active",
            })
            fwd["selected_group"] = key
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ Group যোগ + Selected: {key}", reply_markup=channel_group_kb())
            return

        if state["step"] == "await_cg_select":
            key = t.strip() if t.strip() in fwd["groups"] else (f"@{t.strip()}" if f"@{t.strip()}" in fwd["groups"] else t.strip())
            if key not in fwd["groups"]:
                await update.message.reply_text("⚠️ এই Group list-এ নেই।", reply_markup=channel_group_kb())
                return
            fwd["selected_group"] = key
            save_settings(settings)
            user_state.pop(uid, None)
            await update.message.reply_text(f"✅ Selected: {key}", reply_markup=channel_group_kb())
            return

        group = selected_forward_group()
        if not group:
            user_state.pop(uid, None)
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())
            return

        value = t.strip()
        if state["step"] == "await_cg_count" and value.isdigit():
            group["count"] = max(1, min(20, int(value)))
        elif state["step"] == "await_cg_delay" and value.isdigit():
            group["delay_seconds"] = max(0, int(value))
        elif state["step"] == "await_cg_schedule":
            parts = value.split()
            if len(parts) == 3 and parts[0].lower() in ("on", "off"):
                group["schedule"] = {"enabled": parts[0].lower() == "on", "start": parts[1], "end": parts[2]}
            else:
                await update.message.reply_text("Format: `on 09:00 23:00` অথবা `off 00:00 23:59`")
                return
        else:
            await update.message.reply_text("⚠️ সঠিক মান লিখুন।")
            return
        save_settings(settings)
        user_state.pop(uid, None)
        await update.message.reply_text("✅ সেভ হয়েছে!", reply_markup=channel_group_kb())
        return

    # ── মূল মেনু ──
    if t == "📡 চ্যানেল সেটিংস":
        await update.message.reply_text("📡 চ্যানেল সেটিংস\n\nকোনটি খুলবেন?", reply_markup=channel_kb())

    elif t == "🏠 Destination":
        lst = "\n".join(f"🟢 {d}" for d in settings["destinations"]) or "খালি"
        await update.message.reply_text(f"🏠 Destination চ্যানেল:\n{lst}", reply_markup=channel_kb())

    elif t == "📡 Source":
        lst = "\n".join(f"📡 {s}" for s in settings["sources"]) or "খালি"
        await update.message.reply_text(f"📡 Source চ্যানেল:\n{lst}", reply_markup=channel_kb())

    elif t == "➕ Source যোগ":
        user_state[uid] = {"step": "await_channel", "type": "source_add"}
        await update.message.reply_text("Source চ্যানেলের @username বা t.me লিংক পাঠান।", reply_markup=channel_kb())

    elif t == "➖ Source বাদ":
        user_state[uid] = {"step": "await_channel", "type": "source_remove"}
        await update.message.reply_text("বাদ দিতে চাওয়া Source-এর @username লিখুন।", reply_markup=channel_kb())

    elif t == "➕ Destination যোগ":
        user_state[uid] = {"step": "await_channel", "type": "destination_add"}
        await update.message.reply_text("Destination চ্যানেলের @username বা t.me লিংক পাঠান।", reply_markup=channel_kb())

    elif t == "➖ Destination বাদ":
        user_state[uid] = {"step": "await_channel", "type": "destination_remove"}
        await update.message.reply_text("বাদ দিতে চাওয়া Destination-এর ID লিখুন।", reply_markup=channel_kb())

    elif t == "🛡️ প্রাইভেসি ফিল্টার":
        await update.message.reply_text(
            "🛡️ প্রাইভেসি ফিল্টার\n\nযে তথ্য মুছে যাবে — ON/OFF করুন:", reply_markup=privacy_kb())

    elif t in ("👤 @username", "📞 ফোন", "✉️ ইমেইল", "🔗 t.me লিংক"):
        key = {"👤 @username": "username", "📞 ফোন": "phone",
               "✉️ ইমেইল": "email", "🔗 t.me লিংক": "tme_link"}[t]
        settings["privacy"][key]["on"] = not settings["privacy"][key]["on"]
        save_settings(settings)
        st = "🟢 চালু" if settings["privacy"][key]["on"] else "🔴 বন্ধ"
        await update.message.reply_text(f"✅ {t}: {st}", reply_markup=privacy_kb())

    elif t == "📝 অটো পোস্ট":
        status = "🟢 চালু" if settings.get("autopost") else "🔴 বন্ধ"
        await update.message.reply_text(f"📝 অটো পোস্ট\n\nঅবস্থা: {status}", reply_markup=autopost_kb())

    elif t == "🟢 চালু করুন":
        set_autopost(True)
        await update.message.reply_text("✅ অটো পোস্ট চালু হয়েছে!", reply_markup=autopost_kb())

    elif t == "🔴 বন্ধ করুন":
        set_autopost(False)
        await update.message.reply_text("🔴 অটো পোস্ট বন্ধ।", reply_markup=autopost_kb())

    elif t == "📊 পরিসংখ্যান":
        pub = skip = 0
        try:
            with open(DATA_DIR / "posts.log") as f:
                for line in f:
                    if line.strip() == "published": pub += 1
                    elif line.strip() == "skipped": skip += 1
        except FileNotFoundError:
            pass
        await update.message.reply_text(
            f"📊 পরিসংখ্যান\n\n✅ পাবলিশ: {pub}\n⏭️ স্কিপ: {skip}\n📡 সোর্স: {len(settings.get('sources', []))}\n🏠 ডেস্টিনেশন: {len(settings.get('destinations', []))}",
            reply_markup=main_kb())

    elif t == "🤖 AI সেটিংস":
        ai = settings["ai"]
        await update.message.reply_text(
            f"🤖 AI Post Editing\n\n"
            f"অবস্থা: {'🟢 চালু' if ai['enabled'] else '🔴 বন্ধ'}\n"
            f"Style: {ai['style']}\nLength: {ai['length']}\n"
            f"Emoji: {'ON' if ai['emoji'] else 'OFF'}\n"
            f"Custom prompt: {ai['custom_prompt'] or '(খালি)'}",
            reply_markup=ai_kb())

    elif t in ("🟢 AI Editing চালু", "🔴 AI Editing বন্ধ"):
        settings["ai"]["enabled"] = t.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ AI সেটিংস আপডেট!", reply_markup=ai_kb())

    elif t == "✨ AI Emoji ON/OFF":
        settings["ai"]["emoji"] = not settings["ai"].get("emoji", True)
        save_settings(settings)
        await update.message.reply_text("✅ AI Emoji আপডেট!", reply_markup=ai_kb())

    elif t == "🎨 AI Style":
        user_state[uid] = {"step": "await_ai_style"}
        await update.message.reply_text("নতুন AI Style লিখুন। খালি করতে 'না'।")

    elif t == "🧠 Custom Prompt":
        user_state[uid] = {"step": "await_ai_prompt"}
        await update.message.reply_text("Custom Prompt লিখুন। খালি করতে 'না'।")

    elif t == "📏 Post Length":
        user_state[uid] = {"step": "await_ai_length"}
        await update.message.reply_text("Post Length (Short/Medium/Long) লিখুন।")

    elif t == "📢 Channel → Group":
        fwd = settings["channel_group_forwarding"]
        await update.message.reply_text(
            f"📢 Channel → Group\n\n"
            f"অবস্থা: {'🟢 চালু' if fwd['enabled'] else '🔴 বন্ধ'}\n"
            f"Group: {len(fwd['groups'])}\n"
            f"Selected: {fwd.get('selected_group') or '(নেই)'}",
            reply_markup=channel_group_kb())

    elif t == "➕ Group যোগ":
        user_state[uid] = {"step": "await_cg_add"}
        await update.message.reply_text("Group ID বা @username পাঠান।")

    elif t == "👥 Group List":
        rows = []
        for key, grp in settings["channel_group_forwarding"]["groups"].items():
            st = "⏸️" if grp.get("paused") else ("🟢" if grp.get("enabled") else "🔴")
            rows.append(f"{st} {key} — count:{grp.get('count',1)} delay:{grp.get('delay_seconds',0)}s")
        await update.message.reply_text("\n".join(rows) or "খালি।", reply_markup=channel_group_kb())

    elif t == "🎯 Select Group":
        user_state[uid] = {"step": "await_cg_select"}
        await update.message.reply_text("Group ID/@username পাঠান।")

    elif t == "⚙️ Forward Settings":
        grp = selected_forward_group()
        if not grp:
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())
        else:
            s = settings["channel_group_forwarding"]
            await update.message.reply_text(
                f"Selected: {s['selected_group']}\n"
                f"Status: {'paused' if grp.get('paused') else ('active' if grp.get('enabled') else 'disabled')}\n"
                f"Count: {grp.get('count',1)} | Delay: {grp.get('delay_seconds',0)}s\n"
                f"AI: {'ON' if grp.get('ai_enabled') else 'OFF'}",
                reply_markup=channel_group_kb())

    elif t in ("🔢 Forward Count", "⏱️ Delay", "📅 Schedule"):
        steps = {"🔢 Forward Count": "await_cg_count", "⏱️ Delay": "await_cg_delay", "📅 Schedule": "await_cg_schedule"}
        if not selected_forward_group():
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())
        else:
            user_state[uid] = {"step": steps[t]}
            prompts = {"🔢 Forward Count": "Count (1-20) দিন।", "⏱️ Delay": "Delay seconds দিন।",
                        "📅 Schedule": "`on 09:00 23:00` অথবা `off 00:00 23:59`"}
            await update.message.reply_text(prompts[t])

    elif t == "🤖 AI Editing":
        grp = selected_forward_group()
        if grp:
            grp["ai_enabled"] = not grp.get("ai_enabled", False)
            save_settings(settings)
            await update.message.reply_text(f"✅ AI: {'ON' if grp['ai_enabled'] else 'OFF'}", reply_markup=channel_group_kb())
        else:
            await update.message.reply_text("⚠️ আগে Group যোগ করুন।", reply_markup=channel_group_kb())

    elif t in ("🟢 C→G চালু", "🔴 C→G বন্ধ"):
        settings["channel_group_forwarding"]["enabled"] = t.startswith("🟢")
        save_settings(settings)
        await update.message.reply_text("✅ Status আপডেট!", reply_markup=channel_group_kb())

    elif t == "📊 Status":
        rows = read_forward_history()
        succ = sum(1 for r in rows if r.get("status") == "success")
        fail = sum(1 for r in rows if r.get("status") == "error")
        await update.message.reply_text(
            f"📊 Status\n\nTotal: {len(rows)}\n✅ Success: {succ}\n❌ Failed: {fail}",
            reply_markup=channel_group_kb())

    elif t == "📝 History":
        rows = read_forward_history()[-10:]
        text = "\n".join(f"{r.get('time')} | {r.get('group')} | {r.get('status')}" for r in rows)
        await update.message.reply_text(text or "History খালি।", reply_markup=channel_group_kb())

    elif t == "⚙️ সেটিংস":
        await update.message.reply_text("⚙️ সেটিংস", reply_markup=settings_kb())

    elif t == "⏱️ ডিলে সেট":
        user_state[uid] = {"step": "await_delay"}
        await update.message.reply_text(f"বর্তমান ডিলে: {settings.get('delay_minutes', 0)} মিনিট\n\nনতুন মান লিখুন।")

    elif t == "📝 টেমপ্লেট":
        user_state[uid] = {"step": "await_tmpl_header"}
        await update.message.reply_text(
            f"বর্তমান হেডার: {settings['template']['header'] or '(খালি)'}\n"
            f"বর্তমান ফুটার: {settings['template']['footer'] or '(খালি)'}\n\n"
            f"📝 নতুন **হেডার** লিখুন:")

    elif t == "🔁 Forward সেটিংস":
        fwd = settings["forwarding"]
        await update.message.reply_text(
            f"🔁 Forward\n\n"
            f"Enabled: {'ON' if fwd['enabled'] else 'OFF'}\n"
            f"Repeat: {fwd.get('repeat_count',1)}x\n"
            f"Interval: {fwd.get('repeat_interval_minutes',0)} min",
            reply_markup=settings_kb())

    elif t == "❓ সাহায্য":
        await update.message.reply_text(
            "❓ সাহায্য\n\n"
            "📡 চ্যানেল সেটিংস — Source/Destination যোগ করুন\n"
            "📝 অটো পোস্ট — ON/OFF করুন\n"
            "🛡️ প্রাইভেসি — ব্যক্তিগত তথ্য মুছুন\n"
            "🤖 AI — পোস্ট এডিটিং\n"
            "⚙️ সেটিংস — ডিলে, টেমপ্লেট",
            reply_markup=main_kb())

    else:
        await update.message.reply_text("💡 বাটন চাপুন অথবা /start লিখুন।", reply_markup=main_kb())


# ═══ মেইন ═══
async def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🤖 অ্যাডমিন বট চালু হয়েছে")

    # userbot চালু (session থাকলে)
    try:
        from userbot import user_client
        if user_client:
            from config import SESSION, PHONE
            await user_client.start(phone=PHONE)
            me = await user_client.get_me()
            print(f"👀 Userbot: {me.first_name} ({me.id})")
            sources = settings.get("sources", [])
            print(f"👀 {len(sources)} সোর্স চ্যানেল")
    except Exception as e:
        print(f"⚠️ Userbot চালু হচ্ছে না: {e}")

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
