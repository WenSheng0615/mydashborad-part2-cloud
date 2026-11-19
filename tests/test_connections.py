import json
from unittest.mock import MagicMock
import pytest
from database import save_session,get_session_info
from models.connection import ServiceConnection,AccountProfile
from routers import auth
from services import connection_service as service


def token(provider='tasks'):
    return dict(token='access-private',refresh_token='refresh-private',client_id='test-client',client_secret='test-secret',expiry='2099-01-01T00:00:00Z',scopes=[service.GOOGLE_SCOPES[provider]])

@pytest.fixture
def binding(monkeypatch,tmp_path):
    auth._oauth_attempts.clear()
    f=tmp_path/'oauth.json';f.write_text('{}');monkeypatch.setattr(auth,'CREDENTIALS_FILE',str(f))
    flow=MagicMock();flow.code_verifier='verifier';flow.authorization_url.return_value=('https://accounts.google.com/authorize','binding-state')
    flow.credentials.to_json.return_value=json.dumps(token())
    flow.credentials.granted_scopes=[service.GOOGLE_SCOPES['tasks']]
    flow.oauth2session.token={'scope':service.GOOGLE_SCOPES['tasks']}
    monkeypatch.setattr(auth.Flow,'from_client_secrets_file',MagicMock(return_value=flow))
    api=MagicMock();api.userinfo().get().execute.return_value={'email':'alice@example.test','id':'alice-sub','verified_email':True,'name':'Alice'}
    monkeypatch.setattr(auth,'build',MagicMock(return_value=api))
    yield flow,api
    auth._oauth_attempts.clear()


def callback(client):return client.get('/api/auth/callback?state=binding-state&code=fake',follow_redirects=False)


def test_guest_can_work_and_does_not_call_google(client,monkeypatch):
    monkeypatch.setattr(auth,'build',lambda *a,**k:pytest.fail('Identity must be local'))
    client.get('/api/auth/guest');sid=client.cookies.get('session_id')
    client.get('/api/auth/guest');assert client.cookies.get('session_id')==sid
    assert client.get('/api/auth/user').json()['is_guest']
    assert client.post('/api/workspaces',json={'name':'Trial'}).status_code==201
    assert client.post('/api/connections/google/tasks/connect').status_code==403
    assert client.get('/api/tasks/').json()['connection_required'] is True
    assert client.post('/api/connections/icloud/connect',json={'username':'a@example.test','password':'aaaa-bbbb-cccc-dddd'}).status_code==403


def test_combined_login_scopes_and_guest_content_merge(client,binding,db):
    client.get('/api/auth/guest')
    space=client.post('/api/workspaces',json={'name':'Trial'}).json()
    project=client.post('/api/workspaces/'+space['id']+'/projects',json={'name':'Project'}).json()
    client.post('/api/workspaces/'+space['id']+'/projects/'+project['id']+'/tasks',json={'title':'Keep task'})
    client.get('/api/auth/login?return_to=account')
    scopes=auth.Flow.from_client_secrets_file.call_args.kwargs['scopes']
    assert scopes==auth.SCOPES+list(service.GOOGLE_SCOPES.values())
    result=callback(client);assert result.status_code==307 and result.headers['location'].startswith('/account')
    assert get_session_info(client.cookies.get('session_id')).token_json=='{}'
    assert client.get('/api/workspaces').json()[0]['id']==space['id']
    assert client.get('/api/workspaces/'+space['id']+'/projects/'+project['id']+'/tasks').json()[0]['title']=='Keep task'
    assert client.get('/api/auth/user').json()['logged_in'] is True
    with db() as d:
        assert d.query(ServiceConnection).count()==1
        assert d.get(ServiceConnection,('alice@example.test','tasks')).enabled


def test_google_bind_encrypted_then_disconnect_stays_logged_in(alice,binding,db,monkeypatch):
    assert alice.post('/api/connections/google/tasks/connect').status_code==200
    assert callback(alice).status_code==307
    with db() as d:
        row=d.get(ServiceConnection,('alice@example.test','tasks'))
        assert row.enabled and 'refresh-private' not in row.secret and 'access-private' not in row.secret
    snapshot=alice.get('/api/connections');assert 'private' not in snapshot.text
    assert alice.delete('/api/connections/tasks').json()['local_data_preserved']
    monkeypatch.setattr('services.google_auth_service.build',lambda *a,**k:pytest.fail('Disconnected service must not call Google'))
    assert alice.get('/api/tasks/').status_code==403
    assert alice.get('/api/auth/user').json()['logged_in']
    assert alice.get('/api/workspaces').status_code==200
    assert callback(alice).status_code==400


@pytest.mark.parametrize('case,code',[('different_account','connection_account_mismatch'),('unverified',None),('missing_scope','connection_scope_denied'),('different_session','connection_session_changed'),('no_refresh','connection_offline_denied')])
def test_binding_rejects_wrong_context_or_incomplete_grant(alice,binding,db,case,code):
    flow,api=binding
    alice.post('/api/connections/google/tasks/connect')
    if case=='different_account':api.userinfo().get().execute.return_value={'email':'bob@example.test','id':'bob-sub','verified_email':True}
    if case=='unverified':api.userinfo().get().execute.return_value={'email':'alice@example.test','id':'alice-sub','verified_email':False}
    if case=='missing_scope':flow.credentials.granted_scopes=[];flow.oauth2session.token={'scope':'openid'}
    if case=='different_session':save_session('other-session','{}','alice@example.test');alice.cookies.set('session_id','other-session')
    if case=='no_refresh':value=token();value.pop('refresh_token');flow.credentials.to_json.return_value=json.dumps(value)
    response=callback(alice);assert response.status_code==400
    if code:assert response.json()['code']==code
    with db() as d:assert not d.query(ServiceConnection).filter_by(enabled=True).first()


def test_cancel_keeps_existing_connection_and_nonce_consumed(alice,binding):
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    alice.post('/api/connections/google/tasks/connect')
    r=alice.get('/api/auth/callback?state=binding-state&error=access_denied',follow_redirects=False)
    assert r.status_code==307 and 'cancelled' in r.headers['location']
    assert service.read(get_session_info('alice-session'),'tasks')[0]
    assert callback(alice).status_code==400


def test_disconnect_invalidates_pending_callback_and_refresh(alice,binding):
    alice.post('/api/connections/google/tasks/connect')
    alice.delete('/api/connections/tasks')
    assert callback(alice).status_code==500
    assert service.read(get_session_info('alice-session'),'tasks')[0] is None
    with pytest.raises(ValueError):service.save('alice@example.test','tasks',token(),'alice@example.test',expected=0)


def test_other_owner_and_legacy_tombstone(alice,db):
    save_session('legacy',json.dumps(token()),'alice@example.test')
    alice.cookies.set('session_id','legacy')
    assert service.read(get_session_info('legacy'),'tasks')[0]
    alice.delete('/api/connections/tasks')
    assert service.read(get_session_info('legacy'),'tasks')[0] is None
    save_session('bob','{}','bob@example.test');alice.cookies.set('session_id','bob')
    assert all(x['status']=='not_connected' for x in alice.get('/api/connections').json()['connections'] if x['id']!='icloud')
    alice.delete('/api/connections/tasks')
    with db() as d:assert d.get(ServiceConnection,('alice@example.test','tasks')).enabled is False
    assert alice.delete('/api/connections/tasks',headers={'Origin':'https://attacker.test'}).status_code==403


def test_icloud_private_binding_validation_disconnect_and_redaction(alice,monkeypatch,db):
    import caldav
    dav=MagicMock();monkeypatch.setattr(caldav,'DAVClient',dav)
    secret='aaaa-bbbb-cccc-dddd'
    result=alice.post('/api/connections/icloud/connect',json={'username':'apple@example.test','password':secret})
    assert result.status_code==200
    assert service.icloud_config('alice@example.test')['password']==secret
    assert service.icloud_config('bob@example.test') is None
    assert secret not in alice.get('/api/connections').text
    with db() as d:assert secret not in d.get(ServiceConnection,('alice@example.test','icloud')).secret
    invalid=alice.post('/api/connections/icloud/connect',json={'username':'x','password':'private-short'})
    assert invalid.status_code==422 and 'private-short' not in invalid.text
    alice.delete('/api/connections/icloud');assert service.icloud_config('alice@example.test') is None
    dav.return_value.__enter__.return_value.principal.side_effect=RuntimeError(secret)
    r=alice.post('/api/connections/icloud/connect',json={'username':'apple@example.test','password':secret})
    assert r.status_code==502 and secret not in r.text


def test_missing_key_does_not_generate_replacement_or_break_core(alice,db):
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    with db() as d:
        from pathlib import Path
        key=Path(d.get_bind().url.database).parent/'.local/secrets/connections.key'
    key.unlink()
    assert alice.get('/api/connections').status_code==200
    assert not key.exists()
    assert alice.get('/api/auth/user').json()['logged_in']
    assert alice.get('/api/workspaces').status_code==200


def test_connection_is_account_owned_survives_logout(alice,db):
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    alice.get('/api/auth/logout')
    save_session('new-session','{}','alice@example.test');alice.cookies.set('session_id','new-session')
    assert service.read(get_session_info('new-session'),'tasks')[0]['refresh_token']=='refresh-private'


def test_encrypted_restore_drill(db,tmp_path,monkeypatch):
    import shutil
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database
    from scripts.backup_restore import snapshot
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    with db() as d:source=Path(d.get_bind().url.database)
    restored=tmp_path/'isolated'/'restore.db'
    snapshot(source,restored)
    key=restored.parent/'.local/secrets/connections.key';key.parent.mkdir(parents=True)
    shutil.copyfile(source.parent/'.local/secrets/connections.key',key)
    engine=create_engine('sqlite:///'+restored.as_posix())
    monkeypatch.setattr(database,'SessionLocal',sessionmaker(bind=engine))
    from types import SimpleNamespace
    assert service.read(SimpleNamespace(user_email='alice@example.test'), 'tasks')[0]['refresh_token']=='refresh-private'
    engine.dispose()


def test_login_context_change_never_merges_another_guest(client,binding):
    client.get('/api/auth/guest');client.get('/api/auth/login')
    save_session('other-guest','{}','guest-other@focusflow.local');client.cookies.set('session_id','other-guest')
    assert callback(client).status_code==400
    binding[0].fetch_token.assert_not_called()


@pytest.mark.parametrize('allow', [True,False])
def test_real_sdk_incremental_or_partial_scope_is_checked(alice,tmp_path,monkeypatch,allow):
    import requests
    from urllib.parse import urlsplit,parse_qs
    credentials=tmp_path/'client.json'
    credentials.write_text(json.dumps({'web':{'client_id':'test.apps.googleusercontent.com','client_secret':'fake-secret','auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token','redirect_uris':['http://localhost']}}))
    monkeypatch.setattr(auth,'CREDENTIALS_FILE',str(credentials))
    identity=MagicMock();identity.userinfo().get().execute.return_value={'email':'alice@example.test','id':'subject-alice','verified_email':True}
    monkeypatch.setattr(auth,'build',lambda *a,**k:identity)
    actual=auth.SCOPES+[service.GOOGLE_SCOPES['drive']]+([service.GOOGLE_SCOPES['tasks']] if allow else [])
    def send(session,request,**kwargs):
        response=requests.Response();response.status_code=200;response.request=request
        response._content=json.dumps({'access_token':'sdk-fake-access','refresh_token':'sdk-fake-refresh','token_type':'Bearer','expires_in':3600,'scope':' '.join(actual)}).encode()
        return response
    monkeypatch.setattr(requests.sessions.Session,'send',send)
    auth._oauth_attempts.clear()
    start=alice.post('/api/connections/google/tasks/connect')
    state=parse_qs(urlsplit(start.json()['url']).query)['state'][0]
    result=alice.get('/api/auth/callback',params={'state':state,'code':'sdk-code'},follow_redirects=False)
    assert result.status_code==(307 if allow else 400)
    assert service.read(get_session_info('alice-session'),'drive')[0] is None
    assert bool(service.read(get_session_info('alice-session'),'tasks')[0]) is allow
    auth._oauth_attempts.clear()


def grant(flow,providers,refresh=True):
    value=token();value['scopes']=[service.GOOGLE_SCOPES[p] for p in providers]
    if not refresh:value.pop('refresh_token')
    flow.credentials.to_json.return_value=json.dumps(value)
    flow.credentials.granted_scopes=value['scopes']
    flow.oauth2session.token={'scope':' '.join(value['scopes'])}


def test_combined_login_saves_four_actual_grants_encrypted(client,binding,db):
    grant(binding[0],service.GOOGLE_SCOPES)
    client.get('/api/auth/login?return_to=connections')
    response=callback(client)
    assert response.status_code==307 and response.headers['location']=='/account#connections'
    session=get_session_info(client.cookies.get('session_id'))
    assert session.token_json=='{}'
    with db() as d:
        rows=d.query(ServiceConnection).all()
        assert {r.provider for r in rows}==set(service.GOOGLE_SCOPES)
        assert all(r.enabled and 'private' not in r.secret for r in rows)
    for provider in service.GOOGLE_SCOPES:
        assert service.read(session,provider)[0]['refresh_token']=='refresh-private'
    assert 'private' not in client.get('/api/connections').text


def test_combined_login_does_not_infer_requested_permissions(client,binding,db):
    grant(binding[0],service.GOOGLE_SCOPES)
    binding[0].credentials.granted_scopes=None
    binding[0].oauth2session.token={}
    client.get('/api/auth/login');assert callback(client).status_code==307
    with db() as d:assert d.query(ServiceConnection).count()==0


def test_partial_login_only_connects_granted_services(client,binding,db):
    grant(binding[0],['calendar','youtube'])
    client.get('/api/auth/login');assert callback(client).status_code==307
    with db() as d:assert {r.provider for r in d.query(ServiceConnection)}=={'calendar','youtube'}


def test_combined_callback_preserves_concurrent_disconnect(alice,binding,db):
    grant(binding[0],service.GOOGLE_SCOPES)
    alice.get('/api/auth/login')
    alice.delete('/api/connections/tasks')
    assert callback(alice).status_code==307
    with db() as d:
        assert not d.get(ServiceConnection,('alice@example.test','tasks')).enabled
        assert d.get(ServiceConnection,('alice@example.test','drive')).enabled


def test_existing_account_can_explicitly_reconnect_all(alice,binding,db):
    service.disconnect('alice@example.test','tasks')
    grant(binding[0],service.GOOGLE_SCOPES)
    alice.get('/api/auth/login');assert callback(alice).status_code==307
    with db() as d:assert all(r.enabled for r in d.query(ServiceConnection))


def test_anonymous_login_cannot_resurrect_preexisting_tombstone(client,binding,db):
    service.disconnect('alice@example.test','tasks')
    grant(binding[0],service.GOOGLE_SCOPES)
    client.get('/api/auth/login');assert callback(client).status_code==307
    with db() as d:assert not d.get(ServiceConnection,('alice@example.test','tasks')).enabled


def test_missing_refresh_only_reuses_matching_existing_service(alice,binding,db):
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    grant(binding[0],service.GOOGLE_SCOPES,refresh=False)
    alice.get('/api/auth/login');assert callback(alice).status_code==307
    with db() as d:assert {r.provider for r in d.query(ServiceConnection)}=={'tasks'}


def test_google_login_batch_rolls_back_on_storage_failure(db,monkeypatch):
    original=service.cipher;calls=[]
    def fail_later(db):
        calls.append(1)
        if len(calls)>1:raise ValueError('Private storage error')
        return original(db)
    monkeypatch.setattr(service,'cipher',fail_later)
    value=token();value['scopes']=list(service.GOOGLE_SCOPES.values())
    with pytest.raises(ValueError):service.save_google_login('alice@example.test',value)
    with db() as d:assert d.query(ServiceConnection).count()==0


def test_provider_check_independent_of_app_visibility(alice,monkeypatch):
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    alice.patch('/api/modules/tasks',json={'enabled':False})
    monkeypatch.setattr('services.module_connections.check_google',lambda session,module:dict(provider='Google Tasks',status='connected',message='OK'))
    response=alice.post('/api/connections/tasks/check')
    assert response.status_code==200 and response.json()['status']=='connected'
    assert response.headers['cache-control']=='no-store'
    assert alice.get('/api/connections').headers['cache-control']=='no-store'


def test_provider_check_does_not_report_disconnected_token_as_connected(alice,monkeypatch):
    service.save('alice@example.test','tasks',token(),'alice@example.test')
    def disconnected(session,module):
        service.disconnect(session.user_email,'tasks')
        return dict(provider='Google Tasks',status='connected',message='OK')
    monkeypatch.setattr('services.module_connections.check_google',disconnected)
    assert alice.post('/api/connections/tasks/check').json()['status']=='not_connected'
