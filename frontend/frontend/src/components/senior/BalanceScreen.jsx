import { useState, useEffect, useRef, useCallback } from 'react';
import { submitTransfer, getTransactions, getMe, getTransactionById } from '../../utils/api';
import { useSocket } from '../../utils/useSocket';

function BalanceScreen({ currentUser }) {
  const [balance, setBalance] = useState(currentUser?.balance || 0);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading]   = useState(true);

  // Modal states
  const [showSendModal, setShowSendModal] = useState(false);

  // Send form state
  const [formData, setFormData]   = useState({ payeeName: '', payeeAccount: '', amount: '', note: 'Payment' });
  const [txState, setTxState]     = useState('form'); // form | loading | safe | paused | blocked
  const [currentTx, setCurrentTx] = useState(null);
  const [timeLeft, setTimeLeft]   = useState('00:00');
  const countdownRef              = useRef(null);
  const expiryHandledRef          = useRef(false);

  const { socket } = useSocket();

  const loadAll = useCallback(async () => {
    setLoading(true);
    // Load balance and transactions independently so each renders as soon as ready.
    // Balance is fast (single row); transactions can be slow with many records.
    getMe()
      .then(res => { if (res?.user?.balance !== undefined) setBalance(res.user.balance); })
      .catch(() => {});

    getTransactions()
      .then(res => setTransactions(res.transactions || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Initial data load
  useEffect(() => {
    let cancelled = false;
    // Balance — fast single-row fetch
    getMe()
      .then(res => { if (!cancelled && res?.user?.balance !== undefined) setBalance(res.user.balance); })
      .catch(() => {});
    // Transactions — potentially slow, renders independently
    getTransactions()
      .then(res => { if (!cancelled) setTransactions(res.transactions || []); })
      .catch(err => { if (!cancelled) console.error(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!socket) return;
    const handle = (data) => {
      loadAll();
      if (currentTx && data.tx_id === currentTx.txId) {
        setTxState(data.status === 'APPROVED' ? 'safe' : 'blocked');
      }
    };
    socket.on('tx_update', handle);
    return () => socket.off('tx_update', handle);
  }, [socket, currentTx]);



  const openSendModal = () => {
    setTxState('form');
    setCurrentTx(null);
    setFormData({ payeeName: '', payeeAccount: '', amount: '', note: 'Payment' });
    setShowSendModal(true);
  };

  const closeSendModal = () => {
    setShowSendModal(false);
    if (countdownRef.current) clearInterval(countdownRef.current);
    loadAll();
  };

  const startCountdown = (expiryStr, txId) => {
    if (!expiryStr) return;
    if (countdownRef.current) clearInterval(countdownRef.current);
    expiryHandledRef.current = false;
    const value = String(expiryStr);
    const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
    const expiryMs = Date.parse(hasTimeZone ? value : `${value}Z`);

    const tick = () => {
      const diff = Number.isNaN(expiryMs)
        ? 0
        : Math.max(0, Math.floor((expiryMs - Date.now()) / 1000));
      const m = Math.floor(diff / 60);
      const s = diff % 60;
      setTimeLeft(`${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`);

      if (diff === 0 && !expiryHandledRef.current) {
        expiryHandledRef.current = true;
        clearInterval(countdownRef.current);
        getTransactionById(txId)
          .then(res => {
            const latest = res.transaction;
            setCurrentTx(prev => prev ? { ...prev, status: latest.status } : prev);
            if (latest.status === 'BLOCKED') {
              setTxState('blocked');
            } else if (latest.status === 'APPROVED') {
              setTxState('safe');
            }
            loadAll();
          })
          .catch(() => {
            // Keep the protection screen visible if the status check fails.
            setTxState('blocked');
          });
      }
    };
    tick();
    if (!expiryHandledRef.current) {
      countdownRef.current = setInterval(tick, 1000);
    }
  };

  const handleTransferSubmit = async (e) => {
    e.preventDefault();
    setTxState('loading');
    expiryHandledRef.current = false;
    try {
      const result = await submitTransfer({
        payee_name:    formData.payeeName,
        payee_account: formData.payeeAccount,
        amount:        parseFloat(formData.amount),
        note:          formData.note,
      });
      const tx = result.transaction;
      setCurrentTx({
        txId:            tx.tx_id,
        amount:          tx.amount,
        beneficiary:     tx.payee_name,
        riskReasons:     tx.risk_reasons || [],
        score:           result.risk?.score || 0,
        status:          tx.status,
        coolingOffExpiry: tx.cooling_off_expiry,
      });

      // Small artificial delay so the spinner is visible
      setTimeout(() => {
        if (tx.status === 'APPROVED') {
          setBalance(prev => Math.max(0, prev - tx.amount));
          setTxState('safe');
        } else {
          setTxState('paused');
          startCountdown(tx.cooling_off_expiry, tx.tx_id);
        }
        loadAll();
      }, 900);
    } catch (err) {
      alert(err.message);
      setTxState('form');
    }
  };

  // ── derived stats ─────────────────────────────────────────────────────────
  let totalProtected = 0;
  transactions.forEach(tx => {
    const st  = String(tx.status     || '').toLowerCase();
    const res = String(tx.resolution || '').toLowerCase();
    const amt = parseFloat(tx.amount || 0);
    if (st === 'blocked' || st === 'pending_approval' || st === 'pending_caregiver_approval' || res.includes('blocked') || res.includes('reject')) {
      totalProtected += amt;
    }
  });

  const txStatusClass = (st) => {
    st = String(st).toLowerCase();
    if (st === 'approved')                                            return 'safe';
    if (st === 'pending_approval' || st === 'pending_caregiver_approval') return 'warning';
    if (st === 'blocked')                                             return 'blocked';
    return 'safe';
  };
  const txIcon    = (st) => ({ safe: '✓', warning: '!', blocked: '×' }[txStatusClass(st)] || '✓');
  const txTagText = (st) => ({ safe: 'APPROVED', warning: 'NEEDS REVIEW', blocked: 'BLOCKED' }[txStatusClass(st)] || 'SAFE');

  return (
    <div className="app-wrap">

      {/* ── PARTNER STATUS BANNER (caregiver connection) ── */}
      <div className="partner-banner">
        <div className="partner-info">
          <span style={{ fontSize: '1.3rem' }}>🛡</span>
          <div>
            <div id="partnerStatusText">Your transactions are protected by Aegis.</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--secondary-text)', fontWeight: 600 }}>
              Suspicious payments are automatically routed to your caregiver for approval.
            </div>
          </div>
        </div>
      </div>

      {/* ── GREETING ── */}
      <div className="greeting-box">
        <div>
          <h1 className="greeting-title">
            Good morning, {currentUser?.name?.split(' ')[0]} 👋
          </h1>
          <div className="greeting-sub">Your money is protected by Aegis.</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <span className="demo-simulated-badge">Demo / Simulated Account Data</span>
        </div>
      </div>

      {/* ── STATS ROW ── */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-lbl">Available Balance</div>
          <div className="stat-val">₹{balance.toLocaleString('en-IN')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Transactions</div>
          <div className="stat-val">{transactions.length}</div>
        </div>
        <div className="stat-card highlight">
          <div className="stat-lbl">Protected</div>
          <div className="stat-val" style={{ color: 'var(--trusted-green)' }}>
            ₹{totalProtected.toLocaleString('en-IN')}
          </div>
        </div>
      </div>

      {/* ── MAIN SEND BUTTON ── */}
      <button className="btn-main-send" onClick={openSendModal}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5"  y1="12" x2="19" y2="12" />
        </svg>
        Send Money
      </button>

      {/* ── RECENT TRANSACTIONS CARD ── */}
      <div className="dash-card">
        <div className="card-header">
          <div>
            <div className="card-title">Recent Transactions</div>
            <div className="card-sub">Protected by Aegis Risk Engine</div>
          </div>
          <button
            onClick={loadAll}
            style={{ background: 'none', border: 'none', color: 'var(--trusted-green)', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}
          >
            ↻ Refresh
          </button>
        </div>

        <div>
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--secondary-text)', fontWeight: 600 }}>
              Loading recent transactions…
            </div>
          ) : transactions.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--secondary-text)' }}>
              No transactions recorded yet. Click <strong>+ Send Money</strong> to start.
            </div>
          ) : (
            transactions.map(tx => {
              const cls  = txStatusClass(tx.status);
              const icon = txIcon(tx.status);
              const tag  = txTagText(tx.status);
              const dateStr = tx.created_at
                ? new Date(tx.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
                : 'Recent';
              return (
                <div className="tx-item" key={tx.tx_id}>
                  <div className="tx-left">
                    <div className={`tx-badge-icon ${cls}`}>{icon}</div>
                    <div>
                      <div className="tx-name">{tx.payee_name}</div>
                      <div className="tx-date">{tx.payee_account} · {dateStr}</div>
                    </div>
                  </div>
                  <div className="tx-right">
                    <div className="tx-amt">₹{Number(tx.amount).toLocaleString('en-IN')}</div>
                    <span className={`status-tag ${cls}`}>{tag}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── SEND MONEY MODAL ── */}
      {showSendModal && (
        <div className="send-modal" style={{ display: 'flex' }}>
          <div className="modal-box">
            <div className="modal-top">
              <div className="modal-title">Send Money</div>
              <button className="btn-close" onClick={closeSendModal}>✕</button>
            </div>

            {/* FORM STATE */}
            {txState === 'form' && (
              <form onSubmit={handleTransferSubmit}>
                <div className="form-group">
                  <label>Recipient Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Raj Enterprises"
                    value={formData.payeeName}
                    onChange={e => setFormData({ ...formData, payeeName: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>UPI / Account Number</label>
                  <input
                    type="text"
                    placeholder="e.g. 9876543210 or upi@bank"
                    value={formData.payeeAccount}
                    onChange={e => setFormData({ ...formData, payeeAccount: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Amount (₹)</label>
                  <input
                    type="number"
                    placeholder="e.g. 5000"
                    min="1"
                    step="0.01"
                    value={formData.amount}
                    onChange={e => setFormData({ ...formData, amount: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Note</label>
                  <input
                    type="text"
                    placeholder="e.g. Monthly rent"
                    value={formData.note}
                    onChange={e => setFormData({ ...formData, note: e.target.value })}
                  />
                </div>
                <button type="submit" className="btn-continue">Continue</button>
              </form>
            )}

            {/* LOADING STATE */}
            {txState === 'loading' && (
              <div className="loading-overlay" style={{ display: 'block', textAlign: 'center', padding: '2.5rem 1rem' }}>
                <div className="spinner-ring" />
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--primary-navy)', marginBottom: '0.25rem' }}>
                  Checking your transaction...
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--secondary-text)', fontWeight: 600 }}>
                  Aegis is analyzing this payment.
                </div>
              </div>
            )}

            {/* SAFE STATE */}
            {txState === 'safe' && currentTx && (
              <div className="result-screen" style={{ display: 'block', textAlign: 'center', padding: '1.2rem 0' }}>
                <div className="result-icon-circle safe">✓</div>
                <div className="result-heading" style={{ color: 'var(--trusted-green)' }}>PAYMENT APPROVED</div>
                <div className="result-amount">₹{currentTx.amount.toLocaleString('en-IN')}</div>
                <div className="result-payee">To: {currentTx.beneficiary}</div>
                <div className="result-details-box">
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>Risk Score</span>
                    <span style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--trusted-green)' }}>
                      {currentTx.score} / 100 SAFE
                    </span>
                  </div>
                  <div className="result-details-title">Signals</div>
                  <ul className="reasons-list">
                    {currentTx.riskReasons.length === 0
                      ? <li style={{ color: 'var(--trusted-green)' }}>✓ No risk signals detected</li>
                      : currentTx.riskReasons.map((r, i) => <li key={i} style={{ color: 'var(--trusted-green)' }}>✓ {r}</li>)
                    }
                  </ul>
                </div>
                <button className="btn-done" onClick={closeSendModal}>Done</button>
              </div>
            )}

            {/* PAUSED / HIGH-RISK STATE */}
            {txState === 'paused' && currentTx && (
              <div className="result-screen" style={{ display: 'block', textAlign: 'center', padding: '1.2rem 0' }}>
                <div className="result-icon-circle warning">⚠</div>
                <div className="result-heading" style={{ color: '#8C6E2A' }}>PAYMENT PAUSED</div>
                <div className="result-amount">₹{currentTx.amount.toLocaleString('en-IN')}</div>
                <div className="result-payee">To: {currentTx.beneficiary}</div>
                <div className="result-details-box" style={{ background: 'rgba(200,168,93,0.08)', borderColor: 'var(--warning-amber)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>Risk Score</span>
                    <span style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--danger-red)' }}>
                      {currentTx.score} / 100 HIGH RISK
                    </span>
                  </div>
                  <div className="result-details-title" style={{ color: '#8C6E2A' }}>Why was this paused?</div>
                  <ul className="reasons-list">
                    {currentTx.riskReasons.map((r, i) => (
                      <li key={i} style={{ color: 'var(--danger-red)' }}>⚠ {r}</li>
                    ))}
                  </ul>
                </div>
                <div style={{ background: 'rgba(200,168,93,0.12)', border: '1px solid rgba(200,168,93,0.3)', borderRadius: 14, padding: '0.9rem', marginBottom: '1.25rem', fontSize: '0.88rem', fontWeight: 700, color: '#8C6E2A' }}>
                  <div>Your money has NOT been sent.</div>
                  <div style={{ fontWeight: 600, marginTop: 2 }}>Your trusted caregiver has been asked to review this payment.</div>
                </div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--secondary-text)', marginBottom: '1rem' }}>
                  Cooling-off period: <span style={{ color: 'var(--primary-navy)', fontWeight: 800 }}>{timeLeft}</span>
                </div>
                <button className="btn-done" onClick={closeSendModal}>View Protection Details</button>
              </div>
            )}

            {/* BLOCKED STATE */}
            {txState === 'blocked' && currentTx && (
              <div className="result-screen" style={{ display: 'block', textAlign: 'center', padding: '1.2rem 0' }}>
                <div className="result-icon-circle blocked">🛡</div>
                <div className="result-heading" style={{ color: 'var(--danger-red)' }}>PAYMENT BLOCKED</div>
                <div className="result-amount">₹{currentTx.amount.toLocaleString('en-IN')}</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--main-text)', marginBottom: '1.25rem' }}>
                  Your trusted caregiver blocked this transaction to protect your savings.
                </div>
                <button className="btn-done" onClick={closeSendModal}>Done</button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── BOTTOM NAV ── */}
      <nav className="bottom-nav">
        <div className="nav-item active">
          <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
          Dashboard
        </div>
        <div className="nav-item" onClick={openSendModal} style={{ cursor: 'pointer' }}>
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          Send Money
        </div>
        <div className="nav-item" onClick={loadAll} style={{ cursor: 'pointer' }}>
          <svg viewBox="0 0 24 24"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          Transactions
        </div>
      </nav>
    </div>
  );
}

export default BalanceScreen;
