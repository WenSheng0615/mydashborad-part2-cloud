import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, migrate


def test_fresh_repeat_and_model_parity(tmp_path):
    path = tmp_path / "fresh.db"
    migrate(path)
    migrate(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("select version_num from alembic_version").fetchone()[0] == "0004_daily_workspace"
        assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert len(conn.execute("select name from sqlite_master where type='table'").fetchall()) == 16
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = f"sqlite:///{path.as_posix()}"
    command.check(cfg)


def test_legacy_note_preservation_and_known_columns(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE notes (id VARCHAR PRIMARY KEY, user_email VARCHAR, title VARCHAR, content TEXT, color VARCHAR, created_at VARCHAR)")
        conn.execute("INSERT INTO notes VALUES ('n', 'owner', '筆記', 'keep me', 'yellow', '2026-09-15')")
    migrate(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("select title, content, image_url from notes").fetchone() == ('筆記', 'keep me', None)


def test_schema_drift_refused_before_legacy_ddl(tmp_path):
    path = tmp_path / "bad.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE notes (id VARCHAR PRIMARY KEY)")
    with pytest.raises(RuntimeError, match="Unexpected missing column"):
        migrate(path)
    with sqlite3.connect(path) as conn:
        names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
        assert names <= {"notes", "alembic_version"}


def test_import_does_not_create_database(tmp_path):
    path = tmp_path / "unused.db"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{path.as_posix()}", PYTHON_DOTENV_DISABLED="1")
    subprocess.run([sys.executable, "-c", "import database; import models"], cwd=ROOT, env=env, check=True)
    assert not path.exists()


def test_cli_backup_and_upgrade(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("create table untouched (value TEXT)")
        conn.execute("insert into untouched values ('keep')")
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{path.as_posix()}", PYTHON_DOTENV_DISABLED="1")
    subprocess.run([sys.executable, str(ROOT / "migrate_db.py")], cwd=tmp_path, env=env, check=True)
    backups = list((tmp_path / ".local" / "backups").glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert conn.execute("select value from untouched").fetchone()[0] == "keep"
        assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"


def test_daily_workspace_upgrade_preserves_existing_notes(tmp_path):
    path = tmp_path / "before_daily.db"
    migrate(path, "0003_project_content")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO notes (id, user_email, title, content, color) VALUES (?, ?, ?, ?, ?)",
                     ("kept-note", "owner@example.test", "Original", "Keep this content", "yellow"))
        original_columns = [row[1] for row in conn.execute("PRAGMA table_info(notes)")]
        projection = ",".join('"' + name + '"' for name in original_columns)
        original = conn.execute("SELECT " + projection + " FROM notes").fetchall()
    migrate(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT " + projection + " FROM notes").fetchall() == original
        assert conn.execute("SELECT deleted_at FROM notes").fetchone() == (None,)
        assert "archived_at" in {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
        assert conn.execute("SELECT count(*) FROM project_links").fetchone() == (0,)
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_legacy_session_and_quiz_columns(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sessions (session_id VARCHAR PRIMARY KEY, token_json TEXT, user_email VARCHAR, last_active DATETIME)")
        conn.execute("CREATE TABLE quiz_questions (id VARCHAR PRIMARY KEY, bank_id VARCHAR, content TEXT, type VARCHAR, created_at VARCHAR)")
        conn.execute("INSERT INTO quiz_questions VALUES ('q', 'b', 'keep', 'single', '2026')")
    migrate(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT content, tag FROM quiz_questions").fetchone() == ("keep", "")
        assert "expires_at" in {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        assert "ix_sessions_expires_at" in {r[1] for r in conn.execute("PRAGMA index_list(sessions)")}
