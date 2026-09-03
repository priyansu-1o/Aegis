import { useState } from 'react';

// Fixed deposit details — in a real app these would come from props/API
const FD_AMOUNT = 1500000;
const FD_TENURE = '24 months';
const FD_RATE = '7.1% p.a.';
const FD_ACCOUNT = 'Savings Account · ····4821';

function FDBreakFlow({ onBack, onSubmit, apiError }) {
  const [step, setStep] = useState('review'); // 'review' | 'confirm'
  const [loading, setLoading] = useState(false);

  const formatINR = (n) => '₹' + n.toLocaleString('en-IN');

  const handleConfirm = async () => {
    setLoading(true);
    await onSubmit?.({ amount: FD_AMOUNT });
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
      {/* Top bar */}
      <div className="container" style={{ paddingTop: 'var(--space-5)', paddingBottom: 'var(--space-4)' }}>
        <button
          onClick={step === 'confirm' ? () => setStep('review') : onBack}
          className="btn-text"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontWeight: 600 }}
        >
          <BackIcon /> Back
        </button>
      </div>

      <div className="container stack-loose" style={{ paddingBottom: 'var(--space-7)' }}>
        <h1 className="font-serif">
          {step === 'review' ? 'Break Fixed Deposit' : 'Confirm FD Break'}
        </h1>

        {step === 'review' ? (
          <div className="stack-loose">
            {/* FD details card */}
            <div className="card stack-loose">
              <SummaryRow label="Fixed Deposit" value={formatINR(FD_AMOUNT)} large />
              <Divider />
              <SummaryRow label="Tenure" value={FD_TENURE} />
              <SummaryRow label="Interest Rate" value={FD_RATE} />
              <Divider />
              <SummaryRow label="Proceeds to" value={FD_ACCOUNT} />
            </div>

            <p className="text-soft" style={{ fontSize: 'var(--text-xs)', textAlign: 'center' }}>
              Breaking your FD before maturity may result in a reduced interest payout.
            </p>

            <button className="btn btn-primary" onClick={() => setStep('confirm')}>
              Continue
            </button>
          </div>
        ) : (
          <div className="stack-loose">
            {/* Confirmation summary */}
            <div className="card stack-loose">
              <SummaryRow label="Breaking FD of" value={formatINR(FD_AMOUNT)} large />
              <Divider />
              <SummaryRow label="Credited to" value={FD_ACCOUNT} />
            </div>

            {apiError && (
              <div
                className="card-flush"
                style={{ background: 'var(--color-status-held-bg)', padding: 'var(--space-3)', borderRadius: 'var(--radius-sm)' }}
              >
                <p style={{ color: 'var(--color-status-held-text)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                  ⚠ {apiError}
                </p>
              </div>
            )}

            <p className="text-soft" style={{ fontSize: 'var(--text-xs)', textAlign: 'center' }}>
              Aegis reviews every large account action for your safety before it completes.
            </p>

            <button
              id="confirm-fd-break"
              className="btn btn-primary"
              onClick={handleConfirm}
              disabled={loading}
            >
              {loading ? 'Submitting…' : 'Confirm FD Break'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryRow({ label, value, large }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>{label}</span>
      <span
        className={large ? 'font-serif' : ''}
        style={{ fontSize: large ? 'var(--text-lg)' : 'var(--text-base)', fontWeight: large ? 500 : 600 }}
      >
        {value}
      </span>
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--color-border)' }} />;
}

function BackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M15 18L9 12L15 6" stroke="var(--color-forest-700)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default FDBreakFlow;
