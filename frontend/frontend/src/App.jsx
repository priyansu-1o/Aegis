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
import SignupPage from './components/SignupPage';
import LandingPage from './components/LandingPage';
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
  useEffect(() => {
    document.body.classList.add('dashboard-active');
    return () => document.body.classList.remove('dashboard-active');
  }, []);

  return (
    <>
      <header className="dashboard-header">
        <div className="header-inner">
          <a href="/" className="brand-logo">
            <img src="/logo.svg" alt="Aegis Logo" />
            AEGIS
          </a>
          <div className="nav-user">
            <span className="user-pill caregiver">Caregiver · {currentUser?.name}</span>
            <button onClick={onLogout} style={{color:'var(--secondary-text)', fontSize:'0.82rem', fontWeight:600, border:'none', background:'none', cursor:'pointer'}}>Logout</button>
          </div>
        </div>
      </header>
      <main className="app-wrap">
        <PendingList caregiverName={currentUser?.name} />
      </main>
    </>
  );
}

// =============================================================================
// SeniorApp — verbatim from frontend-senior/src/App.jsx
// sender_id now comes from currentUser.user_id (no longer hardcoded)
// =============================================================================

function SeniorApp({ currentUser, onLogout }) {
  useEffect(() => {
    document.body.classList.add('dashboard-active');
    return () => document.body.classList.remove('dashboard-active');
  }, []);

  return (
    <>
      <header className="dashboard-header">
        <div className="header-inner">
          <a href="/" className="brand-logo">
            <img src="/logo.svg" alt="Aegis Logo" />
            AEGIS
          </a>
          <div className="nav-user">
            <span className="user-pill">{currentUser?.name} · ID #{currentUser?.user_id}</span>
            <button onClick={onLogout} style={{color:'var(--secondary-text)', fontSize:'0.82rem', fontWeight:600, border:'none', background:'none', cursor:'pointer'}}>Logout</button>
          </div>
        </div>
      </header>
      <BalanceScreen currentUser={currentUser} />
    </>
  );
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
