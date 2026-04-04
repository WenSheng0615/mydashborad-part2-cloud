import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from database import get_db, Note, get_session_info

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.get("/")
async def get_notes(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"notes": []})
    
    session = get_session_info(session_id)
    if not session: return JSONResponse({"notes": []})
    
    db = get_db()
    notes = db.query(Note).filter(Note.user_email == session.user_email).order_by(Note.created_at.desc()).all()
    
    result = []
    for n in notes:
        result.append({
            "id": n.id, "title": n.title, "description": n.content, 
            "color": n.color, "created_at": n.created_at
        })
    db.close()
    return JSONResponse({"notes": result})

@router.post("/add")
async def add_note(request: Request, title: str = Form(...), description: str = Form(""), color: str = Form("yellow")):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"status": "unauthorized"}, 401)
    
    session = get_session_info(session_id)
    if not session: return JSONResponse({"status": "unauthorized"}, 401)
    
    db = get_db()
    new_note = Note(
        id=str(uuid.uuid4()),
        user_email=session.user_email,
        title=title,
        content=description,
        color=color,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(new_note)
    db.commit()
    db.close()
    return {"status": "success"}

@router.post("/delete")
async def delete_note(request: Request, note_id: str = Form(...)):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"status": "unauthorized"}, 401)
    
    db = get_db()
    note = db.query(Note).filter(Note.id == note_id).first()
    if note:
        db.delete(note)
        db.commit()
    db.close()
    return {"status": "success"}
