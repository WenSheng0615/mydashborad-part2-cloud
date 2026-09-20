import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, CheckConstraint
from .base import Base

class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="ck_workspace_name"),)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class Project(Base):
    archived_at = Column(DateTime, nullable=True)
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("kind IN ('project', 'course')", name="ck_project_kind"),
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="ck_project_name"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    kind = Column(String(16), nullable=False, default="project")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
