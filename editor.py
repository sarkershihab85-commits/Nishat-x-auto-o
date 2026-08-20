import re

# ═══ এডিটর — পোস্ট ক্লিন, ফরম্যাট, টেমপ্লেট ═══

def clean_text(text: str) -> str:
    """অতিরিক্ত স্পেস, লাইন পরিষ্কার"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def apply_template(text: str, header: str = "", footer: str = "") -> str:
    """হেডার/ফুটার যোগ"""
    parts = []
    if header:
        parts.append(header)
    parts.append(text)
    if footer:
        parts.append(footer)
    return "\n\n".join(parts)


def apply_replacements(text: str, replacements: dict) -> str:
    """শব্দ প্রতিস্থাপন"""
    for old, new in replacements.items():
        if old and new:
            text = text.replace(old, new)
    return text


def format_post(text: str, settings: dict) -> str:
    """পুরো পাইপলাইন: ক্লিন → রিপ্লেস → টেমপ্লেট"""
    text = clean_text(text)
    text = apply_replacements(text, settings.get("replacements", {}))
    header = settings.get("template", {}).get("header", "")
    footer = settings.get("template", {}).get("footer", "")
    text = apply_template(text, header, footer)
    return text
