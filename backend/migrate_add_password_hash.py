"""
migrate_add_password_hash.py
============================
Repeatable migration that:
  1. Adds  email TEXT  and  password_hash TEXT  columns to the users table
     (safe no-ops if the columns already exist — SQLite doesn't support
     IF NOT EXISTS on ALTER TABLE, so we check PRAGMA first).
  2. Seeds demo credentials for the two primary demo users:

     user_id=1  email=caregiver@aegis.demo  password=demo1234  role=caregiver
     user_id=2  email=senior@aegis.demo     password=demo1234  role=senior

Run with:
    py migrate_add_password_hash.py

Safe to re-run: existing hashes are only updated when the email column was
previously NULL, so repeated runs don't clobber user-changed passwords.

Works on the local SQLite database (kavach.db).  For Supabase, run the
equivalent SQL migration via the Supabase dashboard:

    ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
    -- Then update the rows with the bcrypt hashes printed by this script.
"""

import sqlite3
import sys

try:
    import bcrypt
except ImportError:
    sys.exit(
        "ERROR: bcrypt is not installed.\n"
        "Run:  pip install bcrypt\n"
        "Then re-run this migration."
    )

DB_PATH = "kavach.db"
DEMO_PASSWORD = "demo1234"

DEMO_CREDENTIALS = [
    # (user_id, email, role_label)
    (1,   "caregiver@aegis.demo", "Caregiver"),
    (2,   "senior@aegis.demo",    "Senior"),
    (101, "ramesh@aegis.demo",    "Senior (Ramesh)"),
    (201, "priya@aegis.demo",     "Caregiver (Priya)"),
]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── Step 1: add columns (idempotent) ─────────────────────────────────────
    existing = {row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()}

    if "email" not in existing:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
        print("[migration] Added column: users.email")
    else:
        print("[migration] Column already exists: users.email  (skip)")

    if "password_hash" not in existing:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        print("[migration] Added column: users.password_hash")
    else:
        print("[migration] Column already exists: users.password_hash  (skip)")

    conn.commit()

    # ── Step 2: seed demo credentials ────────────────────────────────────────
    hash_bytes = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt())
    pw_hash = hash_bytes.decode()

    print(f"\n[migration] Seeding demo credentials (password: '{DEMO_PASSWORD}')")
    print(f"            bcrypt hash: {pw_hash}\n")

    for user_id, email, label in DEMO_CREDENTIALS:
        row = cur.execute(
            "SELECT user_id, email FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not row:
            print(f"  [SKIP] user_id={user_id} ({label}) not found in DB — run init_db() first.")
            continue

        # Only write if email not yet set (idempotent — won't clobber a real password)
        if row["email"] is None:
            cur.execute(
                "UPDATE users SET email = ?, password_hash = ? WHERE user_id = ?",
                (email, pw_hash, user_id),
            )
            print(f"  [OK]   user_id={user_id:>3}  email={email:<30}  role={label}")
        else:
            print(
                f"  [SKIP] user_id={user_id:>3}  email already set ({row['email']}) — "
                f"password not overwritten."
            )

    conn.commit()
    conn.close()
    print("\n[migration] Done.")


if __name__ == "__main__":
    migrate()
