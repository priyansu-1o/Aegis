"""
tests/test_risk_engine.py
=========================
Unit tests for every rule in risk_engine.py and the top-level
calculate_risk() / evaluate_transaction() aggregators.

Run with:
    pytest tests/ -v
"""

import pytest
from datetime import datetime, timedelta, timezone
from risk_engine import (
    is_new_payee,
    is_large_amount,
    is_recent_fd_break,
    is_odd_hour,
    has_flag_words,
    is_high_velocity,
    calculate_risk,
    evaluate_transaction,
    WEIGHTS,
    RISK_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_user():
    """A typical senior with one known payee and no recent transactions."""
    return {
        "known_payees": {"9876543210"},
        "avg_transaction_amount": 5000.0,
        "recent_transactions": [],
    }


@pytest.fixture
def base_tx():
    """A safe, low-risk transaction — known payee, normal amount, daytime."""
    return {
        "payee_account": "9876543210",
        "amount": 3000.0,
        "note": "",
        "preceded_by_fd_break": False,
        "fd_break_timestamp": None,
        "timestamp": datetime.now().replace(hour=14),   # 2 PM — normal hour
    }


# ── is_new_payee ──────────────────────────────────────────────────────────────

class TestIsNewPayee:
    def test_known_payee_not_flagged(self, base_tx, base_user):
        assert is_new_payee(base_tx, base_user) is False

    def test_unknown_payee_flagged(self, base_tx, base_user):
        base_tx["payee_account"] = "0000000000"
        assert is_new_payee(base_tx, base_user) is True

    def test_empty_known_payees_always_new(self, base_tx):
        user = {"known_payees": set(), "avg_transaction_amount": 5000, "recent_transactions": []}
        assert is_new_payee(base_tx, user) is True


# ── is_large_amount ───────────────────────────────────────────────────────────

class TestIsLargeAmount:
    def test_normal_amount_not_flagged(self, base_tx, base_user):
        # 3000 vs avg 5000 * 2 = 10000 threshold → not large
        assert is_large_amount(base_tx, base_user) is False

    def test_exactly_at_threshold_not_flagged(self, base_tx, base_user):
        # 5000 * 2 = 10000; amount must be > threshold, not >=
        base_tx["amount"] = 10000.0
        assert is_large_amount(base_tx, base_user) is False

    def test_above_threshold_flagged(self, base_tx, base_user):
        base_tx["amount"] = 10001.0
        assert is_large_amount(base_tx, base_user) is True

    def test_large_amount_with_zero_avg_uses_default(self, base_tx):
        user = {"known_payees": set(), "recent_transactions": []}  # no avg key
        base_tx["amount"] = 10001.0   # > default 5000 * 2
        assert is_large_amount(base_tx, user) is True


# ── is_recent_fd_break ────────────────────────────────────────────────────────

class TestIsRecentFdBreak:
    def test_no_fd_break_not_flagged(self, base_tx):
        assert is_recent_fd_break(base_tx) is False

    def test_fd_break_within_window_flagged(self, base_tx):
        base_tx["preceded_by_fd_break"] = True
        base_tx["fd_break_timestamp"] = datetime.now() - timedelta(minutes=5)
        assert is_recent_fd_break(base_tx) is True

    def test_fd_break_with_browser_utc_timestamp_flagged(self, base_tx):
        base_tx["preceded_by_fd_break"] = True
        base_tx["fd_break_timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        assert is_recent_fd_break(base_tx) is True

    def test_fd_break_exactly_at_window_edge_flagged(self, base_tx):
        # Use 29.5 min (well within 30-min window) to avoid flakiness from
        # the few milliseconds of test execution time eating into the boundary.
        base_tx["preceded_by_fd_break"] = True
        base_tx["fd_break_timestamp"] = datetime.now() - timedelta(minutes=29, seconds=30)
        assert is_recent_fd_break(base_tx) is True

    def test_fd_break_outside_window_not_flagged(self, base_tx):
        base_tx["preceded_by_fd_break"] = True
        base_tx["fd_break_timestamp"] = datetime.now() - timedelta(minutes=31)
        assert is_recent_fd_break(base_tx) is False

    def test_fd_break_true_but_missing_timestamp_not_flagged(self, base_tx):
        base_tx["preceded_by_fd_break"] = True
        base_tx["fd_break_timestamp"] = None
        assert is_recent_fd_break(base_tx) is False


# ── is_odd_hour ───────────────────────────────────────────────────────────────

class TestIsOddHour:
    @pytest.mark.parametrize("hour", [0, 1, 3, 5])
    def test_early_morning_flagged(self, base_tx, hour):
        base_tx["timestamp"] = datetime.now().replace(hour=hour)
        assert is_odd_hour(base_tx) is True

    @pytest.mark.parametrize("hour", [23])
    def test_late_night_flagged(self, base_tx, hour):
        base_tx["timestamp"] = datetime.now().replace(hour=hour)
        assert is_odd_hour(base_tx) is True

    @pytest.mark.parametrize("hour", [6, 10, 14, 20, 22])
    def test_normal_hours_not_flagged(self, base_tx, hour):
        base_tx["timestamp"] = datetime.now().replace(hour=hour)
        assert is_odd_hour(base_tx) is False


# ── has_flag_words ────────────────────────────────────────────────────────────

class TestHasFlagWords:
    def test_clean_note_not_flagged(self, base_tx):
        base_tx["note"] = "monthly rent"
        assert has_flag_words(base_tx) is False

    def test_empty_note_not_flagged(self, base_tx):
        base_tx["note"] = ""
        assert has_flag_words(base_tx) is False

    def test_none_note_not_flagged(self, base_tx):
        base_tx["note"] = None
        assert has_flag_words(base_tx) is False

    @pytest.mark.parametrize("note", [
        "RBI verification required",
        "Transfer to safe account",
        "Police asked me to send",
        "CBI investigation funds",
        "Digital arrest avoid",
    ])
    def test_scam_keywords_flagged(self, base_tx, note):
        base_tx["note"] = note
        assert has_flag_words(base_tx) is True

    def test_case_insensitive(self, base_tx):
        base_tx["note"] = "RBI VERIFICATION"
        assert has_flag_words(base_tx) is True


# ── is_high_velocity ──────────────────────────────────────────────────────────

class TestIsHighVelocity:
    def test_no_recent_transactions_not_flagged(self, base_user):
        assert is_high_velocity(base_user) is False

    def test_two_transactions_not_flagged(self, base_user):
        base_user["recent_transactions"] = [
            datetime.now() - timedelta(minutes=2),
            datetime.now() - timedelta(minutes=4),
        ]
        assert is_high_velocity(base_user) is False

    def test_three_transactions_in_window_flagged(self, base_user):
        base_user["recent_transactions"] = [
            datetime.now() - timedelta(minutes=1),
            datetime.now() - timedelta(minutes=3),
            datetime.now() - timedelta(minutes=5),
        ]
        assert is_high_velocity(base_user) is True

    def test_old_transactions_outside_window_not_flagged(self, base_user):
        base_user["recent_transactions"] = [
            datetime.now() - timedelta(minutes=15),
            datetime.now() - timedelta(minutes=20),
            datetime.now() - timedelta(minutes=25),
        ]
        assert is_high_velocity(base_user) is False


# ── calculate_risk ────────────────────────────────────────────────────────────

class TestCalculateRisk:
    def test_safe_transaction_low_score(self, base_tx, base_user):
        result = calculate_risk(base_tx, base_user)
        assert result["score"] == 0
        assert result["is_high_risk"] is False
        assert result["reasons"] == []

    def test_new_payee_adds_correct_weight(self, base_tx, base_user):
        base_tx["payee_account"] = "9999999999"
        result = calculate_risk(base_tx, base_user)
        assert result["score"] == WEIGHTS["new_payee"]
        assert "New payee" in result["reasons"]

    def test_flag_word_adds_correct_weight(self, base_tx, base_user):
        base_tx["note"] = "rbi verification"
        result = calculate_risk(base_tx, base_user)
        assert result["score"] == WEIGHTS["flag_words"]

    def test_multiple_flags_scores_accumulate(self, base_tx, base_user):
        # New payee (30) + flag word (40) = 70 → high risk
        base_tx["payee_account"] = "9999999999"
        base_tx["note"] = "safe account"
        result = calculate_risk(base_tx, base_user)
        assert result["score"] == WEIGHTS["new_payee"] + WEIGHTS["flag_words"]
        assert result["is_high_risk"] is True

    def test_score_at_threshold_is_high_risk(self, base_tx, base_user):
        # new_payee (30) + large_amount (55) = 85 — above threshold
        base_tx["payee_account"] = "9999999999"
        base_tx["amount"] = 60000.0        # triggers large_amount
        result = calculate_risk(base_tx, base_user)
        assert result["score"] >= RISK_THRESHOLD
        assert result["is_high_risk"] is True

    # Exact edge cases from risk_engine.py's own __main__ block
    def test_edge_new_payee_odd_hour_only(self, base_user):
        now = datetime.now()
        tx = {
            "payee_account": "stranger", "amount": 3000, "note": "",
            "preceded_by_fd_break": False, "timestamp": now.replace(hour=23),
        }
        result = calculate_risk(tx, base_user)
        assert result["score"] == 45
        assert result["is_high_risk"] is False

    def test_edge_new_payee_large_amount(self, base_user):
        now = datetime.now()
        tx = {
            "payee_account": "stranger", "amount": 100000, "note": "",
            "preceded_by_fd_break": False, "timestamp": now.replace(hour=14),
        }
        result = calculate_risk(tx, base_user)
        assert result["score"] == WEIGHTS["new_payee"] + WEIGHTS["large_amount"]
        assert result["is_high_risk"] is True

    def test_edge_fd_break_and_keyword_known_payee(self, base_user):
        now = datetime.now()
        tx = {
            "payee_account": "9876543210",   # known payee
            "amount": 3000, "note": "safe account transfer",
            "preceded_by_fd_break": True,
            "fd_break_timestamp": now - timedelta(minutes=2),
            "timestamp": now.replace(hour=14),
        }
        result = calculate_risk(tx, base_user)
        assert result["score"] == 75
        assert result["is_high_risk"] is True


# ── evaluate_transaction ──────────────────────────────────────────────────────

class TestEvaluateTransaction:
    def test_safe_tx_auto_approved(self, base_tx, base_user):
        result = evaluate_transaction(base_tx, base_user)
        assert result["action"] == "auto_approve"
        assert result["is_high_risk"] is False

    def test_high_risk_tx_held(self, base_tx, base_user):
        base_tx["payee_account"] = "stranger"
        base_tx["note"] = "rbi verification"
        result = evaluate_transaction(base_tx, base_user)
        assert result["action"] == "hold_for_approval"
        assert result["is_high_risk"] is True

    def test_result_contains_score_and_reasons(self, base_tx, base_user):
        result = evaluate_transaction(base_tx, base_user)
        assert "score" in result
        assert "reasons" in result
        assert "action" in result
        assert "is_high_risk" in result
