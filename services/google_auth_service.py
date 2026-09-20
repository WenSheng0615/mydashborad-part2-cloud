import json
from fastapi import Request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build

from database import get_session_info, save_session

# Google 相關功能（Drive/Music/Calendar/Tasks）原本各自複製了一份「讀 token → 過期就 refresh → build service」
# 的邏輯，而且統一用 bare except 吞掉所有錯誤，導致「token 真的失效，需要重新登入」跟「暫時網路問題」
# 回傳的結果一模一樣，使用者永遠只看到「請先登入」。這裡把邏輯抽成一份，並把兩種情況分開回報。


class AuthResult:
    """
    status:
      - "ok"              可用，creds 已經是有效的
      - "no_session"      根本沒有 session_id / session 不存在，就是還沒登入
      - "reauth_required" Google 授權已經失效（refresh_token 被撤銷/過期/從未取得），需要使用者重新走一次 Google 登入
      - "error"           非身份問題的暫時性錯誤（例如打 Google API 網路失敗），不代表登入失效
    """
    def __init__(self, status, creds=None, detail=None):
        self.status = status
        self.creds = creds
        self.detail = detail


def get_valid_credentials(session, scopes=None) -> AuthResult:
    if not session:
        return AuthResult("no_session")

    try:
        info = json.loads(session.token_json)
    except (json.JSONDecodeError, TypeError) as e:
        return AuthResult("reauth_required", detail=f"token 資料損毀: {e}")

    try:
        creds = Credentials.from_authorized_user_info(info, scopes) if scopes else Credentials.from_authorized_user_info(info)
    except ValueError as e:
        # 缺必要欄位（例如訪客的 token_json 是 "{}"，或根本沒完成過 Google 登入）
        return AuthResult("reauth_required", detail=f"缺少有效的 Google 授權: {e}")

    if creds and creds.expired:
        if not creds.refresh_token:
            return AuthResult("reauth_required", detail="缺少 refresh_token，無法自動續期")
        try:
            creds.refresh(GoogleRequest())
            is_guest = session.user_email.endswith("@focusflow.local") if session.user_email else False
            save_session(session.session_id, creds.to_json(), session.user_email,
                         max_age=86400 if is_guest else 604800)
        except RefreshError as e:
            # 這才是真的「登入失效」：refresh_token 被使用者在 Google 帳號設定裡撤銷，或已過期
            return AuthResult("reauth_required", detail=str(e))
        except Exception as e:
            # 網路逾時之類的暫時性錯誤，不該被當成登入失效
            return AuthResult("error", detail=str(e))

    return AuthResult("ok", creds=creds)


def build_google_service(request: Request, api_name: str, api_version: str, scopes=None):
    """回傳 (service, AuthResult)。service 為 None 時，用 AuthResult.status 判斷該回什麼錯誤。"""
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id) if session_id else None

    result = get_valid_credentials(session, scopes)
    if result.status != "ok":
        return None, result

    try:
        service = build(api_name, api_version, credentials=result.creds)
        return service, result
    except Exception as e:
        return None, AuthResult("error", detail=str(e))


def auth_error_body(result: AuthResult):
    """(response_dict, status_code)，給各 router 統一組錯誤回應用。"""
    if result.status == "reauth_required":
        return {"error": "Google 授權無效或已過期，請重新登入 Google 帳號", "reauth_required": True}, 401
    if result.status == "no_session":
        return {"error": "Login Required"}, 401
    return {"error": "暫時無法連線 Google，請稍後再試"}, 503
