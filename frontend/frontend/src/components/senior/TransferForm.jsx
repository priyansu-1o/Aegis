import { useState, useEffect } from 'react';
import { getTransactions } from '../../utils/api';

/**
 * TransferForm — updated with:
 * - payee_account input (required by backend)
 * - loading spinner while the API call is in flight
 * - inline error display if the API returns an error
 */
function TransferForm({ onBack, onSubmit, apiError, balance = 0 }) {
  const [step, setStep] = useState('form'); // 'form' | 'review'
  const [payeeName,    setPayeeName]    = useState('');
  const [payeeAccount, setPayeeAccount] = useState('');
  const [amount,       setAmount]       = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);

  // Fetch the senior's past approved payee accounts once on mount so we can
  // show the "New Beneficiary" badge accurately instead of on every entry.
  const [knownAccounts, setKnownAccounts] = useState(null); // null = loading

  useEffect(() => {
    getTransactions()
      .then((data) => {
        const approved = (data.transactions || [])
          .filter((tx) => tx.status === 'APPROVED')
          .map((tx) => tx.payee_account);
        setKnownAccounts(new Set(approved));
      })
      .catch(() => setKnownAccounts(new Set())); // graceful fallback
  }, []);

  // True when the typed account number hasn't been seen in approved history.
  // While history is loading (null) we conservatively assume it IS new.
  const isNewBeneficiary = payeeAccount
    ? knownAccounts === null || !knownAccounts.has(payeeAccount)
    : false;

  const formatINR = (value) => {
    const num = Number(String(value).replace(/[^0-9]/g, ''));
    if (!num) return '';
    return num.toLocaleString('en-IN');
  };

  const numericAmount = Number(String(amount).replace(/[^0-9]/g, '')) || 0;
  const exceedsBalance = numericAmount > balance;

  const handleAmountChange = (e) => {
    setAmount(e.target.value.replace(/[^0-9]/g, ''));
  };

  const handleContinue = () => {
    if (exceedsBalance) return; // guard — button is also disabled, but belt-and-suspenders
    setStep('review');
  };

  const handleConfirm = async () => {
    setLoading(true);
    await onSubmit?.({ payeeName, payeeAccount, amount: Number(amount), note });
    // App.jsx will redirect to status screen on success;
    // on error it sets apiError and we stay on review step.
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
      {/* Top bar */}
      <div className="container" style={{ paddingTop: 'var(--space-5)', paddingBottom: 'var(--space-4)' }}>
        <button
          onClick={step === 'review' ? () => setStep('form') : onBack}
          className="btn-text"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontWeight: 600 }}
        >
          <BackIcon /> Back
        </button>
      </div>

      <div className="container stack-loose" style={{ paddingBottom: 'var(--space-7)' }}>
        <h1 className="font-serif">
          {step === 'form' ? 'Transfer Money' : 'Review Transfer'}
        </h1>

        {step === 'form' ? (
          <div className="stack-loose">
            {/* Beneficiary name */}
            <div className="stack-tight">
              <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                Send to (Name)
              </label>
              <input
                id="payee-name"
                type="text"
                value={payeeName}
                onChange={(e) => setPayeeName(e.target.value)}
                className="card"
                style={{ border: '1px solid var(--color-border-strong)', fontSize: 'var(--text-md)', width: '100%' }}
              />
              {isNewBeneficiary && (
                <span className="pill pill-pending" style={{ alignSelf: 'flex-start' }}>
                  New Beneficiary
                </span>
              )}
            </div>

            {/* Account / UPI number */}
            <div className="stack-tight">
              <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                Account / UPI Number
              </label>
              <input
                id="payee-account"
                type="text"
                inputMode="numeric"
                value={payeeAccount}
                onChange={(e) => setPayeeAccount(e.target.value.replace(/[^0-9@.]/g, ''))}
                placeholder="e.g. 9876543210 or name@upi"
                className="card"
                style={{ border: '1px solid var(--color-border-strong)', fontSize: 'var(--text-md)', width: '100%' }}
              />
            </div>

            {/* Amount */}
            <div className="stack-tight">
              <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                Amount
              </label>
              <div
                className="card"
                style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                  border: exceedsBalance
                    ? '1.5px solid var(--color-status-held-text)'
                    : '1px solid var(--color-border-strong)',
                }}
              >
                <span className="font-serif" style={{ fontSize: 'var(--text-lg)', color: 'var(--color-ink-faint)' }}>₹</span>
                <input
                  id="amount"
                  type="text"
                  inputMode="numeric"
                  value={formatINR(amount)}
                  onChange={handleAmountChange}
                  className="font-serif"
                  style={{ border: 'none', outline: 'none', background: 'transparent', fontSize: 'var(--text-lg)', width: '100%' }}
                />
              </div>

              {/* Available balance hint — always visible */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ink-faint)' }}>
                  Available balance
                </span>
                <span
                  style={{
                    fontSize: 'var(--text-xs)', fontWeight: 600,
                    color: exceedsBalance
                      ? 'var(--color-status-held-text)'
                      : 'var(--color-status-safe-text)',
                  }}
                >
                  ₹{balance.toLocaleString('en-IN')}
                </span>
              </div>

              {/* Inline error when amount exceeds balance */}
              {exceedsBalance && numericAmount > 0 && (
                <div
                  style={{
                    display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                    background: 'var(--color-status-held-bg)',
                    borderRadius: 'var(--radius-sm)',
                    padding: 'var(--space-2) var(--space-3)',
                    marginTop: 'var(--space-1)',
                  }}
                >
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-status-held-text)', fontWeight: 600 }}>
                    ⚠ Amount exceeds your available balance of ₹{balance.toLocaleString('en-IN')}
                  </span>
                </div>
              )}
            </div>

            {/* Optional note */}
            <div className="stack-tight">
              <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                Note <span style={{ fontWeight: 400, color: 'var(--color-ink-faint)' }}>(optional)</span>
              </label>
              <input
                id="note"
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Rent, medical bill…"
                className="card"
                style={{ border: '1px solid var(--color-border-strong)', fontSize: 'var(--text-md)', width: '100%' }}
              />
            </div>

            <button
              className="btn btn-primary"
              onClick={handleContinue}
              disabled={!payeeName || !payeeAccount || !amount || exceedsBalance}
            >
              Continue
            </button>
          </div>
        ) : (
          <div className="stack-loose">
            {/* Review summary */}
            <div className="card stack-loose">
              <SummaryRow label="To" value={payeeName} sub={isNewBeneficiary ? 'New Beneficiary' : null} />
              <Divider />
              <SummaryRow label="Account" value={payeeAccount} />
              <Divider />
              <SummaryRow label="Amount" value={'₹' + formatINR(amount)} large />
              <Divider />
              <SummaryRow label="From" value="Savings Account" />
              {note && (
                <>
                  <Divider />
                  <SummaryRow label="Note" value={note} />
                </>
              )}
            </div>

            {/* API error */}
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
              Aegis reviews every transfer for your safety before it completes.
            </p>

            <button
              id="confirm-transfer"
              className="btn btn-primary"
              onClick={handleConfirm}
              disabled={loading}
              style={{ position: 'relative' }}
            >
              {loading ? 'Submitting…' : 'Confirm Transfer'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryRow({ label, value, sub, large }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <span className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>{label}</span>
      <div style={{ textAlign: 'right' }}>
        <div
          className={large ? 'font-serif' : ''}
          style={{ fontSize: large ? 'var(--text-lg)' : 'var(--text-base)', fontWeight: large ? 500 : 600 }}
        >
          {value}
        </div>
        {sub && (
          <span className="pill pill-pending" style={{ marginTop: 'var(--space-1)' }}>
            {sub}
          </span>
        )}
      </div>
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

export default TransferForm;
