import os
from dotenv import load_dotenv

load_dotenv()

RISK_THRESHOLD = int(os.getenv("RISK_THRESHOLD", 50))
COOLING_OFF_SECONDS = int(os.getenv("COOLING_OFF_SECONDS", 60))

FLAG_WORDS = [
    "rbi",
    "police",
    "cbi",
    "customs",
    "verification",
    "safe account",
    "government",
    "digital arrest"
]