/**
 * api.js — Unified API client for Aegis
 * =======================================
 * All fetch calls use:
 *   credentials: 'include'   → sends/receives the httpOnly aegis_token cookie
 *   Content-Type: application/json
 *
 * Auth:
 *   - login(email, password) → POST /api/login
 *   - logout()               → POST /api/logout
 *   - getMe()                → GET  /api/me
 *
 * Senior:
 *   - submitTransfer(payload)        → POST /api/transfer
 *   - getTransactionById(id)         → GET  /api/transactions/:id
 *
 * Caregiver:
 *   - fetchPendingTransactions()     → GET  /api/transactions/pending
 *   - resolveTransaction(id, dec)    → POST /api/resolve/:id
 */

const BASE_URL = 'http://localhost:5000';

const DEFAULT_OPTS = {
  credentials: 'include',         // send the httpOnly JWT cookie on every request
  headers: { 'Content-Type': 'application/json' },
};

async function _fetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...DEFAULT_OPTS,
    ...options,
    headers: { ...DEFAULT_OPTS.headers, ...(options.headers || {}) },
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    // Attach the status so callers can branch on 401 vs other errors.
    const err = new Error(body.error || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }

  return body;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email, password) {
  return _fetch('/api/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function logout() {
  return _fetch('/api/logout', { method: 'POST' });
}

export async function getMe() {
  return _fetch('/api/me');
}

// ── Senior ────────────────────────────────────────────────────────────────────

export async function submitTransfer(payload) {
  // sender_id is now derived server-side from the JWT — do NOT pass it here.
  // The payload should contain: payee_name, payee_account, amount, note, etc.
  return _fetch('/api/transfer', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTransactionById(txId) {
  return _fetch(`/api/transactions/${txId}`);
}

export async function signup({ name, email, password, role }) {
  return _fetch('/api/signup', {
    method: 'POST',
    body: JSON.stringify({ name, email, password, role }),
  });
}

export async function getTransactions() {
  return _fetch('/api/transactions');
}

// ── Caregiver ─────────────────────────────────────────────────────────────────

export async function fetchPendingTransactions() {
  // caregiver_id is now derived server-side from the JWT — no query param needed.
  return _fetch('/api/transactions/pending');
}

export async function resolveTransaction(txId, decision) {
  return _fetch(`/api/resolve/${txId}`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  });
}
