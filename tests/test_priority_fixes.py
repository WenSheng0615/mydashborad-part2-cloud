from unittest.mock import MagicMock
import pytest
from routers import calendar, drive

@pytest.fixture
def provider(monkeypatch):
    service = MagicMock()
    monkeypatch.setattr(calendar, '_calendar_service', lambda request: (service, None))
    monkeypatch.setattr(drive, '_drive_service', lambda request: (service, None))
    return service

def test_calendar_patch_and_invalid_range(client, provider):
    data = dict(summary='Changed', description='Retained', start_date='2026-09-16', end_date='2026-09-16', start_time='09:00', end_time='10:00', event_id='event-1')
    assert client.post('/api/calendar/update', data=data).status_code == 200
    call = provider.events().patch.call_args.kwargs
    assert call['eventId'] == 'event-1'
    assert call['body']['start']['dateTime'].endswith('+08:00')
    assert call['body']['description'] == 'Retained'
    assert not provider.events().update.called
    data['end_time'] = '08:00'
    assert client.post('/api/calendar/update', data=data).status_code == 422
    assert provider.events().patch.call_count == 1

def test_calendar_provider_failure_redacted(client, provider):
    provider.events().patch.return_value.execute.side_effect = RuntimeError('private-provider-detail')
    response = client.post('/api/calendar/update', data=dict(summary='Test', start_date='2026-09-16', end_date='2026-09-17', is_all_day='true', event_id='event-1'))
    assert response.status_code == 502
    assert 'private-provider-detail' not in response.text

def test_drive_moves_to_trash(client, provider):
    assert client.post('/api/drive/delete', data={'file_id': 'file-1'}).status_code == 200
    provider.files().update.assert_called_once_with(fileId='file-1', body={'trashed': True})
    provider.files().delete.assert_not_called()

def test_drive_upload_limit_and_cleanup(client, provider, monkeypatch, tmp_path):
    from services import upload_service
    monkeypatch.setattr(upload_service, 'BASE_DIR', tmp_path)
    monkeypatch.setattr(upload_service, 'FILE_LIMIT', 3)
    assert client.post('/api/drive/upload', files={'file': ('test.txt', b'oversize')}).status_code == 413
    assert list((tmp_path/'temp').iterdir()) == []
    provider.files().create.assert_not_called()

def test_quiz_rejects_payload_before_writes(alice):
    import json
    alice.post('/api/quiz/banks/add', data={'name': 'Validation'})
    bank = alice.get('/api/quiz/banks').json()['banks'][0]['id']
    valid = {'name': 'Question', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    for items, status in [([valid, 123], 422), ([valid]*1001, 413), ([dict(valid, options=['x']*21)], 422)]:
        response = alice.post('/api/quiz/import', data={'bank_id': bank}, files={'file': ('quiz.json', json.dumps(items).encode(), 'application/json')})
        assert response.status_code == status
    assert alice.get('/api/quiz/questions', params={'bank_id': bank}).json()['questions'] == []
