"""
Supabase persistence layer.

Expected Supabase tables (same columns as SQLite):

  users(user_id, name, role, caregiver_id, baseline_avg_tx)
  transactions(
      tx_id, sender_id, payee_name, payee_account, amount, note,
      risk_score, risk_reasons, status, resolution, cooling_off_expiry, created_at
  )
"""
from datetime import datetime, timedelta

from config import SUPABASE_URL, SUPABASE_KEY, VELOCITY_WINDOW_MINUTES

_supabase_client = None


def using_supabase():
    return True


def _client():
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "Supabase is required. Set SUPABASE_URL and SUPABASE_KEY "
                "(or SUPABASE_SERVICE_ROLE_KEY) in backend/.env."
            )
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _row(data):
    return dict(data) if data else None


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def _reasons_to_str(risk_reasons):
    if isinstance(risk_reasons, list):
        return ", ".join(risk_reasons)
    return str(risk_reasons or "")


DEMO_USERS = [
    {
        "user_id": 1,
        "name": "Priya (Caregiver)",
        "role": "caregiver",
        "caregiver_id": None,
        "baseline_avg_tx": 0.0,
    },
    {
        "user_id": 2,
        "name": "Meena Sharma",
        "role": "senior",
        "caregiver_id": 1,
        "baseline_avg_tx": 2000.0,
    },
    {
        "user_id": 101,
        "name": "Ramesh (Senior)",
        "role": "senior",
        "caregiver_id": 201,
        "baseline_avg_tx": 2000.0,
    },
    {
        "user_id": 201,
        "name": "Priya (Caregiver)",
        "role": "caregiver",
        "caregiver_id": None,
        "baseline_avg_tx": 0.0,
    },
]


def init_db():
    client = _client()
    for user in DEMO_USERS:
        existing = (
            client.table("users")
            .select("user_id")
            .eq("user_id", user["user_id"])
            .execute()
            .data
        )
        if not existing:
            client.table("users").insert(user).execute()
    print("Supabase initialization complete.")


def get_user(user_id):
    rows = (
        _client()
        .table("users")
        .select("*")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    return _row(rows[0]) if rows else None


def get_all_users():
    rows = (
        _client()
        .table("users")
        .select("*")
        .order("user_id")
        .execute()
        .data
    )
    return [dict(row) for row in (rows or [])]


def get_risk_user_data(sender_id):
    user = get_user(sender_id)
    if not user:
        return None
    return {
        "user_id": sender_id,
        "known_payees": get_known_payees(sender_id),
        "avg_transaction_amount": user.get("baseline_avg_tx") or 5000.0,
        "recent_transactions": get_recent_transaction_timestamps(
            sender_id, minutes=VELOCITY_WINDOW_MINUTES
        ),
    }


def create_transaction(
    sender_id,
    payee_name,
    payee_account,
    amount,
    risk_score,
    risk_reasons,
    status,
    note="",
    resolution=None,
    cooling_off_expiry=None,
):
    payload = {
        "sender_id": sender_id,
        "payee_name": payee_name,
        "payee_account": payee_account,
        "amount": amount,
        "note": note,
        "risk_score": risk_score,
        "risk_reasons": _reasons_to_str(risk_reasons),
        "status": status,
        "resolution": resolution,
        "cooling_off_expiry": _iso(cooling_off_expiry),
    }
    rows = _client().table("transactions").insert(payload).execute().data
    if not rows:
        raise RuntimeError("Supabase insert did not return a transaction row")
    return rows[0]["tx_id"]


def _attach_sender(row):
    if not row:
        return None
    tx = dict(row)
    sender = get_user(tx.get("sender_id"))
    tx["sender_name"] = sender["name"] if sender else None
    return tx


def get_transaction(tx_id):
    rows = (
        _client()
        .table("transactions")
        .select("*")
        .eq("tx_id", tx_id)
        .execute()
        .data
    )
    return _attach_sender(rows[0]) if rows else None


def get_pending_transactions_for_caregiver(caregiver_id):
    rows = (
        _client()
        .table("transactions")
        .select("*")
        .eq("status", "pending_caregiver_approval")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    pending = []
    for row in rows:
        tx = _attach_sender(row)
        sender = get_user(row.get("sender_id"))
        if sender and sender.get("caregiver_id") == caregiver_id:
            pending.append(tx)
    return pending


def get_transactions_by_sender(sender_id):
    rows = (
        _client()
        .table("transactions")
        .select("*")
        .eq("sender_id", sender_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return [_attach_sender(row) for row in rows]


def update_transaction_status(tx_id, new_status):
    _client().table("transactions").update({"status": new_status}).eq("tx_id", tx_id).execute()


def set_transaction_hold(tx_id, cooling_off_expiry):
    _client().table("transactions").update({
        "status": "pending_caregiver_approval",
        "cooling_off_expiry": _iso(cooling_off_expiry),
    }).eq("tx_id", tx_id).execute()


def set_transaction_resolution(tx_id, new_status, resolution):
    _client().table("transactions").update({
        "status": new_status,
        "resolution": resolution,
    }).eq("tx_id", tx_id).execute()


def get_known_payees(sender_id):
    rows = (
        _client()
        .table("transactions")
        .select("payee_account")
        .eq("sender_id", sender_id)
        .eq("status", "approved")
        .execute()
        .data
        or []
    )
    return {row["payee_account"] for row in rows if row.get("payee_account")}


def get_recent_transaction_timestamps(sender_id, minutes=10):
    cutoff = datetime.now() - timedelta(minutes=minutes)
    rows = (
        _client()
        .table("transactions")
        .select("created_at")
        .eq("sender_id", sender_id)
        .gte("created_at", cutoff.isoformat())
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    timestamps = []
    for row in rows:
        created_at_val = row.get("created_at")
        if not created_at_val:
            continue
        if isinstance(created_at_val, datetime):
            timestamps.append(created_at_val)
            continue
        text = str(created_at_val).replace("Z", "")
        try:
            timestamps.append(datetime.fromisoformat(text))
        except ValueError:
            pass
    return timestamps


if __name__ == "__main__":
    init_db()
    print("Backend: supabase")