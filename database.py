import os
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Float, Boolean
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

class MusicHistory(Base):
    __tablename__ = "music_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, index=True)
    video_id = Column(String)
    title = Column(String)
    thumbnail = Column(String)
    played_at = Column(DateTime, default=datetime.utcnow)

class ExamSession(Base):
    __tablename__ = "exam_sessions"
    id = Column(String, primary_key=True, index=True)
    user_email = Column(String, index=True)
    bank_id = Column(String, index=True)
    bank_name = Column(String)
    total = Column(Integer)
    correct = Column(Integer)
    score = Column(Float)       # 0~100
    created_at = Column(String)

class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True)
    question_content = Column(Text)
    question_type = Column(String)   # single / multiple
    options_json = Column(Text)      # [{text, is_correct}]
    selected_json = Column(Text)     # [text, ...]  使用者選的
    is_correct = Column(Boolean)

class QuizBank(Base):
    __tablename__ = "quiz_banks"
    id = Column(String, primary_key=True, index=True)
    user_email = Column(String, index=True)
    name = Column(String)
    description = Column(Text, default="")
    created_at = Column(String)

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id = Column(String, primary_key=True, index=True)
    bank_id = Column(String, index=True)
    content = Column(Text)
    type = Column(String, default="single")  # single / multiple
    tag = Column(String, default="")
    created_at = Column(String)

class QuizOption(Base):
    __tablename__ = "quiz_options"
    id = Column(String, primary_key=True, index=True)
    question_id = Column(String, index=True)
    text = Column(String)
    is_correct = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# 補上舊版資料庫缺少的欄位
with engine.connect() as _conn:
    _cols = [row[1] for row in _conn.exec_driver_sql("PRAGMA table_info(quiz_questions)").fetchall()]
    if "tag" not in _cols:
        _conn.exec_driver_sql("ALTER TABLE quiz_questions ADD COLUMN tag VARCHAR DEFAULT ''")
        _conn.commit()

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
