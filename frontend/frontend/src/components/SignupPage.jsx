import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { signup } from '../utils/api';

export default function SignupPage({ onLogin }) {
  const navigate = useNavigate();
  const [role, setRole] = useState('senior');
  const [form, setForm] = useState({ name: '', email: '', phone: '', linkCode: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [createdUser, setCreatedUser] = useState(null);
  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function submit(event) {
    event.preventDefault(); setError(''); setLoading(true);
    try {
      const { user } = await signup({ name: form.name.trim(), email: form.email.trim().toLowerCase(), password: form.password, role, link_code: form.linkCode.trim() });
      setCreatedUser(user);
    } catch (err) { setError(err.message || 'Unable to create your account. Please try again.'); }
    finally { setLoading(false); }
  }

  return <div className="auth-page signup-page">
    <header className="auth-header"><Link to="/" className="ref-brand"><img src="/logo.svg" className="brand-mark" alt="Aegis Logo" /> AEGIS</Link></header>
    <main className="auth-shell signup-shell">
      <div className="auth-tabs"><Link className="auth-tab auth-tab-link" to="/login">Sign In</Link><span className="auth-tab active">Create Account</span></div>
      <div className="auth-head"><h1>Create your account</h1><p>One account for the senior, one for the caregiver.</p></div>
      <form onSubmit={submit} noValidate>
        <div className="role-picker" aria-label="Choose your role"><button className={role === 'senior' ? 'role-option selected' : 'role-option'} type="button" onClick={() => setRole('senior')}>I&apos;m the Senior</button><button className={role === 'caregiver' ? 'role-option selected' : 'role-option'} type="button" onClick={() => setRole('caregiver')}>I&apos;m the Caregiver</button></div>
        <div className="form-group"><label htmlFor="signup-name">Full name</label><input id="signup-name" value={form.name} onChange={update('name')} placeholder="Your full name" autoComplete="name" required /></div>
        <div className="form-group"><label htmlFor="signup-email">Email</label><input id="signup-email" type="email" value={form.email} onChange={update('email')} placeholder="you@example.com" autoComplete="email" required /></div>
        <div className="form-group"><label htmlFor="signup-phone">Phone number <span className="field-optional">(optional)</span></label><input id="signup-phone" type="tel" value={form.phone} onChange={update('phone')} placeholder="+91" autoComplete="tel" /></div>
        {role === 'caregiver' && <div className="form-group"><label htmlFor="signup-link-code">Senior&apos;s link code <span className="field-optional">(optional)</span></label><input id="signup-link-code" value={form.linkCode} onChange={update('linkCode')} placeholder="Ask the senior for their code" /><p className="field-hint">You can connect accounts later.</p></div>}
        <div className="form-group"><label htmlFor="signup-password">Password</label><input id="signup-password" type="password" value={form.password} onChange={update('password')} placeholder="••••••••" autoComplete="new-password" minLength="8" required /><p className="field-hint">At least 8 characters.</p></div>
        {error && <div className="error-box">⚠ {error}</div>}<button className="auth-submit" type="submit" disabled={loading || !form.name || !form.email || !form.password}>{loading ? 'Creating account…' : 'Create account'} <span>→</span></button>
      </form>
      {createdUser && <div className="success-card show"><div className="success-badge">✓ Registration successful</div><p>Your permanent User ID</p><strong>{createdUser.user_id}</strong><span>Save this ID for connecting with your caregiver.</span><button className="auth-submit" type="button" onClick={() => { onLogin?.(createdUser); navigate(`/${createdUser.role}`, { replace: true }); }}>Go to my dashboard <span>→</span></button></div>}
      <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
    </main>
  </div>;
}
