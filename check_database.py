"""Read-only schema preflight. Never creates or migrates a database."""
import sqlite3
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url
from config import BASE_DIR, DATABASE_URL
from models import Base


def check_database(database_url=DATABASE_URL):
    url = make_url(database_url)
    if url.get_backend_name() != 'sqlite' or not url.database or url.database == ':memory:':
        raise RuntimeError('Preflight requires a file-backed SQLite database')
    path = Path(url.database).resolve()
    if not path.is_file():
        raise RuntimeError('Database missing. Run python migrate_db.py before starting the app.')
    expected = set(ScriptDirectory.from_config(Config(str(BASE_DIR / 'alembic.ini'))).get_heads())
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'alembic_version' not in tables:
            raise RuntimeError('Migration version missing. Back up and run python migrate_db.py.')
        actual = {row[0] for row in db.execute('SELECT version_num FROM alembic_version')}
        if actual != expected:
            raise RuntimeError('Migration version mismatch. Back up and run python migrate_db.py.')
        for table in Base.metadata.sorted_tables:
            if table.name not in tables:
                raise RuntimeError(f'Missing table: {table.name}. Restore/repair the schema before startup.')
            columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table.name}")')}
            missing = set(table.columns.keys()) - columns
            if missing:
                raise RuntimeError(f'Missing columns in {table.name}: {sorted(missing)}. Restore/repair before startup.')
    return True


if __name__ == '__main__':
    try:
        check_database()
    except (RuntimeError, sqlite3.Error) as error:
        raise SystemExit(str(error))
    print('Database schema preflight passed (read-only).')
