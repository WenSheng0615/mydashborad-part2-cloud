import os
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focusflow.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---

class UserSession(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True, index=True)
    token_json = Column(Text)
    user_email = Column(String, index=True) # 用於區分資料歸屬
    last_active = Column(DateTime, default=datetime.utcnow)

class Note(Base):
    __tablename__ = "notes"
    id = Column(String, primary_key=True, index=True)
    user_email = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    color = Column(String, default="yellow")
    image_url = Column(String, nullable=True) # 儲存 Firebase 下載連結
    created_at = Column(String) # 改存字串方便前端顯示

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, index=True)
    user_email = Column(String, index=True)
    item = Column(String)
    amount = Column(Float)
    category = Column(String)
    type = Column(String) # income/expense
    date = Column(String)
    note = Column(Text)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, index=True)
    name = Column(String)
    budget = Column(Float, default=0)
    type = Column(String)

Base.metadata.create_all(bind=engine)

# --- Utils ---

def get_db():
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise

def save_session(session_id, token_json, user_email=None):
    db = get_db()
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session:
        session.token_json = token_json
        if user_email: session.user_email = user_email
    else:
        session = UserSession(session_id=session_id, token_json=token_json, user_email=user_email)
        db.add(session)
    db.commit()
    db.close()

def get_session_info(session_id):
    db = get_db()
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    db.close()
    return session if session else None

def delete_session(session_id):
    db = get_db()
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session:
        db.delete(session)
        db.commit()
    db.close()
