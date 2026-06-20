# FILE: backend/app/routes/manufacturer/routes_blockchain.py

from fastapi import APIRouter, Depends, HTTPException
from app.utils.blockchain_storage import load_blockchain, save_blockchain
from app.utils.qr_generator import generate_qr
from app.utils.jwt_handler import get_current_user
from app.utils.rbac import require_role
import time

router = APIRouter(prefix="/blockchain", tags=["Blockchain"])


@router.post("/add_transaction")
def add_transaction(
    batch_no: str,
    medicine_name: str,
    receiver: str,
    user=Depends(require_role("manufacturer"))
):
    chain = load_blockchain()

    data = {
        "batch_no": batch_no,
        "medicine_name": medicine_name,
        "sender": user.name,
        "receiver": receiver,
        "timestamp": time.time()
    }

    new_block = chain.add_block(data)
    save_blockchain(chain)

    qr_path = generate_qr(batch_no, medicine_name, new_block.hash)

    return {
        "success": True,
        "message": "Batch transaction added successfully",
        "data": {
            "block_hash": new_block.hash,
            "qr_path": qr_path
        }
    }


@router.get("/chain")
def get_chain(user=Depends(get_current_user)):
    chain = load_blockchain()
    return {"success": True, "data": [block.__dict__ for block in chain.chain]}


@router.get("/verify/{batch_no}")
def verify_batch(batch_no: str, user=Depends(get_current_user)):
    chain = load_blockchain()

    history = [b.__dict__ for b in chain.chain if b.data.get("batch_no") == batch_no]

    if not history:
        raise HTTPException(status_code=404, detail="Batch not found")

    return {
        "success": True,
        "valid": chain.is_chain_valid(),
        "data": history
    }

@router.delete("/delete/{index}")
def delete_block(index: int, user=Depends(require_role("manufacturer"))):
    """
    HARD delete a block (by index). This will remove the block,
    re-index the remaining blocks, recompute their hashes, and save the chain.
    """
    chain = load_blockchain()

    # chain.chain is a list of Block objects (see app.utils.blockchain_handler.Block)
    blocks = chain.chain

    # Validate index
    if index < 0 or index >= len(blocks):
        raise HTTPException(status_code=404, detail="Block index not found")

    # Remove the block
    blocks.pop(index)

    # Rebuild chain indexes + previous_hash + hashes (use Block.compute_hash())
    for i, block in enumerate(blocks):
        block.index = i
        block.previous_hash = blocks[i - 1].hash if i > 0 else "0"
        # recompute this block's hash using its own compute_hash() method
        block.hash = block.compute_hash()

    # Persist
    save_blockchain(chain)

    return {"success": True, "message": "Block deleted successfully"}