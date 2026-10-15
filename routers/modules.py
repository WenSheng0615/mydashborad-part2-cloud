from fastapi import APIRouter, HTTPException, WebSocketException, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool
from starlette.requests import HTTPConnection
from database import get_db, get_session_info
from routers.workspaces import User, DB
from services import module_service as service
from services import module_connections as connections

router = APIRouter(prefix="/api/modules", tags=["modules"])


class ModuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool


@router.get("")
def list_modules(user: User, db: DB):
    return {"modules": service.catalog(db, user)}


@router.patch("/{module_id}")
def update_module(module_id: str, body: ModuleUpdate, user: User, db: DB):
    module = service.BY_ID.get(module_id)
    if module is None:
        raise HTTPException(404, "找不到模組")
    if module["core"]:
        if not body.enabled:
            raise HTTPException(409, "核心功能無法停用")
    else:
        service.set_enabled(db, user, module_id, body.enabled)
    return {"modules": service.catalog(db, user)}


@router.get("/connections")
def connection_summary(request: Request, response: Response, user: User):
    response.headers['Cache-Control'] = 'no-store'
    session = get_session_info(request.cookies.get('session_id'))
    if not session or session.user_email != user:
        raise HTTPException(401, '請先登入')
    return {'connections': connections.snapshot(session)}


@router.post("/{module_id}/connections/check")
def check_connections(module_id: str, request: Request, response: Response, user: User, db: DB):
    response.headers['Cache-Control'] = 'no-store'
    if module_id not in connections.GOOGLE:
        raise HTTPException(404, '此 App 沒有外部帳號連線檢查')
    if not service.enabled(db, user, module_id):
        raise HTTPException(409, '請先啟用此 App 再檢查連線')
    session = get_session_info(request.cookies.get('session_id'))
    if not session or session.user_email != user:
        raise HTTPException(401, '請先登入')
    result = [connections.check_google(session, module_id)]
    if module_id == 'calendar':
        result.append(connections.check_icloud(user))
    return {'connections': result}


def require_enabled(module_id):
    def guard(connection: HTTPConnection):
        session = get_session_info(connection.cookies.get("session_id"))
        # Retain each existing router's unauthenticated/guest policy.
        if not session or not session.user_email:
            return
        with get_db() as db:
            allowed = service.enabled(db, session.user_email, module_id)
        if not allowed:
            if connection.scope["type"] == "websocket":
                raise WebSocketException(code=4403, reason="Module disabled")
            raise HTTPException(403, "此 App 已停用，請至設定的模組管理重新啟用")
    return guard
