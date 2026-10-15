from sqlalchemy import Boolean, Column, String
from .base import Base


class ModulePreference(Base):
    __tablename__ = "module_preferences"
    user_email = Column(String, primary_key=True)
    module_id = Column(String(40), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
