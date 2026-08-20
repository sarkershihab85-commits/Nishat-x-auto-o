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
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.loads(response.read().decode("utf-8"))
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
        "শুধু স
