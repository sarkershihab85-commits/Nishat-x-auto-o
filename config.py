# config.py — প্রজেক্ট কনফিগারেশন ও এনভায়রনমেন্ট ভ্যারিয়েবল ফাইল
import os
from pathlib import Path
from dotenv import load_dotenv

# .env ফাইল লোড করা
load_dotenv()

# Project Directories Configuration
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"

# Telegram Bot Token & Admin Setup
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Primary Admin List (Environment Variable থেকে নিয়ে Integer-এ রূপান্তর)
raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(a.strip()) for a in raw_admins.split(",") if a.strip().isdigit()]

# Userbot (Personal Account) Pyrogram/Telethon Credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# AI Engine Configuration
AI_API_KEY = os.getenv("AI_API_KEY", "")
