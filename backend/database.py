"""
Legacy database module proxying to models.py.
"""
from models import (
    DB_NAME,
    get_connection,
    init_db,
    get_user,
    get_risk_user_data,
    create_transaction,
    get_transaction,
    get_pending_transactions_for_caregiver,
    update_transaction_status,
    set_transaction_hold,
    set_transaction_resolution,
    get_known_payees,
    get_recent_transaction_timestamps
)

if __name__ == "__main__":
    init_db()