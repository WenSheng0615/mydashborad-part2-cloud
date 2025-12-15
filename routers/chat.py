from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import json
import datetime
import uuid

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Redis URL (雲端資料庫)
redis_url = "redis://:peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT@redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com:11812"

# ★★★ 修改：增加連線超時時間，避免網路稍微卡頓就報錯 ★★★
r = redis.from_url(
    redis_url, 
    decode_responses=True,
    socket_timeout=10, 
    socket_connect_timeout=10
)

HISTORY_KEY = "chat:history"
CHANNEL_KEY = "chat:channel"

@router.get("/history")
async def get_chat_history():
    try:
        # 讀取最近 50 則
        logs = await r.lrange(HISTORY_KEY, 0, 49)
        return JSONResponse({"messages": [json.loads(x) for x in logs][::-1]})
    except Exception as e:
        print(f"Chat History Error: {e}")
        return JSONResponse({"messages": []})

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = r.pubsub()
    
    try:
        # 訂閱頻道
        await pubsub.subscribe(CHANNEL_KEY)
        
        while True:
            # 等待 Redis 廣播 (非阻塞)
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            
            if message:
                await websocket.send_text(message['data'])
            
            # 保持連線活躍，避免被切斷
            # 這裡可以加入簡單的 ping/pong 機制，目前先保持簡單
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        print("Chat client disconnected")
    except Exception as e:
        print(f"Chat WS Error: {e}")
    finally:
        # 確保斷線時取消訂閱，釋放資源
        try:
            await pubsub.unsubscribe(CHANNEL_KEY)
            await pubsub.close()
        except: pass

@router.post("/send")
async def send_message(content: str):
    msg_data = {
        "id": str(uuid.uuid4()),
        "content": content,
        "time": datetime.datetime.now().strftime("%H:%M"),
        "type": "text"
    }
    
    if content.startswith("http"):
        msg_data["type"] = "link"

    msg_json = json.dumps(msg_data)

    try:
        await r.lpush(HISTORY_KEY, msg_json)
        await r.ltrim(HISTORY_KEY, 0, 99)
        await r.publish(CHANNEL_KEY, msg_json)
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
        
import asyncio