"""Owner-scoped operations. Callers own the session transaction."""
from models import Workspace, Project

class NotFoundError(Exception):
    pass

def owned_workspace(db, user_email, workspace_id):
    item = db.query(Workspace).filter_by(id=workspace_id, user_email=user_email).first()
    if item is None:
        raise NotFoundError()
    return item

def list_workspaces(db, user_email, limit, offset):
    return db.query(Workspace).filter_by(user_email=user_email).order_by(Workspace.created_at, Workspace.id).offset(offset).limit(limit).all()

def create_workspace(db, user_email, name):
    item = Workspace(user_email=user_email, name=name)
    db.add(item)
    db.flush()
    return item

def rename_workspace(db, user_email, workspace_id, name):
    item = owned_workspace(db, user_email, workspace_id)
    item.name = name
    db.flush()
    return item

def list_projects(db, user_email, workspace_id, limit, offset, include_archived=False):
    owned_workspace(db, user_email, workspace_id)
    query = db.query(Project).filter_by(workspace_id=workspace_id)
    if not include_archived:
        query = query.filter(Project.archived_at.is_(None))
    return query.order_by(Project.created_at, Project.id).offset(offset).limit(limit).all()

def create_project(db, user_email, workspace_id, name, kind):
    owned_workspace(db, user_email, workspace_id)
    item = Project(workspace_id=workspace_id, name=name, kind=kind)
    db.add(item)
    db.flush()
    return item

def rename_project(db, user_email, workspace_id, project_id, name):
    owned_workspace(db, user_email, workspace_id)
    item = db.query(Project).filter_by(id=project_id, workspace_id=workspace_id).first()
    if item is None:
        raise NotFoundError()
    item.name = name
    db.flush()
    return item


class WorkspaceNotEmptyError(Exception):
    pass


def delete_empty_workspace(db, user_email, workspace_id):
    item = owned_workspace(db, user_email, workspace_id)
    if db.query(Project.id).filter_by(workspace_id=workspace_id).first():
        raise WorkspaceNotEmptyError()
    db.delete(item)
    db.flush()
