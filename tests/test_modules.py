import pytest
from starlette.websockets import WebSocketDisconnect
from database import save_session, merge_guest_data
from models import ModulePreference


def preference(client, module):
    return next(m for m in client.get('/api/modules').json()['modules'] if m['id']==module)


def test_catalog_auth_validation_and_core_protection(client, alice):
    assert len(alice.get('/api/modules').json()['modules'])==10
    assert all(m['enabled'] for m in alice.get('/api/modules').json()['modules'])
    assert alice.patch('/api/modules/settings',json={'enabled':False}).status_code==409
    assert alice.patch('/api/modules/workspace',json={'enabled':False}).status_code==409
    assert alice.patch('/api/modules/unknown',json={'enabled':False}).status_code==404
    assert alice.patch('/api/modules/music',json={'enabled':'false'}).status_code==422
    assert alice.patch('/api/modules/music',json={'enabled':False,'user_email':'other'}).status_code==422
    alice.cookies.clear()
    assert client.get('/api/modules').status_code==401
    assert client.patch('/api/modules/music',json={'enabled':False}).status_code==401


def test_disable_is_owner_scoped_and_preserves_notes(alice, db):
    created=alice.post('/api/notes/add',data={'title':'Keep me','description':'Content'})
    assert created.status_code==200
    assert alice.patch('/api/modules/notes',json={'enabled':False}).status_code==200
    assert preference(alice,'notes')['enabled'] is False
    assert alice.get('/api/notes/').status_code==403
    # Core export/context remain independent from the standalone Notes App.
    assert alice.get('/api/overview/export').json()['notes'][0]['title']=='Keep me'
    save_session('bob','{}','bob@example.test',3600)
    alice.cookies.set('session_id','bob')
    assert preference(alice,'notes')['enabled'] is True
    assert alice.get('/api/notes/').json()['notes']==[]
    alice.cookies.set('session_id','alice-session')
    assert alice.patch('/api/modules/notes',json={'enabled':True}).status_code==200
    assert alice.get('/api/notes/').json()['notes'][0]['id']==created.json()['id']


@pytest.mark.parametrize('module,path',[('music','/api/music/history'),('drive','/api/drive/storage'),('tasks','/api/tasks/'),('calendar','/api/calendar/icloud/events?year=2026&month=10'),('money','/api/money/'),('chat','/api/chat/history'),('quiz','/api/quiz/banks')])
def test_disabled_app_blocked_before_provider_call(alice,module,path):
    assert alice.patch('/api/modules/'+module,json={'enabled':False}).status_code==200
    assert alice.get(path).status_code==403
    assert alice.get('/api/workspaces').status_code==200


def test_disabled_chat_denies_websocket(alice):
    alice.patch('/api/modules/chat',json={'enabled':False})
    with pytest.raises(WebSocketDisconnect) as closed:
        with alice.websocket_connect('/api/chat/ws'):
            pass
    assert closed.value.code==4403


def test_guest_preferences_merge_without_overwriting_signed_in(db):
    with db() as session:
        session.add_all([ModulePreference(user_email='guest',module_id='music',enabled=False),ModulePreference(user_email='guest',module_id='notes',enabled=False),ModulePreference(user_email='signed',module_id='notes',enabled=True)])
        session.commit()
    merge_guest_data('guest','signed')
    with db() as session:
        assert session.get(ModulePreference,('signed','music')).enabled is False
        assert session.get(ModulePreference,('signed','notes')).enabled is True
        assert session.query(ModulePreference).filter_by(user_email='guest').count()==0
