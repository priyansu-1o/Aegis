/**
 * Aegis — Unified App Router (with auth)
 *
 * Auth flow:
 *   1. On mount, GET /api/me to check for an existing valid JWT cookie.
 *   2. If authenticated → render the appropriate route.
 *      If not           → redirect everything to /login.
 *   3. On login, the server returns the user's role; we redirect accordingly.
 *   4. On logout, the cookie is cleared and the user returns to /login.
 *
 * Protected routes:
 *   /login              → LoginPage (unauthenticated only)
 *   /caregiver/*        → CaregiverApp (role: caregiver only)
 *   /senior/*           → SeniorApp    (role: senior only)
 *   /                   → smart redirect based on authenticated role
 *
 * All business logic inside CaregiverApp and SeniorApp is verbatim from the
 * original apps. Only the hardcoded sender_id has been removed — it now comes
 * from the authenticated user state (currentUser.user_id).
 */

import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';

import LoginPage from './components/ReferenceLoginPage';
import SignupPage from './components/SignupPage';
import LandingPage from './components/LandingPage';
import PendingList from './components/caregiver/PendingList';
import BalanceScreen from './components/senior/BalanceScreen';
import ReferenceSeniorDashboard from './components/senior/ReferenceSeniorDashboard';
import TransferForm from './components/senior/TransferForm';
import FDBreakFlow from './components/senior/FDBreakFlow';
import TransactionStatus from './components/senior/TransactionStatus';

import { saveTxId, clearTransaction } from './utils/store';
import { submitTransfer, getMe, logout } from './utils/api';

// =============================================================================
// Auth bootstrap — checks for an existing session on app load
// =============================================================================

function useAuth() {
  const [currentUser, setCurrentUser] = useState(null);  // null = loading
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    getMe()
      .then((data) => setCurrentUser(data.user))
      .catch(() => setCurrentUser(false))          // false = not authenticated
      .finally(() => setAuthChecked(true));
  }, []);

  return { currentUser, setCurrentUser, authChecked };
}

// =============================================================================
// ProtectedRoute — wraps a component behind auth + optional role check
// =============================================================================

function ProtectedRoute({ currentUser, requiredRole, children }) {
  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }
  if (requiredRole && currentUser.role !== requiredRole) {
    // Wrong role — send to the correct view for this user
    return <Navigate to={`/${currentUser.role}`} replace />;
  }
  return children;
}

// =============================================================================
// CaregiverApp — verbatim from frontend-caregiver/src/App.jsx
// =============================================================================

function CaregiverApp({ currentUser, onLogout }) {
  return (
    <div className="ref-skin">
      <header className="ref-header"><div className="ref-header-inner"><div className="ref-brand"><span className="brand-mark">♜</span> AEGIS</div><div style={{display:'flex',alignItems:'center',gap:10}}><span className="user-pill">Caregiver · {currentUser?.name}</span><button onClick={onLogout} className="utility-button">↗ Sign out</button></div></div></header>
      <main className="app-wrap">
        <div className="partner-banner"><div className="partner-info"><div className="partner-icon" style={{background:'rgba(200,168,93,.15)',color:'var(--gold-dark)'}}>🛡</div><div><div className="partner-title">Caregiver Protection Active</div><div className="partner-sub">You receive approval requests for held transactions.</div></div></div></div>
        <div className="ref-page-heading"><div><h1>CAREGIVER PROTECTION CENTER</h1><p>Review transactions Aegis has temporarily held.</p></div><span className="demo-badge">Demo / Simulated Account Data</span></div>
        <div className="stat-grid"><div className="stat-card"><div className="stat-label">Pending Reviews</div><div className="stat-value" style={{color:'var(--gold-dark)'}}>Live</div></div><div className="stat-card"><div className="stat-label">Protected Today</div><div className="stat-value" style={{color:'var(--forest)'}}>Active</div></div><div className="stat-card"><div className="stat-label">High Risk</div><div className="stat-value" style={{color:'var(--danger)'}}>Alerts</div></div></div>
        <div className="urgent-banner">⚠ <span>Transactions needing your review appear below.</span></div>
        <PendingList />
      </main>
    </div>
  );
}

// =============================================================================
// SeniorApp — verbatim from frontend-senior/src/App.jsx
// sender_id now comes from currentUser.user_id (no longer hardcoded)
// =============================================================================

function SeniorApp({ currentUser, onLogout }) {
  const [screen, setScreen]       = useState('balance');
  const [currentTx, setCurrentTx] = useState(null);
  const [apiError, setApiError]   = useState(null);
  // Balance lives here so it can be deducted after a successful transfer
  const [balance, setBalance]     = useState(845000);

  const handleBack = () => { setApiError(null); setScreen('balance'); };

  const handleDone = () => {
    clearTransaction();
    setCurrentTx(null);
    setApiError(null);
    setScreen('balance');
  };

  /**
   * Called by TransactionStatus once the caregiver resolves a held tx.
   * decision: 'approved' | 'blocked' | 'expired'
   * amount: the original transaction amount
   */
  const handleBalanceUpdate = (decision, amount) => {
    if (decision === 'approved') {
      // Money actually leaves the account only when the caregiver approves
      setBalance((prev) => Math.max(0, prev - amount));
    }
    // blocked / expired → no money moved, balance unchanged
  };

  const handleTransferSubmit = async (formData) => {
    setApiError(null);
    try {
      const result = await submitTransfer({
        payee_name:    formData.payeeName,
        payee_account: formData.payeeAccount,
        amount:        formData.amount,
        note:          formData.note || '',
      });

      const tx = result.transaction;
      saveTxId(tx.tx_id);

      // Only deduct balance immediately for auto-approved transactions.
      // Held transactions wait for caregiver approval before any money moves.
      if (tx.status === 'APPROVED') {
        setBalance((prev) => Math.max(0, prev - tx.amount));
      }

      setCurrentTx({
        txId:             tx.tx_id,
        amount:           tx.amount,
        beneficiary:      tx.payee_name,
        riskReasons:      tx.risk_reasons,
        status:           tx.status,
        coolingOffExpiry: tx.cooling_off_expiry,
        transactionType:  'transfer',
      });
      setScreen('status');
    } catch (err) {
      setApiError(err.message);
    }
  };

  const handleFDSubmit = async (formData) => {
    setApiError(null);
    try {
      const result = await submitTransfer({
        payee_name:            'Savings Account',
        payee_account:         '0000004821',
        amount:                formData.amount,
        note:                  'FD break — proceeds to savings',
        preceded_by_fd_break:  true,
        fd_break_timestamp:    new Date().toISOString(),
      });

      const tx = result.transaction;
      saveTxId(tx.tx_id);

      // Only deduct balance immediately for auto-approved transactions.
      // Held FD-break transactions wait for caregiver approval.
      if (tx.status === 'APPROVED') {
        setBalance((prev) => Math.max(0, prev - tx.amount));
      }

      setCurrentTx({
        txId:             tx.tx_id,
        amount:           tx.amount,
        beneficiary:      'Savings Account · ····4821',
        riskReasons:      tx.risk_reasons,
        status:           tx.status,
        coolingOffExpiry: tx.cooling_off_expiry,
        transactionType:  'fd_break',
      });
      setScreen('status');
    } catch (err) {
      setApiError(err.message);
    }
  };

  if (screen === 'transfer') return (
    <TransferForm
      onBack={handleBack}
      onSubmit={handleTransferSubmit}
      apiError={apiError}
      balance={balance}
    />
  );
  if (screen === 'fdbreak') return (
    <FDBreakFlow
      onBack={handleBack}
      onSubmit={handleFDSubmit}
      apiError={apiError}
      balance={balance}
    />
  );
  if (screen === 'status') return <TransactionStatus transaction={currentTx} onDone={handleDone} onBalanceUpdate={handleBalanceUpdate} />;

  return <ReferenceSeniorDashboard
    currentUser={currentUser}
    onLogout={onLogout}
    balance={balance}
    onTransfer={() => { setApiError(null); setScreen('transfer'); }}
    onBreakFD={() => { setApiError(null); setScreen('fdbreak'); }}
  />;
}
function LoadingScreen() {
  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'var(--color-bg)',
      }}
    >
      <p className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>Loading…</p>
    </div>
  );
}

// =============================================================================
// Root App — auth state + router
// =============================================================================

function App() {
  const { currentUser, setCurrentUser, authChecked } = useAuth();
  const navigate = useNavigate();

  // Show a blank loading screen while we check for an existing session
  if (!authChecked) return <LoadingScreen />;

  const handleLogin = (user) => setCurrentUser(user);

  const handleLogout = async () => {
    try { await logout(); } catch { /* ignore */ }
    setCurrentUser(false);
    navigate('/login', { replace: true });
  };

  // Smart root redirect — sends authenticated users straight to their view
  const RootRedirect = () => {
    if (!currentUser) return <LandingPage />;
    return <Navigate to={`/${currentUser.role}`} replace />;
  };

  return (
    <Routes>
      {/* Login — redirect away if already authenticated */}
      <Route
        path="/login"
        element={
          currentUser
            ? <Navigate to={`/${currentUser.role}`} replace />
            : <LoginPage onLogin={handleLogin} />
        }
      />

      <Route
        path="/signup"
        element={currentUser ? <Navigate to={`/${currentUser.role}`} replace /> : <SignupPage onLogin={handleLogin} />}
      />

      {/* Caregiver — protected, role-gated */}
      <Route
        path="/caregiver/*"
        element={
          <ProtectedRoute currentUser={currentUser} requiredRole="caregiver">
            <CaregiverApp currentUser={currentUser} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />

      {/* Senior — protected, role-gated */}
      <Route
        path="/senior/*"
        element={
          <ProtectedRoute currentUser={currentUser} requiredRole="senior">
            <SeniorApp currentUser={currentUser} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />

      {/* Root — smart redirect */}
      <Route path="/" element={<RootRedirect />} />

      {/* Catch-all */}
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}

export default App;
