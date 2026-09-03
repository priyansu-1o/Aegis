import { useState, useEffect, useCallback } from 'react';
import AlertCard from './AlertCard';
import { fetchPendingTransactions } from '../../utils/api';
import { useSocket } from '../../utils/useSocket';
import { normaliseStatus } from '../../statusConfig';

/**
 * PendingList — shows the caregiver's pending transactions.
 *
 * Real-time strategy:
 *   PRIMARY  — Socket.IO 'pending_update' event fires instantly when a new
 *              transaction is created by the senior.
 *   FALLBACK — 10-second polling (reduced from 5 s since socket covers the
 *              fast path). Also runs as the initial load.
 *
 * The socket connection status is shown in the header so the caregiver can
 * see if they're receiving live updates.
 */
function PendingList() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [fetchError, setFetchError]     = useState(null);
  const { socket, connected }           = useSocket();

  // Normalise a backend transaction object to the shape AlertCard expects.
  const normalise = (tx) => ({
    txId:         tx.tx_id,
    id:           String(tx.tx_id),
    customerName: tx.sender?.name ?? `User #${tx.sender_id}`,
    amount:       tx.amount,
    beneficiary:  tx.payee_name,
    riskReasons:  tx.risk_reasons ?? [],
    status:       normaliseStatus(tx.status),
  });

  const loadPending = useCallback(async () => {
    try {
      const data = await fetchPendingTransactions(); // caregiver_id from JWT
      setTransactions(data.pending.map(normalise));
      setFetchError(null);
    } catch (err) {
      if (err.status === 401) {
        // Session expired — let the parent auth guard handle the redirect
        setFetchError('Session expired. Please log in again.');
      } else {
        setFetchError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => { loadPending(); }, [loadPending]);

  // Polling fallback — 10 s (socket covers the fast path)
  useEffect(() => {
    const interval = setInterval(loadPending, 10_000);
    return () => clearInterval(interval);
  }, [loadPending]);

  // Socket: real-time new-pending notification
  useEffect(() => {
    if (!socket) return;

    const handlePendingUpdate = () => {
      // A new transaction was flagged — refresh the list immediately
      loadPending();
    };

    socket.on('pending_update', handlePendingUpdate);
    return () => socket.off('pending_update', handlePendingUpdate);
  }, [socket, loadPending]);

  // Called by AlertCard after a successful resolve — update local state immediately
  const handleResolved = (txId, newStatus) => {
    setTransactions((prev) =>
      prev.map((t) => (t.txId === txId ? { ...t, status: newStatus } : t))
    );
  };

  if (loading) {
    return (
      <div className="card-flush" style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
        <p className="text-soft">Loading pending transactions…</p>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div
        className="card-flush"
        style={{ textAlign: 'center', padding: 'var(--space-6)', background: 'var(--color-status-held-bg)' }}
      >
        <p style={{ color: 'var(--color-status-held-text)', fontWeight: 600 }}>
          ⚠ Could not connect to backend
        </p>
        <p className="text-soft" style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>
          {fetchError}
        </p>
      </div>
    );
  }

  const pending  = transactions.filter((t) => t.status === 'pending_verification');
  const resolved = transactions.filter((t) => t.status !== 'pending_verification');

  // Live indicator shown inside the list area
  const LiveBadge = () => (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
        marginBottom: 'var(--space-3)',
      }}
    >
      <span
        style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: connected ? 'var(--color-status-safe-text)' : 'var(--color-status-held-text)',
          boxShadow: connected ? '0 0 0 3px rgba(52,199,89,0.25)' : 'none',
        }}
      />
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ink-soft)' }}>
        {connected ? 'Live updates active' : 'Live updates unavailable — polling every 10 s'}
      </span>
    </div>
  );

  if (transactions.length === 0) {
    return (
      <div className="stack-tight">
        <LiveBadge />
        <div className="card-flush" style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
          <p className="text-soft">No safety checks right now. All clear.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="stack-loose">
      <LiveBadge />
      {pending.map((transaction) => (
        <AlertCard
          key={transaction.txId}
          transaction={transaction}
          onResolved={handleResolved}
        />
      ))}
      {resolved.map((transaction) => (
        <AlertCard
          key={transaction.txId}
          transaction={transaction}
          onResolved={handleResolved}
        />
      ))}
    </div>
  );
}

export default PendingList;
