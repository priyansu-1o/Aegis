import { useState, useEffect } from 'react';
import AlertCard from './AlertCard';
import { fetchPendingTransactions } from '../utils/api';
import { normaliseStatus } from '../statusConfig';

/**
 * PendingList — fetches PENDING_APPROVAL transactions from the backend.
 * Polls every 5 s so new transactions submitted by the senior appear automatically.
 */
function PendingList() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Normalise a backend transaction object to the shape AlertCard expects.
  const normalise = (tx) => ({
    txId:         tx.tx_id,
    id:           String(tx.tx_id),     // AlertCard uses string id
    customerName: tx.sender?.name ?? `User #${tx.sender_id}`,
    amount:       tx.amount,
    beneficiary:  tx.payee_name,
    riskReasons:  tx.risk_reasons ?? [],
    status:       normaliseStatus(tx.status),
  });

  const loadPending = async () => {
    try {
      const data = await fetchPendingTransactions(1); // caregiver id=1
      setTransactions(data.pending.map(normalise));
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => { loadPending(); }, []);

  // Poll every 5 s
  useEffect(() => {
    const interval = setInterval(loadPending, 5000);
    return () => clearInterval(interval);
  }, []);

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

  if (error) {
    return (
      <div
        className="card-flush"
        style={{ textAlign: 'center', padding: 'var(--space-6)', background: 'var(--color-status-held-bg)' }}
      >
        <p style={{ color: 'var(--color-status-held-text)', fontWeight: 600 }}>
          ⚠ Could not connect to backend
        </p>
        <p className="text-soft" style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>
          {error}
        </p>
      </div>
    );
  }

  // Show only truly pending items (not yet resolved in this session)
  const pending = transactions.filter((t) => t.status === 'pending_verification');
  const resolved = transactions.filter((t) => t.status !== 'pending_verification');

  if (transactions.length === 0) {
    return (
      <div className="card-flush" style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
        <p className="text-soft">No safety checks right now. All clear.</p>
      </div>
    );
  }

  return (
    <div className="stack-loose">
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