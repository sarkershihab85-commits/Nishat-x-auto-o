"""Small Groq REST client with safe fallback behavior.

The key is read only from the GROQ_API_KEY environment variable.  No key is
stored in settings.json or written to logs.
"""
import asyncio
import json
import os
import urllib.error
import urllib.request


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _request(payload: dict, api_key: str) -> str:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        GROQ_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; NishatXBot/1.0; +https://railway.app)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise urllib.error.HTTPError(error.url, error.code, f"{error.reason} — {detail}", error.headers, None)
    return data["choices"][0]["message"]["content"].strip()


async def ask_groq(
    prompt: str,
    *,
    system: str,
    model: str = "openai/gpt-oss-120b",
    max_tokens: int = 900,
) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY সেট করা নেই")
    payload = {
        "model": model,
        "temperature": 0.35,
        "max_tokens": max(100, min(max_tokens, 1800)),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    last_error = None
    for attempt in range(2):
        try:
            return await asyncio.to_thread(_request, payload, api_key)
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as error:
            last_error = error
            if attempt == 0:
                await asyncio.sleep(1)
    raise RuntimeError(f"Groq request failed: {last_error}")


async def edit_post_with_ai(text: str, settings: dict) -> str:
    ai = settings.get("ai", {})
    style = ai.get("style") or "পরিষ্কার, স্বাভাবিক ও পেশাদার"
    length = ai.get("length") or "মূল পোস্টের কাছাকাছি"
    emoji = "প্রয়োজনে অল্প emoji ব্যবহার করুন" if ai.get("emoji", True) else "কোনো emoji ব্যবহার করবেন না"
    custom = ai.get("custom_prompt") or "কোনো অতিরিক্ত নির্দেশ নেই"
    system = (
        "আপনি Telegram পোস্ট সম্পাদক। মূল তথ্য, সংখ্যা, নাম, লিংক ও অর্থ পরিবর্তন করবেন না। "
        "অপ্রয়োজনীয় call-to-action, বিজ্ঞাপন বা নতুন তথ্য যোগ করবেন না। একই ভাষায় লিখুন। "
        f"Style: {style}. Length: {length}. {emoji}. Custom instruction: {custom}. "
        "শুধু সম্পাদিত পোস্টটি ফেরত দিন, কোনো ব্যাখ্যা নয়।"
    )
    return await ask_groq(f"এই পোস্টটি সম্পাদনা করুন:\n\n{text}", system=system, model=ai.get("model", "openai/gpt-oss-120b"))


async def answer_group_message(text: str, settings: dict, context: str = "") -> str:
    style = settings.get("style") or "সহায়ক, ভদ্র ও সংক্ষিপ্ত"
    length = settings.get("answer_length") or "মাঝারি"
    custom = settings.get("custom_prompt") or "কোনো অতিরিক্ত নির্দেশ নেই"
    context_text = f"\nসাম্প্রতিক context:\n{context}" if context and settings.get("context_enabled", True) else ""
    system = (
        "আপনি Telegram group-এর AI assistant। ব্যবহারকারী যে ভাষায় লিখেছে সেই ভাষাতেই উত্তর দিন। "
        "নিশ্চিত না হলে বানিয়ে বলবেন না; সংক্ষেপে জানাবেন। "
        f"Style: {style}. Answer length: {length}. Custom instruction: {custom}."
    )
    return await ask_groq(f"ব্যবহারকারীর message:\n{text}{context_text}", system=system)
