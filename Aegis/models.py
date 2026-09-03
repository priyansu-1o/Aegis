import sqlite3
from datetime import datetime, timedelta

DB_NAME = "Aegis.db"


def get_connection():

    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn



def init_db():

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            caregiver_id INTEGER,
            baseline_avg_tx REAL DEFAULT 5000.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,

            sender_id INTEGER NOT NULL,

            payee_name TEXT NOT NULL,

            payee_account TEXT NOT NULL,

            amount REAL NOT NULL,

            note TEXT DEFAULT '',

            risk_score INTEGER,

            risk_reasons TEXT,

            status TEXT NOT NULL,

            resolution TEXT,

            cooling_off_expiry TIMESTAMP,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(sender_id)
                REFERENCES users(user_id)
        )
    """)

    cursor.execute("PRAGMA table_info(transactions)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if existing_cols:
        if "note" not in existing_cols:
            cursor.execute("ALTER TABLE transactions ADD COLUMN note TEXT DEFAULT ''")
        if "resolution" not in existing_cols:
            cursor.execute("ALTER TABLE transactions ADD COLUMN resolution TEXT")
        if "cooling_off_expiry" not in existing_cols:
            cursor.execute("ALTER TABLE transactions ADD COLUMN cooling_off_expiry TIMESTAMP")


    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    if cursor.fetchone()[0] == 0:

        cursor.execute("""
            INSERT INTO users
            (
                user_id,
                name,
                role,
                caregiver_id,
                baseline_avg_tx
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            101,
            "Ramesh (Senior)",
            "senior",
            201,
            2000.0
        ))

        cursor.execute("""
            INSERT INTO users
            (
                user_id,
                name,
                role,
                caregiver_id,
                baseline_avg_tx
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            201,
            "Priya (Caregiver)",
            "caregiver",
            None,
            0.0
        ))

        print("Demo users inserted.")

    conn.commit()
    conn.close()

    print("Database initialization complete.")


def get_user(user_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM users
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    return dict(row) if row else None


def get_risk_user_data(sender_id):

    user = get_user(sender_id)

    if not user:
        return None

    known_payees = get_known_payees(
        sender_id
    )

    recent_transactions = \
        get_recent_transaction_timestamps(
            sender_id
        )

    return {
        "user_id": sender_id,

        "known_payees":
            known_payees,

        "avg_transaction_amount":
            user["baseline_avg_tx"] or 5000.0,

        "recent_transactions":
            recent_transactions
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
    cooling_off_expiry=None
):

    conn = get_connection()

    cursor = conn.cursor()

    if isinstance(risk_reasons, list):
        risk_reasons_str = ", ".join(risk_reasons)
    else:
        risk_reasons_str = str(risk_reasons or "")

    cursor.execute("""
        INSERT INTO transactions
        (
            sender_id,
            payee_name,
            payee_account,
            amount,
            note,
            risk_score,
            risk_reasons,
            status,
            resolution,
            cooling_off_expiry
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sender_id,
        payee_name,
        payee_account,
        amount,
        note,
        risk_score,
        risk_reasons_str,
        status,
        resolution,
        cooling_off_expiry
    ))

    tx_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return tx_id


def get_transaction(tx_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT
            t.*,
            u.name AS sender_name
        FROM transactions t

        JOIN users u
        ON t.sender_id = u.user_id

        WHERE t.tx_id = ?
    """, (tx_id,)).fetchone()

    conn.close()

    return dict(row) if row else None

def get_pending_transactions_for_caregiver(
    caregiver_id
):

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            t.*,
            u.name AS sender_name
        FROM transactions t

        JOIN users u
        ON t.sender_id = u.user_id

        WHERE u.caregiver_id = ?

        AND t.status =
            'pending_caregiver_approval'

        ORDER BY t.created_at DESC
    """, (caregiver_id,)).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def update_transaction_status(
    tx_id,
    new_status
):

    conn = get_connection()

    conn.execute("""
        UPDATE transactions

        SET status = ?

        WHERE tx_id = ?
    """, (
        new_status,
        tx_id
    ))

    conn.commit()
    conn.close()


def set_transaction_hold(
    tx_id,
    cooling_off_expiry
):

    conn = get_connection()

    conn.execute("""
        UPDATE transactions

        SET status =
            'pending_caregiver_approval',

            cooling_off_expiry = ?

        WHERE tx_id = ?
    """, (
        cooling_off_expiry,
        tx_id
    ))

    conn.commit()
    conn.close()


def set_transaction_resolution(
    tx_id,
    new_status,
    resolution
):

    conn = get_connection()

    conn.execute("""
        UPDATE transactions

        SET status = ?,
            resolution = ?

        WHERE tx_id = ?
    """, (
        new_status,
        resolution,
        tx_id
    ))

    conn.commit()
    conn.close()


def get_known_payees(sender_id):

    conn = get_connection()

    rows = conn.execute("""
        SELECT DISTINCT payee_account

        FROM transactions

        WHERE sender_id = ?

        AND status = 'approved'
    """, (sender_id,)).fetchall()

    conn.close()

    return {
        row["payee_account"]
        for row in rows
    }



def get_recent_transaction_timestamps(
    sender_id,
    minutes=10
):

    conn = get_connection()

    cutoff = (
        datetime.now()
        - timedelta(minutes=minutes)
    )

    rows = conn.execute("""
        SELECT created_at

        FROM transactions

        WHERE sender_id = ?

        AND created_at >= ?

        ORDER BY created_at DESC
    """, (
        sender_id,
        cutoff.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )).fetchall()

    conn.close()

    timestamps = []

    for row in rows:
        created_at_val = row["created_at"]
        if not created_at_val:
            continue
        if isinstance(created_at_val, datetime):
            timestamps.append(created_at_val)
            continue
        try:
            timestamps.append(datetime.fromisoformat(str(created_at_val)))
        except (TypeError, ValueError):
            try:
                timestamps.append(datetime.strptime(str(created_at_val), "%Y-%m-%d %H:%M:%S"))
            except (TypeError, ValueError):
                pass

    return timestamps