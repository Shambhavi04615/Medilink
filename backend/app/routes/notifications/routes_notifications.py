from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.database.session import SessionLocal
from app.database.models import Notification
from app.utils.jwt_handler import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic Schemas
class NotificationCreate(BaseModel):
    user_id: int
    message: str


# -------------------------
# SEND NOTIFICATION
# -------------------------
@router.post("/send")
def send_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
):
    notif = Notification(
        user_id=payload.user_id,
        message=payload.message,
        is_read=False,
        created_at=datetime.utcnow()
    )

    db.add(notif)
    db.commit()
    db.refresh(notif)

    return {"success": True, "notification": {
        "id": notif.id,
        "user_id": notif.user_id,
        "message": notif.message,
        "is_read": notif.is_read,
        "created_at": notif.created_at
    }}


# -------------------------
# GET MY NOTIFICATIONS
# -------------------------
@router.get("/")
def get_notifications(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "count": len(notifs),
        "notifications": [
            {
                "id": n.id,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at
            }
            for n in notifs
        ]
    }


# -------------------------
# MARK AS READ
# -------------------------
@router.post("/read/{notif_id}")
def mark_read(notif_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):

    notif = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == user.id)
        .first()
    )

    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    db.commit()

    return {"success": True, "message": "Notification marked as read"}
