import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from .base import Base

class ProjectLink(Base):
    __tablename__ = "project_links"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
