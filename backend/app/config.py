from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

print("Loaded ENV from:", ENV_PATH)
print("HF Key Loaded:", os.getenv("HUGGINGFACE_API_KEY"))
