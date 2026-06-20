from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database.session import get_db
from app.database.models import MedicinePrice

router = APIRouter(prefix="/prices", tags=["Pharmacist – Prices"])

# -----------------------------------------
# 1) UPDATE OR ADD NEW PRICE THRESHOLD
# -----------------------------------------
@router.post("/update")
def update_price_threshold(data: dict, db: Session = Depends(get_db)):

    medicine_name = data.get("medicine_name", "").lower()
    batch_no = data.get("batch_no", "").lower()
    min_t = data.get("min_threshold")
    max_t = data.get("max_threshold")
    notes = data.get("notes", "")

    if not medicine_name:
        raise HTTPException(status_code=400, detail="Medicine name is required")

    # find entry by medicine or batch number (if provided)
    existing = db.query(MedicinePrice).filter(
        MedicinePrice.medicine_name == medicine_name
    ).first()

    if existing:
        existing.threshold_min = min_t
        existing.threshold_max = max_t
        existing.notes = notes
        existing.last_updated = datetime.utcnow()
    else:
        new_entry = MedicinePrice(
            medicine_name=medicine_name,
            batch_no=batch_no,
            threshold_min=min_t,
            threshold_max=max_t,
            notes=notes,
            last_updated=datetime.utcnow()
        )
        db.add(new_entry)

    db.commit()
    return {"success": True, "message": "Price threshold saved successfully."}


# -----------------------------------------
# 2) GET PRICE THRESHOLD BY MEDICINE NAME
# -----------------------------------------
@router.get("/get")
def get_price_threshold(medicine_name: str, db: Session = Depends(get_db)):
    medicine_name = medicine_name.lower()

    results = db.query(MedicinePrice).filter(
        MedicinePrice.medicine_name == medicine_name
    ).all()

    if not results:
        return {
            "success": False,
            "data": {"raw": []},
            "message": f"No thresholds found for {medicine_name}"
        }

    formatted = []
    for r in results:
        formatted.append({
            "medicine_name": r.medicine_name,
            "batch_no": r.batch_no,
            "min_threshold": r.threshold_min,
            "max_threshold": r.threshold_max,
            "notes": r.notes,
            "last_updated": r.last_updated
        })

    return {
        "success": True,
        "data": {
            "raw": formatted
        }
    }
