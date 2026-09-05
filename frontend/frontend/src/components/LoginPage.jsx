import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login } from '../utils/api';

function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await login(email.trim().toLowerCase(), password);
      const { role, user_id, name } = data.user;
      onLogin?.({ role, user_id, name });
      navigate(role === 'caregiver' ? '/caregiver' : '/senior', { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return <div className="auth-page">
    <header className="auth-header"><Link to="/" className="ref-brand"><img src="/logo.svg" className="brand-mark" alt="Aegis Logo" /> AEGIS</Link></header>
    <main className="auth-shell">
      <div className="auth-tabs"><span className="auth-tab active">Sign In</span><Link className="auth-tab auth-tab-link" to="/signup">Create Account</Link></div>
      <div className="auth-head"><h1>Welcome back</h1><p>Enter your credentials to access your dashboard.</p></div>
      <form onSubmit={handleSubmit} className="auth-form" noValidate>
        <div className="form-group"><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></div>
        <div className="form-group"><label htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" /></div>
        {error && <div className="error-box">⚠ {error}</div>}
        <button id="login-submit" type="submit" className="auth-submit" disabled={loading || !email || !password}>{loading ? 'Signing in…' : 'Sign in to dashboard'} <span>→</span></button>
      </form>
      <div className="demo-login"><strong>Demo access</strong><span>Caregiver: caregiver@aegis.demo</span><span>Senior: senior@aegis.demo</span><span>Password: demo1234</span></div>
      <p className="auth-switch">New to Aegis? <Link to="/signup">Create an account</Link></p>
    </main>
  </div>;
}

export default LoginPage;
