"""
tests/test_split_gaming.py
==========================
Documents and tests the "split-transaction gaming" vulnerability:
a fraudster can instruct a senior to make multiple smaller transfers
that each individually fall below the risk threshold.

With the current config (config.py):
    baseline_avg_tx     = 2000.0  (Meena Sharma)
    LARGE_AMOUNT_MULTIPLIER = 2   → large_amount threshold = 4000
    RISK_THRESHOLD      = 50
    WEIGHTS = { new_payee: 30, large_amount: 55, high_velocity: 20, ... }
    VELOCITY_WINDOW_MINUTES = 10
    VELOCITY_COUNT_THRESHOLD = 3

Attack surface:
    A transfer of ₹3,999 to a new payee scores only 30 (new_payee weight).
    That is below the hold threshold of 50 → auto-approved.
    Two such transfers slip through; the third triggers the velocity rule
    (+20) pushing the total to 50 → held. But the first two already cleared.

These tests prove the gap, quantify it, and will serve as regression
tests if a fix (e.g. cumulative-amount window rule) is ever added.

Run with:
    pytest tests/test_split_gaming.py -v
"""

import pytest
from datetime import datetime, timedelta
from risk_engine import (
    calculate_risk,
    evaluate_transaction,
    WEIGHTS,
    RISK_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def meena_user():
    """Matches the seeded Meena Sharma profile: baseline_avg_tx = 2000."""
    return {
        "known_payees": set(),          # starts with no approved payees
        "avg_transaction_amount": 2000.0,
        "recent_transactions": [],
    }


def _safe_tx(payee_account: str, amount: float, note: str = "") -> dict:
    """A daytime transaction with no FD break."""
    return {
        "payee_account":        payee_account,
        "amount":               amount,
        "note":                 note,
        "preceded_by_fd_break": False,
        "fd_break_timestamp":   None,
        "timestamp":            datetime.now().replace(hour=14),
    }


# ── Demonstrate the gap ───────────────────────────────────────────────────────

class TestSplitGapExists:
    """
    These tests document that the current rules allow individual split
    transactions to pass through undetected.
    """

    def test_single_transfer_below_large_threshold_is_safe(self, meena_user):
        """
        ₹3,999 to a new payee: new_payee(30) only → score=30 < threshold(50).
        This transfer auto-approves — the gap is real.
        """
        tx = _safe_tx("attacker_acc", 3999.0)
        result = calculate_risk(tx, meena_user)

        assert result["score"] == WEIGHTS["new_payee"]          # 30
        assert result["is_high_risk"] is False
        assert result["action"] if "action" in result else evaluate_transaction(
            tx, meena_user
        )["action"] == "auto_approve"

    def test_large_amount_threshold_for_meena(self, meena_user):
        """
        Confirm the exact threshold so splits can be precisely calibrated.
        avg=2000, multiplier=2 → amounts UP TO AND INCLUDING 4000 are safe.
        """
        from config import LARGE_AMOUNT_MULTIPLIER
        threshold = meena_user["avg_transaction_amount"] * LARGE_AMOUNT_MULTIPLIER
        assert threshold == 4000.0

        # Exactly at threshold — safe (code uses strictly >)
        at_threshold = _safe_tx("new_acc", threshold)
        result = calculate_risk(at_threshold, meena_user)
        assert result["score"] == WEIGHTS["new_payee"]           # large_amount NOT fired

        # One rupee over — flagged
        over_threshold = _safe_tx("new_acc", threshold + 1)
        result2 = calculate_risk(over_threshold, meena_user)
        assert result2["score"] == WEIGHTS["new_payee"] + WEIGHTS["large_amount"]
        assert result2["is_high_risk"] is True

    def test_two_split_transfers_to_different_payees_both_pass(self, meena_user):
        """
        Two transfers of ₹3,999 to two different new payees both auto-approve.
        Velocity rule needs >= 3 transactions, so two slips through.

        This is the confirmed gap: a fraudster gets ₹7,998 through undetected
        in the 10-minute window before velocity kicks in.
        """
        now = datetime.now()

        # First transfer — no prior transactions
        tx1 = _safe_tx("attacker_acc_1", 3999.0)
        r1 = evaluate_transaction(tx1, meena_user)
        assert r1["action"] == "auto_approve", "First split transfer must pass"
        assert r1["score"] == WEIGHTS["new_payee"]

        # Simulate tx1 being approved: update user state
        meena_user["recent_transactions"].append(now - timedelta(minutes=1))
        meena_user["known_payees"].add("attacker_acc_1")  # tx1 now approved

        # Second transfer to a DIFFERENT new payee — still only 1 recent tx
        tx2 = _safe_tx("attacker_acc_2", 3999.0)
        r2 = evaluate_transaction(tx2, meena_user)
        assert r2["action"] == "auto_approve", "Second split transfer must also pass"
        assert r2["score"] == WEIGHTS["new_payee"]          # velocity count = 1, not triggered

    def test_third_split_transfer_triggers_velocity_and_is_held(self, meena_user):
        """
        The (VELOCITY_COUNT_THRESHOLD + 1)-th transfer in the 10-minute window
        triggers velocity (+20), pushing new_payee(30) + velocity(20) = 50 >= threshold.

        VELOCITY_COUNT_THRESHOLD = 3, so we need 3 prior approved transactions
        in recent_transactions before the current evaluation fires the rule.
        """
        from config import VELOCITY_COUNT_THRESHOLD
        now = datetime.now()

        # Simulate VELOCITY_COUNT_THRESHOLD prior approved transactions
        meena_user["recent_transactions"] = [
            now - timedelta(minutes=i * 2) for i in range(1, VELOCITY_COUNT_THRESHOLD + 1)
        ]
        meena_user["known_payees"] = {f"attacker_acc_{i}" for i in range(VELOCITY_COUNT_THRESHOLD)}

        # Next transfer to a brand-new payee — velocity fires
        tx = _safe_tx(f"attacker_acc_{VELOCITY_COUNT_THRESHOLD}", 3999.0)
        r = evaluate_transaction(tx, meena_user)

        assert "Multiple transfers in short window" in r["reasons"]
        expected_score = WEIGHTS["new_payee"] + WEIGHTS["high_velocity"]  # 30+20=50
        assert r["score"] == expected_score
        assert r["is_high_risk"] is True
        assert r["action"] == "hold_for_approval"

    def test_total_amount_exposed_before_velocity_triggers(self, meena_user):
        """
        Quantify the maximum damage before the velocity rule fires.
        Velocity fires when recent_transactions has >= VELOCITY_COUNT_THRESHOLD items.
        So the first VELOCITY_COUNT_THRESHOLD transfers slip through before the hold.
        """
        from config import VELOCITY_COUNT_THRESHOLD
        max_per_tx = meena_user["avg_transaction_amount"] * 2  # 4000 — not flagged
        # The first VELOCITY_COUNT_THRESHOLD transfers all pass; next one is held
        max_undetected = VELOCITY_COUNT_THRESHOLD * (max_per_tx - 1)  # ₹11997
        assert max_undetected == VELOCITY_COUNT_THRESHOLD * 3999.0


# ── Same-payee repeat: gap closes faster ──────────────────────────────────────

class TestSamePayeeRepeat:
    """
    If the fraud uses the same payee account repeatedly, the new_payee
    flag disappears after the first approved transfer. This actually makes
    the subsequent transfers cheaper in risk score — but they still slip
    through individually.
    """

    def test_repeat_transfer_to_known_payee_scores_zero(self, meena_user):
        """
        After the first transfer to attacker_acc is approved, the second
        transfer to the same account scores 0 — known payee, normal amount.
        """
        meena_user["known_payees"].add("attacker_acc")
        tx = _safe_tx("attacker_acc", 3999.0)
        result = calculate_risk(tx, meena_user)
        assert result["score"] == 0
        assert result["is_high_risk"] is False

    def test_velocity_still_catches_rapid_repeat_transfers(self, meena_user):
        """
        Even to a known payee, VELOCITY_COUNT_THRESHOLD+ rapid transfers trigger velocity.
        Requires 3 prior transactions in recent_transactions to fire.
        """
        from config import VELOCITY_COUNT_THRESHOLD
        now = datetime.now()
        meena_user["known_payees"].add("attacker_acc")
        meena_user["recent_transactions"] = [
            now - timedelta(minutes=i * 2) for i in range(1, VELOCITY_COUNT_THRESHOLD + 1)
        ]

        tx = _safe_tx("attacker_acc", 3999.0)
        result = calculate_risk(tx, meena_user)
        assert result["score"] == WEIGHTS["high_velocity"]  # only velocity fires (known payee)
        assert result["is_high_risk"] is False              # 20 < 50 threshold

        # GAP documented: velocity alone (score=20) does NOT hit the hold threshold.
        # A rapid-repeat-same-payee attack using <= VELOCITY_COUNT_THRESHOLD-1
        # transfers per 10-min window evades detection entirely.
        assert result["score"] < RISK_THRESHOLD


# ── Score-just-below-threshold combinations ───────────────────────────────────

class TestThresholdBoundary:
    """
    Enumerate all score combinations that land exactly at threshold-1 (49)
    to document which attack patterns just barely evade detection.
    """

    def test_new_payee_plus_odd_hour_just_below_threshold(self, meena_user):
        """
        new_payee(30) + odd_hour(15) = 45 < 50 → passes.
        A midnight transfer to a new payee of any amount < 4001 is safe.
        """
        tx = _safe_tx("attacker_acc", 3999.0)
        tx["timestamp"] = datetime.now().replace(hour=2)   # 2 AM
        result = calculate_risk(tx, meena_user)
        assert result["score"] == WEIGHTS["new_payee"] + WEIGHTS["odd_hour"]  # 45
        assert result["is_high_risk"] is False

    def test_new_payee_plus_velocity_exactly_at_threshold(self, meena_user):
        """
        new_payee(30) + velocity(20) = 50 >= threshold -> HELD.
        Requires VELOCITY_COUNT_THRESHOLD prior txs in recent_transactions.
        """
        from config import VELOCITY_COUNT_THRESHOLD
        now = datetime.now()
        meena_user["recent_transactions"] = [
            now - timedelta(minutes=i * 2) for i in range(1, VELOCITY_COUNT_THRESHOLD + 1)
        ]
        tx = _safe_tx("attacker_acc_new", 3999.0)
        result = calculate_risk(tx, meena_user)
        assert result["score"] == 50
        assert result["is_high_risk"] is True

    def test_odd_hour_plus_velocity_below_threshold(self, meena_user):
        """
        odd_hour(15) + velocity(20) = 35 < 50 → passes even at 2 AM.
        Requires VELOCITY_COUNT_THRESHOLD prior txs in recent_transactions.
        """
        from config import VELOCITY_COUNT_THRESHOLD
        now = datetime.now()
        meena_user["known_payees"].add("attacker_acc")
        meena_user["recent_transactions"] = [
            now - timedelta(minutes=i * 2) for i in range(1, VELOCITY_COUNT_THRESHOLD + 1)
        ]
        tx = _safe_tx("attacker_acc", 3999.0)
        tx["timestamp"] = datetime.now().replace(hour=2)
        result = calculate_risk(tx, meena_user)
        assert result["score"] == WEIGHTS["odd_hour"] + WEIGHTS["high_velocity"]  # 35
        assert result["is_high_risk"] is False
