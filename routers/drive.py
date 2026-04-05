import os
import json
import io
from fastapi import APIRouter, Form, UploadFile, File, Request
from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ✅ 改用 SQLite
from database import get_session_info, save_session

router = APIRouter(prefix="/api/drive", tags=["drive"])

def get_drive_service(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return None
    
    # ✅ 從 SQLite 讀取
    session = get_session_info(session_id)
    if not session: return None
    token_json = session.token_json
    
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            # ✅ 更新 SQLite 中的 Token
            save_session(session_id, creds.to_json(), session.user_email)
            
        return build('drive', 'v3', credentials=creds)
    except: return None

@router.get("/files")
async def get_drive_files(request: Request, folder_id: str = 'root', query: str = None, file_type: str = None):
    try:
        service = get_drive_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        filters = ["trashed = false"]
        if query: filters.append(f"name contains '{query}'")
        else: filters.append(f"'{folder_id}' in parents")
        if file_type == 'folder': filters.append("mimeType = 'application/vnd.google-apps.folder'")
        elif file_type == 'image': filters.append("mimeType contains 'image/'")
        elif file_type == 'pdf': filters.append("mimeType = 'application/pdf'")
        
        results = service.files().list(
            q=" and ".join(filters), 
            pageSize=50, 
            fields="files(id, name, mimeType, webViewLink, iconLink, thumbnailLink, modifiedTime)", 
            orderBy="folder, modifiedTime desc"
        ).execute()
        
        files = results.get('files', [])
        return JSONResponse(content={"source": "google", "files": files})
    except Exception as e: return JSONResponse(content={"error": str(e)}, status_code=500)

@router.get("/storage")
async def get_storage_info(request: Request):
    try:
        service = get_drive_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        about = service.about().get(fields="storageQuota").execute()
        quota = about.get('storageQuota', {})
        return JSONResponse({
            "total": int(quota.get('limit', 0)), 
            "used": int(quota.get('usage', 0)), 
            "trash": int(quota.get('usageInDriveTrash', 0))
        })
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), folder_id: str = Form('root')):
    try:
        service = get_drive_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        metadata = {'name': file.filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(await file.read()), mimetype=file.content_type, resumable=True)
        service.files().create(body=metadata, media_body=media).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/delete")
async def delete_file(request: Request, file_id: str = Form(...)):
    try:
        service = get_drive_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        service.files().delete(fileId=file_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/move")
async def move_file(request: Request, file_id: str = Form(...), folder_id: str = Form(...)):
    try:
        service = get_drive_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        # 取得檔案目前的 parents
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # 移動檔案
        service.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)
