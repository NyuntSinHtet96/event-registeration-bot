import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN in .env")
