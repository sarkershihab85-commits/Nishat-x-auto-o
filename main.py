# main.py — অটো পোস্ট বটের সম্পূর্ণ মূল অ্যাডমিন প্যানেল (Full Updated Code)
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

from config import ADMIN_IDS, BOT_TOKEN, DATA_DIR
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai_client import answer_group_message, edit_post_with_ai, notify_admin_error
from settings_store import load_settings, save_settings
from userbot import user_client

settings = load_settings()
my_channels = {}
user_state = {}
live_chat_history = {}


# --- Multi-Admin Helper (Feature 9) ---
def get_admin_list():
    admins = list(ADMIN_IDS)
    configured_admins = settings.get("multi_admins", [])
    for a in configured_admins:
        if isinstance(a, int) and a not in admins:
            admins.append(a)
    return set(admins)


def is_admin(uid):
    return uid in get_admin_list()


def base_ai_context() -> dict:
    ai = settings.get("ai", {})
    return {
        "identity_name": ai.get("identity_name", ""),
        "owner_name": ai.get("owner_name", ""),
        "identity_filter": ai.get("identity_filter", ""),
        "master_instruction": ai.get("master_instruction", ""),
        "private_knowledge": ai.get("private_knowledge", ""),
    }


def read_stats():
    pub = skip = 0
    try:
        with open(DATA_DIR / "posts.log", encoding="utf-8") as f:
            for line in f:
                if line.strip() == "published":
                    pub += 1
                elif line.strip() == "skipped":
                    skip += 1
    except FileNotFoundError:
        pass
    return pub, skip


# --- Keyboards ---
def main_kb():
    return ReplyKeyboardMarkup(
        [
            ["📡 চ্যানেল সেটিংস"],
            ["🛡️ প্রাইভেসি ফিল্টার"],
            ["📝 অটো পোস্ট", "📊 পরিসংখ্যান"],
            ["🤖 AI সেটিংস", "📩 User Messaging"],
            ["📢 Channel → Group"],
            ["⚙️ সেটিংস", "❓ সাহায্য"],
        ],
        resize_keyboard=True,
    )


def channel_kb():
    return ReplyKeyboardMarkup(
        [
            ["➕ Source চ্যানেল যোগ", "➕ Destination চ্যানেল যোগ"],
            ["📋 চ্যানেল তালিকা", "🗑️ চ্যানেল সরান"],
            ["⬅️ ফিরে যান"],
        ],
        resize_keyboard=True,
    )


def privacy_kb():
    return ReplyKeyboardMarkup(
        [
            ["📱 Phone Filter On/Off", "📧 Email Filter On/Off"],
            ["🔗 Link Filter On/Off", "👤 Username Filter On/Off"],
            ["🔄 Text Replacement Settings", "🔤 Word Filters"],
            ["⬅️ ফিরে যান"],
        ],
        resize_keyboard=True,
    )


def ai_kb():
    return ReplyKeyboardMarkup(
        [
            ["🤖 AI Editing On/Off", "🎭 Style পরিবর্তন"],
            ["📏 Length পরিবর্তন", "😊 Emoji On/Off"],
            ["💬 Custom Prompt Set", "🆔 Identity / Owner Set"],
            ["🧠 Master & Knowledge Set", "🧪 AI Test Run"],
            ["⬅️ ফিরে যান"],
        ],
        resize_keyboard=True,
    )


def user_message_kb():
    return ReplyKeyboardMarkup(
        [
            ["👥 User List", "➕ User যোগ"],
            ["📝 Common Message", "⏰ Schedule"],
            ["📩 এখন পাঠান (Personal Acc)", "🟢 Campaign চালু"],
            ["🔴 Campaign বন্ধ", "🗑️ User সরান"],
            ["⬅️ ফিরে যান"],
        ],
        resize_keyboard=True,
    )


def channel_group_kb():
    return ReplyKeyboardMarkup(
        [
            ["➕ Group যোগ", "📋 Group তালিকা"],
            ["⚙️ Group Settings", "🗑️ Group সরান"],
            ["⬅️ ফিরে যান"],
        ],
        resize_keyboard=True,
    )


def settings_kb():
    return ReplyKeyboardMarkup(
        [
            ["👑 Multi-Admin Settings", "🖼️ Media Filter Settings"],
            ["⏱️ Global Delay Settings", "📋 General Config"],
            ["⬅️ ফিরে যান"],
        ],
        resize_keyboard=True,
    )


# --- Bot Commands (Feature 3) ---
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনার এই বটটি ব্যবহার করার অনুমতি নেই।")
        return
    text = (
        "🤖 **Nishat X Auto Post & AI Bot**\n\n"
        "স্বাগতম! এই বটের মাধ্যমে আপনি সোর্স চ্যানেল থেকে পোস্ট কালেক্ট করে, "
        "AI ফিল্টারিং ও ফরম্যাটিংয়ের মাধ্যমে আপনার টার্গেট চ্যানেল ও গ্রুপে অটো-পোস্ট করতে পারবেন।\n\n"
        "💡 যেকোনো সেটিং পরিবর্তনের জন্য নিচের মেনু বাটনগুলো ব্যবহার করুন।"
    )
    await update.message.reply_text(text, reply_markup=main_kb(), parse_mode="Markdown")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    help_text = (
        "📖 **বট সাহায্য ও নির্দেশিকা**\n\n"
        "• `/start` - বটের মূল মেনু চালু করুন\n"
        "• `/status` - সিস্টেম ও ইউজার ক্লায়েন্টের স্ট্যাটাস দেখুন\n"
        "• `/help` - এই সহায়িকা বার্তাটি দেখুন\n\n"
        "⚙️ **মূল ফিচারসমূহ:**\n"
        "1. **Personal Messaging:** User Client এর সাহায্যে ডাইরেক্ট মেসেজিং\n"
        "2. **AI Post Editing:** Post Publish করার আগে AI Smart Formatting\n"
        "3. **Multi-Channel Watch:** একাধিক চ্যানেল মনিটর ও অটো পোস্ট\n"
        "4. **Smart Notification:** কোনো সমস্যা হলে অ্যাডমিনকে স্বয়ংক্রিয় নোটিফিকেশন"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    is_user_client_online = user_client.is_connected()
    pub, skip = read_stats()

    status_text = (
        "📊 **System Current Status**\n\n"
        f"• **Bot Engine:** 🟢 Online\n"
        f"• **User Client (Personal Account):** {'🟢 Active' if is_user_client_online else '🔴 Disconnected'}\n"
        f"• **Auto Post System:** {'🟢 Active' if settings.get('autopost') else '🔴 Disabled'}\n"
        f"• **AI Processing:** {'🟢 Active' if settings.get('ai', {}).get('enabled') else '🔴 Disabled'}\n"
        f"• **Published Posts:** {pub}\n"
        f"• **Skipped Posts:** {skip}\n"
        f"• **Monitored Sources:** {len(settings.get('sources', []))}\n"
        f"• **Destinations:** {len(settings.get('destinations', []))}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")


# --- Feature 1: Personal Message Campaign Engine ---
async def send_campaign_via_user_client(application):
    campaign = settings.get("user_campaign", {})
    message = campaign.get("message", "").strip()
    if not message:
        return
    delay = max(0, int(campaign.get("delay_minutes", 0)))

    if not user_client.is_connected():
        try:
            await user_client.connect()
        except Exception as err:
            await notify_admin_error(
                application,
                "Personal Account Messaging Failed",
                f"User Client ডিসকানেক্টেড থাকায় Personal Account থেকে মেসেজ পাঠানো সম্ভব হয়নি: {err}",
                ["User Client Session চেক করুন", "টেলিগ্রাম অ্যাকাউন্ট ঠিক আছে কিনা পরোক্ষভাবে নিশ্চিত করুন"],
                "user_client_msg_err",
            )
            return

    for value in campaign.get("user_ids", []):
        record = settings.get("users", {}).get(str(value), {})
        if not record.get("opted_in") or not record.get("enabled", True):
            continue
        try:
            target = record.get("id", value)
            if isinstance(target, str) and target.isdigit():
                target = int(target)

            # Sending message via Personal User Account
            await user_client.send_message(target, message)
            record["status"] = "sent (Personal Account)"
        except Exception as error:
            record["status"] = f"failed: {str(error)[:80]}"
            with open(DATA_DIR / "message_errors.log", "a", encoding="utf-8") as file:
                file.write(f"user={value} error={error}\n")

        save_settings(settings)
        if delay:
            await asyncio.sleep(delay * 60)


# --- Full Interactive Input & State Handler ---
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    st = user_state.get(uid)

    # ------------------ STATE STEP-BY-STEP PROCESSORS ------------------
    if st == "add_source":
        settings.setdefault("sources", []).append(t.strip())
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"✅ Source চ্যানেল যুক্ত হয়েছে: {t}", reply_markup=channel_kb())
        return

    elif st == "add_dest":
        settings.setdefault("destinations", []).append(t.strip())
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"✅ Destination চ্যানেল যুক্ত হয়েছে: {t}", reply_markup=channel_kb())
        return

    elif st == "remove_channel":
        srcs = settings.get("sources", [])
        dsts = settings.get("destinations", [])
        ch = t.strip()
        if ch in srcs: srcs.remove(ch)
        if ch in dsts: dsts.remove(ch)
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"🗑️ চ্যানেল {ch} সরানো হয়েছে।", reply_markup=channel_kb())
        return

    elif st == "set_custom_prompt":
        settings.setdefault("ai", {})["custom_prompt"] = t.strip()
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text("✅ Custom Prompt সেভ করা হয়েছে!", reply_markup=ai_kb())
        return

    elif st == "set_identity":
        parts = t.split("|")
        ai = settings.setdefault("ai", {})
        ai["identity_name"] = parts[0].strip() if len(parts) > 0 else ""
        ai["owner_name"] = parts[1].strip() if len(parts) > 1 else ""
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text("✅ Identity & Owner সেটিংস আপডেট হয়েছে!", reply_markup=ai_kb())
        return

    elif st == "set_master_knowledge":
        parts = t.split("|")
        ai = settings.setdefault("ai", {})
        ai["master_instruction"] = parts[0].strip() if len(parts) > 0 else ""
        ai["private_knowledge"] = parts[1].strip() if len(parts) > 1 else ""
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text("✅ Master Instruction & Private Knowledge আপডেট হয়েছে!", reply_markup=ai_kb())
        return

    elif st == "ai_test_run":
        await update.message.reply_text("⏳ AI টেস্ট সম্পাদনা করা হচ্ছে...")
        res = await edit_post_with_ai(t, settings, bot_app=ctx.application)
        user_state[uid] = None
        await update.message.reply_text(f"🧪 **AI আউটপুট:**\n\n{res}", reply_markup=ai_kb(), parse_mode="Markdown")
        return

    elif st == "add_user":
        users = settings.setdefault("users", {})
        u_id = t.strip()
        users[u_id] = {"id": u_id, "opted_in": True, "enabled": True, "status": "added"}
        campaign_users = settings.setdefault("user_campaign", {}).setdefault("user_ids", [])
        if u_id not in campaign_users:
            campaign_users.append(u_id)
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"✅ User {u_id} সফলভাবে যোগ করা হয়েছে!", reply_markup=user_message_kb())
        return

    elif st == "remove_user":
        u_id = t.strip()
        settings.get("users", {}).pop(u_id, None)
        c_users = settings.get("user_campaign", {}).get("user_ids", [])
        if u_id in c_users: c_users.remove(u_id)
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"🗑️ User {u_id} সরানো হয়েছে।", reply_markup=user_message_kb())
        return

    elif st == "set_common_msg":
        settings.setdefault("user_campaign", {})["message"] = t.strip()
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text("✅ Campaign Message সেট করা হয়েছে!", reply_markup=user_message_kb())
        return

    elif st == "add_group":
        groups = settings.setdefault("channel_group_forwarding", {}).setdefault("groups", {})
        g_id = t.strip()
        groups[g_id] = {"enabled": True, "count": 1, "delay_seconds": 0, "ai_enabled": False}
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"✅ Group {g_id} ফরোয়ার্ড তালিকায় যোগ করা হয়েছে!", reply_markup=channel_group_kb())
        return

    elif st == "add_admin":
        try:
            new_admin = int(t.strip())
            m_admins = settings.setdefault("multi_admins", [])
            if new_admin not in m_admins:
                m_admins.append(new_admin)
                save_settings(settings)
            user_state[uid] = None
            await update.message.reply_text(f"👑 নতুন অ্যাডমিন ID যোগ করা হয়েছে: {new_admin}", reply_markup=settings_kb())
        except ValueError:
            await update.message.reply_text("❌ অবৈধ আইডি! দয়া করে সংখ্যা সম্বলিত Telegram ID দিন।")
        return

    elif st == "add_word_filter":
        parts = t.split("|")
        find_text = parts[0].strip() if len(parts) > 0 else ""
        replace_text = parts[1].strip() if len(parts) > 1 else ""
        w_filters = settings.setdefault("word_filters", [])
        w_filters.append({"find": find_text, "replace": replace_text})
        save_settings(settings)
        user_state[uid] = None
        await update.message.reply_text(f"✅ শব্দ পরিমার্জন সেট করা হয়েছে: '{find_text}' -> '{replace_text}'", reply_markup=privacy_kb())
        return

    # ------------------ MAIN BUTTON HANDLERS ------------------
    if t == "📡 চ্যানেল সেটিংস":
        await update.message.reply_text("📡 চ্যানেল সেটিংসে স্বাগতম:", reply_markup=channel_kb())

    elif t == "➕ Source চ্যানেল যোগ":
        user_state[uid] = "add_source"
        await update.message.reply_text("Source চ্যানেল ইউজারনেম বা আইডি দিন (যেমন: @mychannel বা -100xxx):")

    elif t == "➕ Destination চ্যানেল যোগ":
        user_state[uid] = "add_dest"
        await update.message.reply_text("Destination চ্যানেল ইউজারনেম বা আইডি দিন:")

    elif t == "🗑️ চ্যানেল সরান":
        user_state[uid] = "remove_channel"
        await update.message.reply_text("যে চ্যানেলটি সরাতে চান তার নাম/আইডি দিন:")

    elif t == "📋 চ্যানেল তালিকা":
        src = "\n".join(settings.get("sources", [])) or "খালি"
        dst = "\n".join(settings.get("destinations", [])) or "খালি"
        await update.message.reply_text(f"📌 **Sources:**\n{src}\n\n🎯 **Destinations:**\n{dst}", parse_mode="Markdown")

    elif t == "🛡️ প্রাইভেসি ফিল্টার":
        await update.message.reply_text("🛡️ প্রাইভেসি ফিল্টার সেটিংস:", reply_markup=privacy_kb())

    elif t in ["📱 Phone Filter On/Off", "📧 Email Filter On/Off", "🔗 Link Filter On/Off", "👤 Username Filter On/Off"]:
        priv = settings.setdefault("privacy", {})
        key_map = {
            "📱 Phone Filter On/Off": "phone",
            "📧 Email Filter On/Off": "email",
            "🔗 Link Filter On/Off": "links",
            "👤 Username Filter On/Off": "usernames",
        }
        key = key_map[t]
        priv[key] = not priv.get(key, True)
        save_settings(settings)
        await update.message.reply_text(f"{t.split(' ')[0]} ফিল্টার এখন {'অন 🟢' if priv[key] else 'অফ 🔴'}")

    elif t == "🔤 Word Filters":
        user_state[uid] = "add_word_filter"
        await update.message.reply_text("পরিবর্তন করতে চাওয়া শব্দ এবং নতুন শব্দ দিন (ফরমেট: পুরাতন শব্দ | নতুন শব্দ):")

    elif t == "🤖 AI সেটিংস":
        await update.message.reply_text("🤖 AI সেটিংস কন্ট্রোল প্যানেল:", reply_markup=ai_kb())

    elif t == "🤖 AI Editing On/Off":
        ai = settings.setdefault("ai", {})
        ai["enabled"] = not ai.get("enabled", True)
        save_settings(settings)
        status = "চালু 🟢" if ai["enabled"] else "বন্ধ 🔴"
        await update.message.reply_text(f"AI Editing এখন {status}")

    elif t == "💬 Custom Prompt Set":
        user_state[uid] = "set_custom_prompt"
        await update.message.reply_text("AI কাস্টম প্রম্পট বা বিশেষ নির্দেশনা লিখুন:")

    elif t == "🆔 Identity / Owner Set":
        user_state[uid] = "set_identity"
        await update.message.reply_text("বটের নাম ও মালিকের নাম লিখুন (ফরমেট: Bot Name | Owner Name):")

    elif t == "🧠 Master & Knowledge Set":
        user_state[uid] = "set_master_knowledge"
        await update.message.reply_text("Master Instruction ও Private Knowledge লিখুন (ফরমেট: Instruction | Knowledge):")

    elif t == "🧪 AI Test Run":
        user_state[uid] = "ai_test_run"
        await update.message.reply_text("পরীক্ষা করার জন্য যেকোনো একটি পোস্ট পাঠাক:")

    elif t == "📩 User Messaging":
        await update.message.reply_text("📩 User Messaging প্যানেলে স্বাগতম:", reply_markup=user_message_kb())

    elif t == "➕ User যোগ":
        user_state[uid] = "add_user"
        await update.message.reply_text("ইউজার আইডি বা ইউজারনেম টাইপ করুন:")

    elif t == "🗑️ User সরান":
        user_state[uid] = "remove_user"
        await update.message.reply_text("যে ইউজার সরাতে চান তার আইডি দিন:")

    elif t == "📝 Common Message":
        user_state[uid] = "set_common_msg"
        await update.message.reply_text("ক্যাম্পেইনের জন্য মেসেজ লিখুন:")

    elif t == "📩 এখন পাঠান (Personal Acc)":
        await update.message.reply_text("⏳ Personal Account দিয়ে মেসেজ পাঠানোর ক্যাম্পেইন শুরু হচ্ছে...")
        await send_campaign_via_user_client(ctx.application)
        await update.message.reply_text("✅ Personal Campaign সম্পন্ন হয়েছে। Status দেখুন।", reply_markup=user_message_kb())

    elif t == "👥 User List":
        usr_list = list(settings.get("users", {}).keys())
        msg = "\n".join(usr_list) if usr_list else "কোনো ইউজার যোগ করা নেই।"
        await update.message.reply_text(f"👥 **যুক্ত থাকা ইউজার তালিকা:**\n{msg}", parse_mode="Markdown")

    elif t == "📢 Channel → Group":
        await update.message.reply_text("📢 Channel to Group Auto Forwarding:", reply_markup=channel_group_kb())

    elif t == "➕ Group যোগ":
        user_state[uid] = "add_group"
        await update.message.reply_text("Target Group-এর ID বা Chat Username দিন:")

    elif t == "📋 Group তালিকা":
        grps = list(settings.get("channel_group_forwarding", {}).get("groups", {}).keys())
        msg = "\n".join(grps) if grps else "কোনো গ্রুপ যোগ করা নেই।"
        await update.message.reply_text(f"📢 **গ্রুপ তালিকা:**\n{msg}", parse_mode="Markdown")

    elif t == "⚙️ সেটিংস":
        await update.message.reply_text("⚙️ বটের সার্বিক সেটিংস:", reply_markup=settings_kb())

    elif t == "👑 Multi-Admin Settings":
        user_state[uid] = "add_admin"
        await update.message.reply_text("নতুন অ্যাডমিন যোগ করতে তার Telegram User ID লিখুন:")

    elif t == "📝 অটো পোস্ট":
        settings["autopost"] = not settings.get("autopost", True)
        save_settings(settings)
        st_text = "চালু 🟢" if settings["autopost"] else "বন্ধ 🔴"
        await update.message.reply_text(f"অটো পোস্ট সিস্টেম এখন {st_text}")

    elif t == "📊 পরিসংখ্যান":
        pub, skip = read_stats()
        await update.message.reply_text(f"📊 **পরিসংখ্যান:**\n✅ প্রকাশিত পোস্ট: {pub}\n⏭️ স্কিপ করা পোস্ট: {skip}", parse_mode="Markdown")

    elif t == "❓ সাহায্য":
        await help_cmd(update, ctx)

    elif t == "⬅️ ফিরে যান":
        user_state[uid] = None
        await update.message.reply_text("🏠 মূল মেনুতে ফিরে এলাম।", reply_markup=main_kb())


# --- Execution App ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands Register
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    # Message Handler Register
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle))

    print("🟢 Nishat X System Main Panel Online with Full Features & State Handlers")
    app.run_polling()


if __name__ == "__main__":
    main()
