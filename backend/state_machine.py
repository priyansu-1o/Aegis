from datetime import datetime, timedelta

VALID_STATUSES = {"pending_caregiver_approval", "approved", "blocked"}


def create_hold(transaction, cooling_off_seconds):
    """Puts a transaction into a pending hold with an expiry time."""
    transaction["status"] = "pending_caregiver_approval"
    transaction["cooling_off_expiry"] = datetime.now() + timedelta(seconds=cooling_off_seconds)
    return transaction


def resolve_hold(transaction, decision):
    """Caregiver resolves a pending transaction. decision: 'approve' or 'block'."""
    if transaction["status"] != "pending_caregiver_approval":
        raise ValueError("Transaction is not pending approval")

    if decision == "approve":
        transaction["status"] = "approved"
        transaction["resolution"] = "caregiver_approved"
    elif decision == "block":
        transaction["status"] = "blocked"
        transaction["resolution"] = "caregiver_blocked"
    else:
        raise ValueError(f"Invalid decision: {decision}")

    return transaction


def check_expiry(transaction):
    """Fail-safe: if cooling-off window passed with no response, default to blocked."""
    if transaction["status"] != "pending_caregiver_approval":
        return transaction

    if datetime.now() >= transaction["cooling_off_expiry"]:
        transaction["status"] = "blocked"
        transaction["resolution"] = "expired_no_response"

    return transaction  

if __name__ == "__main__":
    import time

    tx = {"id": "test1"}
    tx = create_hold(tx, cooling_off_seconds=2)
    print("After hold:", tx["status"])

    tx = resolve_hold(tx, "block")
    print("After block:", tx["status"], tx["resolution"])

    tx2 = {"id": "test2"}
    tx2 = create_hold(tx2, cooling_off_seconds=1)
    time.sleep(2)
    tx2 = check_expiry(tx2)
    print("After expiry:", tx2["status"], tx2["resolution"])