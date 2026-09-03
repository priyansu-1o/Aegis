from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

from config import COOLING_OFF_SECONDS
from database import (
    init_db,
    using_supabase,
    get_user,
    get_all_users,
    get_risk_user_data,
    get_known_payees,
    create_transaction,
    get_transaction,
    get_pending_transactions_for_caregiver,
    get_transactions_by_sender,
    set_transaction_hold,
    set_transaction_resolution,
)
from risk_engine import evaluate_transaction
from state_machine import create_hold, check_expiry, resolve_hold


app = Flask(__name__)
CORS(app)
init_db()

API_STATUS = {
    "pending_caregiver_approval": "PENDING_APPROVAL",
    "approved": "APPROVED",
    "blocked": "BLOCKED",
}


def _to_iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    text = str(value).strip().replace(" ", "T")
    # Strip trailing Z or +HH:MM / -HH:MM so the frontend always receives a
    # clean naive UTC string (TransactionStatus.jsx appends 'Z' itself).
    if text.endswith("Z"):
        text = text[:-1]
    elif len(text) > 6 and text[-6] in ("+", "-"):
        text = text[:-6]
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
        "tx_id": row["tx_id"],
        "sender_id": row["sender_id"],
        "sender": {"name": row.get("sender_name")},
        "payee_name": row["payee_name"],
        "payee_account": row["payee_account"],
        "amount": row["amount"],
        "note": row.get("note") or "",
        "risk_score": row.get("risk_score"),
        "risk_reasons": _parse_reasons(row.get("risk_reasons")),
        "status": API_STATUS.get(row["status"], row["status"]),
        "resolution": row.get("resolution"),
        "cooling_off_expiry": _to_iso(row.get("cooling_off_expiry")),
        "created_at": _to_iso(row.get("created_at")),
    }


def apply_expiry(tx):
    if not tx:
        return None
    original_status = tx.get("status")
    original_resolution = tx.get("resolution")
    updated = check_expiry(dict(tx))
    if (
        updated.get("status") != original_status
        or updated.get("resolution") != original_resolution
    ):
        set_transaction_resolution(
            updated["tx_id"],
            updated["status"],
            updated.get("resolution"),
        )
    return updated


def error(message, status_code):
    return jsonify({"error": message}), status_code


def process_transfer(data):
    if not data:
        return None, error("JSON body required", 400)

    sender_id = data.get("sender_id")
    payee_name = data.get("payee_name")
    payee_account = data.get("payee_account")
    amount = data.get("amount")
    note = data.get("note", "")

    if sender_id is None:
        return None, error("sender_id is required", 400)
    if not payee_name:
        return None, error("payee_name is required", 400)
    if not payee_account:
        return None, error("payee_account is required", 400)
    if amount is None:
        return None, error("amount is required", 400)

    try:
        sender_id = int(sender_id)
        amount = float(amount)
    except (TypeError, ValueError):
        return None, error("sender_id and amount must be numeric", 400)

    if amount <= 0:
        return None, error("Amount must be greater than zero", 400)

    user = get_user(sender_id)
    if not user:
        return None, error("Sender not found", 404)
    if user.get("role") == "caregiver":
        return None, error("Caregivers cannot submit transfers", 403)

    # Check if payee is known BEFORE creating the transaction so the new row
    # doesn't pollute the known-payees lookup.
    known_payees = get_known_payees(sender_id)
    new_payee = payee_account not in known_payees

    risk_user = get_risk_user_data(sender_id)
    transaction_input = {
        "payee_name": payee_name,
        "payee_account": payee_account,
        "amount": amount,
        "note": note,
        "timestamp": datetime.now(),
        "preceded_by_fd_break": data.get("preceded_by_fd_break", False),
        "fd_break_timestamp": data.get("fd_break_timestamp"),
    }
    risk = evaluate_transaction(transaction_input, risk_user)

    if risk["action"] == "hold_for_approval":
        status = "pending_caregiver_approval"
        resolution = None
    else:
        status = "approved"
        resolution = "auto_approved"

    tx_id = create_transaction(
        sender_id=sender_id,
        payee_name=payee_name,
        payee_account=payee_account,
        amount=amount,
        risk_score=risk["score"],
        risk_reasons=risk["reasons"],
        status=status,
        note=note,
        resolution=resolution,
    )

    stored = get_transaction(tx_id)
    if status == "pending_caregiver_approval":
        stored = create_hold(stored, COOLING_OFF_SECONDS)
        set_transaction_hold(tx_id, stored["cooling_off_expiry"])
        stored = get_transaction(tx_id)

    return {
        "transaction": public_transaction(stored),
        "risk": risk,
        "is_new_payee": new_payee,
    }, None


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "storage": "supabase",
    }), 200


@app.route("/api/users", methods=["GET"])
def list_users():
    return jsonify({"users": get_all_users()}), 200


@app.route("/api/payees/check", methods=["GET"])
def api_check_payee():
    """Returns whether a payee_account is new for the given sender_id."""
    try:
        sender_id = request.args.get("sender_id", type=int)
        payee_account = request.args.get("payee_account", "").strip()
        if not sender_id or not payee_account:
            return error("sender_id and payee_account are required", 400)
        known = get_known_payees(sender_id)
        return jsonify({"is_new_payee": payee_account not in known}), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_single_user(user_id):
    user = get_user(user_id)
    if not user:
        return error("User not found", 404)
    return jsonify({"user": user}), 200


@app.route("/api/transfer", methods=["POST"])
def api_transfer():
    try:
        payload, err = process_transfer(request.get_json())
        if err:
            return err
        return jsonify(payload), 201
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/transactions/<int:tx_id>", methods=["GET"])
def api_get_transaction(tx_id):
    try:
        transaction = apply_expiry(get_transaction(tx_id))
        if not transaction:
            return error("Transaction not found", 404)
        return jsonify({"transaction": public_transaction(transaction)}), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/transactions/pending", methods=["GET"])
def api_pending():
    try:
        caregiver_id = request.args.get("caregiver_id", default=1, type=int)
        transactions = get_pending_transactions_for_caregiver(caregiver_id)
        pending = []
        for tx in transactions:
            tx = apply_expiry(tx)
            if tx["status"] == "pending_caregiver_approval":
                pending.append(public_transaction(tx))
        return jsonify({
            "caregiver_id": caregiver_id,
            "pending_count": len(pending),
            "pending": pending,
        }), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/transactions", methods=["GET"])
def api_list_transactions():
    try:
        sender_id = request.args.get("sender_id", type=int)
        if sender_id is None:
            return error("sender_id query param is required", 400)
        rows = [apply_expiry(tx) for tx in get_transactions_by_sender(sender_id)]
        return jsonify({
            "sender_id": sender_id,
            "transactions": [public_transaction(tx) for tx in rows],
        }), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/api/resolve/<int:tx_id>", methods=["POST"])
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

        if transaction["status"] != "pending_caregiver_approval":
            return error("Transaction is not pending approval", 409)

        updated = resolve_hold(transaction, decision)
        set_transaction_resolution(
            tx_id,
            updated["status"],
            updated.get("resolution"),
        )
        stored = get_transaction(tx_id)
        return jsonify({"transaction": public_transaction(stored)}), 200
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/transaction", methods=["POST"])
def submit_transaction():
    payload, err = process_transfer(request.get_json())
    if err:
        return err
    return jsonify(payload), 201


@app.route("/transaction/<int:tx_id>", methods=["GET"])
def get_transaction_status(tx_id):
    return api_get_transaction(tx_id)


@app.route("/pending/<int:caregiver_id>", methods=["GET"])
def pending_transactions(caregiver_id):
    try:
        transactions = get_pending_transactions_for_caregiver(caregiver_id)
        pending = []
        for tx in transactions:
            tx = apply_expiry(tx)
            if tx["status"] == "pending_caregiver_approval":
                pending.append(public_transaction(tx))
        return jsonify({
            "caregiver_id": caregiver_id,
            "pending_count": len(pending),
            "pending": pending,
        }), 200
    except Exception as exc:
        return error(str(exc), 500)


@app.route("/transaction/<int:tx_id>/resolve", methods=["POST"])
def resolve_transaction(tx_id):
    return api_resolve(tx_id)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)