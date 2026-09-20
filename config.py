"""Load local configuration before modules read environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'focusflow.db').as_posix()}")
if make_url(DATABASE_URL).get_backend_name() != "sqlite":
    raise ValueError("Phase 1 supports SQLite DATABASE_URL only")

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Taipei")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if os.getenv("RENDER_EXTERNAL_URL", "").startswith("https://") else "false").lower() == "true"
