# settings_store.py — বটের JSON সেটিংস সেভ ও লোড মডিউল
import json
import os
from pathlib import Path
from config import DATA_DIR, SETTINGS_FILE

# ডিফল্ট সেটিংস স্ট্রাকচার
DEFAULT_SETTINGS = {
    "autopost": True,
    "sources": [],
    "destinations": [],
    "multi_admins": [],
    "privacy": {
        "phone": True,
        "email": True,
        "links": True,
        "usernames": True
    },
    "word_filters": [],
    "ai": {
        "enabled": True,
        "custom_prompt": "",
        "identity_name": "Nishat X Bot",
        "owner_name": "Admin",
        "master_instruction": "Format posts cleanly and keep them concise.",
        "private_knowledge": ""
    },
    "user_campaign": {
        "message": "",
        "delay_minutes": 0,
        "user_ids": []
    },
    "users": {},
    "channel_group_forwarding": {
        "groups": {}
    }
}


def load_settings() -> dict:
    """settings.json ফাইল থেকে সেটিংস লোড করে, ফাইল না থাকলে নতুন তৈরি করে"""
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # কোনো নতুন কী (Key) মিসিং থাকলে তা ডিফল্ট থেকে ফিল করে দেওয়া
            for key, val in DEFAULT_SETTINGS.items():
                if key not in data:
                    data[key] = val
            return data
    except Exception as err:
        print(f"⚠️ Settings load error: {err}. Returning defaults.")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings_data: dict) -> bool:
    """সেটিংস ডাটা নিরাপদে settings.json ফাইলে সেভ করে"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as err:
        print(f"❌ Failed to save settings: {err}")
        return False
