/**
 * Aegis — caregiver-side store.
 * Cookie bridge is no longer used; all state comes from the backend API.
 * Exports are kept as no-ops so any residual import sites don't crash.
 */

export function saveTransaction() {}
export function getTransaction() { return null; }
export function updateTransactionStatus() {}
export function clearTransaction() {}

