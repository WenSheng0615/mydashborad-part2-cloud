from datetime import datetime, timedelta
import pytest
from sqlalchemy.exc import IntegrityError
from database import save_session, merge_guest_data
from models import Workspace, Project, Note, UserSession


def test_core_flow_and_validation(alice):
    response = alice.post("/api/workspaces", json={"name": "  Learning  "})
    assert response.status_code == 201
    workspace = response.json()
    assert workspace["name"] == "Learning"
    assert "user_email" not in workspace
    base = f"/api/workspaces/{workspace['id']}"
    course = alice.post(base + "/projects", json={"name": "Database", "kind": "course"})
    assert course.status_code == 201
    project = course.json()
    assert alice.get(base + "/projects").json() == [project]
    assert alice.patch(base, json={"name": "School"}).json()["name"] == "School"
    assert alice.patch(base + "/projects/" + project["id"], json={"name": "DB II"}).json()["name"] == "DB II"
    for name in ("", "  ", "x" * 121):
        assert alice.post("/api/workspaces", json={"name": name}).status_code == 422
    assert alice.post(base + "/projects", json={"name": "bad", "kind": "other"}).status_code == 422
    assert alice.post("/api/workspaces", json={"name": "bad", "user_email": "bob"}).status_code == 422
    assert alice.get("/api/workspaces?limit=201").status_code == 422
    assert alice.get("/api/workspaces?offset=1").json() == []


def test_authentication_and_owner_isolation(alice):
    wid = alice.post("/api/workspaces", json={"name": "Private"}).json()["id"]
    base = f"/api/workspaces/{wid}"
    pid = alice.post(base + "/projects", json={"name": "Private project"}).json()["id"]
    save_session("bob-session", "{}", "bob@example.test", 3600)
    alice.cookies.set("session_id", "bob-session")
    assert alice.get("/api/workspaces").json() == []
    assert alice.get(base + "/projects").status_code == 404
    assert alice.post(base + "/projects", json={"name": "Attack"}).status_code == 404
    assert alice.patch(base, json={"name": "Attack"}).status_code == 404
    assert alice.patch(base + "/projects/" + pid, json={"name": "Attack"}).status_code == 404
    alice.cookies.set("session_id", "forged")
    assert alice.get("/api/workspaces").status_code == 401
    alice.cookies.clear()
    assert alice.post("/api/workspaces", json={"name": "No login"}).status_code == 401


def test_project_cannot_be_accessed_through_another_workspace(alice):
    first = alice.post("/api/workspaces", json={"name": "A"}).json()["id"]
    second = alice.post("/api/workspaces", json={"name": "B"}).json()["id"]
    pid = alice.post(f"/api/workspaces/{first}/projects", json={"name": "P"}).json()["id"]
    assert alice.patch(f"/api/workspaces/{second}/projects/{pid}", json={"name": "wrong"}).status_code == 404


def test_expired_session_denied(client, db):
    with db() as session:
        session.add(UserSession(session_id="expired", user_email="alice", expires_at=datetime.utcnow()-timedelta(seconds=1)))
        session.commit()
    client.cookies.set("session_id", "expired")
    assert client.get("/api/workspaces").status_code == 401


def test_guest_merge_preserves_workspace_projects(alice):
    guest = "guest-test@focusflow.local"
    save_session("guest-session", "{}", guest, 3600)
    alice.cookies.set("session_id", "guest-session")
    wid = alice.post("/api/workspaces", json={"name": "Guest work"}).json()["id"]
    alice.post(f"/api/workspaces/{wid}/projects", json={"name": "P"})
    assert merge_guest_data(guest, "alice@example.test") == 1
    assert alice.get("/api/workspaces").json() == []
    alice.cookies.set("session_id", "alice-session")
    assert len(alice.get(f"/api/workspaces/{wid}/projects").json()) == 1


def test_database_foreign_key_and_constraints(db):
    with db() as session:
        session.add(Project(workspace_id="missing", name="P", kind="project"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        ws = Workspace(user_email="owner", name="W")
        session.add(ws); session.flush()
        session.add(Project(workspace_id=ws.id, name="P", kind="invalid"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(Workspace(user_email="owner", name="  "))
        with pytest.raises(IntegrityError):
            session.commit()


def test_note_delete_requires_owner(alice, db):
    with db() as session:
        session.add(Note(id="bob-note", user_email="bob@example.test", title="Private"))
        session.commit()
    assert alice.post("/api/notes/delete", data={"note_id": "bob-note"}).status_code == 404
    alice.cookies.set("session_id", "forged")
    assert alice.post("/api/notes/delete", data={"note_id": "bob-note"}).status_code == 401
    with db() as session:
        assert session.get(Note, "bob-note") is not None
    save_session("bob-session", "{}", "bob@example.test", 3600)
    alice.cookies.set("session_id", "bob-session")
    assert alice.post("/api/notes/delete", data={"note_id": "bob-note"}).status_code == 200


def test_core_detail_reads_enforce_owner_and_workspace(alice):
    wid = alice.post("/api/workspaces", json={"name": "Private"}).json()["id"]
    base = f"/api/workspaces/{wid}"
    pid = alice.post(base + "/projects", json={"name": "P"}).json()["id"]
    assert alice.get(base).json()["id"] == wid
    assert alice.get(base + "/projects/" + pid).json()["id"] == pid
    assert alice.get(base + "/projects/missing").status_code == 404
    other = alice.post("/api/workspaces", json={"name": "Other"}).json()["id"]
    assert alice.get(f"/api/workspaces/{other}/projects/{pid}").status_code == 404
    save_session("bob-detail", "{}", "bob@example.test", 3600)
    alice.cookies.set("session_id", "bob-detail")
    assert alice.get(base).status_code == 404
    assert alice.get(base + "/projects/" + pid).status_code == 404
    alice.cookies.clear()
    assert alice.get(base).status_code == 401
    assert alice.get(base + "/projects/" + pid).status_code == 401


def test_workspace_delete_and_archive_context(alice):
    wid=alice.post('/api/workspaces',json={'name':'School'}).json()['id']
    base=f'/api/workspaces/{wid}'
    pid=alice.post(base+'/projects',json={'name':'Study'}).json()['id']
    project=base+'/projects/'+pid
    task=alice.post(project+'/tasks',json={'title':'Read'}).json()
    alice.post('/api/notes/add',data={'title':'Reference','description':'keep'})
    nid=alice.get('/api/notes/').json()['notes'][0]['id']
    assert alice.put(project+'/notes/'+nid).status_code==200
    assert alice.post(project+'/archive',json={'archived':True}).status_code==200
    assert alice.get(base+'/projects').json()==[]
    assert alice.delete(base).status_code==409
    assert alice.get(project+'/tasks').json()[0]['id']==task['id']
    assert alice.get(project+'/notes').json()[0]['id']==nid
    save_session('bob-archive','{}','bob@example.test',3600)
    alice.cookies.set('session_id','bob-archive')
    assert alice.post(project+'/archive',json={'archived':False}).status_code==404
    assert alice.delete(base).status_code==404
    alice.cookies.set('session_id','alice-session')
    assert alice.post(project+'/archive',json={'archived':False}).status_code==200
    empty=alice.post('/api/workspaces',json={'name':'Empty'}).json()['id']
    assert alice.delete('/api/workspaces/'+empty).status_code==204
    assert alice.get('/api/workspaces/'+empty).status_code==404
    alice.cookies.clear()
    assert alice.delete(base).status_code==401


def test_provider_errors_do_not_expose_secrets():
    from services.google_auth_service import AuthResult, auth_error_body
    body,status=auth_error_body(AuthResult('error',detail='private-provider-token'))
    assert status==503
    assert 'private-provider-token' not in str(body)
