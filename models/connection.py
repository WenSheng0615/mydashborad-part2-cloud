from sqlalchemy import Column, String, Text, Integer, Boolean
from .base import Base

class AccountProfile(Base):
    __tablename__ = 'account_profiles'
    user_email = Column(String, primary_key=True)
    google_subject = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    picture = Column(Text, nullable=False, default='')

class ServiceConnection(Base):
    __tablename__ = 'service_connections'
    user_email = Column(String, primary_key=True)
    provider = Column(String(40), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    secret = Column(Text, nullable=True)
    account = Column(String, nullable=False, default='')
    generation = Column(Integer, nullable=False, default=0)
