import json
from pathlib import Path
from config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT = {
    "sources": [],
    "destinations": [],
    "delay_minutes": 0,
    "autopost": False,
    "template": {"header": "", "footer": ""},
    "privacy": {
        "username": {"on": True},
        "phone": {"on": True},
        "email": {"on": True},
        "tme_link": {"on": True},
    },
    "replacements": {
        "contact": "@FastOTP_Nishat",
    },
    "forwarding": {
        "enabled": False,
        "repeat_count": 1,
        "repeat_interval_minutes": 0,
    },
    "ai": {
        "enabled": False,
        "style": "সহায়ক, ভদ্র ও সংক্ষিপ্ত",
        "length": "মাঝারি",
        "emoji": True,
        "custom_prompt": "",
    },
    "users": {},
    "user_campaign": {
        "enabled": False,
        "user_ids": [],
        "message": "",
        "delay_minutes": 0,
    },
    "group_ai": {},
    "forward_groups": [],
    "channel_group_forwarding": {
        "enabled": False,
        "groups": {},
        "selected_group": None,
    },
}


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # missing keys fill from DEFAULT
            for key, val in DEFAULT.items():
                if key not in data:
                    data[key] = val
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(DEFAULT))


def save_settings(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
