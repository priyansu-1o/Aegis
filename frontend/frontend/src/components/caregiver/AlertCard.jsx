import { useState } from 'react';
import { getStatusConfig } from '../../statusConfig';
import { resolveTransaction } from '../../utils/api';

/**
 * AlertCard — updated to call POST /api/resolve/:txId via the backend API.
 *
 * Props:
 *   transaction.txId        — backend tx_id (integer)
 *   transaction.customerName
 *   transaction.amount
 *   transaction.beneficiary
 *   transaction.riskReasons  — string[]
 *   transaction.status       — normalised frontend status string
 */
function AlertCard({ transaction, onResolved }) {
  const {
    txId,
    customerName = 'Senior',
    amount = 0,
    beneficiary = '—',
    riskReasons = [],
    status = 'pending_verification',
  } = transaction || {};

  const [currentStatus, setCurrentStatus] = useState(status);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const config = getStatusConfig(currentStatus);
  const isResolved = currentStatus !== 'pending_verification';
  const isHeld     = currentStatus === 'held';

  const formatINR = (n) => '₹' + n.toLocaleString('en-IN');

  const handleResolve = async (decision) => {
    // decision: 'approve' | 'block'
    setLoading(true);
    setError(null);
    try {
      await resolveTransaction(txId, decision);
      const newStatus = decision === 'approve' ? 'approved' : 'held';
      setCurrentStatus(newStatus);
      onResolved?.(txId, newStatus);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card stack-loose">

      {/* Header — label + status pill */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: 'var(--color-ink-faint)',
        }}>
          Safety Check #{txId}
        </span>
        <span className={`pill ${config.pillClass}`}>{config.label}</span>
      </div>

      {/* Amount */}
      <div style={{ textAlign: 'center', padding: 'var(--space-2) 0' }}>
        <span className="font-serif" style={{ fontSize: 'var(--text-2xl)', display: 'block' }}>
          {formatINR(amount)}
        </span>
        <span className="text-soft" style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-1)', display: 'block' }}>
          from {customerName}
        </span>
      </div>

      <div style={{ height: 1, background: 'var(--color-border)' }} />

      {/* Beneficiary */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>Sending to</span>
        <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{beneficiary}</span>
      </div>

      <div style={{ height: 1, background: 'var(--color-border)' }} />

      {/* Risk reasons */}
      {riskReasons.length > 0 && (
        <div className="stack-tight">
          <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            color: 'var(--color-ink-faint)',
          }}>
            Why we're checking
          </span>
          <ul className="stack-tight" style={{ listStyle: 'none' }}>
            {riskReasons.map((reason, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <DotIcon />
                <span style={{ fontSize: 'var(--text-sm)' }}>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* API error */}
      {error && (
        <div
          className="card-flush"
          style={{ background: 'var(--color-status-held-bg)', padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)' }}
        >
          <p style={{ color: 'var(--color-status-held-text)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
            ⚠ {error}
          </p>
        </div>
      )}

      {/* Actions or resolved state */}
      {isResolved ? (
        <div
          className="card-flush"
          style={{
            textAlign: 'center',
            background: isHeld
              ? 'var(--color-status-held-bg)'
              : 'var(--color-status-safe-bg)',
          }}
        >
          <span style={{
            fontWeight: 600,
            fontSize: 'var(--text-sm)',
            color: isHeld
              ? 'var(--color-status-held-text)'
              : 'var(--color-status-safe-text)',
          }}>
            {isHeld
              ? 'You placed this transaction on hold.'
              : 'You verified and allowed this transaction.'}
          </span>
        </div>
      ) : (
        <div className="stack">
          {/* Hold is primary / safe action */}
          <button
            id={`hold-tx-${txId}`}
            className="btn btn-primary"
            onClick={() => handleResolve('block')}
            disabled={loading}
          >
            {loading ? 'Processing…' : 'Hold Transaction'}
          </button>
          {/* Verify & Allow is secondary */}
          <button
            id={`approve-tx-${txId}`}
            className="btn btn-secondary"
            onClick={() => handleResolve('approve')}
            disabled={loading}
          >
            Verify &amp; Allow
          </button>
        </div>
      )}
    </div>
  );
}

function DotIcon() {
  return (
    <svg width="6" height="6" viewBox="0 0 6 6" style={{ flexShrink: 0 }}>
      <circle cx="3" cy="3" r="3" fill="var(--color-status-held-text)" />
    </svg>
  );
}

export default AlertCard;
