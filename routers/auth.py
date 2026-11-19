import os
import json
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

# Sign-in requests the four Google integrations together; persist actual grants only.
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']


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
    return start_oauth(request)

def start_oauth(request: Request, provider=None):
    from services import connection_service as connections
    session = get_session_info(request.cookies.get("session_id"))
    if provider and (not session or connections.guest(session.user_email)):
        return JSONResponse({"error":"請先保存帳號，再連接私人服務","code":"account_required"},403)
    scopes = SCOPES + ([connections.GOOGLE_SCOPES[provider]] if provider else list(connections.GOOGLE_SCOPES.values()))
    login_generations = {p:connections.version(session.user_email,p) for p in connections.GOOGLE_SCOPES} if session and not connections.guest(session.user_email) else None
    # A nonce cookie issued on localhost cannot accompany a public callback.
    if IS_DEPLOYED and str(request.base_url).rstrip("/") != APP_URL:
        return JSONResponse({"error": "請從網站的 HTTPS 網址重新登入", "code": "oauth_origin_mismatch", "login_url": APP_URL}, 400)
    if not os.path.exists(CREDENTIALS_FILE):
        return JSONResponse({"error": "Google 登入尚未設定，請聯絡網站管理者"}, 503)
    
    now = time.monotonic()
    for key, entry in list(_oauth_attempts.items()):
        if entry["expires"] <= now:
            _oauth_attempts.pop(key, None)
    if len(_oauth_attempts) >= OAUTH_MAX_PENDING:
        return JSONResponse({"error": "登入請求過多，請稍後再試"}, 503)
    try:
        flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=scopes, redirect_uri=REDIRECT_URI)
        url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent', **({'login_hint':session.user_email} if session and not connections.guest(session.user_email) else {}))
        
        res = JSONResponse({"status": "redirect", "url": url})
        browser_nonce = secrets.token_urlsafe(32)
        _oauth_attempts[state] = {"browser": browser_nonce, "verifier": flow.code_verifier, "expires": now + OAUTH_TTL, "scopes":scopes, "provider":provider, "session_id":session.session_id if session else None, "owner":session.user_email if session else None, "return_account":request.query_params.get("return_to")=="account", "return_connections":request.query_params.get("return_to")=="connections", "login_generations":login_generations, "login_owner":session.user_email if session else None, "generation":connections.version(session.user_email,provider) if provider else None}
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
    if old_session_id != attempt.get('session_id'):
        return _oauth_error('登入身分已變更，請重新開始',code='connection_session_changed')
    provider = attempt.get('provider')
    if provider:
        current = get_session_info(old_session_id)
        if not current or old_session_id != attempt['session_id'] or current.user_email != attempt['owner']:
            return _oauth_error('連線身分已變更，請重新開始',code='connection_session_changed')
    if not code:
        if provider:
            response=RedirectResponse('/account?connection=cancelled#connections')
            response.delete_cookie('oauth_browser');return response
        return _oauth_error("登入未完成，請重新登入")

    stage = "token_exchange"
    try:
        flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=attempt["scopes"], redirect_uri=REDIRECT_URI)
        try:
            flow.fetch_token(code=code, code_verifier=code_verifier)
        except Warning as changed_scope:
            # oauthlib raises on incremental/partial grants before exposing the token.
            # Accept only its structured scope-change result, then validate actual
            # granted scopes below. Do not globally disable OAuth scope validation.
            if not all(hasattr(changed_scope,key) for key in ('token','new_scope','old_scope')):
                raise
            flow.oauth2session.token=dict(changed_scope.token)
        creds = flow.credentials
        info=json.loads(creds.to_json())
        info['scopes']=[]
        granted=getattr(creds,'granted_scopes',None)
        if isinstance(granted,(list,tuple)):info['scopes']=list(granted)
        token_scope=flow.oauth2session.token.get('scope')
        if isinstance(token_scope,str):info['scopes']=token_scope.split()
        elif isinstance(token_scope,(list,tuple)):info['scopes']=list(token_scope)

        # ✅ 同時獲取使用者 Email
        stage = "userinfo"
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info.get('email')
        if not user_email or not user_info.get('id') or user_info.get('verified_email') is not True:
            # 不能用 fallback 字串頂替：那會讓所有踩到這個情況的人共用同一個 user_email，等於資料互看
            return _oauth_error("無法取得 Google 帳號 Email，請重新登入一次")

        from services import connection_service as connections
        user_email=user_email.strip()
        subject=user_info['id']
        # Preserve the legacy ownership key; Google subject establishes stable identity.
        canonical=connections.owner_for_subject(subject)
        previous_identity=get_session_info(old_session_id) if old_session_id else None
        if canonical:user_email=canonical
        elif previous_identity and not connections.guest(previous_identity.user_email) and previous_identity.user_email.casefold()==user_email.casefold():
            user_email=previous_identity.user_email
        known=connections.profile(user_email)
        if known and known['subject']!=subject:
            return _oauth_error('Google 身分不符，請使用原帳號',code='identity_mismatch')
        if provider:
            if user_email != attempt['owner']:
                return _oauth_error('請使用目前登入帳號連接服務',code='connection_account_mismatch')
            if not connections.permits(info,provider):
                return _oauth_error('未取得此服務需要的權限，請重新連接',code='connection_scope_denied')
            if not info.get('refresh_token'):
                old,_=connections.read(current,provider)
                if old:info['refresh_token']=old.get('refresh_token')
            if not info.get('refresh_token'):
                return _oauth_error('未取得持續連線授權，請重新連接',code='connection_offline_denied')
            connections.save_profile(user_email,subject,user_info.get('name') or user_email,user_info.get('picture') or '')
            connections.save(user_email,provider,info,user_email,expected=attempt['generation'])
            response=RedirectResponse('/account?connection=connected#connections')
            response.delete_cookie('oauth_browser');return response

        # Preserve existing service grants before replacing an old combined login session.
        previous=get_session_info(old_session_id) if old_session_id else None
        stage = 'service_save'
        same_owner=previous if previous and previous.user_email==user_email else None
        expected=attempt.get('login_generations') if attempt.get('login_owner')==user_email else None
        connections.save_google_login(user_email,info,expected=expected,legacy_session=same_owner)
        if same_owner:connections.preserve_legacy(same_owner)
        connections.save_profile(user_email,subject,user_info.get('name') or user_email,user_info.get('picture') or '')
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
        save_session(session_id, "{}", user_email, max_age=604800)
        if old_session_id:delete_session(old_session_id)

        redirect_url = f"/?guest_merged={merged_count}" if merged_count else "/"
        if attempt.get("return_account"):redirect_url="/account"+(f"?guest_merged={merged_count}" if merged_count else "")
        if attempt.get("return_connections"):redirect_url="/account#connections"
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
async def guest_login(request: Request):
    existing=get_session_info(request.cookies.get('session_id'))
    if existing:return RedirectResponse(url='/')
    session_id = str(uuid.uuid4())
    # ✅ 每個訪客各自獨立的 email，避免所有訪客共用同一份資料（筆記/記帳/題庫互看互改）
    guest_email = f"guest-{session_id}@focusflow.local"
    save_session(session_id, "{}", guest_email, max_age=604800)

    res = RedirectResponse(url="/")
    res.set_cookie(key="session_id", value=session_id, httponly=True, max_age=604800, samesite="lax", secure=IS_DEPLOYED)
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

    from services.connection_service import profile
    identity=profile(session.user_email)
    return JSONResponse({"logged_in": True,"is_guest":False,"info":{
        "name":identity['name'] if identity else session.user_email.split('@')[0],
        "email":session.user_email,
        "picture":identity['picture'] if identity and identity['picture'] else '/static/icons/icon-192.png'}})


@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        from services.connection_service import preserve_legacy
        try:preserve_legacy(get_session_info(session_id))
        except Exception:logger.warning('Could not preserve legacy service grants at logout')
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
    max_age = 604800
    save_session(new_session_id, token_json, user_email, max_age=max_age)

    res = RedirectResponse(url="/")
    res.set_cookie(key="session_id", value=new_session_id, httponly=True,
                    max_age=max_age, samesite="lax", secure=IS_DEPLOYED)
    return res
