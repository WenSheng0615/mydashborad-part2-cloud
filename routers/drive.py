import os
import json
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import JSONResponse
import redis
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

router = APIRouter(prefix="/api/drive", tags=["drive"])

# Redis
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
    socket_timeout=5
)

def get_drive_service():
    # 改從 Redis 讀 Token
    token_json = r.get("auth:google_token")
    if not token_json: return None
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                r.set("auth:google_token", creds.to_json())
            except:
                return None 
        return build('drive', 'v3', credentials=creds)
    except: return None

@router.get("/files")
async def get_drive_files(folder_id: str = 'root', query: str = None, file_type: str = None):
    cache_key = f"drive:files:{folder_id}:{query}:{file_type}"
    
    try:
        if r.exists(cache_key):
            return JSONResponse(content={"source": "redis", "files": json.loads(r.get(cache_key))})
    except: pass

    try:
        service = get_drive_service()
        if not service: 
            return JSONResponse({"error": "Login Required"}, 401)
        
        filters = ["trashed = false"]
        if query: filters.append(f"name contains '{query}'")
        else: filters.append(f"'{folder_id}' in parents")

        if file_type == 'folder': filters.append("mimeType = 'application/vnd.google-apps.folder'")
        elif file_type == 'image': filters.append("mimeType contains 'image/'")
        elif file_type == 'pdf': filters.append("mimeType = 'application/pdf'")
        
        results = service.files().list(
            q=" and ".join(filters), pageSize=50,
            fields="files(id, name, mimeType, webViewLink, iconLink, thumbnailLink, modifiedTime)",
            orderBy="folder, modifiedTime desc"
        ).execute()
        files = results.get('files', [])
        
        try: r.set(cache_key, json.dumps(files), ex=300)
        except: pass
        
        return JSONResponse(content={"source": "google", "files": files})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.get("/storage")
async def get_storage_info():
    try:
        service = get_drive_service()
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        about = service.about().get(fields="storageQuota").execute()
        quota = about.get('storageQuota', {})
        
        return JSONResponse({
            "total": int(quota.get('limit', 0)),
            "used": int(quota.get('usage', 0)),
            "trash": int(quota.get('usageInDriveTrash', 0))
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), folder_id: str = Form('root')):
    try:
        service = get_drive_service()
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        metadata = {'name': file.filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(file.file, mimetype=file.content_type, resumable=True)
        service.files().create(body=metadata, media_body=media).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/delete")
async def delete_file(file_id: str = Form(...), folder_id: str = Form('root')):
    try:
        service = get_drive_service()
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        service.files().delete(fileId=file_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)