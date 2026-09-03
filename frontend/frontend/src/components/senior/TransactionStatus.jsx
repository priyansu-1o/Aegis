import { useState, useEffect, useCallback } from 'react';
import { getStatusConfig, normaliseStatus } from '../../statusConfig';
import { getTransactionById } from '../../utils/api';
import { useSocket } from '../../utils/useSocket';

/**
 * TransactionStatus — shows the current state of a submitted transaction.
 *
 * Real-time strategy:
 *   PRIMARY  — Socket.IO 'tx_update' event fires instantly when the caregiver
 *              approves or blocks, or when the cooling-off timer expires.
 *   FALLBACK — 5-second polling (reduced from 2 s; socket covers the fast path).
 */
function TransactionStatus({ transaction, onDone }) {
  const {
    txId,
    amount = 1500000,
    beneficiary = 'Raj Enterprises',
    riskReasons = ['High transaction amount', 'New beneficiary', 'Unusual transaction activity'],
    status: rawInitialStatus = 'PENDING_APPROVAL',
    coolingOffExpiry = null,
    transactionType = 'transfer',
  } = transaction || {};

  const isFDBreak = transactionType === 'fd_break';

  const { socket, connected } = useSocket();

  // Normalise initial backend status to frontend key
  const [status, setStatus] = useState(normaliseStatus(rawInitialStatus));

  // ── Countdown derived from cooling_off_expiry ────────────────────────────
  const computeSecondsLeft = () => {
    if (!coolingOffExpiry) return 180;
    const expiry = new Date(coolingOffExpiry + 'Z'); // backend stores naive UTC — append Z
    const diff = Math.floor((expiry - Date.now()) / 1000);
    return Math.max(diff, 0);
  };

  const [secondsLeft, setSecondsLeft] = useState(computeSecondsLeft);

  // Countdown tick — only while pending
  useEffect(() => {
    if (status !== 'pending_verification') return;
    if (secondsLeft <= 0) {
      setStatus('expired');
      return;
    }
    const timer = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [secondsLeft, status]);

  // ── Socket: instant update from server push ──────────────────────────────
  useEffect(() => {
    if (!socket || status !== 'pending_verification' || !txId) return;

    const handleTxUpdate = (data) => {
      if (data.tx_id !== txId) return;
      const next = normaliseStatus(data.status);
      if (next !== 'pending_verification') setStatus(next);
    };

    socket.on('tx_update', handleTxUpdate);
    return () => socket.off('tx_update', handleTxUpdate);
  }, [socket, status, txId]);

  // ── Poll backend every 5 s as fallback ───────────────────────────────────
  const pollOnce = useCallback(async () => {
    if (status !== 'pending_verification' || !txId) return;
    try {
      const data = await getTransactionById(txId);
      const latestStatus = normaliseStatus(data.transaction.status);
      if (latestStatus !== 'pending_verification') setStatus(latestStatus);
    } catch {
      // Network hiccup — keep trying
    }
  }, [status, txId]);

  useEffect(() => {
    if (status !== 'pending_verification' || !txId) return;
    const poll = setInterval(pollOnce, 5000);
    return () => clearInterval(poll);
  }, [pollOnce, status, txId]);

  const formatINR = (n) => '₹' + n.toLocaleString('en-IN');

  const formatTime = (totalSeconds) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const config = getStatusConfig(status);
  const isPending  = status === 'pending_verification';
  const isHeld     = status === 'held';
  const isApproved = status === 'approved';

  const actionLabel = isFDBreak ? 'FD break' : 'transfer';

  const hero = isPending
    ? {
        iconBg: 'var(--color-status-pending-bg)',
        icon: <ShieldPauseIcon />,
        heading: 'Your caregiver has been notified',
        sub: `This ${actionLabel} is temporarily paused while they review it. No money has moved yet.`,
      }
    : isHeld
    ? {
        iconBg: 'var(--color-status-held-bg)',
        icon: <ShieldHoldIcon />,
        heading: 'Transaction on hold',
        sub: `Your caregiver paused this ${actionLabel} for your safety. No money has been transferred.`,
      }
    : isApproved
    ? {
        iconBg: 'var(--color-status-safe-bg)',
        icon: <ShieldCheckIcon />,
        heading: isFDBreak ? 'FD break approved' : 'Transfer approved',
        sub: 'Your caregiver reviewed and verified this transaction.',
      }
    : {
        // expired
        iconBg: 'var(--color-status-held-bg)',
        icon: <ShieldPauseIcon />,
        heading: 'Review window expired',
        sub: 'The safety check period ended. No money has been transferred.',
      };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
      <div className="container stack-loose" style={{ paddingTop: 'var(--space-6)', paddingBottom: 'var(--space-7)' }}>

        {/* State-driven hero */}
        <div className="stack-tight" style={{ alignItems: 'center', textAlign: 'center' }}>
          <div
            style={{
              width: 64, height: 64, borderRadius: '50%',
              background: hero.iconBg,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 'var(--space-2)',
            }}
          >
            {hero.icon}
          </div>
          <h1 className="font-serif" style={{ fontSize: 'var(--text-lg)' }}>
            {hero.heading}
          </h1>
          <p className="text-soft" style={{ fontSize: 'var(--text-sm)', maxWidth: 300 }}>
            {hero.sub}
          </p>
        </div>

        {/* Transaction summary card */}
        <div className="card stack-loose">
          <div style={{ textAlign: 'center' }}>
            <span className="font-serif" style={{ fontSize: 'var(--text-2xl)', display: 'block' }}>
              {formatINR(amount)}
            </span>
            <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>
              {isFDBreak ? 'credited to' : 'to'} {beneficiary}
            </span>
          </div>

          <div style={{ height: 1, background: 'var(--color-border)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>Status</span>
            <span className={`pill ${config.pillClass}`}>{config.label}</span>
          </div>

          {isPending && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>Safe delay ends in</span>
              <span className="font-serif" style={{ fontSize: 'var(--text-md)' }}>
                {formatTime(secondsLeft)}
              </span>
            </div>
          )}

          {/* Live indicator */}
          {isPending && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span
                style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: connected ? 'var(--color-status-safe-text)' : 'var(--color-status-held-text)',
                }}
              />
              <span className="text-soft" style={{ fontSize: 'var(--text-xs)' }}>
                {connected ? 'Waiting for live update…' : 'Checking every 5 s'}
              </span>
            </div>
          )}

          {/* Show tx_id for easy cross-reference in demo */}
          {txId && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>Reference</span>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, fontFamily: 'monospace' }}>
                #{txId}
              </span>
            </div>
          )}
        </div>

        {/* Risk reasons — only shown while pending */}
        {isPending && (
          <div className="card-flush stack-tight">
            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>Why was this flagged?</span>
            <ul className="stack-tight" style={{ listStyle: 'none' }}>
              {riskReasons.map((reason, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <DotIcon />
                  <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Caregiver notified notice */}
        {isPending && (
          <div
            className="card-flush"
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}
          >
            <div
              style={{
                width: 40, height: 40, borderRadius: '50%',
                background: 'var(--color-status-safe-bg)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <BellIcon />
            </div>
            <p style={{ fontSize: 'var(--text-sm)' }}>
              Your trusted caregiver has been notified and can act on this right now.
            </p>
          </div>
        )}

        <button id="back-to-home" className="btn btn-secondary" onClick={onDone}>
          Back to Home
        </button>
      </div>
    </div>
  );
}

function ShieldPauseIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L4 5V11C4 16 7.5 20.5 12 22C16.5 20.5 20 16 20 11V5L12 2Z" stroke="var(--color-status-pending-text)" strokeWidth="1.8" strokeLinejoin="round" />
      <rect x="10" y="9" width="1.6" height="6" rx="0.8" fill="var(--color-status-pending-text)" />
      <rect x="13" y="9" width="1.6" height="6" rx="0.8" fill="var(--color-status-pending-text)" />
    </svg>
  );
}

function ShieldHoldIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L4 5V11C4 16 7.5 20.5 12 22C16.5 20.5 20 16 20 11V5L12 2Z" stroke="var(--color-status-held-text)" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M9.5 9.5L14.5 14.5M14.5 9.5L9.5 14.5" stroke="var(--color-status-held-text)" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function ShieldCheckIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L4 5V11C4 16 7.5 20.5 12 22C16.5 20.5 20 16 20 11V5L12 2Z" stroke="var(--color-status-safe-text)" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M9 12L11 14L15 10" stroke="var(--color-status-safe-text)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DotIcon() {
  return (
    <svg width="6" height="6" viewBox="0 0 6 6" style={{ flexShrink: 0 }}>
      <circle cx="3" cy="3" r="3" fill="var(--color-forest-600)" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 3C9.5 3 7.5 5 7.5 7.5V11L5.5 14.5H18.5L16.5 11V7.5C16.5 5 14.5 3 12 3Z" stroke="var(--color-status-safe-text)" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M10 17.5C10 18.6 10.9 19.5 12 19.5C13.1 19.5 14 18.6 14 17.5" stroke="var(--color-status-safe-text)" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export default TransactionStatus;
