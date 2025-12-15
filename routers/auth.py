import os
import json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import redis
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest

# 允許 HTTP (Render 內部轉發通常是 HTTP)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Redis 連線
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
    socket_timeout=5
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

# ★★★ 關鍵：自動抓取 Render 的網址，如果沒有就用本機 ★★★
# 請在 Render 後台設定環境變數 RENDER_EXTERNAL_URL = https://您的專案名.onrender.com
APP_URL = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000")
REDIRECT_URI = f"{APP_URL}/api/auth/callback"

@router.get("/login")
async def login():
    if not os.path.exists(CREDENTIALS_FILE):
        return JSONResponse({"error": "找不到 credentials.json"}, 500)
    
    try:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, 
            scopes=SCOPES, 
            redirect_uri=REDIRECT_URI
        )
        
        url, state = flow.authorization_url(
            access_type='offline', 
            include_granted_scopes='true',
            prompt='consent'
        )
        print(f"👉 [Login] Redirect URI: {REDIRECT_URI}")
        return {"status": "redirect", "url": url}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@router.get("/callback")
async def auth_callback(request: Request):
    code = request.query_params.get('code')
    if not code: return JSONResponse({"error": "No code"}, 400)

    try:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, 
            scopes=SCOPES, 
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # ★★★ 改存 Redis：Render 重啟也不會登出 ★★★
        r.set("auth:google_token", creds.to_json())
        print(f"✅ 登入成功！Token 已存入 Redis")

        return RedirectResponse(url="/")
        
    except Exception as e:
        print(f"❌ 驗證失敗: {e}")
        return JSONResponse({"error": str(e)}, 500)

@router.get("/user")
async def get_user_info(request: Request):
    # 從 Redis 讀取 Token
    token_json = r.get("auth:google_token")
    if not token_json: return JSONResponse({"logged_in": False})
    
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info, SCOPES)
        
        # 自動刷新並存回 Redis
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            r.set("auth:google_token", creds.to_json())
        
        service = build('oauth2', 'v2', credentials=creds)
        info = service.userinfo().get().execute()
        
        return JSONResponse({
            "logged_in": True, 
            "info": {
                "name": info.get('name'),
                "email": info.get('email'),
                "picture": info.get('picture')
            }
        })
    except:
        return JSONResponse({"logged_in": False})

@router.get("/logout")
async def logout(request: Request):
    # 刪除 Redis 裡的 Token
    r.delete("auth:google_token")
    return {"status": "logged_out"}