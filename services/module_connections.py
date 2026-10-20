"""Owner-scoped connection summaries. Network checks are explicit and read-only."""
import json
import os
from datetime import datetime, timezone

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google.auth.exceptions import RefreshError

from database import save_session

GOOGLE = {
    'tasks': ('Google Tasks', 'tasks', 'https://tasks.googleapis.com/tasks/v1/users/@me/lists', {'maxResults': 1, 'fields': 'kind'}),
    'calendar': ('Google Calendar', 'calendar', 'https://www.googleapis.com/calendar/v3/calendars/primary/events', {'maxResults': 1, 'fields': 'kind'}),
    'drive': ('Google Drive', 'drive', 'https://www.googleapis.com/drive/v3/about', {'fields': 'kind'}),
    'music': ('YouTube 播放清單', 'youtube', 'https://www.googleapis.com/youtube/v3/playlists', {'part': 'id', 'mine': 'true', 'maxResults': 1, 'fields': 'kind'}),
}


def item(provider, status, message, action=None):
    return dict(provider=provider, status=status, message=message, action=action)


def google_state(session, module_id):
    name, scope, _, _ = GOOGLE[module_id]
    if session.user_email.endswith('@focusflow.local'):
        return item(name, 'not_connected', '尚未連接 Google 帳號', 'google')
    try:
        from services.connection_service import read
        provider='youtube' if module_id=='music' else module_id
        info,_=read(session,provider)
        if info is None:
            # Legacy identity-only sessions also need an explicit service connection.
            return item(name,'not_connected','尚未連接此 Google 服務','google')
        creds = Credentials.from_authorized_user_info(info)
        if not creds.token and not creds.refresh_token:
            raise ValueError()
    except Exception:
        return item(name, 'unavailable', '無法讀取授權，請至帳號與服務連線重新連接', 'google')
    scopes = set((info.get('scope') or '').split()) if isinstance(info.get('scope'), str) else set()
    granted = info.get('scopes')
    if isinstance(granted, str):
        scopes.update(granted.split())
    elif isinstance(granted, list):
        scopes.update(s for s in granted if isinstance(s, str))
    # Missing scope metadata is unknown, not proof of denied authorization.
    from services.connection_service import permits
    if scopes and not permits(info,provider):
        return item(name, 'missing_scope', '尚未取得此服務的授權', 'google')
    if creds.expired and not creds.refresh_token:
        return item(name, 'reauth_required', '授權已過期，請重新登入', 'google')
    return item(name, 'unverified', '已保存授權，尚未檢查服務連線')


def icloud_state(owner):
    try:
        from services.connection_service import icloud_config
        configured=bool(icloud_config(owner))
    except Exception:
        return item('iCloud（選用）','unavailable','無法讀取安全連線設定','icloud')
    return item('iCloud（選用）', 'unverified' if configured else 'not_configured',
                '已設定，尚未驗證 CalDAV' if configured else '尚未設定；Google 行事曆仍可獨立使用', 'icloud')


def snapshot(session):
    result = {module: [google_state(session, module)] for module in GOOGLE}
    result['calendar'].append(icloud_state(session.user_email))
    for module in ('workspace', 'settings', 'notes', 'money', 'chat', 'quiz'):
        result[module] = [item('本機功能', 'ready', '可直接使用')]
    # Storage is optional; configuration loaded does not prove the bucket exists.
    try:
        from firebase_admin import get_app
        configured = bool(get_app().options.get('storageBucket'))
    except Exception:
        configured = False
    for module in ('notes', 'chat'):
        result[module].append(item('附件儲存（選用）', 'unverified' if configured else 'not_configured',
                                  '已載入設定，未驗證儲存桶' if configured else '未設定；文字功能可正常使用'))
    return result


class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, *args, **kwargs):
        kwargs['timeout'] = 8
        return super().__call__(*args, **kwargs)


def check_google(session, module_id):
    initial = google_state(session, module_id)
    if initial['status'] != 'unverified':
        return initial
    name, _, url, params = GOOGLE[module_id]
    try:
        from services.connection_service import read,save
        info,generation=read(session,'youtube' if module_id=='music' else module_id)
        creds = Credentials.from_authorized_user_info(info)
        if not creds.valid:
            with requests.Session() as transport:
                creds.refresh(BoundedGoogleRequest(session=transport))
            if generation is not None:
                save(session.user_email,'youtube' if module_id=='music' else module_id,json.loads(creds.to_json()),session.user_email,expected=generation)
            else:
                save_session(session.session_id, creds.to_json(), session.user_email,
                             max_age=max(1, int((session.expires_at - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()))
                             if session.expires_at else 604800)
        # No event/file/task contents are requested or returned; never follow credential redirects.
        with requests.get(url, params=params, headers={'Authorization': 'Bearer ' + creds.token},
                          timeout=(3, 8), allow_redirects=False) as response:
            code = response.status_code
        if code == 200:
            return item(name, 'connected', '本次唯讀連線檢查成功')
        if code == 401:
            return item(name, 'reauth_required', '授權失效，請重新登入 Google', 'google')
        if code == 403:
            return item(name, 'blocked', '服務拒絕存取；請檢查授權、API 啟用狀態或配額', 'google')
    except RefreshError as error:
        if error.retryable:
            return item(name, 'unavailable', 'Google 暫時無法更新授權，請稍後重試')
        return item(name, 'reauth_required', '授權失效，請重新登入 Google', 'google')
    except Exception:
        pass
    return item(name, 'unavailable', '暫時無法連線；不代表授權已失效，請稍後重試')


def check_icloud(owner):
    initial = icloud_state(owner)
    if initial['status'] != 'unverified':
        return initial
    try:
        import caldav
        from services.connection_service import icloud_config
        settings=icloud_config(owner)
        with caldav.DAVClient(url='https://caldav.icloud.com/', username=settings['username'],
                              password=settings['password'], timeout=8) as client:
            client.principal()
        return item('iCloud（選用）', 'connected', 'CalDAV 驗證成功；未讀取行程內容', 'icloud')
    except Exception:
        return item('iCloud（選用）', 'unavailable', '無法驗證；請檢查網路或 App 專用密碼', 'icloud')
