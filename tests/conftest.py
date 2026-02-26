import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("BOT_TOKEN", "123456:pytest-placeholder-token")
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000")
os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://event_user:event_pass@127.0.0.1:3306/event_bot",
)
