import sqlite3
import pytest
from scripts.backup_restore import snapshot
from conftest import migrate


def test_snapshot_restore_populated_and_refuse_overwrite(tmp_path):
    source=tmp_path/'source.db';migrate(source)
    with sqlite3.connect(source) as c:
        c.execute("INSERT INTO workspaces VALUES ('w','owner','Space','2026-09-20')")
        c.execute("INSERT INTO projects (id,workspace_id,name,kind,created_at) VALUES ('p','w','Project','project','2026-09-20')")
        c.execute("INSERT INTO notes (id,user_email,title,content,project_id) VALUES ('n','owner','Note','keep','p')")
        c.execute("INSERT INTO tasks (id,project_id,title,description,status,created_at) VALUES ('t','p','Task','','todo','2026-09-20')")
    before=source.read_bytes()
    backup=tmp_path/'backup.db';restored=tmp_path/'restored.db'
    assert snapshot(source,backup)==dict(workspaces=1,projects=1,notes=1,tasks=1)
    assert snapshot(backup,restored)==dict(workspaces=1,projects=1,notes=1,tasks=1)
    with sqlite3.connect(source) as a,sqlite3.connect(restored) as b:
        for table in ('workspaces','projects','notes','tasks'):
            assert a.execute('SELECT * FROM '+table).fetchall()==b.execute('SELECT * FROM '+table).fetchall()
    with pytest.raises(FileExistsError): snapshot(backup,source)
    assert source.read_bytes()==before


@pytest.mark.parametrize('revision', [None, 'unexpected_revision'])
def test_invalid_backup_closes_connections_and_removes_destination(tmp_path, revision):
    from contextlib import closing
    source=tmp_path/'invalid.db'
    destination=tmp_path/'rejected.db'
    with closing(sqlite3.connect(source)) as c:
        c.execute('CREATE TABLE alembic_version (version_num TEXT)')
        if revision: c.execute('INSERT INTO alembic_version VALUES (?)',(revision,))
        c.commit()
    before=source.read_bytes()
    with pytest.raises(RuntimeError, match='Unsupported revision'):
        snapshot(source,destination)
    assert not destination.exists()
    assert source.read_bytes()==before
    # Windows refuses these operations when our connection still holds the file.
    source.rename(tmp_path/'renamed.db')
    destination.write_bytes(b'reusable')
    destination.unlink()
