import requests
import os
from io import BytesIO
from PIL import Image

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
HF_MODEL = "falconsai/fake-image-detection"  # or any image classifier model

def classify_image(pil_image):
    """
    Sends the image to HuggingFace Inference API and receives fake/real score.
    """
    if HUGGINGFACE_API_KEY is None:
        return {"error": "Missing HUGGINGFACE_API_KEY in .env"}

    # Convert PIL image to bytes
    buf = BytesIO()
    pil_image.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}

    response = requests.post(
        f"https://api-inference.huggingface.co/models/{HF_MODEL}",
        headers=headers,
        data=img_bytes,
        timeout=60
    )

    if response.status_code != 200:
        return {"error": "HF API error", "status": response.status_code, "body": response.text}

    try:
        result = response.json()

        # Fake image detector typically returns probabilities
        # Example: {"fake": 0.78, "real": 0.22}

        score = 0.0

        # Attempt to extract some fake-likelihood score
        if isinstance(result, list) and len(result) > 0 and "label" in result[0]:
            # Classification style: [{"label": "...", "score": 0.98}]
            for item in result:
                if "fake" in item["label"].lower():
                    score = item["score"]
        elif isinstance(result, dict):
            score = result.get("score", 0.0)

        return {
            "fraud_likelihood": score,
            "raw": result
        }

    except Exception as e:
        return {"error": str(e)}
