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
    let active = true;
    getMe()
      .then((data) => {
        if (active) setCurrentUser(data.user);
      })
      .catch(() => {
        if (active) setCurrentUser(false);          // false = not authenticated
      })
      .finally(() => {
        if (active) setAuthChecked(true);
      });

    return () => { active = false; };
  }, []);

  const skipAuthCheck = () => {
    setCurrentUser(false);
    setAuthChecked(true);
  };

  return { currentUser, setCurrentUser, authChecked, skipAuthCheck };
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
function LoadingScreen({ onSkip }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--color-bg, #f8fafc)',
        padding: '1.5rem',
        textAlign: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.75rem' }}>
        <img src="/logo.svg" alt="Aegis Logo" style={{ width: '32px', height: '32px' }} />
        <span style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '0.05em', color: 'var(--primary-navy, #1e293b)' }}>
          AEGIS
        </span>
      </div>

      <div className="spinner-ring" style={{ marginBottom: '1.25rem' }} />

      <p style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--primary-navy, #1e293b)', margin: '0 0 0.5rem' }}>
        {elapsed < 4 ? 'Connecting to secure server…' : 'Waking up backend server…'}
      </p>

      <p style={{ fontSize: '0.85rem', color: 'var(--secondary-text, #64748b)', maxWidth: '380px', margin: '0 0 1.5rem', lineHeight: 1.5 }}>
        {elapsed >= 4
          ? 'Free deployment instances pause when inactive. Initial spin-up can take up to a minute.'
          : 'Verifying session and security status…'}
      </p>

      {elapsed >= 4 && onSkip && (
        <button
          onClick={onSkip}
          style={{
            background: 'white',
            border: '1px solid #cbd5e1',
            padding: '0.5rem 1rem',
            borderRadius: '8px',
            fontSize: '0.85rem',
            fontWeight: 600,
            color: 'var(--primary-navy, #1e293b)',
            cursor: 'pointer',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            transition: 'all 0.2s',
          }}
        >
          Skip waiting & continue to site →
        </button>
      )}
    </div>
  );
}

// =============================================================================
// Root App — auth state + router
// =============================================================================

function App() {
  const { currentUser, setCurrentUser, authChecked, skipAuthCheck } = useAuth();
  const navigate = useNavigate();

  // Show a blank loading screen while we check for an existing session
  if (!authChecked) return <LoadingScreen onSkip={skipAuthCheck} />;

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
