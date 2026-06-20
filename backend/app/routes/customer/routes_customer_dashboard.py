# FILE: backend/app/routes/customer/routes_customer_dashboard.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import os, json

from app.database.session import SessionLocal
from app.database.models import Inventory, MedicinePrice
from app.utils.jwt_handler import get_current_user
from app.utils.blockchain_storage import load_blockchain

router = APIRouter(prefix="/customer", tags=["Customer Dashboard"])

# -----------------------------------------
# DB Session
# -----------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------
# Expiry Status Helper
# -----------------------------------------
def get_expiry_status(expiry_date: date):
    if not expiry_date:
        return "Unknown"

    today = date.today()
    if expiry_date < today:
        return "Expired"
    if expiry_date <= today + timedelta(days=30):
        return "Expiring Soon"
    return "Valid"

# -----------------------------------------
# JSON Blockchain Fallback Loader
# -----------------------------------------
def load_chain_fallback():
    candidates = [
        "app/blockchain/chain.json",
        "app/data/chain.json",
        "app/data/blockchain.json",
        "blockchain_data.json",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "chain" in data:
                        return data["chain"]
                    if isinstance(data, list):
                        return data
            except:
                pass
    return []

def find_blocks(chain, batch_no: str):
    results = []
    bn = batch_no.lower()

    for block in chain:
        try:
            data = block.get("data", {})
            b = (
                data.get("batch_no") or
                data.get("batch") or
                data.get("batchNo")
            )
            if isinstance(b, str) and b.lower() == bn:
                results.append(block)
        except:
            continue
    return results

# =====================================================
#  NEW: BATCH LIST ENDPOINT (for dropdown)
# =====================================================
@router.get("/batches")
def get_all_batches(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Returns distinct batch numbers for History dropdown.
    """
    batches = db.query(Inventory.batch_no).distinct().all()
    batch_list = [b[0] for b in batches]
    return {"success": True, "data": batch_list}

# =====================================================
#  UNIFIED VERIFICATION ENDPOINT
# =====================================================
@router.get("/verify/{batch_no}")
def unified_verify(batch_no: str, customer_price: float = None, db: Session = Depends(get_db), user=Depends(get_current_user)):

    # ---- Load from Old Blockchain ----
    old_chain_blocks = []
    chain_valid = False
    try:
        chain = load_blockchain()
        chain_valid = chain.is_chain_valid()
        for block in chain.chain:
            data = block.data or {}
            if batch_no in {
                data.get("batch_no"),
                data.get("batch"),
                data.get("batchNo"),
            }:
                old_chain_blocks.append(block.__dict__)
    except:
        pass

    # ---- Load from JSON Fallback ----
    json_chain = load_chain_fallback()
    json_blocks = find_blocks(json_chain, batch_no)

    # ---- Determine Validity ----
    validity = "valid" if (json_blocks or old_chain_blocks) else "tampered"

    # ---- Latest Block ----
    latest = json_blocks[-1] if json_blocks else (old_chain_blocks[-1] if old_chain_blocks else None)

    if latest:
        data = latest.get("data", {})
        medicine_name = data.get("medicine_name") or data.get("name")
        manufacturer = data.get("sender") or data.get("manufacturer")
        last_receiver = data.get("receiver")
        timestamp = data.get("timestamp")
        block_hash = latest.get("hash")
    else:
        medicine_name = manufacturer = last_receiver = timestamp = block_hash = None

    # ---- Inventory Lookup ----
    inv = db.query(Inventory).filter(Inventory.batch_no == batch_no).first()

    inv_info = None
    if inv:
        inv_info = {
            "expiry_status": get_expiry_status(inv.expiry_date),
            "expiry_date": inv.expiry_date,
            "stock_qty": inv.quantity,
            "location": getattr(inv, "location", None),
            "pharmacist_id": inv.user_id
        }

    # ---- Pricing Block ----
    price_info = None
    price_check = None

    if medicine_name:
        prices = db.query(MedicinePrice).filter(
            MedicinePrice.medicine_name.ilike(medicine_name)
        ).all()

        if prices:
            mins = [p.threshold_min for p in prices]
            maxs = [p.threshold_max for p in prices]

            global_min = min(mins)
            global_max = max(maxs)

            price_info = {
                "global_min_threshold": global_min,
                "global_max_threshold": global_max,
                "avg_min_threshold": sum(mins) / len(mins),
                "avg_max_threshold": sum(maxs) / len(maxs),
                "raw": [
                    {
                        "id": p.id,
                        "pharmacy_id": getattr(p, "pharmacy_id", None),
                        "min_threshold": p.threshold_min,
                        "max_threshold": p.threshold_max,
                        "notes": p.notes
                    } for p in prices
                ]
            }

            # PRICE CHECK LOGIC
            if customer_price is not None:
                if customer_price < global_min:
                    price_check = {
                        "customer_price": customer_price,
                        "threshold_min": global_min,
                        "threshold_max": global_max,
                        "status": "Price is TOO LOW — suspicious or incorrect entry.",
                        "is_valid": False
                    }
                elif customer_price > global_max:
                    price_check = {
                        "customer_price": customer_price,
                        "threshold_min": global_min,
                        "threshold_max": global_max,
                        "status": "Price is TOO HIGH — overcharged / invalid price.",
                        "is_valid": False
                    }
                else:
                    price_check = {
                        "customer_price": customer_price,
                        "threshold_min": global_min,
                        "threshold_max": global_max,
                        "status": "Price is valid and within prescribed range.",
                        "is_valid": True
                    }

    # ---- Final API Response ----
    return {
        "success": True,
        "data": {
            "validity": validity,
            "chain_valid": chain_valid,
            "batch_no": batch_no,

            "medicine_name": medicine_name,
            "manufacturer": manufacturer,
            "last_receiver": last_receiver,
            "timestamp": timestamp,
            "block_hash": block_hash,

            "inventory": inv_info,
            "price_info": price_info,
            "price_check": price_check,

            "blocks_found": len(json_blocks) + len(old_chain_blocks)
        }
    }

# =====================================================
#  HISTORY ENDPOINT
# =====================================================
@router.get("/history/{batch_no}")
def unified_history(batch_no: str, db: Session = Depends(get_db), user=Depends(get_current_user)):

    if not batch_no:
        raise HTTPException(status_code=400, detail="batch_no required")

    history = []

    # Old chain
    try:
        chain = load_blockchain()
        for block in chain.chain:
            data = block.data or {}
            if batch_no in {
                data.get("batch_no"),
                data.get("batch"),
                data.get("batchNo"),
            }:
                history.append({
                    "sender": data.get("sender") or data.get("manufacturer"),
                    "receiver": data.get("receiver"),
                    "timestamp": data.get("timestamp") or block.timestamp,
                    "block_hash": block.hash,
                    "raw": block.__dict__
                })
    except:
        pass

    # JSON fallback
    json_chain = load_chain_fallback()
    json_blocks = find_blocks(json_chain, batch_no)

    for b in json_blocks:
        data = b.get("data", {})
        history.append({
            "sender": data.get("sender") or data.get("manufacturer"),
            "receiver": data.get("receiver"),
            "timestamp": data.get("timestamp") or b.get("timestamp"),
            "block_hash": b.get("hash"),
            "raw": b
        })

    # Sort timeline
    def sort_key(item):
        t = item.get("timestamp")
        try:
            if isinstance(t, (int, float)):
                return float(t)
            return datetime.fromisoformat(t).timestamp()
        except:
            return 9999999999

    history.sort(key=sort_key)

    return {
        "success": True,
        "data": {
            "batch_no": batch_no,
            "count": len(history),
            "timeline": history
        }
    }
