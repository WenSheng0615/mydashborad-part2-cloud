import os
import json
import time
import uuid
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest

# 引入 SQLite 工具
from database import save_session, delete_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

APP_URL = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000")
REDIRECT_URI = f"{APP_URL}/api/auth/callback"

@router.get("/login")
async def login(response: Response):
    if not os.path.exists(CREDENTIALS_FILE):
        return JSONResponse({"error": f"找不到 {CREDENTIALS_FILE}"}, 500)
    
    try:
        flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
        
        res = JSONResponse({"status": "redirect", "url": url})
        res.set_cookie(key="code_verifier", value=flow.code_verifier, httponly=True, max_age=600, samesite="lax")
        return res
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@router.get("/callback")
async def auth_callback(request: Request):
    code = request.query_params.get('code')
    code_verifier = request.cookies.get("code_verifier")
    if not code: return JSONResponse({"error": "No code"}, 400)

    try:
        flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        flow.fetch_token(code=code, code_verifier=code_verifier)
        creds = flow.credentials
        
        # ✅ 同時獲取使用者 Email
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info.get('email', 'guest')

        session_id = str(uuid.uuid4())
        save_session(session_id, creds.to_json(), user_email)
        
        res = RedirectResponse(url="/")
        res.set_cookie(key="session_id", value=session_id, httponly=True, max_age=604800, samesite="lax")
        res.delete_cookie("code_verifier")
        return res
        
    except Exception as e:
        return JSONResponse({"error": f"驗證失敗: {str(e)}"}, 500)

@router.get("/guest")
async def guest_login():
    session_id = str(uuid.uuid4())
    # 訪客使用空的 token_json，但有固定的 email 標記
    save_session(session_id, "{}", "guest@focusflow.local")

    res = RedirectResponse(url="/")
    res.set_cookie(key="session_id", value=session_id, httponly=True, max_age=86400, samesite="lax")
    return res

@router.get("/user")
async def get_user_info(request: Request):
    from database import get_session_info
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"logged_in": False})

    session = get_session_info(session_id)
    if not session: return JSONResponse({"logged_in": False})

    # ✅ 處理訪客模式
    if session.user_email == "guest@focusflow.local":
        return JSONResponse({
            "logged_in": True,
            "is_guest": True,
            "info": {
                "name": "訪客使用者",
                "email": "Guest Mode",
                "picture": "https://cdn-icons-png.flaticon.com/512/1144/1144760.png"
            }
        })

    try:
        info = json.loads(session.token_json)
        creds = Credentials.from_authorized_user_info(info, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            save_session(session_id, creds.to_json(), session.user_email)

        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()

        return JSONResponse({
            "logged_in": True, 
            "is_guest": False,
            "info": {"name": user_info.get('name'), "email": user_info.get('email'), "picture": user_info.get('picture')}
        })
    except:
        return JSONResponse({"logged_in": False})

@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(session_id)
    res = RedirectResponse(url="/")
    res.delete_cookie("session_id")
    return res
