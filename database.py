import sqlite3

DB_NAME = "Aegis.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    print("Initializing Aegis Database...")

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            caregiver_id INTEGER,
            baseline_avg_tx REAL DEFAULT 5000.0
        )
    """)

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            payee_name TEXT NOT NULL,
            payee_account TEXT NOT NULL,
            amount REAL NOT NULL,
            risk_score INTEGER,
            risk_reasons TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(user_id)
        )
    """)

    # Insert demo users only if table is empty
    cursor.execute("SELECT COUNT(*) FROM users")

    if cursor.fetchone()[0] == 0:

        cursor.execute("""
            INSERT INTO users
            (user_id, name, role, caregiver_id, baseline_avg_tx)
            VALUES (?, ?, ?, ?, ?)
        """, (101, "Ramesh (Senior)", "senior", 201, 2000.0))

        cursor.execute("""
            INSERT INTO users
            (user_id, name, role, caregiver_id, baseline_avg_tx)
            VALUES (?, ?, ?, ?, ?)
        """, (201, "Priya (Caregiver)", "caregiver", None, 0.0))

        print("Demo users inserted.")

    conn.commit()
    conn.close()

    print("Database initialization complete.")


def get_user(user_id):
    """Fetch a user by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE user_id = ?
    """, (user_id,))

    user = cursor.fetchone()
    conn.close()

    return dict(user) if user else None


def create_transaction(
    sender_id,
    payee_name,
    payee_account,
    amount,
    risk_score,
    risk_reasons,
    status
):
    """Create a transaction in the database."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO transactions
        (
            sender_id,
            payee_name,
            payee_account,
            amount,
            risk_score,
            risk_reasons,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        sender_id,
        payee_name,
        payee_account,
        amount,
        risk_score,
        risk_reasons,
        status
    ))

    tx_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return tx_id


def get_transaction(tx_id):
    """Get a transaction by ID."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM transactions
        WHERE tx_id = ?
    """, (tx_id,))

    tx = cursor.fetchone()

    conn.close()

    return dict(tx) if tx else None


def get_pending_transactions_for_caregiver(caregiver_id):
    """Get pending transactions belonging to the caregiver's seniors."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            t.*,
            u.name AS sender_name
        FROM transactions t
        JOIN users u
            ON t.sender_id = u.user_id
        WHERE u.caregiver_id = ?
        AND t.status = 'PENDING_APPROVAL'
        ORDER BY t.created_at DESC
    """, (caregiver_id,))

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def update_transaction_status(tx_id, new_status):
    """Change transaction status."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE transactions
        SET status = ?
        WHERE tx_id = ?
    """, (new_status, tx_id))

    conn.commit()
    conn.close()

    return True


if __name__ == "__main__":
    init_db()
