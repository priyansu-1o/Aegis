from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

from models import (
    init_db,
    get_user,
    get_risk_user_data,
    create_transaction,
    get_transaction,
    get_pending_transactions_for_caregiver
)

from risk_engine import evaluate_transaction

from state_machine import (
    create_hold,
    check_expiry,
    resolve_hold
)


app = Flask(__name__)
CORS(app)
init_db()


@app.route(
    "/transaction",
    methods=["POST"]
)
def submit_transaction():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "error":
                    "JSON body required"
            }), 400

        sender_id = data.get(
            "sender_id"
        )

        payee_name = data.get(
            "payee_name"
        )

        payee_account = data.get(
            "payee_account"
        )

        amount = data.get(
            "amount"
        )

        note = data.get(
            "note",
            ""
        )

        if sender_id is None:

            return jsonify({
                "error":
                    "sender_id is required"
            }), 400

        if not payee_name:

            return jsonify({
                "error":
                    "payee_name is required"
            }), 400

        if not payee_account:

            return jsonify({
                "error":
                    "payee_account is required"
            }), 400

        if amount is None:

            return jsonify({
                "error":
                    "amount is required"
            }), 400


        sender_id = int(sender_id)
        amount = float(amount)


        if amount <= 0:

            return jsonify({
                "error":
                    "Amount must be greater than zero"
            }), 400


        user = get_user(
            sender_id
        )

        if not user:

            return jsonify({
                "error":
                    "Sender not found"
            }), 404

        risk_user = \
            get_risk_user_data(
                sender_id
            )


        transaction = {

            "payee_name":
                payee_name,

            "payee_account":
                payee_account,

            "amount":
                amount,

            "note":
                note,

            "timestamp":
                datetime.now(),

            # These can later come
            # from the Senior frontend
            "preceded_by_fd_break":
                data.get(
                    "preceded_by_fd_break",
                    False
                ),

            "fd_break_timestamp":
                data.get(
                    "fd_break_timestamp"
                )
        }
        risk = evaluate_transaction(
            transaction,
            risk_user
        )


        if risk["action"] == \
                "hold_for_approval":

            status = \
                "pending_caregiver_approval"

        else:

            status = "approved"

        tx_id = create_transaction(

            sender_id=sender_id,

            payee_name=payee_name,

            payee_account=payee_account,

            amount=amount,

            risk_score=risk["score"],

            risk_reasons=risk["reasons"],

            status=status,

            note=note,

            resolution=(
                "auto_approved"
                if status == "approved"
                else None
            )
        )




        if status == \
                "pending_caregiver_approval":

            transaction = \
                create_hold(tx_id)

        else:

            transaction = \
                get_transaction(tx_id)


        return jsonify({

            "id":
                transaction["tx_id"],

            "sender_id":
                sender_id,

            "sender_name":
                user["name"],

            "payee_name":
                payee_name,

            "payee_account":
                payee_account,

            "amount":
                amount,

            "risk_score":
                risk["score"],

            "risk_reasons":
                risk["reasons"],

            "risk_level":
                (
                    "HIGH"
                    if risk["score"] >= 70
                    else
                    "MEDIUM"
                    if risk["score"] >= 50
                    else
                    "LOW"
                ),

            "action":
                risk["action"],

            "status":
                transaction["status"],

            "resolution":
                transaction.get(
                    "resolution"
                ),

            "cooling_off_expiry":
                transaction.get(
                    "cooling_off_expiry"
                )

        }), 201


    except ValueError as e:

        return jsonify({
            "error": str(e)
        }), 400


    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500
    
@app.route(
    "/transaction/<int:tx_id>",
    methods=["GET"]
)
def get_transaction_status(tx_id):

    try:

        transaction = \
            get_transaction(tx_id)

        if not transaction:

            return jsonify({
                "error":
                    "Transaction not found"
            }), 404


        # Automatically check
        # cooling-off expiry
        transaction = check_expiry(
            transaction
        )


        return jsonify(
            transaction
        ), 200


    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/pending/<int:caregiver_id>",
    methods=["GET"]
)
def pending_transactions(
    caregiver_id
):

    try:

        transactions = \
            get_pending_transactions_for_caregiver(
                caregiver_id
            )


        valid_transactions = []


        for tx in transactions:

            tx = check_expiry(tx)

            if tx["status"] == \
                    "pending_caregiver_approval":

                valid_transactions.append(tx)


        return jsonify({

            "caregiver_id":
                caregiver_id,

            "pending_count":
                len(valid_transactions),

            "transactions":
                valid_transactions

        }), 200


    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

@app.route(
    "/transaction/<int:tx_id>/resolve",
    methods=["POST"]
)
def resolve_transaction(tx_id):

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "error":
                    "JSON body required"
            }), 400


        decision = data.get(
            "decision"
        )


        if decision not in [
            "approve",
            "block"
        ]:

            return jsonify({
                "error":
                    "decision must be "
                    "'approve' or 'block'"
            }), 400


        transaction = resolve_hold(
            tx_id,
            decision
        )


        return jsonify({

            "message":
                (
                    "Transaction approved"
                    if decision == "approve"
                    else
                    "Transaction blocked"
                ),

            "transaction":
                transaction

        }), 200


    except ValueError as e:

        return jsonify({
            "error": str(e)
        }), 400


    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )