import json
from types import SimpleNamespace

import pytest
import requests
from google.auth.exceptions import RefreshError

from database import save_session
from services import module_connections as connections


def google_session(client, scope='tasks'):
    token = dict(token='test-access', refresh_token='test-refresh', client_id='test-client',
                 client_secret='test-secret', expiry='2099-01-01T00:00:00Z',
                 scopes=['https://www.googleapis.com/auth/' + scope])
    save_session('google-connection-test', json.dumps(token), 'alice@example.test', 3600)
    client.cookies.set('session_id', 'google-connection-test')


def test_summary_is_private_local_only_and_owner_scoped(alice, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Summary must not contact a provider')
    monkeypatch.setattr(requests, 'get', forbidden)
    monkeypatch.setenv('ICLOUD_OWNER_EMAIL', 'alice@example.test')
    monkeypatch.setenv('ICLOUD_USERNAME', 'private-apple@example.test')
    monkeypatch.setenv('ICLOUD_APP_PASSWORD', 'private-password')
    response = alice.get('/api/modules/connections')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()['connections']
    assert data['calendar'][1]['status'] == 'unverified'
    assert data['money'][0]['status'] == 'ready'
    assert data['tasks'][0]['status'] == 'not_connected'
    assert 'private-password' not in response.text and 'private-apple' not in response.text
    save_session('bob-connection', '{}', 'bob@example.test', 3600)
    alice.cookies.set('session_id', 'bob-connection')
    assert alice.get('/api/modules/connections').json()['connections']['calendar'][1]['status'] == 'not_configured'
    alice.cookies.clear()
    assert alice.get('/api/modules/connections').status_code == 401
    assert alice.post('/api/modules/tasks/connections/check').status_code == 401


@pytest.mark.parametrize('code,expected', [(200, 'connected'), (401, 'reauth_required'), (403, 'blocked'), (503, 'unavailable')])
def test_explicit_google_probe_is_bounded_and_redacted(alice, monkeypatch, code, expected):
    google_session(alice)
    calls = []
    class Reply:
        status_code = code
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def probe(url, **kwargs):
        calls.append(url)
        assert kwargs['timeout'] == (3, 8) and kwargs['allow_redirects'] is False
        assert kwargs['params']['fields'] == 'kind'
        return Reply()
    monkeypatch.setattr(requests, 'get', probe)
    response = alice.post('/api/modules/tasks/connections/check')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['connections'][0]['status'] == expected
    assert calls == ['https://tasks.googleapis.com/tasks/v1/users/@me/lists']
    assert all(secret not in response.text for secret in ('test-access', 'test-refresh', 'test-secret'))


def test_guest_missing_scope_disabled_and_timeout(alice, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('Not eligible for a probe')
    monkeypatch.setattr(requests, 'get', forbidden)
    save_session('guest-connection', '{}', 'guest@focusflow.local', 3600)
    alice.cookies.set('session_id', 'guest-connection')
    assert alice.post('/api/modules/tasks/connections/check').json()['connections'][0]['status'] == 'not_connected'
    google_session(alice, 'drive')
    assert alice.post('/api/modules/tasks/connections/check').json()['connections'][0]['status'] == 'missing_scope'
    google_session(alice)
    alice.patch('/api/modules/tasks', json={'enabled': False})
    assert alice.post('/api/modules/tasks/connections/check').status_code == 409
    assert alice.post('/api/modules/money/connections/check').status_code == 404
    alice.patch('/api/modules/tasks', json={'enabled': True})
    def timeout(*args, **kwargs): raise requests.Timeout('private-provider-detail')
    monkeypatch.setattr(requests, 'get', timeout)
    response = alice.post('/api/modules/tasks/connections/check')
    assert response.json()['connections'][0]['status'] == 'unavailable'
    assert 'private-provider-detail' not in response.text


def test_icloud_probe_owner_boundary_and_no_event_reads(monkeypatch,db):
    import caldav
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['url'] == 'https://caldav.icloud.com/' and kwargs['timeout'] == 8
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def principal(self): calls.append('principal'); return object()
    monkeypatch.setenv('ICLOUD_OWNER_EMAIL', 'alice@example.test')
    monkeypatch.setenv('ICLOUD_USERNAME', 'private-apple')
    monkeypatch.setenv('ICLOUD_APP_PASSWORD', 'private-password')
    monkeypatch.setattr(caldav, 'DAVClient', Client)
    assert connections.check_icloud('bob@example.test')['status'] == 'not_configured'
    assert calls == []
    assert connections.check_icloud('alice@example.test')['status'] == 'connected'
    assert calls == ['principal']
    def fail(**kwargs): raise ValueError('private-password')
    monkeypatch.setattr(caldav, 'DAVClient', fail)
    result = connections.check_icloud('alice@example.test')
    assert result['status'] == 'unavailable' and 'private-password' not in str(result)


def test_expired_google_refresh_uses_bound_and_preserves_session_expiry(alice, monkeypatch):
    google_session(alice)
    fake = SimpleNamespace(valid=False, token='refreshed-token')
    def refresh(transport):
        assert isinstance(transport, connections.BoundedGoogleRequest)
        fake.valid = True
    fake.refresh = refresh
    fake.to_json = lambda: '{}'
    monkeypatch.setattr(connections.Credentials, 'from_authorized_user_info', lambda _: fake)
    monkeypatch.setattr(connections, 'google_state', lambda *_: connections.item('Google Tasks', 'unverified', ''))
    saved = []
    monkeypatch.setattr(connections, 'save_session', lambda *args, **kwargs: saved.append(kwargs['max_age']))
    class Reply:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(requests, 'get', lambda *a, **k: Reply())
    assert alice.post('/api/modules/tasks/connections/check').json()['connections'][0]['status'] == 'connected'
    assert len(saved) == 1 and 3500 <= saved[0] <= 3600


@pytest.mark.parametrize('retryable,expected', [(True, 'unavailable'), (False, 'reauth_required')])
def test_refresh_failure_distinguishes_network_and_revocation(alice, monkeypatch, retryable, expected):
    google_session(alice)
    def refresh(_): raise RefreshError('sensitive provider response', retryable=retryable)
    fake = SimpleNamespace(valid=False, refresh=refresh)
    monkeypatch.setattr(connections.Credentials, 'from_authorized_user_info', lambda _: fake)
    monkeypatch.setattr(connections, 'google_state', lambda *_: connections.item('Google Tasks', 'unverified', ''))
    response = alice.post('/api/modules/tasks/connections/check')
    assert response.json()['connections'][0]['status'] == expected
    assert 'sensitive provider response' not in response.text


def test_refresh_transport_has_explicit_timeout(monkeypatch):
    seen = []
    def fake_call(self, *args, **kwargs): seen.append(kwargs['timeout'])
    monkeypatch.setattr(connections.GoogleRequest, '__call__', fake_call)
    with requests.Session() as session:
        connections.BoundedGoogleRequest(session=session)(url='https://oauth2.googleapis.com/token', timeout=120)
    assert seen == [8]
