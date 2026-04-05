import os
import json
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv
from routers import drive, music, auth, calendar, notes, tasks, money, chat
from database import get_db, Note, get_session_info
from services.firebase_service import init_firebase

# 載入環境變數
load_dotenv()

app = FastAPI()

# 初始化 Firebase
init_firebase()

# --- 部署專用：從環境變數還原憑證 ---
def restore_credentials_from_env():
    # Google API 憑證
    token_content = os.getenv("GOOGLE_TOKEN")
    if token_content:
        with open("token.json", "w") as f: f.write(token_content)
    
    creds_content = os.getenv("GOOGLE_CREDENTIALS")
    if creds_content:
        with open("credentials.json", "w") as f: f.write(creds_content)

    # Firebase 憑證
    fb_content = os.getenv("FIREBASE_KEY_CONTENT")
    fb_path = os.getenv("FIREBASE_KEY_FILE", "firebase_key.json")
    if fb_content:
        with open(fb_path, "w") as f: f.write(fb_content)
        # 確保環境變數指向正確的路徑供 firebase_service 使用
        os.environ["FIREBASE_KEY_FILE"] = fb_path

restore_credentials_from_env()

# --- 路徑與掛載 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")
templates_path = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=static_path), name="static")

# --- 註冊路由 ---
app.include_router(drive.router)
app.include_router(music.router)
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(notes.router)
app.include_router(tasks.router)
app.include_router(money.router)
app.include_router(chat.router)

templates = Jinja2Templates(directory=templates_path)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    session_id = request.cookies.get("session_id")
    notes = []
    
    if session_id:
        session = get_session_info(session_id)
        if session:
            db = get_db()
            notes_db = db.query(Note).filter(Note.user_email == session.user_email).order_by(Note.created_at.desc()).all()
            for n in notes_db:
                notes.append({
                    "id": n.id, 
                    "title": n.title, 
                    "description": n.content, 
                    "color": n.color,
                    "image_url": n.image_url,
                    "created_at": n.created_at
                })
            db.close()
            
    return templates.TemplateResponse("index.html", {"request": request, "notes": notes})

if __name__ == "__main__":
    print("🚀 FocusFlow OS 啟動中...")
    print("請開啟瀏覽器訪問: http://127.0.0.1:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

