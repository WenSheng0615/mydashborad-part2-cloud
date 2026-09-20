import os
import time
import uuid
import socket
import secrets
import logging
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# 引入 SQLite 工具
from database import save_session, delete_session, get_session_info, merge_guest_data
from services.google_auth_service import get_valid_credentials

logger = logging.getLogger(__name__)

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

APP_URL = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
# 優先使用手動指定的 REDIRECT_URI，否則自動生成
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", f"{APP_URL}/api/auth/callback")

# 只有正式部署（Render，走 HTTPS）才加 secure flag；本機開發是 http://127.0.0.1，加了 cookie 會送不出去
from config import COOKIE_SECURE
IS_DEPLOYED = COOKIE_SECURE

# 「掃碼把手機接上同一個帳號」用的一次性 token。
# ⚠️ 純記憶體儲存：單一 process 內有效即可（5 分鐘過期 + 用過即刪），
# 符合目前 Dockerfile 單一 uvicorn process 的部署方式，重啟就重新產生一次沒關係。
_device_link_tokens = {}
DEVICE_LINK_TTL = 300  # 秒
# One worker, like device-link tokens. Restarting requires a fresh login.
_oauth_attempts = {}
OAUTH_TTL = 600
OAUTH_MAX_PENDING = 1000

def _oauth_error(message, status=400, code=None):
    body = {"error": message}
    if code:
        body["code"] = code
    response = JSONResponse(body, status)
    response.delete_cookie("oauth_browser")
    response.delete_cookie("code_verifier")
    return response



def _get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

@router.get("/login")
async def login(request: Request, response: Response):
    # A nonce cookie issued on localhost cannot accompany a public callback.
    if IS_DEPLOYED and str(request.base_url).rstrip("/") != APP_URL:
        return JSONResponse({"error": "請從網站的 HTTPS 網址重新登入", "code": "oauth_origin_mismatch", "login_url": APP_URL}, 400)
    if not os.path.exists(CREDENTIALS_FILE):
        return JSONResponse({"error": f"找不到 {CREDENTIALS_FILE}"}, 500)
    
    now = time.monotonic()
    for key, entry in list(_oauth_attempts.items()):
        if entry["expires"] <= now:
            _oauth_attempts.pop(key, None)
    if len(_oauth_attempts) >= OAUTH_MAX_PENDING:
        return JSONResponse({"error": "登入請求過多，請稍後再試"}, 503)
    try:
        flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
        
        res = JSONResponse({"status": "redirect", "url": url})
        browser_nonce = secrets.token_urlsafe(32)
        _oauth_attempts[state] = {"browser": browser_nonce, "verifier": flow.code_verifier, "expires": now + OAUTH_TTL}
        res.set_cookie(key="oauth_browser", value=browser_nonce, httponly=True, max_age=OAUTH_TTL, samesite="lax", secure=IS_DEPLOYED)
        return res
    except Exception as e:
        return JSONResponse({"error": "Google 登入設定無效，請檢查 credentials.json 與 GOOGLE_CREDENTIALS 設定", "code": "oauth_configuration_error"}, 500)

@router.get("/callback")
async def auth_callback(request: Request):
    code = request.query_params.get('code')
    state = request.query_params.get("state", "")
    attempt = _oauth_attempts.get(state)
    browser_nonce = request.cookies.get("oauth_browser", "")
    if (not attempt or attempt["expires"] <= time.monotonic()
            or not secrets.compare_digest(attempt["browser"].encode(), browser_nonce.encode())):
        return _oauth_error("登入驗證已失效，請重新登入")
    # Consume before any token exchange: callbacks cannot be replayed.
    _oauth_attempts.pop(state, None)
    code_verifier = attempt["verifier"]
    old_session_id = request.cookies.get("session_id")  # 登入前瀏覽器帶著的 cookie，可能是訪客 session
    if not code: return _oauth_error("登入未完成，請重新登入")

    stage = "token_exchange"
    try:
        flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        flow.fetch_token(code=code, code_verifier=code_verifier)
        creds = flow.credentials

        # ✅ 同時獲取使用者 Email
        stage = "userinfo"
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info.get('email')
        if not user_email:
            # 不能用 fallback 字串頂替：那會讓所有踩到這個情況的人共用同一個 user_email，等於資料互看
            return _oauth_error("無法取得 Google 帳號 Email，請重新登入一次")

        # 登入前如果是訪客模式在用，把訪客期間累積的資料自動接到這個正式帳號上
        stage = "session_merge"
        merged_count = 0
        old_session = get_session_info(old_session_id) if old_session_id else None
        if old_session and old_session.user_email and old_session.user_email.endswith("@focusflow.local") \
                and old_session.user_email != user_email:
            merged_count = merge_guest_data(old_session.user_email, user_email)
            delete_session(old_session_id)

        stage = "session_save"
        session_id = str(uuid.uuid4())
        save_session(session_id, creds.to_json(), user_email, max_age=604800)

        redirect_url = f"/?guest_merged={merged_count}" if merged_count else "/"
        res = RedirectResponse(url=redirect_url)
        res.set_cookie(key="session_id", value=session_id, httponly=True, max_age=604800, samesite="lax", secure=IS_DEPLOYED)
        res.delete_cookie("code_verifier")
        res.delete_cookie("oauth_browser")
        return res

    except Exception as e:
        # Never log exception text/tracebacks: providers may include codes or tokens.
        failure = f"oauth_{stage}_{type(e).__name__}"
        logger.error("OAuth callback failed: %s", failure)
        return _oauth_error("驗證失敗，請重新登入", 500, code=failure)

@router.get("/guest")
async def guest_login():
    session_id = str(uuid.uuid4())
    # ✅ 每個訪客各自獨立的 email，避免所有訪客共用同一份資料（筆記/記帳/題庫互看互改）
    guest_email = f"guest-{session_id}@focusflow.local"
    save_session(session_id, "{}", guest_email, max_age=86400)

    res = RedirectResponse(url="/")
    res.set_cookie(key="session_id", value=session_id, httponly=True, max_age=86400, samesite="lax", secure=IS_DEPLOYED)
    return res

@router.get("/user")
async def get_user_info(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"logged_in": False})

    session = get_session_info(session_id)
    if not session: return JSONResponse({"logged_in": False})

    # ✅ 處理訪客模式（每個訪客各自獨立的 guest-<uuid>@focusflow.local）
    if session.user_email and session.user_email.endswith("@focusflow.local"):
        return JSONResponse({
            "logged_in": True,
            "is_guest": True,
            "info": {
                "name": "訪客使用者",
                "email": "Guest Mode",
                "picture": "https://cdn-icons-png.flaticon.com/512/1144/1144760.png"
            }
        })

    result = get_valid_credentials(session, SCOPES)

    if result.status == "reauth_required":
        # Google 授權真的失效了（token 被撤銷/過期），前端該導去重新登入，而不是單純顯示未登入
        return JSONResponse({"logged_in": False, "reauth_required": True})
    if result.status == "error":
        # 暫時性錯誤（例如打 Google API 網路失敗），不代表登入失效，前端不該把使用者導去重新登入
        return JSONResponse({"logged_in": False, "error": True})

    try:
        service = build('oauth2', 'v2', credentials=result.creds)
        user_info = service.userinfo().get().execute()

        return JSONResponse({
            "logged_in": True,
            "is_guest": False,
            "info": {"name": user_info.get('name'), "email": user_info.get('email'), "picture": user_info.get('picture')}
        })
    except Exception as e:
        return JSONResponse({"logged_in": False, "error": True})

@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(session_id)
    res = RedirectResponse(url="/")
    res.delete_cookie("session_id")
    return res


@router.get("/device-link")
async def create_device_link(request: Request):
    """給手機掃描用的一次性連結：讓另一台裝置直接以同一個帳號登入（不用重新走 Google OAuth）。"""
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"error": "unauthorized"}, 401)
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)

    token = str(uuid.uuid4())
    _device_link_tokens[token] = (session.user_email, session.token_json, time.time() + DEVICE_LINK_TTL)

    external = os.getenv("RENDER_EXTERNAL_URL")
    if external:
        base = external.rstrip("/")
    else:
        ip = _get_local_ip()
        port = request.url.port or 8000
        base = f"http://{ip}:{port}"

    return JSONResponse({"url": f"{base}/api/auth/device-link/{token}"})


@router.get("/device-link/{token}")
async def redeem_device_link(token: str):
    entry = _device_link_tokens.pop(token, None)
    if not entry:
        return JSONResponse({"error": "連結不存在或已使用過"}, 404)

    user_email, token_json, expires_at = entry
    if time.time() > expires_at:
        return JSONResponse({"error": "連結已過期，請回原本的裝置重新產生 QR Code"}, 400)

    new_session_id = str(uuid.uuid4())
    is_guest = user_email.endswith("@focusflow.local")
    max_age = 86400 if is_guest else 604800
    save_session(new_session_id, token_json, user_email, max_age=max_age)

    res = RedirectResponse(url="/")
    res.set_cookie(key="session_id", value=new_session_id, httponly=True,
                    max_age=max_age, samesite="lax", secure=IS_DEPLOYED)
    return res
