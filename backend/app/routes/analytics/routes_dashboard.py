from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database.session import SessionLocal
from app.database.models import (
    Inventory,
    BatchEvent,
    Alerts,
    MedicinePrice,
)
from app.utils.jwt_handler import get_current_user
from app.utils.blockchain_storage import load_blockchain

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    role = user.role

    # Load blockchain object
    chain = load_blockchain()
    blocks = chain.chain  # list of Block objects
    total_transactions = len(blocks)

    # ============================
    # MANUFACTURER DASHBOARD
    # ============================
    if role == "manufacturer":

        # total inventory entries (batches)
        total_batches = db.query(Inventory).count()

        # total supply chain events
        total_events = db.query(BatchEvent).count()

        # 5 most recent events
        recent_events = (
            db.query(BatchEvent)
            .order_by(BatchEvent.timestamp.desc())
            .limit(5)
            .all()
        )

        return {
            "role": "manufacturer",
            "total_batches": total_batches,
            "total_blockchain_transactions": total_transactions,
            "total_events_logged": total_events,
            "recent_events": [
                {
                    "type": e.event_type,
                    "batch_no": e.batch_no,
                    "timestamp": e.timestamp,
                }
                for e in recent_events
            ],
        }

    # ============================
    # PHARMACIST DASHBOARD
    # ============================
    if role == "pharmacist":

        inventory_items = (
            db.query(Inventory)
            .filter(Inventory.user_id == user.id)
            .all()
        )

        expiring_soon = [
            {
                "batch_no": i.batch_no,
                "medicine": i.medicine_name,
                "expiry_date": i.expiry_date,
            }
            for i in inventory_items
            if i.expiry_date
            and i.expiry_date <= datetime.utcnow().date() + timedelta(days=30)
        ]

        low_stock = [
            {
                "medicine": i.medicine_name,
                "batch_no": i.batch_no,
                "quantity": i.quantity,
            }
            for i in inventory_items
            if i.quantity <= 10
        ]

        price_updates = (
            db.query(MedicinePrice)
            .filter(MedicinePrice.pharmacy_id == user.id)
            .order_by(MedicinePrice.last_updated.desc())
            .limit(5)
            .all()
        )

        return {
            "role": "pharmacist",
            "total_inventory_items": len(inventory_items),
            "expiring_soon": expiring_soon,
            "low_stock": low_stock,
            "recent_price_updates": [
                {
                    "medicine_name": p.medicine_name,
                    "min": p.min_threshold,
                    "max": p.max_threshold,
                    "updated": p.last_updated,
                }
                for p in price_updates
            ],
        }

    # ============================
    # CUSTOMER DASHBOARD
    # ============================
    if role == "customer":

        # Count how many blocks this customer created (sender matches their name)
        verifications = sum(
            1 for block in blocks
            if isinstance(block.data, dict)
            and block.data.get("sender") == user.name
        )

        # Fake report count
        fake_reports = (
            db.query(Alerts)
            .filter(Alerts.user_id == user.id)
            .count()
        )

        return {
            "role": "customer",
            "total_verifications": verifications,
            "fake_reports_submitted": fake_reports,
        }

    return {"error": "Invalid role"}
