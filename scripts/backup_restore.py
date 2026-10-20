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
        if revision not in ([('0004_daily_workspace',)], [('0005_module_preferences',)], [('0006_account_connections',)]):
            raise RuntimeError('Unsupported revision; review restore procedure')
        if revision in ([('0005_module_preferences',)], [('0006_account_connections',)]):
            columns = {row[1] for row in c.execute('PRAGMA table_info(module_preferences)')}
            if not {'user_email', 'module_id', 'enabled'}.issubset(columns):
                raise RuntimeError('Module preference schema missing')
        if revision == [('0006_account_connections',)]:
            for table,required in {'account_profiles':{'user_email','google_subject','name','picture'},'service_connections':{'user_email','provider','enabled','secret','account','generation'}}.items():
                columns={row[1] for row in c.execute('PRAGMA table_info('+table+')')}
                if not required<=columns:raise RuntimeError('Account connection schema missing')
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
