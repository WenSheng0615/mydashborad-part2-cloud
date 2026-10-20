"""Adopt explicitly scoped legacy session grants, without contacting a provider."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime
from database import get_db, UserSession
from services.connection_service import preserve_legacy

def preserve():
    with get_db() as db:
        sessions=db.query(UserSession).filter(UserSession.expires_at>datetime.utcnow()).order_by(UserSession.last_active.desc()).all()
        db.expunge_all()
    for session in sessions:preserve_legacy(session)
    print('Legacy service authorization adoption completed; no credentials printed')

if __name__=='__main__':preserve()
