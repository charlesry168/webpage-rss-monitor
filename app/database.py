import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./monitors.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    name = Column(String, nullable=False)
    check_interval = Column(Integer, default=3600)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, nullable=True)
    last_changed = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    css_selector = Column(String, nullable=True)
    api_key = Column(String, nullable=True)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    monitor_id = Column(String, nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow)
    content_hash = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    diff_summary = Column(Text, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
