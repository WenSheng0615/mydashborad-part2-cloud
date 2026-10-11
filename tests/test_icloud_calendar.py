from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from services import icloud_calendar


def test_icloud_requires_session(client):
    assert client.get('/api/calendar/icloud/events?year=2026&month=10').status_code == 401


def test_icloud_owner_isolation(alice, monkeypatch):
    monkeypatch.setenv('ICLOUD_OWNER_EMAIL', 'someone-else@example.test')
    assert alice.get('/api/calendar/icloud/events?year=2026&month=10').json() == {'events': [], 'status': 'not_configured'}
    assert alice.get('/api/calendar/icloud/events?year=2026&month=13').status_code == 422


def test_icloud_errors_redacted(alice, monkeypatch):
    def fail(*args):
        raise RuntimeError('secret-password')
    monkeypatch.setattr(icloud_calendar, 'read_events', fail)
    response = alice.get('/api/calendar/icloud/events?year=2026&month=10')
    assert response.status_code == 502
    assert 'secret-password' not in response.text


def test_icloud_readonly_all_day_and_timezone(monkeypatch):
    import sys
    from icalendar import Calendar
    source = Calendar.from_ical('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:all-day\r\nDTSTART;VALUE=DATE:20261011\r\nSUMMARY:Holiday\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:timed\r\nDTSTART:20261011T160000Z\r\nDTEND:20261011T170000Z\r\nSUMMARY:Meeting\r\nEND:VEVENT\r\nEND:VCALENDAR')
    dav = MagicMock()
    calendar = dav.return_value.__enter__.return_value.principal.return_value.calendars.return_value = [MagicMock()]
    calendar[0].search.return_value = [SimpleNamespace(icalendar_instance=source)]
    monkeypatch.setitem(sys.modules, 'caldav', SimpleNamespace(DAVClient=dav))
    for key, value in {'ICLOUD_OWNER_EMAIL':'alice@example.test','ICLOUD_USERNAME':'test','ICLOUD_APP_PASSWORD':'test'}.items():
        monkeypatch.setenv(key, value)
    result = icloud_calendar.read_events('alice@example.test', datetime(2026,10,1,tzinfo=ZoneInfo('UTC')), datetime(2026,11,1,tzinfo=ZoneInfo('UTC')))
    assert result['status'] == 'connected'
    assert result['events'][0]['end'] == '2026-10-12'
    assert all(e['read_only'] and e['source'] == 'icloud' for e in result['events'])
    dav.return_value.__exit__.assert_called_once()
