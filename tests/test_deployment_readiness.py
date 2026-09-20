from unittest.mock import MagicMock
from routers import tasks
from sqlalchemy import text


def test_tasks_provider_error_is_not_empty_success(client, monkeypatch):
    service=MagicMock()
    service.tasklists().list().execute.side_effect=RuntimeError('private information')
    monkeypatch.setattr(tasks,'_tasks_service',lambda request:(service,None))
    response=client.get('/api/tasks/')
    assert response.status_code==502
    assert 'private information' not in response.text


def test_readiness_detects_drift(client, db):
    assert client.get('/health/live').status_code==200
    assert client.get('/health/ready').json()=={'status':'ready'}
    with db() as session:
        session.execute(text("UPDATE alembic_version SET version_num='old'"));session.commit()
    response=client.get('/health/ready')
    assert response.status_code==503 and response.json()=={'status':'not_ready'}
    assert client.get('/health/live').status_code==200

def test_tasks_disabled_api_has_actionable_safe_error(client, monkeypatch):
    import httplib2
    from googleapiclient.errors import HttpError
    service=MagicMock()
    service.tasklists().list().execute.side_effect=HttpError(httplib2.Response({'status':'403'}), b'{"error":{"errors":[{"reason":"accessNotConfigured"}],"message":"private-provider-details"}}')
    monkeypatch.setattr(tasks,'_tasks_service',lambda request:(service,None))
    response=client.get('/api/tasks/')
    assert response.status_code==503
    assert response.json()['code']=='google_tasks_api_disabled'
    assert 'private-provider-details' not in response.text
