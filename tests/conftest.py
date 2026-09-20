import os
import tempfile
from pathlib import Path
# Disable real secrets and original DB before importing application modules.
_sandbox = tempfile.TemporaryDirectory(prefix="focusflow-tests-")
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_sandbox.name).as_posix()}/unused.db"
for key in ("GOOGLE_TOKEN", "GOOGLE_CREDENTIALS", "FIREBASE_KEY_CONTENT", "FIREBASE_KEY_FILE", "FIREBASE_STORAGE_BUCKET"):
    os.environ[key] = ""
os.environ["REDIS_URL"] = "redis://127.0.0.1:1"

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import database
from main import app
from routers import chat
ROOT = Path(__file__).resolve().parents[1]

def migrate(path, revision="head"):
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = f"sqlite:///{path.as_posix()}"
    command.upgrade(cfg, revision)

@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    migrate(path)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()

@pytest.fixture
def client(db, monkeypatch):
    async def no_publish(*args, **kwargs):
        return None
    monkeypatch.setattr(chat, "_publish", no_publish)
    with TestClient(app) as client:
        yield client

@pytest.fixture
def alice(client):
    database.save_session("alice-session", "{}", "alice@example.test", 3600)
    client.cookies.set("session_id", "alice-session")
    return client
