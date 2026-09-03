"""
Manual end-to-end API smoke test.
Run against a live server: python tests/api_test.py
"""

import requests
import json

BASE = "http://127.0.0.1:5000"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def show(label, resp):
    status_icon = "[OK]  " if resp.ok else "[FAIL]"
    print(f"\n{status_icon} [{resp.status_code}] {label}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)
    return resp


# ── 1. Health check ──────────────────────────────────────────────────────────
section("1. Health Check")
show("GET /api/health", requests.get(f"{BASE}/api/health"))


# ── 2. List users (seeded demo data) ─────────────────────────────────────────
section("2. List Users (seeded data)")
show("GET /api/users", requests.get(f"{BASE}/api/users"))


# ── 3. Get a single user ──────────────────────────────────────────────────────
section("3. Get Single User")
show("GET /api/users/2  (senior)", requests.get(f"{BASE}/api/users/2"))
show("GET /api/users/99 (not found)", requests.get(f"{BASE}/api/users/99"))


# ── 4. Submit a LOW-risk transfer (should auto-approve) ───────────────────────
section("4. Low-Risk Transfer — expect auto_approve")
low_risk = {
    "sender_id": 2,
    "payee_name": "Rahul Sharma",
    "payee_account": "9876543210",   # will be new payee → score 30, still < 50
    "amount": 1000,
    "note": "monthly groceries",
}
r_low = show("POST /api/transfer (low-risk)", requests.post(f"{BASE}/api/transfer", json=low_risk))
low_tx_id = r_low.json().get("transaction", {}).get("tx_id")


# ── 5. Submit a HIGH-risk transfer (should hold for approval) ─────────────────
section("5. High-Risk Transfer — expect hold_for_approval")
high_risk = {
    "sender_id": 2,
    "payee_name": "Unknown Person",
    "payee_account": "1111111111",
    "amount": 75000,
    "note": "safe account rbi verification",
    "preceded_by_fd_break": True,
    "fd_break_timestamp": "2026-09-03T10:00:00",
}
r_high = show("POST /api/transfer (high-risk)", requests.post(f"{BASE}/api/transfer", json=high_risk))
high_tx_id = r_high.json().get("transaction", {}).get("tx_id")


# ── 6. List pending transactions ──────────────────────────────────────────────
section("6. Pending Transactions")
show("GET /api/transactions/pending", requests.get(f"{BASE}/api/transactions/pending"))
show("GET /api/transactions/pending?caregiver_id=1", requests.get(f"{BASE}/api/transactions/pending?caregiver_id=1"))


# ── 7. Get a single transaction ───────────────────────────────────────────────
section("7. Get Single Transaction")
if high_tx_id:
    show(f"GET /api/transactions/{high_tx_id}", requests.get(f"{BASE}/api/transactions/{high_tx_id}"))
show("GET /api/transactions/9999 (not found)", requests.get(f"{BASE}/api/transactions/9999"))


# ── 8. Resolve: APPROVE the pending transaction ───────────────────────────────
section("8. Caregiver Approves the Pending Transaction")
if high_tx_id:
    show(f"POST /api/resolve/{high_tx_id} approve", requests.post(f"{BASE}/api/resolve/{high_tx_id}", json={"decision": "approve"}))

# ── 9. Try resolving again (should 409 — not pending anymore) ─────────────────
section("9. Double-Resolve — expect 409")
if high_tx_id:
    show(f"POST /api/resolve/{high_tx_id} again", requests.post(f"{BASE}/api/resolve/{high_tx_id}", json={"decision": "approve"}))


# ── 10. Submit another high-risk tx then BLOCK it ────────────────────────────
section("10. Caregiver Blocks a Different Pending Transaction")
r2 = requests.post(f"{BASE}/api/transfer", json={
    "sender_id": 2,
    "payee_name": "Scammer",
    "payee_account": "2222222222",
    "amount": 80000,
    "note": "digital arrest government",
})
tx2_id = r2.json().get("transaction", {}).get("tx_id")
if tx2_id:
    show(f"POST /api/resolve/{tx2_id} block", requests.post(f"{BASE}/api/resolve/{tx2_id}", json={"decision": "block"}))


# ── 11. List all transactions for sender ──────────────────────────────────────
section("11. Transaction History for Senior (sender_id=2)")
show("GET /api/transactions?sender_id=2", requests.get(f"{BASE}/api/transactions?sender_id=2"))


# ── 12. Error cases ───────────────────────────────────────────────────────────
section("12. Error Cases")
show("Missing fields", requests.post(f"{BASE}/api/transfer", json={"sender_id": 2}))
show("Invalid sender", requests.post(f"{BASE}/api/transfer", json={
    "sender_id": 9999, "payee_name": "x", "payee_account": "x", "amount": 100
}))
show("Caregiver as sender (403)", requests.post(f"{BASE}/api/transfer", json={
    "sender_id": 1, "payee_name": "x", "payee_account": "x", "amount": 100
}))
show("Invalid decision", requests.post(f"{BASE}/api/resolve/1", json={"decision": "maybe"}))


print(f"\n{'='*60}")
print("  All tests done!")
print('='*60)
