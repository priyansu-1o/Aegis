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

import LoginPage from './components/LoginPage';
import PendingList from './components/caregiver/PendingList';
import BalanceScreen from './components/senior/BalanceScreen';
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
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
      {/* Header */}
      <div className="surface-dark">
        <div
          className="container"
          style={{
            paddingTop: 'var(--space-6)',
            paddingBottom: 'var(--space-6)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
        >
          <div>
            <span
              className="font-serif"
              style={{ fontSize: 'var(--text-lg)', color: 'var(--color-on-dark)' }}
            >
              Aegis
            </span>
            <p
              className="text-soft"
              style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-1)' }}
            >
              {currentUser?.name ?? 'Trusted Contact'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
            {/* Live indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span
                style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: 'var(--color-status-safe-text)',
                  boxShadow: '0 0 0 3px rgba(52,199,89,0.25)',
                  animation: 'pulse 2s infinite', flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-on-dark-soft)', letterSpacing: '0.04em' }}>
                Live
              </span>
            </div>

            {/* Logout */}
            <button
              onClick={onLogout}
              className="btn-text"
              style={{ fontSize: 'var(--text-xs)', color: 'var(--color-on-dark-soft)' }}
            >
              Sign out
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div
        className="container stack-loose"
        style={{ paddingTop: 'var(--space-6)', paddingBottom: 'var(--space-7)' }}
      >
        <div className="stack-tight">
          <h1 className="font-serif" style={{ fontSize: 'var(--text-lg)' }}>
            Pending Safety Checks
          </h1>
          <p className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>
            You're protecting Meena Sharma's account. Review any flagged activity below.
          </p>
        </div>

        <PendingList />
      </div>
    </div>
  );
}

// =============================================================================
// SeniorApp — verbatim from frontend-senior/src/App.jsx
// sender_id now comes from currentUser.user_id (no longer hardcoded)
// =============================================================================

function SeniorApp({ currentUser, onLogout }) {
  const [screen, setScreen]     = useState('balance');
  const [currentTx, setCurrentTx] = useState(null);
  const [apiError, setApiError] = useState(null);

  const handleBack = () => { setApiError(null); setScreen('balance'); };

  const handleDone = () => {
    clearTransaction();
    setCurrentTx(null);
    setApiError(null);
    setScreen('balance');
  };

  const handleTransferSubmit = async (formData) => {
    setApiError(null);
    try {
      // sender_id is derived from the JWT on the server — not sent here
      const result = await submitTransfer({
        payee_name:    formData.payeeName,
        payee_account: formData.payeeAccount,
        amount:        formData.amount,
        note:          formData.note || '',
      });

      const tx = result.transaction;
      saveTxId(tx.tx_id);
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

  if (screen === 'transfer') return <TransferForm onBack={handleBack} onSubmit={handleTransferSubmit} apiError={apiError} />;
  if (screen === 'fdbreak')  return <FDBreakFlow  onBack={handleBack} onSubmit={handleFDSubmit}      apiError={apiError} />;
  if (screen === 'status')   return <TransactionStatus transaction={currentTx} onDone={handleDone} />;

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={onLogout}
        className="btn-text"
        style={{
          position: 'absolute', top: 'var(--space-5)', right: 'var(--space-4)',
          fontSize: 'var(--text-xs)', color: 'var(--color-on-dark-soft)',
          zIndex: 10,
        }}
      >
        Sign out
      </button>
      <BalanceScreen
        onTransfer={() => { setApiError(null); setScreen('transfer'); }}
        onBreakFD={()  => { setApiError(null); setScreen('fdbreak'); }}
      />
    </div>
  );
}

// =============================================================================
// Loading spinner — shown while /api/me is in-flight on app load
// =============================================================================

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
    if (!currentUser) return <Navigate to="/login" replace />;
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
