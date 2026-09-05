"""
database.py — Supabase storage layer
====================================
All application data is stored directly in Supabase.
"""

from config import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY are required. "
        "AEGIS no longer supports local SQLite storage."
    )

try:
    from supabase import create_client as _create_client
except ImportError as exc:
    raise RuntimeError(
        "The supabase package is required. Install backend/requirements.txt."
    ) from exc

_USE_SUPABASE = True


def using_supabase() -> bool:
    """Returns True because Supabase is the only supported storage backend."""
    return True

# ── Supabase implementation ──────────────────────────────────────────────────

if _USE_SUPABASE:
    from datetime import datetime, timedelta
    from config import VELOCITY_WINDOW_MINUTES

    _supabase_client = None

    def _client():
        global _supabase_client
        if _supabase_client is None:
            _supabase_client = _create_client(SUPABASE_URL, SUPABASE_KEY)
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
        {"user_id": 1,   "name": "Priya (Caregiver)", "role": "caregiver", "caregiver_id": None, "baseline_avg_tx": 0.0},
        {"user_id": 2,   "name": "Meena Sharma",       "role": "senior",    "caregiver_id": 1,    "baseline_avg_tx": 2000.0},
        {"user_id": 101, "name": "Ramesh (Senior)",    "role": "senior",    "caregiver_id": 201,  "baseline_avg_tx": 2000.0},
        {"user_id": 201, "name": "Priya (Caregiver)",  "role": "caregiver", "caregiver_id": None, "baseline_avg_tx": 0.0},
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
        rows = _client().table("users").select("*").eq("user_id", user_id).execute().data
        return _row(rows[0]) if rows else None

    def get_user_by_email(email):
        rows = _client().table("users").select("*").eq("email", email).execute().data
        return _row(rows[0]) if rows else None

    def set_password_hash(user_id, password_hash):
        _client().table("users").update({"password_hash": password_hash}).eq("user_id", user_id).execute()

    def create_user(name, email, password_hash, role):
        latest = (
            _client().table("users")
            .select("user_id")
            .order("user_id", desc=True)
            .limit(1)
            .execute()
            .data or []
        )
        next_user_id = int(latest[0]["user_id"]) + 1 if latest else 1
        rows = _client().table("users").insert({
            "user_id": next_user_id,
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "caregiver_id": None,
            "baseline_avg_tx": 0.0 if role == "caregiver" else 5000.0,
            "balance": 0.0 if role == "caregiver" else 845000.0,
        }).execute().data
        if not rows:
            raise RuntimeError("Could not create account")
        return dict(rows[0])

    def get_all_users():
        rows = _client().table("users").select("*").order("user_id").execute().data
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

    def create_transaction(sender_id, payee_name, payee_account, amount,
                           risk_score, risk_reasons, status, note="",
                           resolution=None, cooling_off_expiry=None):
        payload = {
            "sender_id": sender_id, "payee_name": payee_name,
            "payee_account": payee_account, "amount": amount, "note": note,
            "risk_score": risk_score, "risk_reasons": _reasons_to_str(risk_reasons),
            "status": status, "resolution": resolution,
            "cooling_off_expiry": _iso(cooling_off_expiry),
        }
        rows = _client().table("transactions").insert(payload).execute().data
        if not rows:
            raise RuntimeError("Supabase insert did not return a transaction row")
        return rows[0]["tx_id"]

    def _attach_sender(row, user_cache=None):
        """Attach sender_name to a transaction row.
        If user_cache (dict of user_id->user) is provided, no extra DB call is made.
        """
        if not row:
            return None
        tx = dict(row)
        sender_id = tx.get("sender_id")
        if user_cache is not None:
            sender = user_cache.get(sender_id)
        else:
            sender = get_user(sender_id)
        tx["sender_name"] = sender["name"] if sender else None
        return tx

    def _fetch_user_cache(sender_ids):
        """Batch-fetch all users for the given sender_ids in ONE Supabase call.
        Returns a dict { user_id: user_row }.
        """
        if not sender_ids:
            return {}
        unique_ids = list(set(sender_ids))
        rows = (
            _client().table("users").select("*")
            .in_("user_id", unique_ids)
            .execute().data or []
        )
        return {row["user_id"]: dict(row) for row in rows}

    def get_transaction(tx_id):
        rows = _client().table("transactions").select("*").eq("tx_id", tx_id).execute().data
        return _attach_sender(rows[0]) if rows else None

    def get_pending_transactions_for_caregiver(caregiver_id):
        # 1 query: all pending transactions
        rows = (
            _client().table("transactions").select("*")
            .eq("status", "pending_caregiver_approval")
            .order("created_at", desc=True).execute().data or []
        )
        if not rows:
            return []
        # 1 query: all senders in one batch
        sender_ids = [r.get("sender_id") for r in rows if r.get("sender_id")]
        user_cache = _fetch_user_cache(sender_ids)
        # Filter to only this caregiver's seniors
        pending = []
        for row in rows:
            sender = user_cache.get(row.get("sender_id"))
            if sender and sender.get("caregiver_id") == caregiver_id:
                tx = _attach_sender(row, user_cache)
                pending.append(tx)
        return pending

    def get_transactions_by_sender(sender_id):
        # 1 query: all transactions for this sender
        rows = (
            _client().table("transactions").select("*")
            .eq("sender_id", sender_id).order("created_at", desc=True)
            .execute().data or []
        )
        if not rows:
            return []
        # 1 query: sender user (single user, not N)
        user_cache = _fetch_user_cache([sender_id])
        return [_attach_sender(row, user_cache) for row in rows]

    def update_transaction_status(tx_id, new_status):
        _client().table("transactions").update({"status": new_status}).eq("tx_id", tx_id).execute()

    def set_transaction_hold(tx_id, cooling_off_expiry):
        _client().table("transactions").update({
            "status": "pending_caregiver_approval",
            "cooling_off_expiry": _iso(cooling_off_expiry),
        }).eq("tx_id", tx_id).execute()

    def set_transaction_resolution(tx_id, new_status, resolution):
        # ── Race-condition guard ───────────────────────────────────────────────
        # Only update when the transaction is still pending.  This prevents a
        # check_expiry pass from overwriting a manual caregiver resolve (or
        # vice-versa) when both fire within the same polling window.
        _client().table("transactions").update({
            "status": new_status,
            "resolution": resolution,
        }).eq("tx_id", tx_id).eq("status", "pending_caregiver_approval").execute()

    def get_known_payees(sender_id):
        rows = (
            _client().table("transactions").select("payee_account")
            .eq("sender_id", sender_id).eq("status", "approved")
            .execute().data or []
        )
        return {row["payee_account"] for row in rows if row.get("payee_account")}

    def get_recent_transaction_timestamps(sender_id, minutes=10):
        cutoff = datetime.now() - timedelta(minutes=minutes)
        rows = (
            _client().table("transactions").select("created_at")
            .eq("sender_id", sender_id).gte("created_at", cutoff.isoformat())
            .order("created_at", desc=True).execute().data or []
        )
        timestamps = []
        for row in rows:
            val = row.get("created_at")
            if not val:
                continue
            if isinstance(val, datetime):
                timestamps.append(val)
                continue
            text = str(val).replace("Z", "")
            try:
                timestamps.append(datetime.fromisoformat(text))
            except ValueError:
                pass
        return timestamps

    def log_audit_event(
        tx_id,
        event,
        actor_id=None,
        actor_role=None,
        risk_score=None,
        details=None,
    ):
        _client().table("audit_log").insert({
            "tx_id":      tx_id,
            "event":      event,
            "actor_id":   actor_id,
            "actor_role": actor_role,
            "risk_score": risk_score,
            "details":    details,
        }).execute()

    def get_audit_log(tx_id):
        rows = (
            _client().table("audit_log").select("*")
            .eq("tx_id", tx_id).order("log_id").execute().data or []
        )
        return [dict(row) for row in rows]

    def link_caregiver_to_senior(senior_id, caregiver_id):
        """Set senior.caregiver_id = caregiver_id in Supabase."""
        _client().table("users").update(
            {"caregiver_id": caregiver_id}
        ).eq("user_id", senior_id).eq("role", "senior").execute()

    def update_user_balance(user_id, amount_to_deduct):
        user = get_user(user_id)
        if not user: return
        new_balance = max(0, float(user.get("balance", 0)) - amount_to_deduct)
        _client().table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()

    if __name__ == "__main__":
        init_db()
        print("Backend: supabase")
