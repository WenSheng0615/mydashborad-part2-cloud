from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import redis
import json
import uuid
import datetime

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
# 請確保使用您的雲端 Redis 設定
r = redis.Redis(host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812, decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
    socket_timeout=5
)

KEYS = {"todo": "tasks:todo", "doing": "tasks:doing", "done": "tasks:done"}

@router.get("/")
async def get_tasks():
    try:
        data = {
            "todo": [json.loads(x) for x in r.lrange(KEYS["todo"], 0, -1)],
            "doing": [json.loads(x) for x in r.lrange(KEYS["doing"], 0, -1)],
            "done": [json.loads(x) for x in r.lrange(KEYS["done"], 0, -1)]
        }
        return JSONResponse(data)
    except: return JSONResponse({"todo": [], "doing": [], "done": []})

@router.post("/add")
async def add_task(content: str = Form(...), due_date: str = Form("")):
    task = {
        "id": str(uuid.uuid4()),
        "content": content,
        "due_date": due_date, # 新增截止時間
        "created_at": datetime.datetime.now().strftime("%m/%d %H:%M")
    }
    r.rpush(KEYS["todo"], json.dumps(task))
    return {"status": "success"}

@router.post("/move")
async def move_task(task_id: str = Form(...), from_stage: str = Form(...), to_stage: str = Form(...)):
    if from_stage not in KEYS or to_stage not in KEYS: return {"error": "Invalid stage"}
    
    items = r.lrange(KEYS[from_stage], 0, -1)
    target = None
    for item in items:
        if json.loads(item)['id'] == task_id:
            target = item
            break
    
    if target:
        r.lrem(KEYS[from_stage], 1, target)
        r.rpush(KEYS[to_stage], target)
        return {"status": "success"}
    return {"error": "Task not found"}

@router.post("/update")
async def update_task(task_id: str = Form(...), content: str = Form(...), stage: str = Form(...), due_date: str = Form("")):
    if stage not in KEYS: return {"error": "Invalid stage"}
    
    items = r.lrange(KEYS[stage], 0, -1)
    for i, item in enumerate(items):
        task = json.loads(item)
        if task['id'] == task_id:
            task['content'] = content
            task['due_date'] = due_date # 更新時間
            r.lset(KEYS[stage], i, json.dumps(task))
            return {"status": "success"}
            
    return {"error": "Task not found"}

@router.post("/delete")
async def delete_task(task_id: str = Form(...), stage: str = Form(...)):
    items = r.lrange(KEYS[stage], 0, -1)
    for item in items:
        if json.loads(item)['id'] == task_id:
            r.lrem(KEYS[stage], 1, item)
            break
    return {"status": "success"}