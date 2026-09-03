"""smoke_test.py — end-to-end API verification using requests"""
import requests, sys

BASE = "http://localhost:5000"

def section(title):
    print(f"\n\033[96m=== {title} ===\033[0m")

def ok(msg):   print(f"  [OK]   {msg}")
def fail(msg): print(f"  [FAIL] {msg}")

errors = 0
def check(cond, msg):
    global errors
    if cond: ok(msg)
    else:
        fail(msg)
        errors += 1

# ── 1. Health ──────────────────────────────────────────────────────────────────
section("1. Health")
r = requests.get(f"{BASE}/api/health")
check(r.status_code == 200, f"200 OK — storage: {r.json()['storage']}")

# ── 2. Unauthenticated ────────────────────────────────────────────────────────
section("2. Unauthenticated endpoints → 401")
for url in ["/api/me", "/api/transactions/pending", "/api/transactions"]:
    r = requests.get(f"{BASE}{url}")
    check(r.status_code == 401, f"401 {url}")

# ── 3. Caregiver login ────────────────────────────────────────────────────────
section("3. Caregiver login")
cg = requests.Session()
r = cg.post(f"{BASE}/api/login", json={"email": "caregiver@aegis.demo", "password": "demo1234"})
check(r.status_code == 200, f"200 login — role={r.json()['user']['role']}")
check(r.json()["user"]["role"] == "caregiver", "role=caregiver")
check("aegis_token" in r.cookies or "aegis_token" in cg.cookies, "aegis_token cookie set")

# ── 4. /api/me ────────────────────────────────────────────────────────────────
section("4. /api/me with caregiver session")
r = cg.get(f"{BASE}/api/me")
check(r.status_code == 200, f"200 — name={r.json()['user']['name']}")

# ── 5. /api/transactions/pending ─────────────────────────────────────────────
section("5. GET /api/transactions/pending (caregiver)")
r = cg.get(f"{BASE}/api/transactions/pending")
check(r.status_code == 200, f"200 — {r.json()['pending_count']} pending")

# ── 6. Senior login ───────────────────────────────────────────────────────────
section("6. Senior login")
sr = requests.Session()
r = sr.post(f"{BASE}/api/login", json={"email": "senior@aegis.demo", "password": "demo1234"})
check(r.status_code == 200, f"200 — name={r.json()['user']['name']}")
check(r.json()["user"]["role"] == "senior", "role=senior")

# ── 7. Role fence: senior cannot access caregiver route ──────────────────────
section("7. Role fence: senior → /api/transactions/pending (expect 403)")
r = sr.get(f"{BASE}/api/transactions/pending")
check(r.status_code == 403, f"403 role gate")

# ── 8. Submit high-risk transfer ─────────────────────────────────────────────
section("8. POST /api/transfer (₹55,000, new payee → hold)")
r = sr.post(f"{BASE}/api/transfer", json={
    "payee_name": "Test Scammer",
    "payee_account": "9999999999",
    "amount": 55000,
})
check(r.status_code == 201, "201 created")
tx = r.json()["transaction"]
tx_id = tx["tx_id"]
check(tx["status"] == "PENDING_APPROVAL", f"status=PENDING_APPROVAL (tx_id={tx_id})")
check(tx["risk_score"] >= 50, f"risk_score={tx['risk_score']} >= 50")
print(f"     reasons: {tx['risk_reasons']}")

# ── 9. Audit log (initial) ────────────────────────────────────────────────────
section(f"9. GET /api/transactions/{tx_id}/audit (senior)")
r = sr.get(f"{BASE}/api/transactions/{tx_id}/audit")
check(r.status_code == 200, "200 OK")
events = [e["event"] for e in r.json()["audit_log"]]
check("transaction_created" in events, f"transaction_created present — log: {events}")
check("hold_created" in events, f"hold_created present")

# ── 10. Senior cannot resolve ─────────────────────────────────────────────────
section(f"10. Senior tries to resolve (expect 403)")
r = sr.post(f"{BASE}/api/resolve/{tx_id}", json={"decision": "approve"})
check(r.status_code == 403, f"403 role gate on resolve")

# ── 11. Caregiver approves ────────────────────────────────────────────────────
section("11. Caregiver approves")
r = cg.post(f"{BASE}/api/resolve/{tx_id}", json={"decision": "approve"})
check(r.status_code == 200, "200 OK")
resolved = r.json()["transaction"]
check(resolved["status"] == "APPROVED", f"status=APPROVED resolution={resolved['resolution']}")

# ── 12. Full audit trail ──────────────────────────────────────────────────────
section("12. Full audit trail after resolution")
r = sr.get(f"{BASE}/api/transactions/{tx_id}/audit")
log = r.json()["audit_log"]
expected_events = ["transaction_created", "hold_created", "caregiver_approved"]
for ev in expected_events:
    check(any(e["event"] == ev for e in log), f"event '{ev}' in audit log")
for e in log:
    print(f"     [{e['created_at']}] {e['event']}  actor_role={e['actor_role']}  actor_id={e['actor_id']}")

# ── 13. Logout ────────────────────────────────────────────────────────────────
section("13. Logout")
r = sr.post(f"{BASE}/api/logout")
check(r.status_code == 200, "200 OK")
r = sr.get(f"{BASE}/api/me")
check(r.status_code == 401, "401 after logout")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
if errors == 0:
    print("\033[92mAll checks passed ✓\033[0m")
else:
    print(f"\033[91m{errors} check(s) FAILED\033[0m")
    sys.exit(1)
