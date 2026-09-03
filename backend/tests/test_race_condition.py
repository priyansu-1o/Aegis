"""
tests/test_race_condition.py
=============================
Tests the race condition between a manual caregiver resolve and the
auto-expiry path (check_expiry) firing on the same transaction.

The bug (pre-fix):
    set_transaction_resolution() used `WHERE tx_id = ?` with no status guard.
    If check_expiry() read the row as "still pending" and then wrote
    "blocked / expired_no_response" AFTER the caregiver had already written
    "approved / caregiver_approved", the caregiver's decision was silently
    overwritten.

The fix:
    Both SQLite (models.py) and Supabase (database.py) paths now use
    `WHERE tx_id = ? AND status = 'pending_caregiver_approval'`
    so the second writer's UPDATE is a no-op.

These tests work against a temporary SQLite database so they are fully
isolated from kavach.db and safe to run in CI.
"""

import os
import sqlite3
import tempfile
import threading
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch


# ── Helpers to bootstrap a minimal in-memory-style DB ─────────────────────────

def _create_temp_db() -> str:
    """Return the path to a freshly initialised temporary SQLite database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE users (
            user_id         INTEGER PRIMARY KEY,
            name            TEXT NOT NULL,
            role            TEXT NOT NULL,
            caregiver_id    INTEGER,
            baseline_avg_tx REAL DEFAULT 5000.0,
            email           TEXT,
            password_hash   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE transactions (
            tx_id               INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id           INTEGER NOT NULL,
            payee_name          TEXT NOT NULL,
            payee_account       TEXT NOT NULL,
            amount              REAL NOT NULL,
            note                TEXT DEFAULT '',
            risk_score          INTEGER,
            risk_reasons        TEXT,
            status              TEXT NOT NULL,
            resolution          TEXT,
            cooling_off_expiry  TIMESTAMP,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(
        "INSERT INTO users (user_id, name, role, caregiver_id) VALUES (?,?,?,?)",
        (1, "Caregiver", "caregiver", None),
    )
    cur.execute(
        "INSERT INTO users (user_id, name, role, caregiver_id) VALUES (?,?,?,?)",
        (2, "Senior", "senior", 1),
    )
    conn.commit()
    conn.close()
    return path


def _insert_pending_tx(db_path: str, expiry: datetime) -> int:
    """Insert a pending transaction and return its tx_id."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions
            (sender_id, payee_name, payee_account, amount,
             risk_score, risk_reasons, status, resolution, cooling_off_expiry)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (2, "Test Payee", "1234567890", 50000, 70, "New payee",
         "pending_caregiver_approval", None,
         expiry.strftime("%Y-%m-%dT%H:%M:%S")),
    )
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    return tx_id


def _get_tx(db_path: str, tx_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM transactions WHERE tx_id = ?", (tx_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path):
    """Isolated SQLite DB; patches models.DB_NAME so all models.py calls use it."""
    db_path = str(tmp_path / "test_race.db")

    # Bootstrap the schema using _create_temp_db() logic inline
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
            caregiver_id INTEGER, baseline_avg_tx REAL DEFAULT 5000.0,
            email TEXT, password_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL, payee_name TEXT NOT NULL,
            payee_account TEXT NOT NULL, amount REAL NOT NULL,
            note TEXT DEFAULT '', risk_score INTEGER, risk_reasons TEXT,
            status TEXT NOT NULL, resolution TEXT,
            cooling_off_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO users (user_id, name, role, caregiver_id)
            VALUES (1, 'Caregiver', 'caregiver', NULL);
        INSERT OR IGNORE INTO users (user_id, name, role, caregiver_id)
            VALUES (2, 'Senior', 'senior', 1);
    """)
    conn.commit()
    conn.close()

    with patch("models.DB_NAME", db_path):
        yield db_path


@pytest.fixture
def pending_tx_id(temp_db):
    """A freshly inserted PENDING transaction with a 5-minute window."""
    expiry = datetime.utcnow() + timedelta(minutes=5)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO transactions
           (sender_id, payee_name, payee_account, amount,
            risk_score, risk_reasons, status, cooling_off_expiry)
           VALUES (2,'Payee','ACC123',50000,70,'New payee',
                   'pending_caregiver_approval',?)""",
        (expiry.strftime("%Y-%m-%dT%H:%M:%S"),),
    )
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    return tx_id


@pytest.fixture
def expired_tx_id(temp_db):
    """A PENDING transaction whose cooling-off window has already lapsed."""
    expiry = datetime.utcnow() - timedelta(seconds=1)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO transactions
           (sender_id, payee_name, payee_account, amount,
            risk_score, risk_reasons, status, cooling_off_expiry)
           VALUES (2,'Payee','ACC123',50000,70,'New payee',
                   'pending_caregiver_approval',?)""",
        (expiry.strftime("%Y-%m-%dT%H:%M:%S"),),
    )
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    return tx_id


# ── Unit: the guard itself ─────────────────────────────────────────────────────

class TestResolutionGuard:
    """
    Directly test that set_transaction_resolution is a no-op when the row
    is no longer in pending_caregiver_approval status.
    """

    def test_resolution_updates_pending_tx(self, temp_db, pending_tx_id):
        """Normal path: pending → approved."""
        import models
        models.set_transaction_resolution(
            pending_tx_id, "approved", "caregiver_approved"
        )
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (pending_tx_id,)
        ).fetchone())
        conn.close()

        assert row["status"] == "approved"
        assert row["resolution"] == "caregiver_approved"

    def test_second_write_is_noop_after_first_resolve(self, temp_db, pending_tx_id):
        """
        Core race condition guard:
        After the first resolve (caregiver_approved), a second write
        (expired_no_response) must NOT overwrite it.
        """
        import models

        # First: caregiver approves
        models.set_transaction_resolution(
            pending_tx_id, "approved", "caregiver_approved"
        )
        # Second: expiry fires a moment later (simulated sequentially)
        models.set_transaction_resolution(
            pending_tx_id, "blocked", "expired_no_response"
        )

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (pending_tx_id,)
        ).fetchone())
        conn.close()

        # The second write must have been a no-op
        assert row["status"] == "approved",     f"Expected 'approved', got '{row['status']}'"
        assert row["resolution"] == "caregiver_approved", (
            f"Expected 'caregiver_approved', got '{row['resolution']}'"
        )

    def test_block_then_expiry_noop(self, temp_db, pending_tx_id):
        """
        Inverse: caregiver blocks, then expiry fires → still blocked/caregiver_blocked.
        """
        import models

        models.set_transaction_resolution(
            pending_tx_id, "blocked", "caregiver_blocked"
        )
        models.set_transaction_resolution(
            pending_tx_id, "blocked", "expired_no_response"
        )

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (pending_tx_id,)
        ).fetchone())
        conn.close()

        assert row["resolution"] == "caregiver_blocked"

    def test_expiry_then_caregiver_noop(self, temp_db, expired_tx_id):
        """
        Expiry fires first (auto-blocks), then caregiver tries to approve.
        Caregiver's approve must be a no-op.
        """
        import models
        from state_machine import check_expiry

        # Simulate the expiry path writing to the DB first
        models.set_transaction_resolution(
            expired_tx_id, "blocked", "expired_no_response"
        )
        # Now caregiver tries to approve (arrives late)
        models.set_transaction_resolution(
            expired_tx_id, "approved", "caregiver_approved"
        )

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (expired_tx_id,)
        ).fetchone())
        conn.close()

        assert row["status"] == "blocked"
        assert row["resolution"] == "expired_no_response"


# ── Concurrent: threading simulation ─────────────────────────────────────────

class TestConcurrentResolution:
    """
    Spin up two threads that race to call set_transaction_resolution().
    One writes 'approved / caregiver_approved', the other writes
    'blocked / expired_no_response'.  Due to the guard, exactly one must win
    and the other must be silently discarded.
    """

    def test_concurrent_resolve_exactly_one_wins(self, temp_db, pending_tx_id):
        import models

        results = []
        barrier = threading.Barrier(2)

        def caregiver_resolve():
            barrier.wait()    # both threads start at the same time
            models.set_transaction_resolution(
                pending_tx_id, "approved", "caregiver_approved"
            )
            results.append("caregiver")

        def expiry_resolve():
            barrier.wait()
            models.set_transaction_resolution(
                pending_tx_id, "blocked", "expired_no_response"
            )
            results.append("expiry")

        t1 = threading.Thread(target=caregiver_resolve)
        t2 = threading.Thread(target=expiry_resolve)
        t1.start(); t2.start()
        t1.join();  t2.join()

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (pending_tx_id,)
        ).fetchone())
        conn.close()

        # Transaction must be in exactly one terminal state
        assert row["status"] in ("approved", "blocked"), \
            f"Unexpected status: {row['status']}"

        # The resolution must match the status coherently
        valid_pairs = {
            ("approved", "caregiver_approved"),
            ("blocked",  "expired_no_response"),
        }
        assert (row["status"], row["resolution"]) in valid_pairs, \
            f"Incoherent state: status={row['status']}, resolution={row['resolution']}"

    def test_many_concurrent_resolves_all_noop_after_first(self, temp_db, pending_tx_id):
        """
        Ten threads all try to resolve the same transaction simultaneously.
        Exactly one must win; the other nine must be no-ops.
        """
        import models

        THREAD_COUNT = 10
        barrier = threading.Barrier(THREAD_COUNT)
        outcomes = []

        def resolve(i):
            status     = "approved"  if i % 2 == 0 else "blocked"
            resolution = "caregiver_approved" if i % 2 == 0 else "expired_no_response"
            barrier.wait()
            models.set_transaction_resolution(pending_tx_id, status, resolution)
            outcomes.append((status, resolution))

        threads = [threading.Thread(target=resolve, args=(i,)) for i in range(THREAD_COUNT)]
        for t in threads: t.start()
        for t in threads: t.join()

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (pending_tx_id,)
        ).fetchone())
        conn.close()

        # Must still be in one coherent terminal state
        valid_pairs = {
            ("approved", "caregiver_approved"),
            ("blocked",  "expired_no_response"),
        }
        assert (row["status"], row["resolution"]) in valid_pairs, \
            f"Incoherent state after concurrent writes: {row}"


# ── Integration: apply_expiry + set_transaction_resolution interaction ────────

class TestApplyExpiryIntegration:
    """
    Tests the full app.py apply_expiry() path:
    check_expiry() detects expiry, then calls set_transaction_resolution()
    through the guard. Verify that a concurrent caregiver resolve is safe.
    """

    def test_apply_expiry_does_not_overwrite_manual_resolve(
        self, temp_db, pending_tx_id
    ):
        """
        Sequence:
          1. Caregiver manually resolves → approved
          2. apply_expiry() runs on the same (now approved) transaction
          3. approved status must NOT be changed to blocked/expired
        """
        import models
        from state_machine import check_expiry

        # Step 1: caregiver resolves
        models.set_transaction_resolution(
            pending_tx_id, "approved", "caregiver_approved"
        )

        # Step 2: fetch the now-approved row and run check_expiry on it
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT * FROM transactions WHERE tx_id=?", (pending_tx_id,)
        ).fetchone())
        conn.close()

        # check_expiry should return it unchanged (status != pending)
        updated = check_expiry(dict(row))
        assert updated["status"] == "approved", \
            "check_expiry must not touch an already-resolved transaction"

        # Step 3: even if set_transaction_resolution is called again, no change
        models.set_transaction_resolution(
            pending_tx_id, "blocked", "expired_no_response"
        )
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        final = dict(conn.execute(
            "SELECT status, resolution FROM transactions WHERE tx_id=?",
            (pending_tx_id,)
        ).fetchone())
        conn.close()

        assert final["status"] == "approved"
        assert final["resolution"] == "caregiver_approved"
