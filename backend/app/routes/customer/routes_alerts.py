# FILE: backend/app/customer/routes_alerts.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.session import SessionLocal
from app.database.models import Alerts
from app.utils.jwt_handler import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts / Reporting"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/report")
def report_issue(
    batch_no: str,
    description: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Customer or pharmacist reports a suspicious or fake medicine batch.
    """

    alert = Alerts(
        user_id=user.id,
        batch_no=batch_no,
        description=description,
        timestamp=datetime.now()
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return {
        "success": True,
        "message": "Report submitted successfully",
        "alert_id": alert.id
    }


@router.get("/all")
def get_all_reports(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Only manufacturers should view all alerts.
    """

    if user.role != "manufacturer":
        return {"success": False, "message": "Only manufacturers can view reports"}

    alerts = db.query(Alerts).all()

    return {
        "success": True,
        "data": alerts
    }

