"""
Kavach — Central configuration
All tuneable constants live here so app.py, risk_engine.py, and state_machine.py
can import them instead of hard-coding magic numbers.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY", "").strip()
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
)

# ── Risk engine ──────────────────────────────────────────────────────────────
RISK_THRESHOLD = 50          # score >= this → hold for caregiver approval

FLAG_WORDS = [
    "rbi", "police", "cbi", "customs", "verification",
    "safe account", "government", "digital arrest",
]

WEIGHTS = {
    "new_payee":      30,
    "large_amount":   55,   # raised: large transfers are always suspicious regardless of payee
    "recent_fd_break": 35,
    "odd_hour":       15,
    "flag_words":     40,
    "high_velocity":  20,
}

# is_large_amount: flag if amount > avg * LARGE_AMOUNT_MULTIPLIER
LARGE_AMOUNT_MULTIPLIER = 2

# is_recent_fd_break: FD break within this window is suspicious
FD_BREAK_WINDOW_MINUTES = 30

# is_high_velocity: >= COUNT transfers within WINDOW is suspicious
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_COUNT_THRESHOLD = 3

# ── State machine ─────────────────────────────────────────────────────────────
# How long the caregiver has to respond before the transaction auto-blocks
COOLING_OFF_SECONDS = 300    # 5 minutes default; override per-request if needed
