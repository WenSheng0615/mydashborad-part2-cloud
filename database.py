"""Database access and backwards-compatible model exports. No import-time DDL."""
from datetime import datetime, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import (Base, UserSession, Note, Transaction, Category, KeepItem,
                    MusicHistory, ExamSession, ExamAnswer, QuizBank, QuizQuestion, QuizOption, Workspace, Project)

SQLALCHEMY_DATABASE_URL = DATABASE_URL
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
DB_PATH = engine.url.database

@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Utils ---

def get_db():
    return SessionLocal()

def save_session(session_id, token_json, user_email=None, max_age=None):
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=max_age or 604800)
    with SessionLocal() as db:
        session = db.get(UserSession, session_id)
        if session:
            session.token_json = token_json
            if user_email: session.user_email = user_email
            session.last_active, session.expires_at = now, expires_at
        else:
            db.add(UserSession(session_id=session_id, token_json=token_json, user_email=user_email,
                               last_active=now, expires_at=expires_at))
        db.query(UserSession).filter(UserSession.expires_at.isnot(None), UserSession.expires_at < now).delete()
        db.commit()

def get_session_info(session_id):
    with SessionLocal() as db:
        session = db.get(UserSession, session_id) if session_id else None
        # Legacy records get a bounded lifetime from their last activity, not forever.
        expiry = (session.expires_at or ((session.last_active + timedelta(days=7)) if session.last_active else datetime.min)) if session else None
        if session and expiry < datetime.utcnow():
            db.delete(session); db.commit()
            return None
        if session: db.expunge(session)
        return session

def delete_session(session_id):
    with SessionLocal() as db:
        session = db.get(UserSession, session_id)
        if session: db.delete(session)
        db.commit()


def merge_guest_data(old_email: str, new_email: str) -> int:
    """把訪客帳號底下的所有資料，重新掛到剛登入的正式帳號 email 底下，回傳搬移的總筆數。"""
    db = get_db()
    total = 0
    try:
        for model in (Note, Transaction, Category, MusicHistory, QuizBank, ExamSession, KeepItem, Workspace):
            total += db.query(model).filter(model.user_email == old_email).update({model.user_email: new_email})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return total
