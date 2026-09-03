"""
tests/test_state_machine.py
============================
Unit tests for create_hold(), resolve_hold(), and check_expiry()
in state_machine.py.

Run with:
    pytest tests/ -v
"""

import pytest
import time
from datetime import datetime, timedelta
from state_machine import create_hold, resolve_hold, check_expiry


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_tx():
    """Minimal transaction dict — no status yet."""
    return {"id": "tx_test_001"}


@pytest.fixture
def pending_tx():
    """A transaction already in the pending_caregiver_approval state."""
    tx = {"id": "tx_test_002"}
    return create_hold(tx, cooling_off_seconds=300)   # 5-minute window


# ── create_hold ───────────────────────────────────────────────────────────────

class TestCreateHold:
    def test_sets_pending_status(self, fresh_tx):
        result = create_hold(fresh_tx, cooling_off_seconds=300)
        assert result["status"] == "pending_caregiver_approval"

    def test_sets_expiry_in_future(self, fresh_tx):
        before = datetime.now()
        result = create_hold(fresh_tx, cooling_off_seconds=300)
        after = datetime.now()
        assert before < result["cooling_off_expiry"] <= after + timedelta(seconds=300)

    def test_expiry_respects_cooling_off_duration(self, fresh_tx):
        result = create_hold(fresh_tx, cooling_off_seconds=60)
        expected_expiry = datetime.now() + timedelta(seconds=60)
        # Allow 1 second of execution slack
        assert abs((result["cooling_off_expiry"] - expected_expiry).total_seconds()) < 1

    def test_mutates_and_returns_same_dict(self, fresh_tx):
        result = create_hold(fresh_tx, cooling_off_seconds=300)
        assert result is fresh_tx   # same object returned

    def test_short_cooling_off(self, fresh_tx):
        result = create_hold(fresh_tx, cooling_off_seconds=1)
        assert result["status"] == "pending_caregiver_approval"


# ── resolve_hold ──────────────────────────────────────────────────────────────

class TestResolveHold:
    def test_approve_sets_approved_status(self, pending_tx):
        result = resolve_hold(pending_tx, "approve")
        assert result["status"] == "approved"

    def test_approve_sets_resolution(self, pending_tx):
        result = resolve_hold(pending_tx, "approve")
        assert result["resolution"] == "caregiver_approved"

    def test_block_sets_blocked_status(self, pending_tx):
        result = resolve_hold(pending_tx, "block")
        assert result["status"] == "blocked"

    def test_block_sets_resolution(self, pending_tx):
        result = resolve_hold(pending_tx, "block")
        assert result["resolution"] == "caregiver_blocked"

    def test_invalid_decision_raises(self, pending_tx):
        with pytest.raises(ValueError, match="Invalid decision"):
            resolve_hold(pending_tx, "maybe")

    def test_wrong_status_raises(self, fresh_tx):
        fresh_tx["status"] = "approved"
        with pytest.raises(ValueError, match="not pending approval"):
            resolve_hold(fresh_tx, "approve")

    def test_mutates_and_returns_same_dict(self, pending_tx):
        result = resolve_hold(pending_tx, "approve")
        assert result is pending_tx


# ── check_expiry ──────────────────────────────────────────────────────────────

class TestCheckExpiry:
    def test_non_pending_tx_unchanged(self, fresh_tx):
        fresh_tx["status"] = "approved"
        fresh_tx["cooling_off_expiry"] = datetime.now() - timedelta(seconds=10)
        result = check_expiry(fresh_tx)
        assert result["status"] == "approved"   # not touched

    def test_pending_within_window_unchanged(self, pending_tx):
        result = check_expiry(pending_tx)
        assert result["status"] == "pending_caregiver_approval"

    def test_expired_pending_becomes_blocked(self):
        tx = {"id": "tx_exp_001"}
        tx = create_hold(tx, cooling_off_seconds=1)
        time.sleep(1.1)   # let the window lapse
        result = check_expiry(tx)
        assert result["status"] == "blocked"
        assert result["resolution"] == "expired_no_response"

    def test_expired_pending_sets_resolution(self):
        tx = {"id": "tx_exp_002"}
        tx = create_hold(tx, cooling_off_seconds=1)
        time.sleep(1.1)
        result = check_expiry(tx)
        assert result["resolution"] == "expired_no_response"

    def test_exactly_at_expiry_is_blocked(self):
        tx = {
            "id": "tx_edge_001",
            "status": "pending_caregiver_approval",
            "cooling_off_expiry": datetime.now() - timedelta(milliseconds=1),
        }
        result = check_expiry(tx)
        assert result["status"] == "blocked"

    def test_mutates_and_returns_same_dict(self):
        tx = {"id": "tx_exp_003"}
        tx = create_hold(tx, cooling_off_seconds=1)
        time.sleep(1.1)
        result = check_expiry(tx)
        assert result is tx


# ── Full lifecycle ────────────────────────────────────────────────────────────

class TestStateMachineLifecycle:
    def test_hold_then_approve(self, fresh_tx):
        tx = create_hold(fresh_tx, cooling_off_seconds=300)
        tx = resolve_hold(tx, "approve")
        assert tx["status"] == "approved"
        assert tx["resolution"] == "caregiver_approved"

    def test_hold_then_block(self, fresh_tx):
        tx = create_hold(fresh_tx, cooling_off_seconds=300)
        tx = resolve_hold(tx, "block")
        assert tx["status"] == "blocked"
        assert tx["resolution"] == "caregiver_blocked"

    def test_hold_then_expire(self, fresh_tx):
        tx = create_hold(fresh_tx, cooling_off_seconds=1)
        time.sleep(1.1)
        tx = check_expiry(tx)
        assert tx["status"] == "blocked"
        assert tx["resolution"] == "expired_no_response"

    def test_cannot_resolve_after_expiry(self, fresh_tx):
        tx = create_hold(fresh_tx, cooling_off_seconds=1)
        time.sleep(1.1)
        tx = check_expiry(tx)                      # now "blocked"
        with pytest.raises(ValueError):
            resolve_hold(tx, "approve")            # should fail — not pending
