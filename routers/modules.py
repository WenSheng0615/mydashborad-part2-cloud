from fastapi import APIRouter, HTTPException, WebSocketException
from pydantic import BaseModel, ConfigDict, StrictBool
from starlette.requests import HTTPConnection
from database import get_db, get_session_info
from routers.workspaces import User, DB
from services import module_service as service

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
