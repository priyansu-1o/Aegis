/**
 * Aegis — unified transaction store.
 * This is the senior-side implementation, which already re-exports
 * all caregiver no-ops so both views can import from this single file.
 *
 * Now that the backend is the source of truth we only persist the
 * numeric tx_id in sessionStorage so TransactionStatus can poll the API.
 */

const KEY = 'aegis_tx_id';

/** Save the backend-assigned transaction id. */
export function saveTxId(txId) {
  sessionStorage.setItem(KEY, String(txId));
}

/** Retrieve the stored transaction id (number | null). */
export function getSavedTxId() {
  const raw = sessionStorage.getItem(KEY);
  return raw ? Number(raw) : null;
}

/** Clear the stored id (called after the user dismisses the status screen). */
export function clearTransaction() {
  sessionStorage.removeItem(KEY);
}

// ── Legacy no-ops kept so any remaining import sites don't crash ──────────────
export function saveTransaction() {}
export function getTransaction() { return null; }
export function updateTransactionStatus() {}
