/**
 * Kavach / Aegis — Senior app API client
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
 * Submit a money transfer (or FD break) from the senior.
 *
 * @param {object} payload
 *   sender_id, payee_name, payee_account, amount,
 *   note?, preceded_by_fd_break?, fd_break_timestamp?
 * @returns {{ transaction, risk }}
 */
export function submitTransfer(payload) {
  return request('POST', '/api/transfer', payload);
}

/**
 * Fetch a single transaction by ID (used for status polling).
 * @param {number} txId
 * @returns {{ transaction }}
 */
export function getTransactionById(txId) {
  return request('GET', `/api/transactions/${txId}`);
}
