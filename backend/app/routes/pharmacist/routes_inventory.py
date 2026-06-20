# FILE: backend/app/routes/pharmacist/routes_inventory.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from pydantic import BaseModel

from app.database.session import SessionLocal
from app.database.models import Inventory
from app.utils.jwt_handler import get_current_user
from app.utils.rbac import require_role

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ------------------------------
# DB Dependency
# ------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------
# Pydantic Models 
# ------------------------------
class InventoryIn(BaseModel):
    medicine_name: str
    batch_no: str
    quantity: int
    expiry_date: date


class InventoryOut(BaseModel):
    id: int
    medicine_name: str
    batch_no: str
    quantity: int
    expiry_date: date
    user_id: int

    model_config = {"from_attributes": True}


# ------------------------------
# Add Inventory (FIXED)
# ------------------------------
@router.post("/add")
def add_inventory(
    payload: InventoryIn,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist"))
):
    item = Inventory(
        user_id=user.id,
        medicine_name=payload.medicine_name,
        batch_no=payload.batch_no,
        quantity=payload.quantity,
        expiry_date=payload.expiry_date
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "success": True,
        "message": "Inventory added successfully",
        "data": {"inventory_id": item.id}
    }


# ------------------------------
# Get Inventory (Already FIXED)
# ------------------------------
@router.get("/", response_model=dict)
def get_inventory(
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist"))
):
    items = db.query(Inventory).filter(Inventory.user_id == user.id).all()

    # Convert SQLAlchemy objects → clean dict
    clean_data = []
    for i in items:
        clean_data.append({
            "id": i.id,
            "medicine_name": i.medicine_name,
            "batch_no": i.batch_no,
            "quantity": i.quantity,
            "expiry_date": str(i.expiry_date),
            "user_id": i.user_id
        })

    return {"success": True, "data": clean_data}

# ------------------------------
# Delete Inventory
# ------------------------------
@router.delete("/delete/{item_id}")
def delete_inventory(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist"))
):

    item = db.query(Inventory).filter(
        Inventory.id == item_id,
        Inventory.user_id == user.id
    ).first()

    if not item:
        return {"success": False, "message": "Item not found"}

    db.delete(item)
    db.commit()

    return {"success": True, "message": "Inventory item deleted"}

@router.post("/bulk_add")
def bulk_add_inventory(
    items: List[InventoryIn],
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist"))
):
    success = 0
    for payload in items:
        item = Inventory(
            user_id=user.id,
            medicine_name=payload.medicine_name,
            batch_no=payload.batch_no,
            quantity=payload.quantity,
            expiry_date=payload.expiry_date
        )
        db.add(item)
        success += 1

    db.commit()

    return {"success": True, "added": success}

