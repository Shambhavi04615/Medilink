# FILE: backend/app/database/connection.py

from sqlalchemy import create_engine
from app.database.models import Base

DATABASE_URL = "sqlite:///./medilink.db"   # or absolute path if needed

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db():
    """
    Create all tables if they don't exist.
    """
    Base.metadata.create_all(bind=engine)
