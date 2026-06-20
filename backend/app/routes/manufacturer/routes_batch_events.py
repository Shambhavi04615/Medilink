# FILE: routes_batch_events.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any
import json
import os

from app.database.session import SessionLocal
from app.database.models import BatchEvent
from app.utils.jwt_handler import get_current_user
from app.utils.rbac import require_role

router = APIRouter(prefix="/batch/event", tags=["Batch Events"])


# --------------------------
# Database Session Dependency
# --------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------
# Request Body Schema
# --------------------------
class EventCreate(BaseModel):
    batch_no: str
    event_type: str
    event_data: Dict[str, Any]


# --------------------------
# Helper: Validate Batch from Blockchain
# --------------------------
def check_batch_exists_in_blockchain(batch_no: str) -> bool:
    blockchain_path = "blockchain_data.json"

    if not os.path.exists(blockchain_path):
        return False

    try:
        with open(blockchain_path, "r") as f:
            chain = json.load(f)
    except Exception:
        return False

    # Check if any block contains this batch number
    for block in chain:
        data = block.get("data", {})
        if isinstance(data, dict) and data.get("batch_no") == batch_no:
            return True

    return False


# --------------------------
# ADD EVENT
# --------------------------
@router.post("/add")
def add_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Add a supply chain event for a batch.
    Batch must exist in BLOCKCHAIN (not Inventory).
    Any logged-in user can add production events.
    """

    # 🔥 Validate batch from blockchain JSON
    if not check_batch_exists_in_blockchain(payload.batch_no):
        raise HTTPException(status_code=404, detail="Batch not found in blockchain")

    # Store event in SQL database
    event = BatchEvent(
        batch_no=payload.batch_no,
        event_type=payload.event_type,
        event_data=payload.event_data,
        timestamp=datetime.utcnow(),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "success": True,
        "message": "Event added successfully",
        "event": {
            "id": event.id,
            "batch_no": event.batch_no,
            "event_type": event.event_type,
            "event_data": event.event_data,
            "timestamp": event.timestamp,
        },
    }


# --------------------------
# GET EVENTS FOR A BATCH
# --------------------------
@router.get("/{batch_no}")
def get_events(batch_no: str, db: Session = Depends(get_db)):
    """
    Get all production events for a batch in chronological order.
    """

    # Optional: also check if batch exists in blockchain
    if not check_batch_exists_in_blockchain(batch_no):
        return {
            "success": False,
            "message": "Batch not found in blockchain",
            "events": [],
        }

    # Fetch all events from SQL
    events = (
        db.query(BatchEvent)
        .filter(BatchEvent.batch_no == batch_no)
        .order_by(BatchEvent.timestamp.asc())
        .all()
    )

    if not events:
        return {
            "success": False,
            "message": "No events found for this batch",
            "events": [],
        }

    return {
        "success": True,
        "message": f"{len(events)} events found",
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_data": e.event_data,
                "timestamp": e.timestamp,
            }
            for e in events
        ],
    }
