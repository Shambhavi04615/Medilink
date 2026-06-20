# FILE: backend/app/database/session.py

from sqlalchemy.orm import sessionmaker
from app.database.connection import engine

# Create the SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
