# FILE: backend/app/database/models.py

from sqlalchemy import Column, Integer, String, Date, DateTime, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy import JSON, Boolean
from datetime import datetime   # <-- Correct timestamp generator

Base = declarative_base()

# ===================== USERS =====================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    role = Column(String)


# ===================== INVENTORY =====================
class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    medicine_name = Column(String)
    batch_no = Column(String)
    quantity = Column(Integer)
    expiry_date = Column(Date)


# ===================== ALERTS =====================
class Alerts(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    batch_no = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ===================== MEDICINE PRICE =====================
class MedicinePrice(Base):
    __tablename__ = "medicine_prices"

    id = Column(Integer, primary_key=True, index=True)
    medicine_name = Column(String, index=True)
    batch_no = Column(String, index=True)

    threshold_min = Column(Float, nullable=False)
    threshold_max = Column(Float, nullable=False)
    notes = Column(String, nullable=True)

    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===================== BATCH EVENTS =====================
class BatchEvent(Base):
    __tablename__ = "batch_events"

    id = Column(Integer, primary_key=True, index=True)
    batch_no = Column(String, index=True)
    event_type = Column(String)
    event_data = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ===================== NOTIFICATIONS =====================
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    message = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
