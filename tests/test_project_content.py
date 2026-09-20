from database import save_session, merge_guest_data
from models import Note

def project(client):
    wid = client.post("/api/workspaces", json={"name": "Study"}).json()["id"]
    pid = client.post(f"/api/workspaces/{wid}/projects", json={"name": "DB"}).json()["id"]
    return f"/api/workspaces/{wid}/projects/{pid}"

def test_task_lifecycle_and_validation(alice):
    base = project(alice)
    result = alice.post(base + "/tasks", json={"title": "  Read  ", "due_date": "2026-10-01"})
    assert result.status_code == 201
    task = result.json()
    assert task["title"] == "Read" and task["status"] == "todo"
    assert alice.get(base + "/tasks").json() == [task]
    endpoint = base + "/tasks/" + task["id"]
    for status in ("doing", "done", "todo"):
        assert alice.patch(endpoint, json={"status": status}).json()["status"] == status
    assert alice.patch(endpoint, json={"due_date": None}).json()["due_date"] is None
    for body in ({"title": None}, {"title": " "}, {"status": "invalid"}, {"project_id": "other"}, {"description": "x"*10001}):
        assert alice.patch(endpoint, json=body).status_code == 422
    assert alice.post(base + "/tasks", json={"title": "X", "due_date": "bad"}).status_code == 422
    assert alice.get(base + "/tasks?offset=1").json() == []

def test_tasks_and_notes_owner_isolation(alice, db):
    base = project(alice)
    tid = alice.post(base + "/tasks", json={"title": "Private"}).json()["id"]
    with db() as session:
        session.add(Note(id="alice-note", user_email="alice@example.test", content="private"))
        session.add(Note(id="bob-note", user_email="bob@example.test", content="other"))
        session.commit()
    assert alice.put(base + "/notes/bob-note").status_code == 404
    assert alice.put(base + "/notes/alice-note").status_code == 200
    save_session("bob", "{}", "bob@example.test", 3600)
    alice.cookies.set("session_id", "bob")
    for method, path, kwargs in [
        ("get", "/tasks", {}), ("post", "/tasks", {"json": {"title": "bad"}}),
        ("patch", "/tasks/"+tid, {"json": {"status": "done"}}),
        ("get", "/notes", {}), ("put", "/notes/alice-note", {}), ("delete", "/notes/alice-note", {})]:
        assert getattr(alice, method)(base+path, **kwargs).status_code == 404

def test_link_unlink_preserves_legacy_note(alice, db):
    base = project(alice)
    other = project(alice)
    alice.post("/api/notes/add", data={"title": "Legacy", "description": "Keep"})
    nid = alice.get("/api/notes/").json()["notes"][0]["id"]
    assert alice.get(base + "/notes").json() == []
    assert alice.put(base + "/notes/" + nid).status_code == 200
    assert alice.get(base + "/notes").json()[0]["content"] == "Keep"
    assert alice.delete(other + "/notes/" + nid).status_code == 404
    assert alice.delete(base + "/notes/" + nid).json()["project_id"] is None
    with db() as session:
        assert session.get(Note, nid).content == "Keep"
    assert alice.get("/api/notes/").json()["notes"][0]["id"] == nid

def test_wrong_project_task_and_guest_merge(alice):
    base = project(alice)
    other = project(alice)
    tid = alice.post(base + "/tasks", json={"title": "P"}).json()["id"]
    assert alice.patch(other + "/tasks/" + tid, json={"status": "done"}).status_code == 404
    merge_guest_data("alice@example.test", "new@example.test")
    assert alice.get(base + "/tasks").status_code == 404
    save_session("new", "{}", "new@example.test", 3600)
    alice.cookies.set("session_id", "new")
    assert alice.get(base + "/tasks").json()[0]["id"] == tid
