import { Link } from 'react-router-dom';

export default function LandingPage() {
  return <div className="landing-page">
    <header className="landing-nav"><div className="landing-wrap nav-row"><div className="ref-brand"><span className="brand-mark">♜</span> AEGIS</div><Link className="nav-signin" to="/login">Sign In <span>→</span></Link></div></header>
    <main>
      <section className="hero landing-wrap">
        <div className="hero-copy"><span className="hero-eyebrow"><i /> Financial safety, before money moves</span><h1>Protect every transfer.<br /><em>Before</em> it moves.</h1><p>Aegis spots suspicious payments and gives a trusted caregiver time to review them—so your family stays one step ahead of scams.</p><Link className="hero-cta" to="/login">Protect an account <span>→</span></Link><div className="hero-trust"><div className="trust-dots"><span>R</span><span>P</span><span>✓</span></div><span>Designed for seniors and the people who protect them.</span></div></div>
        <div className="hero-visual"><div className="protection-card"><div className="card-live"><i /> AEGIS PROTECTION ACTIVE</div><div className="payment-top"><span className="payment-icon">₹</span><span className="risk-chip">HIGH RISK</span></div><div className="payment-amount">₹ 50,000</div><div className="payment-name">Unknown Recipient</div><div className="payment-note">Unusual transaction detected</div><div className="held-message">🛡 Payment paused for review</div><div className="caregiver-row"><span>Caregiver Priya has been notified</span><b>Reviewing now</b></div></div></div>
      </section>
      <section className="trust-strip"><div className="landing-wrap trust-grid"><span>✓ Proactive protection</span><span>◷ Caregiver review window</span><span>⌁ Clear, calm decisions</span></div></section>
      <section className="how landing-wrap"><span className="section-kicker">HOW AEGIS WORKS</span><h2>Protection that feels simple.</h2><div className="flow-grid"><article><b>1</b><h3>A payment is checked</h3><p>Our risk engine checks each transfer for unusual signals.</p></article><article><b>2</b><h3>Risk is caught early</h3><p>Suspicious payments are paused before money leaves the account.</p></article><article><b>3</b><h3>Someone trusted decides</h3><p>A caregiver can approve or block the transfer with context.</p></article></div></section>
      <section className="feature-band"><div className="landing-wrap"><span className="section-kicker">BUILT FOR PEACE OF MIND</span><h2>Protection for every kind of transfer.</h2><div className="feature-grid"><article><span>🛡</span><h3>Smart risk signals</h3><p>New payees, unusually large payments and scam-language patterns are checked together.</p></article><article><span>◷</span><h3>Time to think</h3><p>A gentle cooling-off period makes room for a careful conversation.</p></article><article><span>♥</span><h3>Family in the loop</h3><p>Give a trusted caregiver a clear, respectful way to help.</p></article></div></div></section>
      <section className="landing-cta"><h2>Start protecting your family today.</h2><p>Calm, clear financial safety when it matters most.</p><Link className="cta-white" to="/login">Sign in to Aegis <span>→</span></Link></section>
    </main>
    <footer><div className="landing-wrap footer-row"><div className="ref-brand"><span className="brand-mark">♜</span> AEGIS</div><span>Protection with dignity and care.</span></div></footer>
  </div>;
}
