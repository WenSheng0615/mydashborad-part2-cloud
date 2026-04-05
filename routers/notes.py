import os
import uuid
import shutil
from datetime import datetime
from fastapi import APIRouter, Form, Request, File, UploadFile
from fastapi.responses import JSONResponse
from database import get_db, Note, get_session_info
from services.firebase_service import upload_file

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
            "color": n.color, "image_url": n.image_url, "created_at": n.created_at
        })
    db.close()
    return JSONResponse({"notes": result})

@router.post("/add")
async def add_note(
    request: Request, 
    title: str = Form(...), 
    description: str = Form(""), 
    color: str = Form("yellow"),
    image: UploadFile = File(None)
):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"status": "unauthorized"}, 401)
    
    session = get_session_info(session_id)
    if not session: return JSONResponse({"status": "unauthorized"}, 401)
    
    image_url = None
    if image and image.filename:
        # 暫存檔案以便上傳
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{image.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        try:
            # 上傳到 Firebase
            destination_name = f"notes/{session.user_email}/{os.path.basename(temp_path)}"
            image_url = upload_file(temp_path, destination_name)
        finally:
            # 刪除暫存檔
            if os.path.exists(temp_path):
                os.remove(temp_path)

    db = get_db()
    new_note = Note(
        id=str(uuid.uuid4()),
        user_email=session.user_email,
        title=title,
        content=description,
        color=color,
        image_url=image_url,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(new_note)
    db.commit()
    db.close()
    return {"status": "success", "image_url": image_url}

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
