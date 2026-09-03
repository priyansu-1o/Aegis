"""
tests/test_integration.py
=========================
Integration tests that start a real Flask server (SQLite, no Supabase needed)
and verify two contracts:

  A) /api/transfer  → persists to DB, response shape matches dashboard expectations
  B) Caregiver linking → senior signup → link code → caregiver signup
     → /api/transactions/pending only returns transactions linked to that caregiver

Run:
    cd backend
    pytest tests/test_integration.py -v
    # or directly:
    python tests/test_integration.py
"""

import os
import sys
import time
import subprocess
import requests
import uuid
import pytest

# ── Server lifecycle ──────────────────────────────────────────────────────────

BASE = "http://localhost:5001"          # offset from default 5000 to avoid conflicts
_server_proc = None


def _start_server():
    """Spin up the Flask app on port 5001 in SQLite mode (no .env Supabase keys)."""
    global _server_proc
    env = {**os.environ}
    # Force SQLite by blanking Supabase credentials for this test run
    env["SUPABASE_URL"] = ""
    env["SUPABASE_KEY"] = ""
    env["SUPABASE_SERVICE_ROLE_KEY"] = ""
    env["SUPABASE_ANON_KEY"] = ""

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    _server_proc = subprocess.Popen(
        [sys.executable, "-c",
         "import os; os.environ['SUPABASE_URL']=''; os.environ['SUPABASE_KEY']='';"
         "from app import socketio, app; "
         "socketio.run(app, host='127.0.0.1', port=5001, debug=False, allow_unsafe_werkzeug=True)"],
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait until the server accepts connections (max 10 s)
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=1)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.3)
    return False


def _stop_server():
    global _server_proc
    if _server_proc:
        _server_proc.terminate()
        try:
            _server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _server_proc.kill()
        _server_proc = None


# ── Pytest fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def server():
    ok = _start_server()
    assert ok, "Flask server did not start within 10 seconds"
    yield
    _stop_server()


def _uid():
    """Short unique suffix for test account emails."""
    return uuid.uuid4().hex[:8]


def _signup(name, email, password, role, link_code=None):
    s = requests.Session()
    payload = {"name": name, "email": email, "password": password, "role": role}
    if link_code:
        payload["link_code"] = link_code
    r = s.post(f"{BASE}/api/signup", json=payload)
    return s, r


# ─────────────────────────────────────────────────────────────────────────────
# A)  /api/transfer  — persistence & response shape
# ─────────────────────────────────────────────────────────────────────────────

class TestTransferEndpoint:
    """
    Verifies that POST /api/transfer:
      1. Persists the transaction to the database (round-trips via GET)
      2. Returns the exact response shape the dashboard expects:
             { transaction: { tx_id, status, risk_score, risk_reasons, ... },
               risk:        { score, reasons, is_high_risk, action } }
    """

    def setup_method(self):
        uid = _uid()
        self.senior_email = f"senior_{uid}@test.local"
        self.senior_session, r = _signup(
            name="Test Senior",
            email=self.senior_email,
            password="testpass123",
            role="senior",
        )
        assert r.status_code == 201, f"Senior signup failed: {r.text}"
        self.senior_id = r.json()["user"]["user_id"]

    # ── A1. Successful submission returns 201 ─────────────────────────────────

    def test_transfer_returns_201(self):
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "Test Payee",
            "payee_account": "ACCT_NEW_9001",
            "amount":        500,
            "note":          "groceries",
        })
        assert r.status_code == 201, r.text

    # ── A2. Response top-level keys ───────────────────────────────────────────

    def test_transfer_response_has_transaction_and_risk_keys(self):
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "Payee A",
            "payee_account": "ACCT_A_" + _uid(),
            "amount":        300,
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert "transaction" in body, f"Missing 'transaction' key: {body}"
        assert "risk"        in body, f"Missing 'risk' key: {body}"

    # ── A3. Transaction shape — fields the dashboard reads ────────────────────

    def test_transfer_transaction_shape(self):
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "Payee Shape",
            "payee_account": "ACCT_SHAPE_" + _uid(),
            "amount":        400,
            "note":          "shape test",
        })
        assert r.status_code == 201, r.text
        tx = r.json()["transaction"]

        required_fields = [
            "tx_id", "sender_id", "sender",
            "payee_name", "payee_account", "amount",
            "note", "risk_score", "risk_reasons",
            "status", "resolution", "cooling_off_expiry",
            "created_at",
        ]
        for field in required_fields:
            assert field in tx, f"Missing field '{field}' in transaction response: {tx}"

        # status must be the API-level string (PENDING_APPROVAL or APPROVED)
        assert tx["status"] in ("PENDING_APPROVAL", "APPROVED"), \
            f"Unexpected status '{tx['status']}'"

        # risk_score must be a number
        assert isinstance(tx["risk_score"], (int, float)), \
            f"risk_score is not numeric: {tx['risk_score']!r}"

        # risk_reasons must be a list
        assert isinstance(tx["risk_reasons"], list), \
            f"risk_reasons is not a list: {tx['risk_reasons']!r}"

        # sender sub-object must have a name key
        assert "name" in tx["sender"], \
            f"sender sub-object missing 'name': {tx['sender']}"

    # ── A4. Risk object shape ─────────────────────────────────────────────────

    def test_transfer_risk_object_shape(self):
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "Payee Risk",
            "payee_account": "ACCT_RISK_" + _uid(),
            "amount":        350,
        })
        assert r.status_code == 201, r.text
        risk = r.json()["risk"]

        for field in ("score", "reasons", "is_high_risk", "action"):
            assert field in risk, f"Missing field '{field}' in risk response: {risk}"

        assert isinstance(risk["score"],     (int, float))
        assert isinstance(risk["reasons"],   list)
        assert isinstance(risk["is_high_risk"], bool)
        assert risk["action"] in ("auto_approve", "hold_for_approval")

    # ── A5. High-risk transaction is persisted & readable via GET ─────────────

    def test_high_risk_transfer_persists_to_db(self):
        """
        A large new-payee transfer should be held and retrievable via
        GET /api/transactions/<tx_id>.
        """
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "Scam Payee",
            "payee_account": "SCAM_" + _uid(),
            "amount":        999_999,      # triggers large_amount + new_payee
            "note":          "urgent rbi", # triggers flag_words too
        })
        assert r.status_code == 201, r.text
        body = r.json()
        tx   = body["transaction"]
        risk = body["risk"]

        # Confirm the engine flagged it
        assert tx["status"] == "PENDING_APPROVAL", \
            f"Expected PENDING_APPROVAL for high-risk tx, got '{tx['status']}'"
        assert risk["action"] == "hold_for_approval"
        assert risk["is_high_risk"] is True
        assert len(risk["reasons"]) >= 2, f"Expected >= 2 risk reasons: {risk['reasons']}"

        # ── Round-trip: verify the transaction is actually in the DB ──────────
        tx_id = tx["tx_id"]
        get_r = self.senior_session.get(f"{BASE}/api/transactions/{tx_id}")
        assert get_r.status_code == 200, \
            f"GET /api/transactions/{tx_id} returned {get_r.status_code}: {get_r.text}"

        stored = get_r.json()["transaction"]

        # DB values match the POST response
        assert stored["tx_id"]      == tx_id,          "tx_id mismatch between POST and GET"
        assert stored["amount"]     == tx["amount"],    "amount not persisted"
        assert stored["risk_score"] == tx["risk_score"], "risk_score not persisted"
        assert stored["status"]     == "PENDING_APPROVAL", "status not persisted"

        # risk_reasons survived the DB round-trip (stored as CSV, returned as list)
        assert isinstance(stored["risk_reasons"], list), \
            f"risk_reasons should be list on GET, got: {stored['risk_reasons']!r}"
        assert len(stored["risk_reasons"]) >= 2, \
            f"risk_reasons lost in DB round-trip: {stored['risk_reasons']}"

    # ── A6. Low-risk transaction → APPROVED ───────────────────────────────────

    def test_low_risk_transfer_auto_approved(self):
        """
        A tiny amount with no flag words should auto-approve
        (new_payee=30 pts only < 50 threshold).
        """
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "Family Member",
            "payee_account": "FAMILY_SAFE",
            "amount":        100,
            "note":          "monthly",
        })
        assert r.status_code == 201, r.text
        tx   = r.json()["transaction"]
        risk = r.json()["risk"]

        # new_payee=30 only — should be below 50 threshold (unless odd hour fires)
        if risk["score"] < 50:
            assert tx["status"] == "APPROVED", \
                f"Low-risk tx should be APPROVED, got '{tx['status']}'"
            assert tx["resolution"] == "auto_approved", \
                f"Expected resolution='auto_approved', got '{tx['resolution']}'"
        else:
            assert tx["status"] in ("PENDING_APPROVAL", "APPROVED")

    # ── A7. Validation ────────────────────────────────────────────────────────

    def test_transfer_missing_amount_returns_400(self):
        r = self.senior_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "X",
            "payee_account": "Y",
        })
        assert r.status_code == 400, r.text
        assert "error" in r.json()

    def test_transfer_requires_auth(self):
        r = requests.post(f"{BASE}/api/transfer", json={
            "payee_name":    "X",
            "payee_account": "Y",
            "amount":        100,
        })
        assert r.status_code == 401, r.text

    def test_transfer_caregiver_cannot_submit(self):
        uid = _uid()
        cg_session, r = _signup(
            name="Cg Block Test",
            email=f"cg_block_{uid}@test.local",
            password="testpass123",
            role="caregiver",
        )
        assert r.status_code == 201
        r2 = cg_session.post(f"{BASE}/api/transfer", json={
            "payee_name":    "X",
            "payee_account": "Y",
            "amount":        100,
        })
        assert r2.status_code == 403, \
            f"Caregiver should be blocked (403), got {r2.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# B)  Caregiver linking flow
# ─────────────────────────────────────────────────────────────────────────────

class TestCaregiverLinking:
    """
    Tests the full caregiver-linking lifecycle.

    NOTE: The current /api/signup endpoint accepts a 'link_code' field but
    does NOT yet set senior.caregiver_id. The test marks the linking step as
    xfail so the suite clearly reports WHAT is missing vs what already works.
    """

    def _make_high_risk_payload(self):
        return {
            "payee_name":    "Stranger",
            "payee_account": "STRANGER_" + _uid(),
            "amount":        999_999,
            "note":          "urgent rbi",
        }

    def test_full_caregiver_link_and_pending_filter(self):
        uid = _uid()

        # ── Step 1: sign up senior ─────────────────────────────────────────────
        sr_session, r = _signup(
            name="Linked Senior",
            email=f"linked_sr_{uid}@test.local",
            password="testpass123",
            role="senior",
        )
        assert r.status_code == 201, f"Senior signup failed: {r.text}"
        senior = r.json()["user"]
        senior_id = senior["user_id"]

        # ── Step 2: treat senior's user_id as the link code ───────────────────
        # The DB has no dedicated link_code column; the numeric user_id is what
        # the frontend's 'Senior's link code' field currently sends.
        link_code = str(senior_id)

        # ── Step 3: sign up caregiver passing the link code ───────────────────
        cg_uid = _uid()
        cg_session, r = _signup(
            name="Linked Caregiver",
            email=f"linked_cg_{cg_uid}@test.local",
            password="testpass123",
            role="caregiver",
            link_code=link_code,
        )
        assert r.status_code == 201, f"Caregiver signup failed: {r.text}"
        caregiver_id = r.json()["user"]["user_id"]

        # ── Step 4: confirm senior.caregiver_id is set ────────────────────────
        admin_sr = requests.get(
            f"{BASE}/api/users/{senior_id}",
            cookies=sr_session.cookies,
        ).json().get("user", {})

        linked_caregiver_id = admin_sr.get("caregiver_id")

        print(f"\n  [LINK CHECK] senior_id={senior_id}, caregiver_id={caregiver_id}")
        print(f"  [LINK CHECK] senior.caregiver_id in DB = {linked_caregiver_id!r}")

        link_implemented = (linked_caregiver_id == caregiver_id)
        if not link_implemented:
            pytest.xfail(
                f"LINK NOT IMPLEMENTED: senior.caregiver_id={linked_caregiver_id!r}, "
                f"expected {caregiver_id}. "
                "POST /api/signup accepts 'link_code' but does not write "
                "caregiver_id onto the matched senior row."
            )

        # ── Step 5: senior submits a high-risk transfer ────────────────────────
        r = sr_session.post(f"{BASE}/api/transfer", json=self._make_high_risk_payload())
        assert r.status_code == 201, r.text
        tx    = r.json()["transaction"]
        tx_id = tx["tx_id"]
        assert tx["status"] == "PENDING_APPROVAL"

        # ── Step 6: caregiver sees it in /pending ─────────────────────────────
        pending_r = cg_session.get(f"{BASE}/api/transactions/pending")
        assert pending_r.status_code == 200
        pending_body = pending_r.json()
        pending_ids  = [p["tx_id"] for p in pending_body["pending"]]

        print(f"  [PENDING]  caregiver {caregiver_id} sees tx_ids: {pending_ids}")
        assert tx_id in pending_ids, (
            f"tx_id={tx_id} NOT in caregiver {caregiver_id}'s pending list: {pending_ids}"
        )
        assert pending_body["caregiver_id"] == caregiver_id

        # ── Step 7: unrelated caregiver does NOT see it ───────────────────────
        other_uid = _uid()
        other_cg_session, r2 = _signup(
            name="Other Caregiver",
            email=f"other_cg_{other_uid}@test.local",
            password="testpass123",
            role="caregiver",
        )
        assert r2.status_code == 201
        other_ids = [p["tx_id"]
                     for p in other_cg_session.get(f"{BASE}/api/transactions/pending"
                                                    ).json()["pending"]]
        print(f"  [PENDING]  unrelated caregiver sees tx_ids: {other_ids}")
        assert tx_id not in other_ids, (
            f"tx_id={tx_id} leaked into unrelated caregiver's pending list!"
        )

    def test_pending_empty_for_unlinked_caregiver(self):
        """An unlinked caregiver always starts with 0 pending items."""
        uid = _uid()
        cg_session, r = _signup(
            name="Fresh Caregiver",
            email=f"fresh_cg_{uid}@test.local",
            password="testpass123",
            role="caregiver",
        )
        assert r.status_code == 201
        r2 = cg_session.get(f"{BASE}/api/transactions/pending")
        assert r2.status_code == 200
        body = r2.json()
        assert body["pending_count"] == 0
        assert body["pending"] == []

    def test_pending_response_shape(self):
        """GET /api/transactions/pending top-level keys are always present."""
        uid = _uid()
        cg_session, r = _signup(
            name="Shape CG",
            email=f"shape_cg_{uid}@test.local",
            password="testpass123",
            role="caregiver",
        )
        assert r.status_code == 201
        body = cg_session.get(f"{BASE}/api/transactions/pending").json()

        assert "caregiver_id"  in body, f"Missing 'caregiver_id': {body}"
        assert "pending_count" in body, f"Missing 'pending_count': {body}"
        assert "pending"       in body, f"Missing 'pending': {body}"
        assert isinstance(body["pending"],       list)
        assert isinstance(body["pending_count"], int)

        if body["pending"]:
            item = body["pending"][0]
            for field in ("tx_id", "status", "risk_score", "risk_reasons",
                          "amount", "payee_name", "payee_account"):
                assert field in item, f"pending item missing '{field}': {item}"
            assert isinstance(item["risk_reasons"], list)
            assert item["status"] in ("PENDING_APPROVAL", "APPROVED", "BLOCKED")
