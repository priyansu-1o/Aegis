import { useState } from 'react';

function BalanceScreen({ onTransfer, onBreakFD }) {
  const [customerName] = useState('Ramesh');
  const [balance] = useState(845000);
  const [fdAmount] = useState(1500000);

  const formatINR = (amount) =>
    '₹' + amount.toLocaleString('en-IN');

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className="surface-dark" style={{ minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ paddingTop: 'var(--space-6)', paddingBottom: 'var(--space-7)' }}>
        <div className="container">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
            <span className="font-serif" style={{ fontSize: 'var(--text-lg)', color: 'var(--color-on-dark)' }}>
              Aegis
            </span>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: 'var(--color-forest-700)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                color: 'var(--color-on-dark)',
              }}
            >
              {customerName.charAt(0)}
            </div>
          </div>

          <p className="text-soft" style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-1)' }}>
            {getGreeting()}
          </p>
          <h1 className="font-serif" style={{ color: 'var(--color-on-dark)' }}>
            {customerName}
          </h1>
        </div>
      </div>

      {/* Content area — pulled up over the dark header with rounded top */}
      <div
        style={{
          background: 'var(--color-bg)',
          borderTopLeftRadius: 'var(--radius-lg)',
          borderTopRightRadius: 'var(--radius-lg)',
          marginTop: '-32px',
          paddingTop: 'var(--space-6)',
          paddingBottom: 'var(--space-7)',
        }}
      >
        <div className="container stack-loose">

          {/* Balance card */}
          <div className="card stack-tight">
            <span className="text-faint" style={{ fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Account Balance
            </span>
            <span className="font-serif" style={{ fontSize: 'var(--text-2xl)' }}>
              {formatINR(balance)}
            </span>
          </div>

          {/* Fixed Deposit card */}
          <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="stack-tight">
              <span className="text-faint" style={{ fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Fixed Deposit
              </span>
              <span className="font-serif" style={{ fontSize: 'var(--text-xl)' }}>
                {formatINR(fdAmount)}
              </span>
            </div>
            <span className="pill pill-safe" style={{ alignSelf: 'flex-start' }}>7.1% p.a.</span>
          </div>

          {/* Protection status strip */}
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
              <ShieldIcon />
            </div>
            <div>
              <p style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>Account Protected</p>
              <p className="text-soft" style={{ fontSize: 'var(--text-xs)' }}>
                Trusted contact is set up for safety verification
              </p>
            </div>
          </div>

          {/* Primary actions */}
          <div className="stack">
            <button className="btn btn-primary" onClick={onTransfer}>
              Transfer Money
            </button>
            <button className="btn btn-secondary" onClick={onBreakFD}>
              Break Fixed Deposit
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 2L4 5V11C4 16 7.5 20.5 12 22C16.5 20.5 20 16 20 11V5L12 2Z"
        stroke="var(--color-status-safe-text)"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M9 12L11 14L15 10"
        stroke="var(--color-status-safe-text)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default BalanceScreen;
