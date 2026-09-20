import sqlite3
import pytest
from datetime import date
from models import Task
from test_project_content import project
from conftest import migrate
from check_database import check_database


def test_today_counts_pagination_and_owner(alice, db):
    base = project(alice)
    pid = base.rsplit('/', 1)[-1]
    with db() as session:
        session.add_all([Task(project_id=pid, title=f'Task {i}', due_date=date(2026,9,16)) for i in range(101)])
        session.add(Task(project_id=pid, title='Completed', status='done', due_date=date(2026,9,16)))
        session.commit()
    data = alice.get('/api/overview/today?on=2026-09-16').json()
    assert data['counts']['today'] == 101
    assert len(data['today']) == 100 and data['has_more']['today']
    next_page = alice.get('/api/overview/today?on=2026-09-16&offset=100').json()
    assert len(next_page['today']) == 1 and not next_page['has_more']['today']
    assert {x['id'] for x in data['today']}.isdisjoint(x['id'] for x in next_page['today'])
    from database import save_session
    save_session('bob-count', '{}', 'bob@example.test', 3600)
    alice.cookies.set('session_id','bob-count')
    assert alice.get('/api/overview/today?on=2026-09-16').json()['counts']['today'] == 0
    alice.cookies.set('session_id','alice-session')
    alice.post(base+'/archive',json={'archived':True})
    assert alice.get('/api/overview/today?on=2026-09-16').json()['counts']['today'] == 0
    assert alice.get('/api/overview/today?offset=-1').status_code == 422


def test_preflight_missing_database_is_not_created(tmp_path):
    path = tmp_path/'absent.db'
    with pytest.raises(RuntimeError,match='missing'):
        check_database('sqlite:///'+path.as_posix())
    assert not path.exists()


def test_preflight_version_and_column_drift(tmp_path):
    path = tmp_path/'schema.db'
    url = 'sqlite:///'+path.as_posix()
    migrate(path,'0003_project_content')
    before = path.read_bytes()
    with pytest.raises(RuntimeError,match='version mismatch'):
        check_database(url)
    assert path.read_bytes() == before
    migrate(path)
    assert check_database(url)
    with sqlite3.connect(path) as conn:
        conn.execute('ALTER TABLE notes DROP COLUMN deleted_at')
    with pytest.raises(RuntimeError,match='Missing columns'):
        check_database(url)
