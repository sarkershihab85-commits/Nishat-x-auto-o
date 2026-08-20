# ai_client.py — AI এডিটিং, প্রাইভেস ফিল্টারিং ও অটো-নোটিফিকেশন মডিউল
import re
import traceback
from pathlib import Path
from telegram.ext import Application
import google.generativeai as genai

from config import AI_API_KEY, ADMIN_IDS
from settings_store import load_settings

# Gemini API Initialization
if AI_API_KEY:
    genai.configure(api_key=AI_API_KEY)


def apply_privacy_filters(text: str, settings: dict) -> str:
    """লোকাল টেক্সট ফিল্টারিং: ফোন, ইমেইল, লিঙ্ক, ইউজারনেম ও ওয়ার্ড রিপ্লেসমেন্ট"""
    privacy = settings.get("privacy", {})

    # Phone Filter
    if privacy.get("phone", True):
        text = re.sub(r'(\+?88)?01[3-9]\d{8}', '[Phone Removed]', text)

    # Email Filter
    if privacy.get("email", True):
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[Email Removed]', text)

    # Link Filter
    if privacy.get("links", True):
        text = re.sub(r'https?://\S+|www\.\S+', '[Link Removed]', text)

    # Username Filter
    if privacy.get("usernames", True):
        text = re.sub(r'@[a-zA-Z0-9_]+', '[Username Removed]', text)

    # Custom Word Filters Replacement
    for wf in settings.get("word_filters", []):
        find_word = wf.get("find", "")
        replace_word = wf.get("replace", "")
        if find_word:
            text = text.replace(find_word, replace_word)

    return text


async def edit_post_with_ai(original_text: str, settings: dict, bot_app: Application = None) -> str:
    """AI এর মাধ্যমে পোস্ট রিরাইট ও স্মার্ট ফরম্যাটিং"""
    ai_config = settings.get("ai", {})

    # ১. প্রাইভেসি ফিল্টার প্রয়োগ
    clean_text = apply_privacy_filters(original_text, settings)

    # AI বন্ধ থাকলে প্রাইভেসি ক্লিন করা টেক্সটই রিটার্ন হবে
    if not ai_config.get("enabled", True) or not AI_API_KEY:
        return clean_text

    # ২. AI System Prompt তৈরি
    custom_prompt = ai_config.get("custom_prompt", "")
    identity = ai_config.get("identity_name", "")
    owner = ai_config.get("owner_name", "")
    master_inst = ai_config.get("master_instruction", "")

    system_instruction = (
        f"You are an expert Telegram content editor for {identity or 'our channel'}.\n"
        f"Owner/Brand: {owner}\n"
        f"Master Instruction: {master_inst}\n"
        f"Custom Instruction: {custom_prompt}\n"
        "Task: Rewrite, format cleanly, remove promotional fluff, add engaging bullet points and suitable emojis. "
        "Keep the core message clear and professional. Do NOT invent fake information."
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        full_prompt = f"{system_instruction}\n\nOriginal Post:\n{clean_text}"
        response = model.generate_content(full_prompt)

        if response and response.text:
            return response.text.strip()
        return clean_text

    except Exception as err:
        err_msg = f"AI Generation Failed: {str(err)}"
        print(f"⚠️ {err_msg}")
        
        # নোটিফিকেশন সিস্টেম
        if bot_app:
            await notify_admin_error(
                bot_app=bot_app,
                error_title="AI Processing Error",
                error_details=err_msg,
                solutions=["API Key মেয়াদ বা লিমিট চেক করুন", "Gemini Service স্ট্যাটাস দেখুন"],
                error_code="AI_EDIT_ERR"
            )
        return clean_text


async def answer_group_message(user_query: str, settings: dict) -> str:
    """গ্রুপের প্রশ্নের জন্য AI অটো-রিপ্লাই"""
    if not AI_API_KEY:
        return ""

    ai_config = settings.get("ai", {})
    knowledge = ai_config.get("private_knowledge", "")

    prompt = (
        f"Context/Knowledge: {knowledge}\n"
        f"User Question: {user_query}\n"
        "Answer politely, concisely, and accurately in Bengali or English based on the input."
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else ""
    except Exception:
        return ""


async def notify_admin_error(bot_app: Application, error_title: str, error_details: str, solutions: list, error_code: str):
    """যেকোনো ত্রুটি অ্যাডমিনকে নোটিফিকেশন আকারে পাঠানোর সিস্টেম"""
    sol_text = "\n".join([f"• {s}" for s in solutions])
    
    message = (
        f"🚨 **System Alert: {error_title}**\n\n"
        f"⚠️ **Error Code:** `{error_code}`\n"
        f"📝 **Details:** {error_details}\n\n"
        f"💡 **Suggested Fixes:**\n{sol_text}"
    )

    settings = load_settings()
    configured_admins = settings.get("multi_admins", [])
    all_admins = set(ADMIN_IDS + configured_admins)

    for admin_id in all_admins:
        try:
            await bot_app.bot.send_message(chat_id=admin_id, text=message, parse_mode="Markdown")
        except Exception:
            pass
