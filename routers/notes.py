import uuid
from datetime import datetime
from typing import Annotated, Literal
from fastapi import APIRouter, Form, Request, File, UploadFile, HTTPException
from starlette.concurrency import run_in_threadpool
from database import get_db, Note, get_session_info
from services.firebase_service import upload_file
from services.upload_service import bounded_upload

router = APIRouter(prefix="/api/notes", tags=["notes"])
COLORS = {"yellow", "blue", "green", "pink"}

def owner(request):
    sid = request.cookies.get("session_id")
    session = get_session_info(sid) if sid else None
    if not session or not session.user_email:
        raise HTTPException(401, "請先登入")
    return session.user_email

def serialize(note):
    return {"id": note.id, "title": note.title, "description": note.content,
            "color": note.color, "image_url": note.image_url, "created_at": note.created_at,
            "project_id": note.project_id}

def validate(title, description, color):
    if not title.strip() or len(title) > 200 or len(description) > 100000 or color not in COLORS:
        raise HTTPException(422, "標題需 1–200 字，內容最多 100000 字，請使用提供的配色")

@router.get("/")
def get_notes(request: Request):
    try:
        user = owner(request)
    except HTTPException:
        return {"notes": []}
    with get_db() as db:
        notes = db.query(Note).filter(Note.user_email == user, Note.deleted_at.is_(None)).order_by(Note.created_at.desc(), Note.id).all()
        return {"notes": [serialize(note) for note in notes]}

@router.post("/add")
async def add_note(request: Request, title: str = Form(...), description: str = Form(""),
                   color: str = Form("yellow"), image: UploadFile = File(None)):
    user = owner(request)
    validate(title, description, color)
    image_url = None
    if image and image.filename:
        async with bounded_upload(image, image_only=True) as (path, size, name, suffix):
            try:
                image_url = await run_in_threadpool(upload_file, str(path), f"notes/{user}/{uuid.uuid4()}{suffix}")
            except Exception:
                raise HTTPException(503, "圖片上傳失敗，請保留內容稍後重試")
    with get_db() as db:
        note = Note(id=str(uuid.uuid4()), user_email=user, title=title.strip(), content=description,
                    color=color, image_url=image_url, created_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
        db.add(note)
        db.commit()
        return {"status": "success", "image_url": image_url, "id": note.id}

@router.post("/edit")
def edit_note(request: Request, note_id: str = Form(...), title: str = Form(...),
              description: str = Form(""), color: str = Form("yellow")):
    user = owner(request)
    validate(title, description, color)
    with get_db() as db:
        note = db.query(Note).filter_by(id=note_id, user_email=user, deleted_at=None).first()
        if not note:
            raise HTTPException(404, "找不到筆記")
        note.title, note.content, note.color = title.strip(), description, color
        db.commit()
        return {"status": "success"}

@router.post("/delete")
def delete_note(request: Request, note_id: str = Form(...)):
    user = owner(request)
    with get_db() as db:
        note = db.query(Note).filter_by(id=note_id, user_email=user, deleted_at=None).first()
        if not note:
            raise HTTPException(404, "找不到筆記")
        note.deleted_at = datetime.utcnow()
        db.commit()
    return {"status": "success"}


@router.get("/trash")
def trashed_notes(request: Request):
    user = owner(request)
    with get_db() as db:
        notes = db.query(Note).filter(Note.user_email == user, Note.deleted_at.isnot(None)).order_by(Note.deleted_at.desc()).all()
        return {"notes": [serialize(note) for note in notes]}

@router.post("/restore")
def restore_note(request: Request, note_id: str = Form(...)):
    user = owner(request)
    with get_db() as db:
        note = db.query(Note).filter_by(id=note_id, user_email=user).first()
        if not note: raise HTTPException(404, "找不到筆記")
        note.deleted_at = None
        db.commit()
    return {"status": "success"}
