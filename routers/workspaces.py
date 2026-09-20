from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, StringConstraints
from database import get_db, get_session_info
from services import workspace_service as service

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

class Rename(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name

class ProjectCreate(Rename):
    kind: Literal["project", "course"] = "project"

class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    created_at: datetime

class ProjectOut(WorkspaceOut):
    workspace_id: str
    kind: Literal["project", "course"]
    archived_at: datetime | None

def require_user(request: Request):
    sid = request.cookies.get("session_id")
    session = get_session_info(sid) if sid else None
    if not session or not session.user_email:
        raise HTTPException(401, "Authentication required")
    return session.user_email

def db_session():
    with get_db() as db:
        try:
            yield db
            db.commit()
        except service.WorkspaceNotEmptyError:
            db.rollback()
            raise HTTPException(409, "工作空間仍有專案（含封存），無法刪除")
        except service.NotFoundError:
            db.rollback()
            raise HTTPException(404, "Not found")
        except Exception:
            db.rollback()
            raise

User = Annotated[str, Depends(require_user)]
DB = Annotated[object, Depends(db_session, scope="function")]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]

@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(user: User, db: DB, limit: Limit = 100, offset: Offset = 0):
    return [WorkspaceOut.model_validate(x) for x in service.list_workspaces(db, user, limit, offset)]

@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(body: Rename, user: User, db: DB):
    return WorkspaceOut.model_validate(service.create_workspace(db, user, body.name))

@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def rename_workspace(workspace_id: str, body: Rename, user: User, db: DB):
    return WorkspaceOut.model_validate(service.rename_workspace(db, user, workspace_id, body.name))

@router.get("/{workspace_id}/projects", response_model=list[ProjectOut])
def list_projects(workspace_id: str, user: User, db: DB, limit: Limit = 100, offset: Offset = 0, include_archived: bool = False):
    return [ProjectOut.model_validate(x) for x in service.list_projects(db, user, workspace_id, limit, offset, include_archived)]

@router.post("/{workspace_id}/projects", response_model=ProjectOut, status_code=201)
def create_project(workspace_id: str, body: ProjectCreate, user: User, db: DB):
    return ProjectOut.model_validate(service.create_project(db, user, workspace_id, body.name, body.kind))

@router.patch("/{workspace_id}/projects/{project_id}", response_model=ProjectOut)
def rename_project(workspace_id: str, project_id: str, body: Rename, user: User, db: DB):
    return ProjectOut.model_validate(service.rename_project(db, user, workspace_id, project_id, body.name))


class ArchiveRequest(BaseModel):
    archived: bool

@router.post("/{workspace_id}/projects/{project_id}/archive", response_model=ProjectOut)
def archive(workspace_id: str, project_id: str, body: ArchiveRequest, user: User, db: DB):
    from services.project_content_service import owned_project
    item = owned_project(db, user, workspace_id, project_id)
    item.archived_at = datetime.now(timezone.utc).replace(tzinfo=None) if body.archived else None
    db.flush()
    return ProjectOut.model_validate(item)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, user: User, db: DB):
    return WorkspaceOut.model_validate(service.owned_workspace(db, user, workspace_id))


@router.get("/{workspace_id}/projects/{project_id}", response_model=ProjectOut)
def get_project(workspace_id: str, project_id: str, user: User, db: DB):
    from services.project_content_service import owned_project
    return ProjectOut.model_validate(owned_project(db, user, workspace_id, project_id))


@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str, user: User, db: DB):
    service.delete_empty_workspace(db, user, workspace_id)
