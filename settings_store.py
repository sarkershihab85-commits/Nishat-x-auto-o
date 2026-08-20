import json
import os
from copy import deepcopy
from pathlib import Path

from config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"
PROCESSED_FILE = DATA_DIR / "processed_posts.log"

DEFAULT_SETTINGS = {
    "autopost": True,
    "delay_minutes": 0,
    "template": {"header": "", "footer": ""},
    "sources": [],
    "destinations": [],
    "forward_groups": [],
    "forwarding": {
        "enabled": False,
        "repeat_count": 1,
        "repeat_interval_minutes": 0,
    },
    "replacements": {
        "username": "",
        "phone": "",
        "email": "",
        "tme_link": "",
    },
    "emoji_editing": True,
    "ai": {
        "enabled": False,
        "style": "পরিষ্কার, স্বাভাবিক ও পেশাদার",
        "custom_prompt": "",
        "length": "মূল পোস্টের কাছাকাছি",
        "emoji": True,
        "model": "openai/gpt-oss-120b",
        "identity_name": "",
        "owner_name": "",
        "identity_filter": "",
        "master_instruction": "",
    },
    "users": {},
    "user_campaign": {
        "message": "",
        "user_ids": [],
        "delay_minutes": 0,
        "enabled": False,
    },
    "group_ai": {},
    "channel_group_forwarding": {
        "enabled": False,
        "selected_group": "",
        "groups": {},
    },
    "privacy": {
        "username": {"on": True},
        "tme_link": {"on": True},
        "phone": {"on": True},
        "email": {"on": True},
        "user_id": {"on": False},
    },
}


def _merge(default, current):
    if isinstance(default, dict):
        result = {}
        for key, value in default.items():
            result[key] = _merge(value, current.get(key) if isinstance(current, dict) else None)
        return result
    return current if current is not None else default


def load_settings() -> dict:
    try:
        with SETTINGS_FILE.open(encoding="utf-8") as file:
            current = json.load(file)
        legacy_destination = current.get("destination_channel_id")
        settings = _merge(DEFAULT_SETTINGS, current)
        if legacy_destination and not current.get("destinations"):
            settings["destinations"] = [legacy_destination]
        return settings
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    temporary = SETTINGS_FILE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)
    os.replace(temporary, SETTINGS_FILE)


def is_processed(post_key: str) -> bool:
    try:
        with PROCESSED_FILE.open(encoding="utf-8") as file:
            return post_key in {line.strip() for line in file}
    except FileNotFoundError:
        return False


def mark_processed(post_key: str) -> None:
    with PROCESSED_FILE.open("a", encoding="utf-8") as file:
        file.write(post_key + "\n")
