/**
 * LoginPage.jsx — Single login form for both roles
 *
 * On successful login the server returns { user: { role } }.
 * This component redirects to /caregiver or /senior based solely on
 * the role the server returns — never based on which URL was typed.
 *
 * Matches the existing Forest Green design system (index.css).
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../utils/api';

function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await login(email.trim().toLowerCase(), password);
      const { role, user_id, name } = data.user;

      // Notify the root app so it can store the current user in state
      onLogin?.({ role, user_id, name });

      // Server determines where you go — role comes from the verified JWT
      if (role === 'caregiver') {
        navigate('/caregiver', { replace: true });
      } else {
        navigate('/senior', { replace: true });
      }
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--color-bg)',
      }}
    >
      {/* Brand header */}
      <div className="surface-dark">
        <div
          className="container"
          style={{
            paddingTop: 'var(--space-6)',
            paddingBottom: 'var(--space-6)',
            textAlign: 'center',
          }}
        >
          <span
            className="font-serif"
            style={{ fontSize: 'var(--text-2xl)', color: 'var(--color-on-dark)' }}
          >
            Aegis
          </span>
          <p
            className="text-soft"
            style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-1)' }}
          >
            Financial safety for seniors &amp; caregivers
          </p>
        </div>
      </div>

      {/* Card */}
      <div
        style={{
          background: 'var(--color-bg)',
          borderTopLeftRadius: 'var(--radius-lg)',
          borderTopRightRadius: 'var(--radius-lg)',
          marginTop: '-24px',
          flex: 1,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          paddingTop: 'var(--space-7)',
          paddingBottom: 'var(--space-7)',
        }}
      >
        <div
          className="container"
          style={{ maxWidth: 400, width: '100%' }}
        >
          <div className="stack-loose">
            <div className="stack-tight">
              <h1 className="font-serif" style={{ fontSize: 'var(--text-xl)' }}>
                Sign in
              </h1>
              <p className="text-soft" style={{ fontSize: 'var(--text-sm)' }}>
                Your role is set automatically based on your account.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="stack-loose" noValidate>
              {/* Email */}
              <div className="stack-tight">
                <label
                  htmlFor="email"
                  style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}
                >
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="card"
                  style={{
                    border: '1px solid var(--color-border-strong)',
                    fontSize: 'var(--text-md)',
                    width: '100%',
                    outline: 'none',
                  }}
                />
              </div>

              {/* Password */}
              <div className="stack-tight">
                <label
                  htmlFor="password"
                  style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="card"
                  style={{
                    border: '1px solid var(--color-border-strong)',
                    fontSize: 'var(--text-md)',
                    width: '100%',
                    outline: 'none',
                  }}
                />
              </div>

              {/* Error */}
              {error && (
                <div
                  className="card-flush"
                  style={{
                    background: 'var(--color-status-held-bg)',
                    padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  <p
                    style={{
                      color: 'var(--color-status-held-text)',
                      fontSize: 'var(--text-sm)',
                      fontWeight: 600,
                    }}
                  >
                    ⚠ {error}
                  </p>
                </div>
              )}

              <button
                id="login-submit"
                type="submit"
                className="btn btn-primary"
                disabled={loading || !email || !password}
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            {/* Demo hint */}
            <div
              className="card-flush"
              style={{
                background: 'var(--color-status-safe-bg)',
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <p
                style={{
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-status-safe-text)',
                  fontWeight: 600,
                  marginBottom: 'var(--space-1)',
                }}
              >
                Demo credentials
              </p>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ink-soft)' }}>
                <strong>Caregiver:</strong> caregiver@aegis.demo
              </p>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ink-soft)' }}>
                <strong>Senior:</strong> senior@aegis.demo
              </p>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ink-soft)', marginTop: 'var(--space-1)' }}>
                Password for both: <strong>demo1234</strong>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
