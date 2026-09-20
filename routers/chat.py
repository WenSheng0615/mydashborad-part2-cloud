from fastapi import APIRouter, WebSocket, Request, Form, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
import os
import shutil
import redis.asyncio as redis
import json
import datetime
import uuid
import asyncio
import time
from sqlalchemy import or_, and_
from starlette.concurrency import run_in_threadpool
from services.upload_service import bounded_upload
from pydantic import BaseModel

from database import get_db, get_session_info, KeepItem
from services.firebase_service import upload_file as fb_upload_file

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Redis URL (優先從環境變數讀取，否則使用預設)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

# 嘗試初始化 Redis，若失敗則記錄錯誤但不崩潰
# ⚠️ Redis 這裡只當「即時同步的廣播管道」用，不再是資料的儲存位置——
# 真正的資料都在 SQLite 的 keep_items 表，Redis 沒接上也完全不影響 CRUD，只是少了跨裝置即時推播。
r = None
try:
    r = redis.from_url(
        redis_url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5
    )
    print("Redis client configured; connectivity checked on use")
except Exception as e:
    print(f"❌ Redis 連接失敗: {e}")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


def _require_user(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    return get_session_info(session_id)


def _classify_type(content: str) -> str:
    return "link" if content.startswith("http") else "text"


def _user_channel(user_email: str) -> str:
    return f"chat:channel:{user_email}"


def _serialize(item: KeepItem) -> dict:
    return {
        "id": item.id,
        "type": item.type,
        "content": item.content,
        "file_name": item.file_name,
        "file_size": item.file_size,
        "time": item.created_at.strftime("%Y-%m-%d %H:%M")
    }


async def _publish(user_email: str, payload: dict):
    if not r: return
    try:
        await asyncio.wait_for(r.publish(_user_channel(user_email), json.dumps(payload, ensure_ascii=False)), timeout=1)
    except Exception as e:
        print("Keep broadcast unavailable; data remains saved")


@router.get("/history")
def get_chat_history(request: Request, before: str | None = None, limit: int = Query(100, ge=1, le=300)):
    session = _require_user(request)
    if not session: return {"messages": [], "next_cursor": None}
    with get_db() as db:
        query = db.query(KeepItem).filter(KeepItem.user_email == session.user_email)
        if before:
            cursor = query.filter(KeepItem.id == before).first()
            if not cursor: raise HTTPException(404, "找不到分頁位置")
            query = query.filter(or_(KeepItem.created_at < cursor.created_at,
                and_(KeepItem.created_at == cursor.created_at, KeepItem.id < cursor.id)))
        items = query.order_by(KeepItem.created_at.desc(), KeepItem.id.desc()).limit(limit + 1).all()
        page = items[:limit]
        return {"messages": [_serialize(i) for i in reversed(page)],
                "next_cursor": page[-1].id if len(items) > limit else None}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = websocket.cookies.get("session_id")
    session = get_session_info(session_id) if session_id else None
    if not session:
        await websocket.close(code=4401)
        return

    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if origin and origin not in (f"http://{host}", f"https://{host}"):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    if not r:
        await websocket.send_text(json.dumps({"type": "system", "data": {"content": "即時同步暫時無法使用 (Redis 未連接)"}}, ensure_ascii=False))
        return

    channel = _user_channel(session.user_email)
    pubsub = r.pubsub()
    try:
        await pubsub.subscribe(channel)
        last_check = 0
        while True:
            if time.monotonic() - last_check >= 30:
                current = await run_in_threadpool(get_session_info, session_id)
                if not current or current.user_email != session.user_email:
                    await websocket.close(code=4401)
                    break
                last_check = time.monotonic()
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_text(message['data'])
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Chat WS Error: {e}")
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except: pass


@router.post("/send")
async def send_message(request: Request, content: str | None = Form(None),
                       legacy_content: str | None = Query(None, alias="content", max_length=10000)):
    session = _require_user(request)
    if not session: raise HTTPException(401, "請先登入")
    content = content if content is not None else legacy_content
    if not content or not content.strip() or len(content) > 10000:
        raise HTTPException(422, "內容需 1–10000 字")
    with get_db() as db:
        item = KeepItem(id=str(uuid.uuid4()), user_email=session.user_email,
                        type=_classify_type(content), content=content, created_at=datetime.datetime.utcnow())
        db.add(item); db.commit(); data = _serialize(item)
    await _publish(session.user_email, {"type": "new_message", "data": data})
    return {"status": "sent", "message": data}

@router.post("/upload")
async def upload_chat_file(request: Request, file: UploadFile = File(...)):
    session = _require_user(request)
    if not session: raise HTTPException(401, "請先登入")
    is_image = (file.content_type or "").startswith("image/")
    async with bounded_upload(file, image_only=is_image) as (path, size, name, suffix):
        try:
            url = await run_in_threadpool(fb_upload_file, str(path), f"keep/{session.user_email}/{uuid.uuid4()}{suffix}")
        except Exception:
            raise HTTPException(503, "檔案上傳失敗，請稍後再試")
    with get_db() as db:
        item = KeepItem(id=str(uuid.uuid4()), user_email=session.user_email, type="image" if is_image else "file",
                        content=url, file_name=name, file_size=size, created_at=datetime.datetime.utcnow())
        db.add(item); db.commit(); data = _serialize(item)
    await _publish(session.user_email, {"type": "new_message", "data": data})
    return {"status": "sent", "url": url, "message": data}


@router.post("/delete")
async def delete_message(request: Request, msg_id: str = Form(...)):
    session = _require_user(request)
    if not session: return JSONResponse({"status": "unauthorized"}, 401)

    db = get_db()
    item = db.query(KeepItem).filter(KeepItem.id == msg_id, KeepItem.user_email == session.user_email).first()
    if not item:
        db.close()
        return JSONResponse({"status": "not_found"}, 404)
    db.delete(item)
    db.commit()
    db.close()

    await _publish(session.user_email, {"type": "delete", "data": {"id": msg_id}})
    return {"status": "success"}


@router.post("/edit")
async def edit_message(request: Request, msg_id: str = Form(...), new_content: str = Form(...)):
    session = _require_user(request)
    if not session: return JSONResponse({"status": "unauthorized"}, 401)

    db = get_db()
    item = db.query(KeepItem).filter(KeepItem.id == msg_id, KeepItem.user_email == session.user_email).first()
    if not item:
        db.close()
        return JSONResponse({"status": "not_found"}, 404)
    if item.type not in ("text", "link"):
        db.close()
        return JSONResponse({"status": "invalid", "detail": "圖片/檔案訊息無法編輯內容"}, 400)

    if not new_content.strip() or len(new_content) > 10000:
        db.close()
        raise HTTPException(422, "內容需 1–10000 字")
    item.content = new_content
    item.type = _classify_type(new_content)
    db.commit()
    data = _serialize(item)
    db.close()

    await _publish(session.user_email, {"type": "edit", "data": data})
    return {"status": "success"}


@router.post("/clear")
async def clear_chat(request: Request):
    session = _require_user(request)
    if not session: return JSONResponse({"status": "unauthorized"}, 401)

    db = get_db()
    db.query(KeepItem).filter(KeepItem.user_email == session.user_email).delete()
    db.commit()
    db.close()

    await _publish(session.user_email, {"type": "clear", "data": {}})
    return {"status": "success"}
