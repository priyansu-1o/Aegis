/**
 * Kavach / Aegis — Caregiver app API client
 * All calls go to the Flask backend at http://localhost:5000
 */

const BASE_URL = 'http://localhost:5000';

async function request(method, path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) {
    const msg = data?.error || `Request failed: ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/**
 * Fetch all pending transactions for the given caregiver.
 * @param {number} caregiverId
 * @returns {{ pending: Transaction[] }}
 */
export function fetchPendingTransactions(caregiverId = 1) {
  return request('GET', `/api/transactions/pending?caregiver_id=${caregiverId}`);
}

/**
 * Approve or block a pending transaction.
 * @param {number} txId
 * @param {'approve' | 'block'} decision
 * @returns {{ transaction }}
 */
export function resolveTransaction(txId, decision) {
  return request('POST', `/api/resolve/${txId}`, { decision });
}
