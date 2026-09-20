from unittest.mock import MagicMock
import pytest
from routers import auth

@pytest.fixture
def oauth(monkeypatch, tmp_path):
    auth._oauth_attempts.clear()
    credentials = tmp_path / "fake.json"
    credentials.write_text("{}")
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", str(credentials))
    flow = MagicMock()
    flow.code_verifier = "fake-pkce"
    flow.authorization_url.return_value = ("https://accounts.google.com/test", "test-state")
    flow.credentials.to_json.return_value = "{}"
    monkeypatch.setattr(auth.Flow, "from_client_secrets_file", MagicMock(return_value=flow))
    service = MagicMock()
    service.userinfo.return_value.get.return_value.execute.return_value = {"email": "oauth@example.test"}
    monkeypatch.setattr(auth, "build", MagicMock(return_value=service))
    yield flow
    auth._oauth_attempts.clear()

def test_state_cookie_and_success_replay(client, oauth):
    result = client.get("/api/auth/login")
    assert result.status_code == 200
    cookie = result.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=600" in cookie
    assert "code_verifier" not in cookie
    result = client.get("/api/auth/callback?code=abc&state=test-state", follow_redirects=False)
    assert result.status_code == 307
    oauth.fetch_token.assert_called_once_with(code="abc", code_verifier="fake-pkce")
    assert "oauth_browser" not in client.cookies
    assert client.get("/api/auth/callback?code=abc&state=test-state").status_code == 400
    assert oauth.fetch_token.call_count == 1

@pytest.mark.parametrize("case", ["missing_state", "wrong_state", "wrong_browser", "expired", "denied"])
def test_bad_callback_never_exchanges_token(client, oauth, case):
    client.get("/api/auth/login")
    query = "code=abc&state=test-state"
    if case == "missing_state": query = "code=abc"
    if case == "wrong_state": query = "code=abc&state=wrong"
    if case == "wrong_browser": client.cookies.clear()
    if case == "expired": auth._oauth_attempts["test-state"]["expires"] = 0
    if case == "denied": query = "error=access_denied&state=test-state"
    assert client.get("/api/auth/callback?"+query).status_code == 400
    oauth.fetch_token.assert_not_called()

def test_token_failure_cleans_up_without_leaking(client, oauth):
    client.get("/api/auth/login")
    oauth.fetch_token.side_effect = RuntimeError("private-token-content")
    response = client.get("/api/auth/callback?code=abc&state=test-state")
    assert response.status_code == 500
    assert "private-token-content" not in response.text
    assert "oauth_browser" not in client.cookies
    assert not auth._oauth_attempts

def test_pending_capacity_and_expiry(client, oauth, monkeypatch):
    monkeypatch.setattr(auth, "OAUTH_MAX_PENDING", 1)
    client.get("/api/auth/login")
    assert client.get("/api/auth/login").status_code == 503
    auth._oauth_attempts["test-state"]["expires"] = 0
    assert client.get("/api/auth/login").status_code == 200


def test_public_login_rejects_local_origin_before_creating_state(client, oauth, monkeypatch):
    monkeypatch.setattr(auth, "IS_DEPLOYED", True)
    monkeypatch.setattr(auth, "APP_URL", "https://focusflow.example")
    response = client.get("/api/auth/login")
    assert response.status_code == 400
    assert response.json()["code"] == "oauth_origin_mismatch"
    assert response.json()["login_url"] == "https://focusflow.example"
    assert not auth._oauth_attempts
    oauth.authorization_url.assert_not_called()
    response = client.get("https://focusflow.example/api/auth/login")
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_logout_invalidates_session(alice):
    from database import get_session_info
    response=alice.get('/api/auth/logout',follow_redirects=False)
    assert response.status_code==307
    assert get_session_info('alice-session') is None
    assert alice.get('/api/workspaces').status_code==401
