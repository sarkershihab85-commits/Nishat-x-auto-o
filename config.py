import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ═══ সিক্রেট (Environment Variables থেকে) ═══
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
API_ID = int(os.getenv("TELEGRAM_API_ID") or "0")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION = os.getenv("TELEGRAM_SESSION", "telegram_user")
PHONE = os.getenv("TELEGRAM_PHONE")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ═══ ডাটা ডিরেক্টরি ═══
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
