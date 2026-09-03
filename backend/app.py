from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, emit as socket_emit
from datetime import datetime

import bcrypt

from config import COOLING_OFF_SECONDS
from database import (
    init_db,
    using_supabase,
    get_user,
    get_user_by_email,
    get_all_users,
    get_risk_user_data,
    create_transaction,
    get_transaction,
    get_pending_transactions_for_caregiver,
    get_transactions_by_sender,
    set_transaction_hold,
    set_transaction_resolution,
    log_audit_event,
    get_audit_log,
)
from risk_engine import evaluate_transaction
from state_machine import create_hold, check_expiry, resolve_hold
from auth import (
    generate_token,
    decode_token,
    require_auth,
    require_role,
    set_auth_cookie,
    clear_auth_cookie,
    COOKIE_NAME,
)


app = Flask(__name__)

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]
CORS(app, supports_credentials=True, origins=CORS_ORIGINS)

# ── SocketIO ──────────────────────────────────────────────────────────────────
# async_mode='threading' — works with the standard WSGI Flask dev server.
# For production, swap for eventlet or gevent.
socketio = SocketIO(
    app,
    cors_allowed_origins=CORS_ORIGINS,
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

init_db()

API_STATUS = {
    "pending_caregiver_approval": "PENDING_APPROVAL",
    "approved":                   "APPROVED",
    "blocked":                    "BLOCKED",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1]
    return text


def _parse_reasons(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def public_transaction(row):
    if not row:
        return None
    return {
        "tx_id":              row["tx_id"],
        "sender_id":          row["sender_id"],
        "sender":             {"name": row.get("sender_name")},
        "payee_name":         row["payee_name"],
        "payee_account":      row["payee_account"],
        "amount":             row["amount"],
        "note":               row.get("note") or "",
        "risk_score":         row.get("risk_score"),
        "risk_reasons":       _parse_reasons(row.get("risk_reasons")),
        "status":             API_STATUS.get(row["status"], row["status"]),
        "resolution":         row.get("resolution"),
        "cooling_off_expiry": _to_iso(row.get("cooling_off_expiry")),
        "created_at":         _to_iso(row.get("created_at")),
    }


def apply_expiry(tx):
    if not tx:
        return None
    original_status     = tx.get("status")
    original_resolution = tx.get("resolution")
    updated = check_expiry(dict(tx))
    if (
        updated.get("status")     != original_status
        or updated.get("resolution") != original_resolution
    ):
        set_transaction_resolution(
            updated["tx_id"],
            updated["status"],
            updated.get("resolution"),
        )
        # ── Audit: expiry auto-block ──────────────────────────────────────────
        if updated.get("resolution") == "expired_no_response":
            try:
                log_audit_event(
                    tx_id=updated["tx_id"],
                    event="expired_no_response",
                    actor_id=None,
                    actor_role="system",
                    details="Cooling-off window elapsed; transaction auto-blocked",
                )
                # Notify senior's room that their tx was expired
                sender_id = updated.get("sender_id")
                if sender_id:
                    socketio.emit(
                        "tx_update",
                        {"tx_id": updated["tx_id"], "status": "BLOCKED", "resolution": "expired_no_response"},
                        room=f"user_{sender_id}",
                    )
            except Exception:
                pass  # never let audit/socket errors break the response
    return updated


def error(message, status_code):
    return jsonify({"error": message}), status_code


# ── Socket.IO events ──────────────────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    """
    Verify the JWT cookie on every WebSocket connection.
    Put the client into their personal room: user_{user_id}
    so we can push targeted events.
    """
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    if not payload:
        return False                  # reject the connection
    join_room(f"user_{payload['sub']}")


@socketio.on("disconnect")
def handle_disconnect():
    pass


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    if not data:
        return error("JSON body required", 400)

    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")
    if not email or not password:
        return error("email and password are required", 400)

    user = get_user_by_email(email)
    if not user or not user.get("password_hash"):
        return error("Invalid email or password", 401)

    stored_hash = user["password_hash"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()

    if not bcrypt.checkpw(password.encode(), stored_hash):
        return error("Invalid email or password", 401)

    token    = generate_token(user)
    response = jsonify({
        "user": {
            "user_id": user["user_id"],
            "name":    user["name"],
            "role":    user["role"],
        }
    })
    set_auth_cookie(response, token)
    return response, 200


@app.route("/api/logout", methods=["POST"])
def api_logout():
    response = jsonify({"message": "Logged out"})
    clear_auth_cookie(response)
    return response, 200


@app.route("/api/me", methods=["GET"])
@require_auth
def api_me():
    user = get_user(g.current_user["user_id"])
    if not user:
        return error("User not found", 404)
    return jsonify({
        "user": {
            "user_id": user["user_id"],
            "name":    user["name"],
            "role":    user["role"],
            "email":   user.get("email"),
        }
    }), 200


# ── Public ────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":  "ok",
        "storage": "supabase" if using_supabase() else "sqlite",
    }), 200


# ── Senior endpoints ──────────────────────────────────────────────────────────

@app.route("/api/transfer", methods=["POST"])
@require_auth
@require_role("senior")
def api_transfer():
    try:
        data = request.get_json()
        if not data:
            return error("JSON body required", 400)

        sender_id     = g.current_user["user_id"]
        payee_name    = data.get("payee_name")
        payee_account = data.get("payee_account")
        amount        = data.get("amount")
        note          = data.get("note", "")

        if not payee_name:
            return error("payee_name is required", 400)
        if not payee_account:
            return error("payee_account is required", 400)
        if amount is None:
            return error("amount is required", 400)
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return error("amount must be numeric", 400)
        if amount <= 0:
            return error("Amount must be greater than zero", 400)

        user = get_user(sender_id)
        if not user:
            return error("Sender not found", 404)

        risk_user = get_risk_user_data(sender_id)
        tx_input  = {
            "payee_name":           payee_name,
            "payee_account":        payee_account,
            "amount":               amount,
            "note":                 note,
            "timestamp":            datetime.now(),
            "preceded_by_fd_break": data.get("preceded_by_fd_break", False),
            "fd_break_timestamp":   data.get("fd_break_timestamp"),
        }
        risk = evaluate_transaction(tx_input, risk_user)

        if risk["action"] == "hold_for_approval":
            status, resolution = "pending_caregiver_approval", None
        else:
            status, resolution = "approved", "auto_approved"

        tx_id = create_transaction(
            sender_id=sender_id, payee_name=payee_name,
            payee_account=payee_account, amount=amount,
            risk_score=risk["score"], risk_reasons=risk["reasons"],
            status=status, note=note, resolution=resolution,
        )

        # ── Audit: created ────────────────────────────────────────────────────
        log_audit_event(
            tx_id=tx_id, event="transaction_created",
            actor_id=sender_id, actor_role="senior",
            risk_score=risk["score"],
            details=f"payee={payee_name}, amount={amount}",
        )

        stored = get_transaction(tx_id)

        if status == "pending_caregiver_approval":
            stored = create_hold(stored, COOLING_OFF_SECONDS)
            set_transaction_hold(tx_id, stored["cooling_off_expiry"])
            stored = get_transaction(tx_id)

            log_audit_event(
                tx_id=tx_id, event="hold_created",
                actor_id=None, actor_role="system",
                risk_score=risk["score"],
                details=f"reasons={', '.join(risk['reasons'])}",
            )

            # Notify the caregiver of the new pending item
            caregiver_id = user.get("caregiver_id")
            if caregiver_id:
                socketio.emit(
                    "pending_update",
                    {"tx_id": tx_id, "sender_name": user["name"], "amount": amount},
                    room=f"user_{caregiver_id}",
                )
        else:
            log_audit_event(
                tx_id=tx_id, event="auto_approved",
                actor_id=None, actor_role="system",
                risk_score=risk["score"],
            )
            # Notify the senior so their status screen updates immediately
            socketio.emit(
                "tx_update",
                {"tx_id": tx_id, "status": "APPROVED", "resolution": "auto_approved"},
                room=f"user_{sender_id}",
            )

        return jsonify({"transaction": public_transaction(stored), "risk": risk}), 201

    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/transactions/<int:tx_id>", methods=["GET"])
@require_auth
def api_get_transaction(tx_id):
    try:
        transaction = apply_expiry(get_transaction(tx_id))
        if not transaction:
            return error("Transaction not found", 404)

        user = g.current_user
        if user["role"] == "senior":
            if transaction["sender_id"] != user["user_id"]:
                return error("Access denied", 403)
        elif user["role"] == "caregiver":
            sender = get_user(transaction["sender_id"])
            if not sender or sender.get("caregiver_id") != user["user_id"]:
                return error("Access denied", 403)

        return jsonify({"transaction": public_transaction(transaction)}), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/transactions", methods=["GET"])
@require_auth
@require_role("senior")
def api_list_transactions():
    try:
        sender_id = g.current_user["user_id"]
        rows = [apply_expiry(tx) for tx in get_transactions_by_sender(sender_id)]
        return jsonify({
            "sender_id":    sender_id,
            "transactions": [public_transaction(tx) for tx in rows],
        }), 200
    except Exception as exc:
        return error(str(exc), 500)


# ── Caregiver endpoints ───────────────────────────────────────────────────────

@app.route("/api/transactions/pending", methods=["GET"])
@require_auth
@require_role("caregiver")
def api_pending():
    try:
        caregiver_id  = g.current_user["user_id"]
        transactions  = get_pending_transactions_for_caregiver(caregiver_id)
        pending = []
        for tx in transactions:
            tx = apply_expiry(tx)
            if tx["status"] == "pending_caregiver_approval":
                pending.append(public_transaction(tx))
        return jsonify({
            "caregiver_id":  caregiver_id,
            "pending_count": len(pending),
            "pending":       pending,
        }), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/resolve/<int:tx_id>", methods=["POST"])
@require_auth
@require_role("caregiver")
def api_resolve(tx_id):
    try:
        data = request.get_json()
        if not data:
            return error("JSON body required", 400)

        decision = data.get("decision")
        if decision not in ("approve", "block"):
            return error("decision must be 'approve' or 'block'", 400)

        transaction = apply_expiry(get_transaction(tx_id))
        if not transaction:
            return error("Transaction not found", 404)

        sender = get_user(transaction["sender_id"])
        if not sender or sender.get("caregiver_id") != g.current_user["user_id"]:
            return error("Access denied — this transaction does not belong to your senior", 403)

        if transaction["status"] != "pending_caregiver_approval":
            return error("Transaction is not pending approval", 409)

        updated = resolve_hold(transaction, decision)
        set_transaction_resolution(tx_id, updated["status"], updated.get("resolution"))
        stored = get_transaction(tx_id)

        # ── Audit: caregiver decision ─────────────────────────────────────────
        event_name = "caregiver_approved" if decision == "approve" else "caregiver_blocked"
        log_audit_event(
            tx_id=tx_id, event=event_name,
            actor_id=g.current_user["user_id"], actor_role="caregiver",
        )

        # Notify the senior's room immediately
        socketio.emit(
            "tx_update",
            {
                "tx_id":      tx_id,
                "status":     "APPROVED" if decision == "approve" else "BLOCKED",
                "resolution": updated.get("resolution"),
            },
            room=f"user_{transaction['sender_id']}",
        )

        return jsonify({"transaction": public_transaction(stored)}), 200

    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/transactions/<int:tx_id>/audit", methods=["GET"])
@require_auth
def api_audit_log(tx_id):
    """
    GET /api/transactions/:id/audit
    Returns the full event history for a transaction.
    Seniors can only see their own; caregivers only their seniors'.
    """
    try:
        tx = get_transaction(tx_id)
        if not tx:
            return error("Transaction not found", 404)

        user = g.current_user
        if user["role"] == "senior" and tx["sender_id"] != user["user_id"]:
            return error("Access denied", 403)
        if user["role"] == "caregiver":
            sender = get_user(tx["sender_id"])
            if not sender or sender.get("caregiver_id") != user["user_id"]:
                return error("Access denied", 403)

        logs = get_audit_log(tx_id)
        for entry in logs:
            if "created_at" in entry:
                entry["created_at"] = _to_iso(entry["created_at"])

        return jsonify({"tx_id": tx_id, "audit_log": logs}), 200
    except Exception as exc:
        return error(str(exc), 500)


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@require_auth
def list_users():
    return jsonify({"users": get_all_users()}), 200


@app.route("/api/users/<int:user_id>", methods=["GET"])
@require_auth
def get_single_user(user_id):
    user = get_user(user_id)
    if not user:
        return error("User not found", 404)
    return jsonify({"user": user}), 200


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)