import os
import json
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import redis
import uvicorn
from routers import drive, music, auth, calendar, notes, tasks, money, chat

app = FastAPI()

# ★★★ 新增：部署專用 - 從環境變數還原憑證檔案 ★★★
def restore_credentials_from_env():
    # 1. 還原 token.json
    token_content = os.getenv("GOOGLE_TOKEN")
    if token_content:
        print("正在從環境變數還原 token.json...")
        with open("token.json", "w") as f:
            f.write(token_content)
    
    # 2. 還原 credentials.json
    creds_content = os.getenv("GOOGLE_CREDENTIALS")
    if creds_content:
        print("正在從環境變數還原 credentials.json...")
        with open("credentials.json", "w") as f:
            f.write(creds_content)

# 在程式啟動前執行還原
restore_credentials_from_env()

# 路徑設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")
templates_path = os.path.join(BASE_DIR, "templates")

# 掛載
app.mount("/static", StaticFiles(directory=static_path), name="static")
app.include_router(drive.router)
app.include_router(music.router)
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(notes.router)
app.include_router(tasks.router)
app.include_router(money.router)
app.include_router(chat.router)

# Redis
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
    socket_timeout=5
)

templates = Jinja2Templates(directory=templates_path)

@app.post("/add")
async def add_note(request: Request, note: str = Form(...)):
    if note.strip():
        try: r.lpush("my_notes", note); r.ltrim("my_notes", 0, 49)
        except: pass
    return await read_root(request)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try: notes = r.lrange("my_notes", 0, -1)
    except: notes = ["資料庫連線中..."]
    return templates.TemplateResponse("index.html", {"request": request, "notes": notes})

if __name__ == "__main__":
    # ... (前面的 ffmpeg 檢查保持不變) ...

    print("🚀 伺服器啟動中...")
    print("請在手機輸入電腦的 IP，例如: http://192.168.1.XX:8000")
    
    # ★★★ 關鍵修改：改成 0.0.0.0 ★★★
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)