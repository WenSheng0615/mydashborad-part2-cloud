from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import os
import redis.asyncio as redis
import json
import datetime
import uuid
import asyncio

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Redis URL (優先從環境變數讀取，否則使用預設)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

# 嘗試初始化 Redis，若失敗則記錄錯誤但不崩潰
r = None
try:
    r = redis.from_url(
        redis_url, 
        decode_responses=True,
        socket_timeout=5, 
        socket_connect_timeout=5
    )
    print(f"📡 Redis 已連接: {redis_url}")
except Exception as e:
    print(f"❌ Redis 連接失敗: {e}")

HISTORY_KEY = "chat:history"
CHANNEL_KEY = "chat:channel"

@router.get("/history")
async def get_chat_history():
    if not r: return JSONResponse({"messages": []})
    try:
        logs = await r.lrange(HISTORY_KEY, 0, 49)
        return JSONResponse({"messages": [json.loads(x) for x in logs][::-1]})
    except Exception as e:
        print(f"Chat History Error: {e}")
        return JSONResponse({"messages": []})

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if not r:
        await websocket.send_text(json.dumps({"content": "聊天功能暫時無法使用 (Redis 未連接)", "type": "system"}))
        return

    pubsub = r.pubsub()
    try:
        await pubsub.subscribe(CHANNEL_KEY)
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_text(message['data'])
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Chat WS Error: {e}")
    finally:
        try:
            await pubsub.unsubscribe(CHANNEL_KEY)
            await pubsub.close()
        except: pass

@router.post("/send")
async def send_message(content: str):
    if not r: return {"status": "error", "detail": "Redis not connected"}
    
    msg_data = {
        "id": str(uuid.uuid4()),
        "content": content,
        "time": datetime.datetime.now().strftime("%H:%M"),
        "type": "text"
    }
    if content.startswith("http"): msg_data["type"] = "link"
    msg_json = json.dumps(msg_data)

    try:
        await r.lpush(HISTORY_KEY, msg_json)
        await r.ltrim(HISTORY_KEY, 0, 99)
        await r.publish(CHANNEL_KEY, msg_json)
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
        
import asyncio