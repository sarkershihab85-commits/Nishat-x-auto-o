import os
from groq import Groq

# ═══ AI Client — Groq (Llama) দিয়ে পোস্ট রিরাইট ═══

client = None
if os.getenv("GROQ_API_KEY"):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def ai_rewrite(text: str, settings: dict = None) -> str:
    """সোর্স পোস্ট → সুন্দর বাংলায় নতুন করে লেখা"""
    if not client:
        return text

    if settings is None:
        settings = {}

    style = settings.get("style", "সহায়ক, ভদ্র ও সংক্ষিপ্ত")
    length = settings.get("length", "মাঝারি")
    use_emoji = settings.get("emoji", True)
    custom_prompt = settings.get("custom_prompt", "")
    contact = settings.get("contact", "@FastOTP_Nishat")

    system = f"""তুমি একজন পেশাদার বাংলা কনটেন্ট এডিটর। নিচের পোস্টটা সাজিয়ে লেখো:

১. বানান ও ভাষা ঠিক করো
২. দাম, তথ্য, লিংক কখনো বদলাবে না
৩. অন্য কারো @username/ফোন/ব্যক্তিগত তথ্য বাদ দাও
৪. আমার কন্টাক্ট {contact} সবসময় রাখো
৫. স্টাইল: {style}
৬. দৈর্ঘ্য: {length}
৭. এমোজি: {"ব্যবহার করো" if use_emoji else "ব্যবহার করো না"}
৮. 📢 হেডিং + ━━━ সেপারেটর ব্যবহার করো"""

    if custom_prompt:
        system += f"\n৯. অতিরিক্ত নির্দেশনা: {custom_prompt}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️ AI এরর: {e}")
        return text


async def answer_group_message(text: str, group_settings: dict, context: str) -> str:
    """Group-এ AI উত্তর দেওয়ার জন্য"""
    if not client:
        return "⚠️ AI সার্ভিস যুক্ত করা হয়নি।"

    style = group_settings.get("style", "সহায়ক, ভদ্র ও সংক্ষিপ্ত")
    length = group_settings.get("answer_length", "মাঝারি")
    custom = group_settings.get("custom_prompt", "")
    topic = group_settings.get("topic_restriction", "")

    system = f"""তুমি একজন AI সহকারী। ব্যবহারকারীর প্রশ্নের উত্তর দাও।

স্টাইল: {style}
দৈর্ঘ্য: {length}"""

    if custom:
        system += f"\nঅতিরিক্ত নির্দেশনা: {custom}"
    if topic:
        system += f"\nশুধু এই বিষয়ে উত্তর দাও: {topic}"
    if context:
        system += f"\nআগের কথোপকথন:\n{context}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"AI এরর: {e}")
