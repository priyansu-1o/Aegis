from datetime import datetime, timedelta

RISK_THRESHOLD = 50

FLAG_WORDS = ["rbi", "police", "cbi", "customs", "verification",
              "safe account", "government", "digital arrest"]

def is_new_payee(transaction, user):
    """Returns True if this payee has never been paid before."""
    return transaction["payee_account"] not in user["known_payees"]


##remember to change this later
def is_large_amount(transaction, user, multiplier=10):
    """Returns True if amount is far above the user's typical transaction size."""
    avg = user.get("avg_transaction_amount", 5000)  # default if user has no history yet
    return transaction["amount"] > avg * multiplier

def is_recent_fd_break(transaction, window_minutes=30):
    """Returns True if an FD was broken within `window_minutes` before this transfer."""
    if not transaction.get("preceded_by_fd_break"):
        return False

    fd_break_time = transaction.get("fd_break_timestamp")
    if not fd_break_time:
        return False  # malformed data — don't crash, just don't flag

    if isinstance(fd_break_time, str):
        try:
            fd_break_time = datetime.fromisoformat(fd_break_time)
        except (ValueError, TypeError):
            return False

    elapsed = datetime.now() - fd_break_time
    return elapsed <= timedelta(minutes=window_minutes)

def is_odd_hour(transaction):
    """Returns True if the transaction happens outside normal waking hours."""
    timestamp = transaction.get("timestamp")
    if not timestamp:
        timestamp = datetime.now()
    elif isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except (ValueError, TypeError):
            timestamp = datetime.now()

    hour = timestamp.hour
    return hour < 6 or hour > 22

def has_flag_words(transaction):
    """Returns True if the transfer note contains scam-associated language."""
    note = (transaction.get("note") or "").lower()
    return any(word in note for word in FLAG_WORDS)

def is_high_velocity(user, window_minutes=10, count_threshold=3):
    """Returns True if the user has made several transactions in a short window —
    common when a scammer keeps a victim on the phone making repeated transfers."""
    recent_timestamps = user.get("recent_transactions", [])
    now = datetime.now()

    recent_count = sum(
        1 for ts in recent_timestamps
        if now - ts <= timedelta(minutes=window_minutes)
    )
    return recent_count >= count_threshold

WEIGHTS = {
    "new_payee": 30,
    "large_amount": 25,
    "recent_fd_break": 35,
    "odd_hour": 15,
    "flag_words": 40,
    "high_velocity": 20,
}


def calculate_risk(transaction, user):
    """Runs all rules against a transaction and returns a total score + reasons."""
    score = 0
    reasons = []

    if is_new_payee(transaction, user):
        score += WEIGHTS["new_payee"]
        reasons.append("New payee")

    if is_large_amount(transaction, user):
        score += WEIGHTS["large_amount"]
        reasons.append("Unusually large amount")

    if is_recent_fd_break(transaction):
        score += WEIGHTS["recent_fd_break"]
        reasons.append("Fixed deposit broken minutes before transfer")

    if is_odd_hour(transaction):
        score += WEIGHTS["odd_hour"]
        reasons.append("Off-hours transaction")

    if has_flag_words(transaction):
        score += WEIGHTS["flag_words"]
        reasons.append("Suspicious keyword in transfer note")

    if is_high_velocity(user):
        score += WEIGHTS["high_velocity"]
        reasons.append("Multiple transfers in short window")

    return {
        "score": score,
        "reasons": reasons,
        "is_high_risk": score >= RISK_THRESHOLD,
    }

def evaluate_transaction(transaction, user):
    """Full decision: risk score + what action the system should take."""
    risk = calculate_risk(transaction, user)

    if risk["is_high_risk"]:
        action = "hold_for_approval"
    else:
        action = "auto_approve"

    return {**risk, "action": action}   

if __name__ == "__main__":
    now = datetime.now()
    user = {
        "known_payees": {"son_rahul"},
        "avg_transaction_amount": 5000,
        "recent_transactions": [],
    }

    edge_cases = {
        "New payee + odd hour only (expect: NOT held, 45)": {
            "payee_account": "stranger", "amount": 3000, "note": "",
            "preceded_by_fd_break": False, "timestamp": now.replace(hour=23),
        },
        "New payee + large amount (expect: borderline, 55)": {
            "payee_account": "stranger", "amount": 100000, "note": "",
            "preceded_by_fd_break": False, "timestamp": now.replace(hour=14),
        },
        "Large amount + odd hour, known payee (expect: NOT held, 40)": {
            "payee_account": "son_rahul", "amount": 100000, "note": "",
            "preceded_by_fd_break": False, "timestamp": now.replace(hour=23),
        },
        "Keyword alone, known payee, daytime (expect: NOT held, 40)": {
            "payee_account": "son_rahul", "amount": 3000, "note": "RBI verification",
            "preceded_by_fd_break": False, "timestamp": now.replace(hour=14),
        },
        "FD break + keyword only, known payee (expect: held, 75)": {
            "payee_account": "son_rahul", "amount": 3000, "note": "safe account transfer",
            "preceded_by_fd_break": True, "fd_break_timestamp": now - timedelta(minutes=2),
            "timestamp": now.replace(hour=14),
        },
    }

    for label, tx in edge_cases.items():
        result = calculate_risk(tx, user)
        print(f"\n{label}")
        print(f"  Actual score: {result['score']} | Held: {result['is_high_risk']}")