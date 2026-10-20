"""Owner-scoped credentials. Tombstones prevent legacy tokens from reconnecting a service."""
import json
import os
from pathlib import Path
from sqlalchemy import text
from cryptography.fernet import Fernet
from database import get_db
from models.connection import AccountProfile, ServiceConnection

GOOGLE_SCOPES = {
    'calendar':'https://www.googleapis.com/auth/calendar',
    'drive':'https://www.googleapis.com/auth/drive',
    'tasks':'https://www.googleapis.com/auth/tasks',
    'youtube':'https://www.googleapis.com/auth/youtube.readonly',
}
PROVIDERS = (*GOOGLE_SCOPES, 'icloud')

def guest(owner):
    return not owner or owner.endswith('@focusflow.local')

def cipher(db):
    # The key lives next to the actual DB (in /data on Docker), never in an image.
    path = Path(db.get_bind().url.database).resolve().parent / '.local' / 'secrets' / 'connections.key'
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.exists():
        if db.query(ServiceConnection).filter(ServiceConnection.secret.isnot(None)).first():
            raise ValueError('Connection key missing')
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f: f.write(Fernet.generate_key())
        except FileExistsError:
            pass
    return Fernet(path.read_bytes())

def scopes(info):
    value=info.get('scopes') or info.get('scope') or []
    return set(value.split() if isinstance(value,str) else value)

def permits(info,provider,legacy=False):
    granted=scopes(info)
    if not granted:return legacy
    accepted={GOOGLE_SCOPES[provider]}
    if provider=='youtube':accepted.add('https://www.googleapis.com/auth/youtube')
    return bool(accepted & granted)

def version(owner,provider):
    with get_db() as db:
        row=db.get(ServiceConnection,(owner,provider));return row.generation if row else 0

def read(session,provider):
    if guest(session.user_email):return None,None
    with get_db() as db:
        row=db.get(ServiceConnection,(session.user_email,provider))
        if row:
            if not row.enabled or not row.secret:return None,row.generation
            info=json.loads(cipher(db).decrypt(row.secret.encode()))
            return info,row.generation
    # Read-only compatibility for existing sessions. Missing scopes are unknown on legacy data.
    try:
        info=json.loads(session.token_json)
        return (info,None) if provider in GOOGLE_SCOPES and info.get('refresh_token') else (None,None)
    except (TypeError,ValueError):return None,None

def save(owner,provider,info,account,expected=None):
    with get_db() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        row=db.get(ServiceConnection,(owner,provider))
        current=row.generation if row else 0
        if expected is not None and current!=expected:raise ValueError('Connection changed')
        sealed=cipher(db).encrypt(json.dumps(info).encode()).decode()
        if not row:
            row=ServiceConnection(user_email=owner,provider=provider,generation=0);db.add(row)
        row.enabled=True;row.secret=sealed;row.account=account;row.generation=current+1
        db.commit()

def disconnect(owner,provider):
    with get_db() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        row=db.get(ServiceConnection,(owner,provider))
        if not row:
            row=ServiceConnection(user_email=owner,provider=provider,generation=0);db.add(row)
        row.enabled=False;row.secret=None;row.account='';row.generation+=1;db.commit()

def preserve_legacy(session):
    if not session or guest(session.user_email):return
    for provider in GOOGLE_SCOPES:
        info,generation=read(session,provider)
        if generation is None and info and permits(info,provider):
            save(session.user_email,provider,info,session.user_email,expected=0)

def icloud_config(owner):
    with get_db() as db:
        row=db.get(ServiceConnection,(owner,'icloud'))
        if row:
            if not row.enabled or not row.secret:return None
            return json.loads(cipher(db).decrypt(row.secret.encode()))
    if owner==os.getenv('ICLOUD_OWNER_EMAIL','').strip():
        username=os.getenv('ICLOUD_USERNAME','').strip();password=os.getenv('ICLOUD_APP_PASSWORD','').strip()
        if username and password:return dict(username=username,password=password)
    return None

def profile(owner):
    with get_db() as db:
        row=db.get(AccountProfile,owner)
        return dict(subject=row.google_subject,name=row.name,picture=row.picture) if row else None

def save_profile(owner,subject,name,picture):
    with get_db() as db:
        row=db.get(AccountProfile,owner)
        other=db.query(AccountProfile).filter(AccountProfile.google_subject==subject).first()
        if (row and row.google_subject!=subject) or (other and other.user_email!=owner):raise ValueError('Identity mismatch')
        if not row:row=AccountProfile(user_email=owner,google_subject=subject);db.add(row)
        row.name=name[:200];row.picture=picture[:2000];db.commit()

def owner_for_subject(subject):
    with get_db() as db:
        row=db.query(AccountProfile).filter_by(google_subject=subject).first()
        return row.user_email if row else None
