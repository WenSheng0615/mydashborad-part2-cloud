"""Explicit SQLite migration with online backup; stop app writers before use."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from config import DATABASE_URL, BASE_DIR

def upgrade_database():
    url = make_url(DATABASE_URL)
    if not url.database or url.database == ":memory:":
        raise RuntimeError("Migration CLI requires a file-backed SQLite database")
    path = Path(url.database).resolve()
    if path.exists():
        backup_dir = path.parent / ".local" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backup_dir / f"{path.name}.{stamp}.db"
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(backup) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed")
        print(f"Verified backup: {backup}")
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")
    print("Database is at migration head")

if __name__ == "__main__":
    upgrade_database()
