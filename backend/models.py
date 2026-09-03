import sqlite3
from datetime import datetime, timedelta

DB_NAME = "kavach.db"


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

    # Audit log table — append-only, never updated
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_id       INTEGER NOT NULL,
            event       TEXT NOT NULL,
            actor_id    INTEGER,
            actor_role  TEXT,
            risk_score  INTEGER,
            details     TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(tx_id) REFERENCES transactions(tx_id)
        )
    """)

    # Auth columns — added by migration; safe to attempt here for fresh DBs
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    if user_cols:
        if "email" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "password_hash" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")


    demo_users = [
        (1, "Priya (Caregiver)", "caregiver", None, 0.0),
        (2, "Meena Sharma", "senior", 1, 2000.0),
        (101, "Ramesh (Senior)", "senior", 201, 2000.0),
        (201, "Priya (Caregiver)", "caregiver", None, 0.0),
    ]
    inserted = 0
    for user in demo_users:
        exists = cursor.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user[0],),
        ).fetchone()
        if exists:
            continue
        cursor.execute(
            """
            INSERT INTO users
            (user_id, name, role, caregiver_id, baseline_avg_tx)
            VALUES (?, ?, ?, ?, ?)
            """,
            user,
        )
        inserted += 1
    if inserted:
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
            cooling_off_expiry,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        cooling_off_expiry,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    # ── Race-condition guard ───────────────────────────────────────────────────
    # Only update when the transaction is still pending.  This makes the update
    # a no-op if check_expiry or a concurrent caregiver resolve already fired,
    # preventing two conflicting resolutions on the same transaction.
    conn = get_connection()

    conn.execute("""
        UPDATE transactions

        SET status = ?,
            resolution = ?

        WHERE tx_id = ?
        AND   status = 'pending_caregiver_approval'
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


def get_all_users():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY user_id"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_transactions_by_sender(sender_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            t.*,
            u.name AS sender_name
        FROM transactions t
        JOIN users u ON t.sender_id = u.user_id
        WHERE t.sender_id = ?
        ORDER BY t.created_at DESC
        """,
        (sender_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Auth helpers ──────────────────────────────────────────────────────────────

def get_user_by_email(email):
    """Look up a user by their email address (used during login)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_password_hash(user_id, password_hash):
    """Persist a bcrypt password hash for the given user."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE user_id = ?",
        (password_hash, user_id),
    )
    conn.commit()
    conn.close()


# ── Audit log ───────────────────────────────────────────────────────────────

def log_audit_event(
    tx_id: int,
    event: str,
    actor_id: int | None = None,
    actor_role: str | None = None,
    risk_score: int | None = None,
    details: str | None = None,
):
    """
    Append one immutable row to the audit_log table.

    event values used by the app:
        'transaction_created'   — new tx submitted by senior
        'auto_approved'         — risk score below threshold
        'hold_created'          — risk score at/above threshold, cooling-off started
        'caregiver_approved'    — caregiver manually approved
        'caregiver_blocked'     — caregiver manually blocked
        'expired_no_response'   — cooling-off window elapsed, auto-blocked
    """
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO audit_log
            (tx_id, event, actor_id, actor_role, risk_score, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tx_id, event, actor_id, actor_role, risk_score, details),
    )
    conn.commit()
    conn.close()


def get_audit_log(tx_id: int) -> list[dict]:
    """Return the full ordered audit trail for a single transaction."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT log_id, tx_id, event, actor_id, actor_role,
               risk_score, details, created_at
        FROM   audit_log
        WHERE  tx_id = ?
        ORDER  BY log_id ASC
        """,
        (tx_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]