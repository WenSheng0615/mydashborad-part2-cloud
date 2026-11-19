"""Account-bound integration management; never returns credentials."""
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from routers.workspaces import User
from database import get_session_info
from services import connection_service as service

router=APIRouter(prefix='/api/connections',tags=['connections'])

@router.get('')
def summary(request:Request,response:Response,user:User):
    response.headers["Cache-Control"]="no-store"
    from services.module_connections import google_state,icloud_state
    session=get_session_info(request.cookies.get('session_id'))
    modules={'calendar':'calendar','drive':'drive','tasks':'tasks','youtube':'music'}
    rows=[dict(id=provider,**google_state(session,module)) for provider,module in modules.items()]
    rows.append(dict(id='icloud',**icloud_state(user)))
    from database import get_db
    from models.connection import ServiceConnection
    with get_db() as db:
        for item in rows:
            saved=db.get(ServiceConnection,(user,item['id']))
            item['account']=saved.account if saved and saved.enabled else ''
    return {'is_guest':service.guest(user),'connections':rows}

@router.post('/google/{provider}/connect')
def connect(provider:str,request:Request,user:User):
    if provider not in service.GOOGLE_SCOPES:raise HTTPException(404,'找不到服務')
    from routers.auth import start_oauth
    return start_oauth(request,provider)

@router.delete('/{provider}')
def disconnect(provider:str,user:User):
    if provider not in service.PROVIDERS:raise HTTPException(404,'找不到服務')
    service.disconnect(user,provider)
    return {'status':'disconnected','local_data_preserved':True}

class ICloudConnect(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username:str=Field(min_length=3,max_length=254)
    password:SecretStr=Field(min_length=16,max_length=64)

@router.post('/icloud/connect')
def connect_icloud(body:ICloudConnect,user:User):
    if service.guest(user):raise HTTPException(403,'請先保存帳號，再連接私人服務')
    username=body.username.strip()
    password=body.password.get_secret_value().strip()
    if '@' not in username:raise HTTPException(422,'請輸入 Apple 帳號 Email')
    generation=service.version(user,'icloud')
    try:
        import caldav
        with caldav.DAVClient(url='https://caldav.icloud.com/',username=username,password=password,timeout=8) as client:
            client.principal()
    except Exception:
        raise HTTPException(502,'無法連接 iCloud，請檢查網路、Apple 帳號與 App 專用密碼') from None
    try:
        service.save(user,'icloud',dict(username=username,password=password),username,expected=generation)
    except Exception:
        raise HTTPException(409,'無法安全保存連線，請稍後重試') from None
    return {'status':'connected'}


@router.post('/{provider}/check')
def check(provider:str,request:Request,response:Response,user:User):
    """Read-only provider probe, independent of App visibility/preferences."""
    if provider not in service.PROVIDERS:raise HTTPException(404,'找不到服務')
    response.headers['Cache-Control']='no-store'
    session=get_session_info(request.cookies.get('session_id'))
    if not session or session.user_email!=user:raise HTTPException(401,'請先登入')
    from services.module_connections import check_google,check_icloud
    result=check_icloud(user) if provider=='icloud' else check_google(session,'music' if provider=='youtube' else provider)
    # Re-read a concurrently disconnected service rather than reporting stale success.
    if service.guest(user):return {'id':provider,**result}
    from services.module_connections import google_state,icloud_state
    latest=icloud_state(user) if provider=='icloud' else google_state(session,'music' if provider=='youtube' else provider)
    if latest['status']!='unverified':result=latest
    return {'id':provider,**result}
