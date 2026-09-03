import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login } from '../utils/api';

export default function ReferenceLoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault(); setError(''); setLoading(true);
    try {
      const { user } = await login(email.trim().toLowerCase(), password);
      onLogin?.(user);
      navigate(`/${user.role}`, { replace: true });
    } catch (err) { setError(err.message || 'Unable to sign in. Please try again.'); }
    finally { setLoading(false); }
  }

  return <div className="auth-page">
    <div className="auth-brand"><div className="ref-brand"><span className="brand-mark">♜</span> AEGIS</div></div>
    <main className="auth-shell">
      <div className="auth-tabs"><button className="auth-tab active" type="button">Sign In</button><Link className="auth-tab auth-tab-link" to="/signup">Create Account</Link></div>
      <h1 className="auth-heading">Welcome Back</h1>
      <p className="auth-sub">Enter your credentials to access your dashboard.</p>
      <form onSubmit={submit} noValidate>
        <div className="form-group"><label htmlFor="email">Email address</label><input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required /></div>
        <div className="form-group"><label htmlFor="password">Password</label><input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete="current-password" required /></div>
        {error && <div className="error-box">⚠ {error}</div>}
        <button id="login-submit" className="auth-submit" type="submit" disabled={loading || !email || !password}>{loading ? 'Signing in…' : 'Sign In to Dashboard'}</button>
      </form>
      <div className="demo-login"><strong>Demo credentials</strong><p>Caregiver: caregiver@aegis.demo</p><p>Senior: senior@aegis.demo</p><p>Password for both: <b>demo1234</b></p></div>
      <p className="auth-switch">New to Aegis? <Link to="/signup">Create an account</Link></p>
    </main>
  </div>;
}
