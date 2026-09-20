from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from routers.workspaces import User, DB
from routers.project_content import TaskOut, NoteOut
from models import Workspace, Project, Task, Note, ProjectLink
from config import APP_TIMEZONE

router = APIRouter(prefix="/api/overview", tags=["overview"])

@router.get("/today")
def today(user: User, db: DB, on: date | None = None,
          limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    today = on or datetime.now(ZoneInfo(APP_TIMEZONE)).date()
    query = db.query(Task, Project).join(Project, Task.project_id == Project.id).join(Workspace).filter(
        Workspace.user_email == user, Project.archived_at.is_(None), Task.status != "done")
    result = {"date": today.isoformat(), "overdue": [], "today": [], "unscheduled": [], "upcoming": [], "counts": {}, "has_more": {}}
    # Each section can be fetched in full from the project; avoid unbounded homepage responses.
    for name, condition in (("overdue", Task.due_date < today), ("today", Task.due_date == today),
                            ("unscheduled", Task.due_date.is_(None)), ("upcoming", Task.due_date > today)):
        filtered = query.filter(condition)
        result["counts"][name] = filtered.count()
        result["has_more"][name] = offset + limit < result["counts"][name]
        rows = filtered.order_by(Task.due_date, Task.created_at, Task.id).offset(offset).limit(limit).all()
        result[name] = [{**TaskOut.model_validate(task).model_dump(mode="json"),
                         "workspace_id": project.workspace_id, "project_name": project.name} for task, project in rows]
    return result

@router.get("/search")
def search(user: User, db: DB, q: str = Query(..., min_length=1, max_length=200)):
    text = q.strip()
    if not text: return {"projects": [], "tasks": [], "notes": []}
    projects = db.query(Project).join(Workspace).filter(Workspace.user_email == user, Project.name.contains(text, autoescape=True)).limit(50).all()
    tasks = db.query(Task).join(Project).join(Workspace).filter(Workspace.user_email == user,
        or_(Task.title.contains(text, autoescape=True), Task.description.contains(text, autoescape=True))).limit(50).all()
    notes = db.query(Note).filter(Note.user_email == user, Note.deleted_at.is_(None),
        or_(Note.title.contains(text, autoescape=True), Note.content.contains(text, autoescape=True))).limit(50).all()
    return {"projects": [{"id": p.id, "workspace_id": p.workspace_id, "name": p.name, "archived": p.archived_at is not None} for p in projects],
            "tasks": [TaskOut.model_validate(t) for t in tasks], "notes": [NoteOut.model_validate(n) for n in notes]}

@router.get("/export")
def export(user: User, db: DB):
    # Export only user content, never session tokens, credentials, or other users' records.
    workspaces = db.query(Workspace).filter_by(user_email=user).all()
    projects = db.query(Project).join(Workspace).filter(Workspace.user_email == user).all()
    tasks = db.query(Task).join(Project).join(Workspace).filter(Workspace.user_email == user).all()
    links = db.query(ProjectLink).join(Project).join(Workspace).filter(Workspace.user_email == user).all()
    notes = db.query(Note).filter_by(user_email=user).all()
    return JSONResponse({"format_version": 1,
        "workspaces": [{"id": w.id, "name": w.name} for w in workspaces],
        "projects": [{"id": p.id, "workspace_id": p.workspace_id, "name": p.name, "kind": p.kind, "archived": p.archived_at is not None} for p in projects],
        "tasks": [TaskOut.model_validate(t).model_dump(mode="json") for t in tasks],
        "notes": [{**NoteOut.model_validate(n).model_dump(mode="json"), "deleted": n.deleted_at is not None} for n in notes],
        "links": [{"id": l.id, "project_id": l.project_id, "title": l.title, "url": l.url} for l in links]},
        headers={"Content-Disposition": 'attachment; filename="focusflow-content.json"', "Cache-Control": "no-store"})
