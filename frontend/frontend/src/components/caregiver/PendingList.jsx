import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchPendingTransactions, resolveTransaction, getTransactions } from '../../utils/api';
import { useSocket } from '../../utils/useSocket';

function PendingList() {
  const [transactions, setTransactions] = useState([]);
  const [history,      setHistory]      = useState([]);
  const [activeTab,    setActiveTab]    = useState('pending');
  const [loading,      setLoading]      = useState(true);
  const [fetchError,   setFetchError]   = useState(null);
  const [timers,       setTimers]       = useState({});   // { [tx_id]: 'MM:SS' }
  const timerRefs = useRef({});

  const { socket, connected } = useSocket();

  const loadPending = useCallback(async () => {
    // Load pending first — it's urgent and fast
    fetchPendingTransactions()
      .then(res => {
        setTransactions(res.pending || []);
        setFetchError(null);
      })
      .catch(err => setFetchError(err.status === 401 ? 'Session expired. Please log in again.' : err.message))
      .finally(() => setLoading(false));
    // Load history in the background — it can be slow without blocking pending cards
    getTransactions()
      .then(res => setHistory(res.transactions || []))
      .catch(() => {});
  }, []);

  // Initial load
  useEffect(() => {
    let cancelled = false;
    // Pending — fast, shows immediately
    fetchPendingTransactions()
      .then(res => { if (!cancelled) { setTransactions(res.pending || []); setFetchError(null); } })
      .catch(err => { if (!cancelled) setFetchError(err.status === 401 ? 'Session expired. Please log in again.' : err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    // History — loads in background without blocking
    getTransactions()
      .then(res => { if (!cancelled) setHistory(res.transactions || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!socket) return;
    socket.on('pending_update', loadPending);
    return () => socket.off('pending_update', loadPending);
  }, [socket, loadPending]);

  // ── Countdown timers for each pending card ─────────────────────────────────
  useEffect(() => {
    // Clear all old timers
    const refs = timerRefs.current;
    Object.values(refs).forEach(clearInterval);
    timerRefs.current = {};

    transactions.forEach(tx => {
      if (!tx.cooling_off_expiry) return;

      
      // SQLite returns a naive UTC timestamp; preserve the UTC interpretation
      // when the server response does not include an explicit timezone.
      const value = String(tx.cooling_off_expiry);
      const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
      const expiryMs = Date.parse(hasTimeZone ? value : `${value}Z`);
      if (Number.isNaN(expiryMs)) return;

      const updateTimer = () => {
        const diff = Math.max(0, Math.floor((expiryMs - Date.now()) / 1000));

        if (diff === 0) {
          setTransactions(prev => prev.filter(item => item.tx_id !== tx.tx_id));
          setTimers(prev => {
            const next = { ...prev };
            delete next[tx.tx_id];
            return next;
          });
          return;
        }

        const m = Math.floor(diff / 60);
        const s = diff % 60;
        setTimers(prev => ({ ...prev, [tx.tx_id]: `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` }));
      };

      updateTimer();
      const intervalId = setInterval(updateTimer, 1000);
      timerRefs.current[tx.tx_id] = intervalId;
    });

    return () => Object.values(timerRefs.current).forEach(clearInterval);
  }, [transactions]);

  const handleResolve = async (txId, decision) => {
    // Optimistically remove from view
    setTransactions(prev => prev.filter(t => t.tx_id !== txId));
    try {
      await resolveTransaction(txId, decision);
      // Reload both lists to get updated history
      loadPending();
    } catch (err) {
      alert(err.message);
      loadPending(); // re-sync on error
    }
  };

  // ── Derived caregiver stats ────────────────────────────────────────────────
  const pendingCount = transactions.length;
  const highRiskCount = transactions.filter(tx => (tx.risk_score || 0) >= 70).length;
  const protectedAmount = history
    .filter(tx => String(tx.status).toLowerCase() === 'blocked')
    .reduce((sum, tx) => sum + parseFloat(tx.amount || 0), 0);

  // ── History status helpers ─────────────────────────────────────────────────
  const histStatusCls = (st) => {
    st = String(st).toLowerCase();
    if (st === 'approved') return 'safe';
    if (st === 'blocked')  return 'blocked';
    return 'warning';
  };
  const histIcon    = (st) => ({ safe: '✓', blocked: '×', warning: '!' }[histStatusCls(st)]);
  const histTagText = (st) => ({ safe: 'APPROVED', blocked: 'BLOCKED', warning: 'PENDING' }[histStatusCls(st)]);

  return (
    <div>
      {/* ── PAGE HEADER ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">CAREGIVER PROTECTION CENTER</h1>
          <div className="page-sub">Review transactions Aegis has temporarily held.</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <span className="demo-simulated-badge caregiver">Demo / Simulated Account Data</span>
          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--secondary-text)' }}>
            Live updates {connected ? 'active ●' : 'unavailable'}
          </div>
        </div>
      </div>

      {/* ── STATS ROW ── */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-lbl">Pending Reviews</div>
          <div className="stat-val" style={{ color: '#8C6E2A' }}>{pendingCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Protected (Blocked)</div>
          <div className="stat-val" style={{ color: 'var(--trusted-green)' }}>
            ₹{protectedAmount.toLocaleString('en-IN')}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">High Risk</div>
          <div className="stat-val" style={{ color: 'var(--danger-red)' }}>{highRiskCount}</div>
        </div>
      </div>

      {/* ── URGENT ACTION BANNER ── */}
      {pendingCount > 0 && (
        <div className="urgent-banner">
          <div className="urgent-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8C6E2A" strokeWidth="2.5">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            ⚠ ACTION REQUIRED
          </div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#8C6E2A' }}>
            {pendingCount} transaction{pendingCount > 1 ? 's are' : ' is'} waiting for your review.
          </div>
        </div>
      )}

      {/* ── CONTENT ── */}
      <div className="pending-list">
        {loading ? (
          <div className="empty-state">Loading transactions…</div>
        ) : fetchError ? (
          <div className="empty-state" style={{ color: 'var(--danger-red)' }}>{fetchError}</div>
        ) : activeTab === 'pending' ? (
          pendingCount === 0 ? (
            <div className="empty-state">
              <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>✅</div>
              No pending transactions waiting for review.
            </div>
          ) : (
            transactions.map(tx => {
              const rr = Array.isArray(tx.risk_reasons)
                ? tx.risk_reasons
                : String(tx.risk_reasons || '').split(',').map(s => s.trim()).filter(Boolean);
              const timerDisplay = timers[tx.tx_id] || '00:00';

              return (
                <div className="pending-card" key={tx.tx_id}>
                  <div className="pending-top">
                    <div>
                      <div className="pending-payee">{tx.payee_name}</div>
                      <div className="pending-meta">
                        {tx.payee_account} · From {tx.sender?.name || 'Senior'}
                      </div>
                    </div>
                    <span className="risk-score-pill">Risk Score: {tx.risk_score || 0} / 100</span>
                  </div>

                  <div className="pending-amount">₹ {Number(tx.amount).toLocaleString('en-IN')}</div>

                  <div className="signals-title">Risk Signals</div>
                  <ul className="signals-list">
                    {rr.length === 0
                      ? <li>Unknown risk</li>
                      : rr.map((r, i) => <li key={i}>{r}</li>)
                    }
                  </ul>

                  {tx.cooling_off_expiry && (
                    <div className="timer-row">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                      </svg>
                      Cooling-off period:&nbsp;
                      <span style={{ fontWeight: 800, marginLeft: 4 }}>{timerDisplay}</span>
                    </div>
                  )}

                  <div className="btn-row">
                    <button className="btn-approve" onClick={() => handleResolve(tx.tx_id, 'approve')}>
                      ✓ APPROVE
                    </button>
                    <button className="btn-block" onClick={() => handleResolve(tx.tx_id, 'block')}>
                      ✕ BLOCK
                    </button>
                  </div>
                </div>
              );
            })
          )
        ) : (
          /* ── HISTORY TAB ── */
          history.length === 0 ? (
            <div className="empty-state">No transaction history yet.</div>
          ) : (
            history.map(tx => {
              const cls     = histStatusCls(tx.status);
              const icon    = histIcon(tx.status);
              const tag     = histTagText(tx.status);
              const dateStr = tx.created_at
                ? new Date(tx.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })
                : '';
              return (
                <div className="pending-card" key={tx.tx_id} style={{ padding: '1.2rem 1.4rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div className="tx-left">
                      <div className={`tx-badge-icon ${cls}`}>{icon}</div>
                      <div>
                        <div className="tx-name">{tx.payee_name}</div>
                        <div className="tx-date">
                          {tx.payee_account}
                          {tx.sender?.name ? ` · ${tx.sender.name}` : ''}
                          {dateStr ? ` · ${dateStr}` : ''}
                        </div>
                      </div>
                    </div>
                    <div className="tx-right">
                      <div className="tx-amt">₹{Number(tx.amount).toLocaleString('en-IN')}</div>
                      <span className={`status-tag ${cls}`}>{tag}</span>
                    </div>
                  </div>
                </div>
              );
            })
          )
        )}
      </div>

      {/* ── BOTTOM NAV ── */}
      <nav className="bottom-nav">
        <div className="nav-item" onClick={() => { setActiveTab('pending'); loadPending(); }} style={{ cursor: 'pointer' }}>
          <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          Overview
        </div>
        <div className={`nav-item ${activeTab === 'pending' ? 'active' : ''}`} onClick={() => setActiveTab('pending')} style={{ cursor: 'pointer' }}>
          <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Pending
          {pendingCount > 0 && <span className="pending-badge">{pendingCount}</span>}
        </div>
        <div className={`nav-item ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')} style={{ cursor: 'pointer' }}>
          <svg viewBox="0 0 24 24"><polyline points="12 8 12 12 14 14"/><circle cx="12" cy="12" r="10"/></svg>
          History
        </div>
      </nav>
    </div>
  );
}

export default PendingList;
