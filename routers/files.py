from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from routers.workspaces import User, DB
from models import Note, KeepItem
from services.firebase_service import file_reference, signed_download

router = APIRouter(prefix="/api/files", tags=["files"])

@router.get("/download")
def download(user: User, db: DB, object: str = Query(..., min_length=1, max_length=1000)):
    reference = file_reference(object)
    note = db.query(Note).filter_by(user_email=user, image_url=reference, deleted_at=None).first()
    keep = db.query(KeepItem).filter_by(user_email=user, content=reference).first()
    if not note and not keep:
        raise HTTPException(404, "找不到檔案")
    try:
        url = signed_download(object)
    except Exception:
        raise HTTPException(503, "暫時無法取得檔案，請稍後再試")
    return RedirectResponse(url, status_code=307, headers={"Cache-Control": "no-store"})
