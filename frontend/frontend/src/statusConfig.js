// Shared transaction status → visual treatment mapping.
// Single source of truth so Senior and Caregiver apps never visually diverge.
//
// Backend statuses are uppercase: PENDING_APPROVAL | APPROVED | BLOCKED.
// We normalise them to lowercase keys below.

export const STATUS_CONFIG = {
  // ── Frontend / normalised keys ────────────────────────────────────────────
  pending_verification: {
    pillClass: 'pill-pending',
    label: 'Pending Verification',
  },
  approved: {
    pillClass: 'pill-safe',
    label: 'Approved',
  },
  held: {
    pillClass: 'pill-held',
    label: 'Held',
  },
  expired: {
    pillClass: 'pill-held',
    label: 'Expired',
  },
  // ── Backend uppercase aliases ─────────────────────────────────────────────
  PENDING_APPROVAL: {
    pillClass: 'pill-pending',
    label: 'Pending Verification',
  },
  APPROVED: {
    pillClass: 'pill-safe',
    label: 'Approved',
  },
  BLOCKED: {
    pillClass: 'pill-held',
    label: 'Held',
  },
};

export function getStatusConfig(status) {
  return STATUS_CONFIG[status] || STATUS_CONFIG.pending_verification;
}

/**
 * Normalise a backend status string to the lowercase frontend key
 * used by TransactionStatus and AlertCard.
 */
export function normaliseStatus(backendStatus) {
  const map = {
    PENDING_APPROVAL: 'pending_verification',
    APPROVED: 'approved',
    BLOCKED: 'held',
  };
  return map[backendStatus] ?? backendStatus;
}
