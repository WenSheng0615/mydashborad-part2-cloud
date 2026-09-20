from fastapi import APIRouter, Form, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.http import MediaFileUpload

from services.google_auth_service import build_google_service, auth_error_body

from services.upload_service import bounded_upload
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/drive", tags=["drive"])


def _drive_service(request: Request):
    service, result = build_google_service(request, 'drive', 'v3')
    if not service:
        body, status = auth_error_body(result)
        return None, JSONResponse(body, status)
    return service, None


@router.get("/files")
async def get_drive_files(request: Request, folder_id: str = 'root', query: str = None, file_type: str = None):
    service, err = _drive_service(request)
    if err: return err
    try:
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
    except Exception as e: return JSONResponse(content={"error": "外部服務暫時無法完成操作，請稍後重試"}, status_code=500)

@router.get("/storage")
async def get_storage_info(request: Request):
    service, err = _drive_service(request)
    if err: return err
    try:
        about = service.about().get(fields="storageQuota").execute()
        quota = about.get('storageQuota', {})
        return JSONResponse({
            "total": int(quota.get('limit', 0)),
            "used": int(quota.get('usage', 0)),
            "trash": int(quota.get('usageInDriveTrash', 0))
        })
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), folder_id: str = Form('root')):
    service, err = _drive_service(request)
    if err: return err
    try:
        async with bounded_upload(file) as (path, size, name, suffix):
            def send():
                media = MediaFileUpload(str(path), mimetype=file.content_type or "application/octet-stream", resumable=True)
                try:
                    service.files().create(body={'name': name, 'parents': [folder_id]}, media_body=media).execute()
                finally:
                    media.stream().close()
            await run_in_threadpool(send)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception:
        return JSONResponse({"error": "Google Drive 上傳失敗，請稍後再試"}, 502)

@router.post("/delete")
async def delete_file(request: Request, file_id: str = Form(...)):
    service, err = _drive_service(request)
    if err: return err
    try:
        service.files().update(fileId=file_id, body={'trashed': True}).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.post("/move")
async def move_file(request: Request, file_id: str = Form(...), folder_id: str = Form(...)):
    service, err = _drive_service(request)
    if err: return err
    try:
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
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)
