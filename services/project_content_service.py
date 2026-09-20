from models import Task, Note
from .workspace_service import owned_workspace, NotFoundError
from models import Project

def owned_project(db, owner, workspace_id, project_id):
    owned_workspace(db, owner, workspace_id)
    item = db.query(Project).filter_by(id=project_id, workspace_id=workspace_id).first()
    if item is None:
        raise NotFoundError()
    return item

def list_tasks(db, owner, wid, pid, limit, offset):
    owned_project(db, owner, wid, pid)
    return db.query(Task).filter_by(project_id=pid).order_by(Task.created_at, Task.id).offset(offset).limit(limit).all()

def create_task(db, owner, wid, pid, values):
    owned_project(db, owner, wid, pid)
    item = Task(project_id=pid, **values)
    db.add(item)
    db.flush()
    return item

def update_task(db, owner, wid, pid, tid, values):
    owned_project(db, owner, wid, pid)
    item = db.query(Task).filter_by(id=tid, project_id=pid).first()
    if item is None:
        raise NotFoundError()
    for key, value in values.items():
        setattr(item, key, value)
    db.flush()
    return item

def list_notes(db, owner, wid, pid, limit, offset):
    owned_project(db, owner, wid, pid)
    return db.query(Note).filter_by(project_id=pid, user_email=owner, deleted_at=None).order_by(Note.created_at, Note.id).offset(offset).limit(limit).all()

def link_note(db, owner, wid, pid, nid, unlink=False):
    owned_project(db, owner, wid, pid)
    note = db.query(Note).filter_by(id=nid, user_email=owner, deleted_at=None).first()
    if note is None or (unlink and note.project_id != pid):
        raise NotFoundError()
    note.project_id = None if unlink else pid
    db.flush()
    return note
