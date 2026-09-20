import pytest


def test_homepage_and_static(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/js/notes.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_guest_login(client):
    assert client.get("/api/auth/guest").status_code == 200
    assert client.get("/api/auth/user").json()["is_guest"] is True


def test_notes_money_keep_and_quiz(alice):
    assert alice.post("/api/notes/add", data={"title": "Test", "description": "Preserved"}).status_code == 200
    note = alice.get("/api/notes/").json()["notes"][0]
    assert note["description"] == "Preserved"
    assert alice.post("/api/money/add", data={"item": "Lunch", "amount": "120", "date": "2026-09-15", "type": "expense", "category": "food"}).status_code == 200
    assert alice.get("/api/money/").json()["total_expense"] == 120
    assert alice.post("/api/chat/send", params={"content": "hello"}).status_code == 200
    assert alice.get("/api/chat/history").json()["messages"][0]["content"] == "hello"
    assert alice.post("/api/quiz/banks/add", data={"name": "Test bank"}).status_code == 200
    banks = alice.get("/api/quiz/banks").json()["banks"]
    assert len(banks) == 1
    assert alice.get("/api/music/history").status_code == 200


@pytest.mark.parametrize("url", ["/api/drive/files", "/api/tasks/", "/api/calendar/events?year=2026&month=9", "/api/music/playlists"])
def test_google_modules_deny_unauthenticated(client, url):
    assert client.get(url).status_code == 401
