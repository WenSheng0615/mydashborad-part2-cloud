import json
from urllib.parse import urlsplit, parse_qs
import pytest
from services.credential_service import restore_json_environment
from routers import auth

@pytest.mark.parametrize("content", ["invalid setting", "[]", '{"web": {}}'])
def test_invalid_environment_preserves_file(tmp_path, monkeypatch, content):
    destination = tmp_path / "credentials.json"
    destination.write_text("existing private content")
    monkeypatch.setenv("GOOGLE_CREDENTIALS", content)
    assert not restore_json_environment("GOOGLE_CREDENTIALS", destination, oauth=True)
    assert destination.read_text() == "existing private content"

def fake_credentials():
    return {"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "fake-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]}}

def test_valid_environment_restored(tmp_path, monkeypatch):
    destination = tmp_path / "credentials.json"
    monkeypatch.setenv("GOOGLE_CREDENTIALS", json.dumps(fake_credentials()))
    assert restore_json_environment("GOOGLE_CREDENTIALS", destination, oauth=True)
    assert json.loads(destination.read_text()) == fake_credentials()

def test_real_sdk_authorization_generation(client, tmp_path, monkeypatch):
    destination = tmp_path / "credentials.json"
    destination.write_text(json.dumps(fake_credentials()))
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", str(destination))
    auth._oauth_attempts.clear()
    try:
        response = client.get("/api/auth/login")
        assert response.status_code == 200
        url = urlsplit(response.json()["url"])
        assert url.hostname == "accounts.google.com"
        query = parse_qs(url.query)
        assert query["code_challenge_method"] == ["S256"]
        assert query["state"][0] in auth._oauth_attempts
        assert auth._oauth_attempts[query["state"][0]]["verifier"]
    finally:
        auth._oauth_attempts.clear()

def test_bad_credential_error_is_actionable(client, tmp_path, monkeypatch):
    destination = tmp_path / "credentials.json"
    destination.write_text("invalid-secret-setting")
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", str(destination))
    response = client.get("/api/auth/login")
    assert response.status_code == 500
    assert response.json()["code"] == "oauth_configuration_error"
    assert "invalid-secret-setting" not in response.text

def test_legacy_worker_route(client):
    response = client.get("/service-worker.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert response.content == client.get("/static/sw.js").content


def test_real_sdk_callback(client, tmp_path, monkeypatch):
    import requests
    from unittest.mock import MagicMock
    from database import get_session_info
    destination = tmp_path / "credentials.json"
    destination.write_text(json.dumps(fake_credentials()))
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", str(destination))
    profile = MagicMock()
    profile.userinfo.return_value.get.return_value.execute.return_value = {"email": "sdk@example.test"}
    monkeypatch.setattr(auth, "build", MagicMock(return_value=profile))
    sent = []

    def send(session, request, **kwargs):
        assert request.url == "https://oauth2.googleapis.com/token"
        sent.append(parse_qs(request.body))
        response = requests.Response()
        response.status_code = 200
        response.request = request
        response._content = json.dumps({"access_token": "test-access", "refresh_token": "test-refresh",
            "token_type": "Bearer", "expires_in": 3600, "scope": " ".join(auth.SCOPES)}).encode()
        return response

    monkeypatch.setattr(requests.sessions.Session, "send", send)
    auth._oauth_attempts.clear()
    try:
        start = client.get("/api/auth/login")
        state = parse_qs(urlsplit(start.json()["url"]).query)["state"][0]
        verifier = auth._oauth_attempts[state]["verifier"]
        response = client.get("/api/auth/callback", params={"state": state, "code": "test-code"}, follow_redirects=False)
        assert response.status_code == 307
        assert sent[0]["code_verifier"] == [verifier]
        assert sent[0]["redirect_uri"] == [auth.REDIRECT_URI]
        assert get_session_info(client.cookies.get("session_id")).user_email == "sdk@example.test"
    finally:
        auth._oauth_attempts.clear()
