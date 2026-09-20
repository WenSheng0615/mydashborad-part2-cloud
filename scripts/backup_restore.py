"""SQLite snapshot/restore to a NEW file only; never overwrite a destination."""
from contextlib import closing
import sqlite3
import sys
from pathlib import Path


def verify(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True)) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Integrity failed')
        if c.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign keys failed')
        revision=c.execute('SELECT version_num FROM alembic_version').fetchall()
        if revision != [('0004_daily_workspace',)]:
            raise RuntimeError('Unsupported revision; review restore procedure')
        return {t:c.execute('SELECT count(*) FROM '+t).fetchone()[0]
                for t in ('workspaces','projects','notes','tasks')}


def snapshot(source,destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if not source.is_file(): raise FileNotFoundError('Source missing')
    if source==destination: raise ValueError('Destination must differ')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation refuses existing DBs, including production files.
    with destination.open('xb'): pass
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
            with closing(sqlite3.connect(destination)) as dst: src.backup(dst)
        return verify(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('Usage: python scripts/backup_restore.py SOURCE NEW_DESTINATION')
    print(snapshot(*sys.argv[1:]))
