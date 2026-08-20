import re

# ═══ প্রাইভেসি ফিল্টার — পোস্ট থেকে ব্যক্তিগত তথ্য মুছে ফেলে ═══

PATTERNS = {
    "username": [
        re.compile(r"@\w{5,32}"),
        re.compile(r"t\.me/\w{5,32}"),
        re.compile(r"telegram\.me/\w{5,32}"),
    ],
    "phone": [
        re.compile(r"\+?\d[\d\s\-]{8,15}"),
        re.compile(r"\b0\d{3}[\s\-]?\d{6,8}\b"),
    ],
    "email": [
        re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    ],
    "tme_link": [
        re.compile(r"https?://t\.me/\S+"),
        re.compile(r"t\.me/\S+"),
    ],
}


def clean_personal(text: str, privacy_settings: dict, allowed_contact: str = "") -> str:
    """
    privacy_settings = {"username": {"on": True}, "phone": {"on": True}, ...}
    allowed_contact = "@FastOTP_Nishat" — এটা মুছবে না
    """
    if not text:
        return text

    for key, enabled in privacy_settings.items():
        if not enabled.get("on", False):
            continue
        for pattern in PATTERNS.get(key, []):
            def replace_match(m):
                match_text = m.group()
                if allowed_contact and allowed_contact.lower() in match_text.lower():
                    return match_text
                return "***"
            text = pattern.sub(replace_match, text)

    # অতিরিক্ত খালি লাইন পরিষ্কার
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text
