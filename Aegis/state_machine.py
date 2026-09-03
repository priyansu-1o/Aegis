from datetime import datetime, timedelta

from config import COOLING_OFF_SECONDS

from models import (
    get_transaction,
    set_transaction_hold,
    set_transaction_resolution
)


VALID_STATUSES = {
    "approved",
    "pending_caregiver_approval",
    "blocked"
}


def create_hold(tx_id):

    expiry = (
        datetime.now()
        + timedelta(
            seconds=COOLING_OFF_SECONDS
        )
    )

    set_transaction_hold(
        tx_id,
        expiry.isoformat()
    )

    return get_transaction(tx_id)


def check_expiry(transaction):

    if transaction["status"] != \
            "pending_caregiver_approval":

        return transaction

    expiry_string = \
        transaction.get(
            "cooling_off_expiry"
        )

    if not expiry_string:

        return transaction

    try:

        expiry = datetime.fromisoformat(
            expiry_string
        )

    except ValueError:

        return transaction

    if datetime.now() >= expiry:

        set_transaction_resolution(
            transaction["tx_id"],
            "blocked",
            "expired_no_response"
        )

        return get_transaction(
            transaction["tx_id"]
        )

    return transaction


def resolve_hold(
    tx_id,
    decision
):

    transaction = get_transaction(
        tx_id
    )

    if not transaction:

        raise ValueError(
            "Transaction not found"
        )

    # Check expiry FIRST
    transaction = check_expiry(
        transaction
    )

    if transaction["status"] != \
            "pending_caregiver_approval":

        raise ValueError(
            "Transaction is no longer pending approval"
        )

    if decision == "approve":

        set_transaction_resolution(
            tx_id,
            "approved",
            "caregiver_approved"
        )

    elif decision == "block":

        set_transaction_resolution(
            tx_id,
            "blocked",
            "caregiver_blocked"
        )

    else:

        raise ValueError(
            "Invalid decision. "
            "Use 'approve' or 'block'."
        )

    return get_transaction(tx_id)