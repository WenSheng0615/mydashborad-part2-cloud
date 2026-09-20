import os
import config  # Load environment before routers read configuration.
import json
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from dotenv import load_dotenv
from routers import drive, music, auth, calendar, notes, tasks, money, chat, quiz, workspaces, project_content, files, overview
from database import get_db, Note, get_session_info
from services.firebase_service import init_firebase

# 載入環境變數
load_dotenv()

# --- 部署專用：從環境變數還原憑證 ---
def restore_credentials_from_env():
    from services.credential_service import restore_json_environment
    # Resolve paths relative to the application, independent of the launch directory.
    restore_json_environment("GOOGLE_TOKEN", config.BASE_DIR / "token.json")
    restore_json_environment("GOOGLE_CREDENTIALS", auth.CREDENTIALS_FILE, oauth=True)
    fb_path = os.getenv("FIREBASE_KEY_FILE") or "firebase_key.json"
    if not os.path.isabs(fb_path):
        fb_path = str(config.BASE_DIR / fb_path)
    if restore_json_environment("FIREBASE_KEY_CONTENT", fb_path):
        os.environ["FIREBASE_KEY_FILE"] = fb_path

restore_credentials_from_env()

from services.logging_service import configure_access_log
configure_access_log()
app = FastAPI()
from routers.health import router as health_router
app.include_router(health_router)

# Reject cross-site browser writes and keep personal responses out of shared caches.
@app.middleware("http")
async def browser_boundaries(request: Request, call_next):
    from fastapi.responses import JSONResponse
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = str(request.base_url).rstrip("/")
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != allowed):
            return JSONResponse({"detail": "不接受跨網站操作"}, status_code=403)
    response = await call_next(request)
    if not request.url.path.startswith("/static/") and request.url.path != "/service-worker.js":
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

# 初始化 Firebase (現在金鑰檔案已經還原了)
init_firebase()

# --- 路徑與掛載 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")
templates_path = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/service-worker.js", include_in_schema=False)
def legacy_service_worker():
    return FileResponse(os.path.join(static_path, "sw.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


# --- 註冊路由 ---
app.include_router(drive.router)
app.include_router(music.router)
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(notes.router)
app.include_router(tasks.router)
app.include_router(money.router)
app.include_router(chat.router)
app.include_router(quiz.router)
app.include_router(workspaces.router)
app.include_router(project_content.router)
app.include_router(files.router)
app.include_router(overview.router)

templates = Jinja2Templates(directory=templates_path)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    session_id = request.cookies.get("session_id")
    notes = []
    
    if session_id:
        session = get_session_info(session_id)
        if session:
            db = get_db()
            notes_db = db.query(Note).filter(Note.user_email == session.user_email, Note.deleted_at.is_(None)).order_by(Note.created_at.desc()).all()
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
            
    return templates.TemplateResponse(request=request, name="index.html", context={"notes": notes})

@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    return templates.TemplateResponse(request=request, name="projects.html")


if __name__ == "__main__":
    from check_database import check_database
    check_database()
    print("🚀 FocusFlow OS 啟動中...")
    print(f"請開啟瀏覽器訪問: {auth.APP_URL}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
