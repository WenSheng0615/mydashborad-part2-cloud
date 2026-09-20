from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey
from .base import Base

class UserSession(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True, index=True)
    token_json = Column(Text)
    user_email = Column(String, index=True) # 用於區分資料歸屬
    last_active = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True) # None = 舊資料尚未補上，視為未過期

class Note(Base):
    deleted_at = Column(DateTime, nullable=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True, index=True)
    __tablename__ = "notes"
    id = Column(String, primary_key=True, index=True)
    user_email = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    color = Column(String, default="yellow")
    image_url = Column(Text, nullable=True) # 儲存 Firebase 下載連結
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

class KeepItem(Base):
    __tablename__ = "keep_items"
    id = Column(String, primary_key=True, index=True)
    user_email = Column(String, index=True)
    type = Column(String)  # text / link / image / file
    content = Column(Text)  # 文字內容，或圖片/檔案的下載網址
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

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
