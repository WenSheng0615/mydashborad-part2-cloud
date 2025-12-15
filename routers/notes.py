from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import redis
import json
import uuid
import datetime

router = APIRouter(prefix="/api/notes", tags=["notes"])
# 請確認這裡的 Redis 連線資訊是正確的
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
)

@router.get("/")
async def get_notes():
    try:
        raw_notes = r.lrange("user:notes", 0, -1)
        notes = [json.loads(n) for n in raw_notes]
        return JSONResponse({"notes": notes})
    except: return JSONResponse({"notes": []})

@router.post("/add")
async def add_note(title: str = Form(...), description: str = Form(""), color: str = Form("yellow")):
    note_data = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description, # 新增描述
        "color": color,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    r.lpush("user:notes", json.dumps(note_data))
    return {"status": "success"}

@router.post("/delete")
async def delete_note(note_id: str = Form(...)):
    all_notes = r.lrange("user:notes", 0, -1)
    for raw in all_notes:
        note = json.loads(raw)
        if note['id'] == note_id:
            r.lrem("user:notes", 1, raw)
            break
    return {"status": "success"}