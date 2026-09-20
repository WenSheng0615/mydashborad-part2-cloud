from datetime import date, datetime
from typing import Annotated, Literal
from fastapi import APIRouter
from pydantic import HttpUrl, BaseModel, ConfigDict, StringConstraints, model_validator
from routers.workspaces import User, DB, Limit, Offset
from services import project_content_service as service

router = APIRouter(prefix="/api/workspaces/{workspace_id}/projects/{project_id}", tags=["project content"])
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(max_length=10000)]
Status = Literal["todo", "doing", "done"]

class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    description: Description = ""
    due_date: date | None = None

class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title | None = None
    description: Description | None = None
    status: Status | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def non_null_fields(self):
        for name in ("title", "description", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    title: str
    description: str
    status: Status
    due_date: date | None
    created_at: datetime

class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str | None
    title: str | None
    content: str | None
    color: str | None
    image_url: str | None
    created_at: str | None

@router.get("/tasks", response_model=list[TaskOut])
def tasks(workspace_id: str, project_id: str, user: User, db: DB, limit: Limit = 100, offset: Offset = 0):
    return [TaskOut.model_validate(x) for x in service.list_tasks(db, user, workspace_id, project_id, limit, offset)]

@router.post("/tasks", response_model=TaskOut, status_code=201)
def add_task(workspace_id: str, project_id: str, body: TaskCreate, user: User, db: DB):
    return TaskOut.model_validate(service.create_task(db, user, workspace_id, project_id, body.model_dump()))

@router.patch("/tasks/{task_id}", response_model=TaskOut)
def edit_task(workspace_id: str, project_id: str, task_id: str, body: TaskPatch, user: User, db: DB):
    return TaskOut.model_validate(service.update_task(db, user, workspace_id, project_id, task_id, body.model_dump(exclude_unset=True)))

@router.get("/notes", response_model=list[NoteOut])
def notes(workspace_id: str, project_id: str, user: User, db: DB, limit: Limit = 100, offset: Offset = 0):
    return [NoteOut.model_validate(x) for x in service.list_notes(db, user, workspace_id, project_id, limit, offset)]

@router.put("/notes/{note_id}", response_model=NoteOut)
def attach_note(workspace_id: str, project_id: str, note_id: str, user: User, db: DB):
    return NoteOut.model_validate(service.link_note(db, user, workspace_id, project_id, note_id))

@router.delete("/notes/{note_id}", response_model=NoteOut)
def detach_note(workspace_id: str, project_id: str, note_id: str, user: User, db: DB):
    return NoteOut.model_validate(service.link_note(db, user, workspace_id, project_id, note_id, unlink=True))


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    url: HttpUrl

@router.get("/links")
def links(workspace_id: str, project_id: str, user: User, db: DB):
    from models import ProjectLink
    service.owned_project(db, user, workspace_id, project_id)
    rows = db.query(ProjectLink).filter_by(project_id=project_id).order_by(ProjectLink.created_at).all()
    return [{"id": x.id, "title": x.title, "url": x.url} for x in rows]

@router.post("/links", status_code=201)
def add_link(workspace_id: str, project_id: str, body: LinkCreate, user: User, db: DB):
    from models import ProjectLink
    from fastapi import HTTPException
    service.owned_project(db, user, workspace_id, project_id)
    if len(str(body.url)) > 2048: raise HTTPException(422, "網址太長")
    item = ProjectLink(project_id=project_id, title=body.title, url=str(body.url))
    db.add(item); db.flush()
    return {"id": item.id, "title": item.title, "url": item.url}

@router.delete("/links/{link_id}")
def remove_link(workspace_id: str, project_id: str, link_id: str, user: User, db: DB):
    from models import ProjectLink
    from services.workspace_service import NotFoundError
    service.owned_project(db, user, workspace_id, project_id)
    item = db.query(ProjectLink).filter_by(id=link_id, project_id=project_id).first()
    if not item: raise NotFoundError()
    db.delete(item)
    return {"status": "success"}
