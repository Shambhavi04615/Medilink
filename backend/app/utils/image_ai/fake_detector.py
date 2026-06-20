import cv2
import numpy as np
from PIL import Image
from app.utils.image_ai.hf_client import classify_image


def extract_qr(image_path: str):
    img = cv2.imread(image_path)

    if img is None:
        return {"qr_found": False, "qr_data": None}

    detector = cv2.QRCodeDetector()

    data, points, _ = detector.detectAndDecode(img)

    if data:
        return {"qr_found": True, "qr_data": data}

    return {"qr_found": False, "qr_data": None}


def generate_fake_score(image_path: str):
    # Convert to PIL image
    pil_img = Image.open(image_path)

    hf_result = classify_image(pil_img)

    # Confidence score (fake probability)
    score = hf_result.get("fraud_likelihood", 0.0)

    return {
        "authenticity_score": round(1 - score, 2),
        "is_fake": score > 0.5,
        "raw": hf_result
    }
