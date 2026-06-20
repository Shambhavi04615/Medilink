import qrcode
import os
import json
from datetime import datetime

QR_DIR = "app/qrcodes"
os.makedirs(QR_DIR, exist_ok=True)


def generate_qr(batch_no: str, medicine_name: str, block_hash: str) -> str:
    """
    Generate QR code image for a medicine batch.
    """
    qr_data = {
        "batch_no": batch_no,
        "medicine_name": medicine_name,
        "hash": block_hash,
        "timestamp": datetime.now().isoformat()
    }

    img = qrcode.make(json.dumps(qr_data))
    file_path = f"{QR_DIR}/{batch_no}.png"
    img.save(file_path)
    return file_path
