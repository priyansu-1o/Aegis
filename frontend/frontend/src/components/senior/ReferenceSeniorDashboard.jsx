import { useEffect, useState } from 'react';
import { getTransactions } from '../../utils/api';

const money = (value) => `₹${Number(value || 0).toLocaleString('en-IN')}`;

export default function ReferenceSeniorDashboard({ currentUser, onTransfer, onBreakFD, onLogout }) {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const refresh = async () => {
    try { const data = await getTransactions(); setTransactions(data.transactions || []); }
    catch { setTransactions([]); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);
  const protectedToday = transactions.filter((tx) => tx.status === 'PENDING_APPROVAL' || tx.status === 'BLOCKED').reduce((sum, tx) => sum + Number(tx.amount || 0), 0);
  return <div className="ref-skin">
    <header className="ref-header"><div className="ref-header-inner"><div className="ref-brand"><span className="brand-mark">♜</span> AEGIS</div><div style={{display:'flex',gap:10,alignItems:'center'}}><span className="user-pill">Sender · {currentUser?.name}</span><button className="utility-button" onClick={onLogout}>↗ Sign out</button></div></div></header>
    <main className="app-wrap">
      <div className="partner-banner"><div className="partner-info"><div className="partner-icon">🛡</div><div><div className="partner-title">Protected by Caregiver: Priya</div><div className="partner-sub">Suspicious transactions are routed to your caregiver.</div></div></div></div>
      <div className="ref-page-heading"><div><h1>Good {new Date().getHours() < 12 ? 'morning' : 'afternoon'}, {currentUser?.name?.split(' ')[0] || 'there'} 👋</h1><p>Your money is protected by Aegis.</p></div><span className="demo-badge">Demo / Simulated Account Data</span></div>
      <section className="stat-grid"><div className="stat-card"><div className="stat-label">Available Balance</div><div className="stat-value">₹1,50,000</div></div><div className="stat-card"><div className="stat-label">Transactions Today</div><div className="stat-value">{transactions.length}</div></div><div className="stat-card"><div className="stat-label">Protected Today</div><div className="stat-value" style={{color:'var(--forest)'}}>{money(protectedToday)}</div></div></section>
      <button className="action-main" onClick={onTransfer}>↗ &nbsp; Send Money Safely</button>
      <button className="btn btn-secondary" style={{marginBottom:20}} onClick={onBreakFD}>Manage Fixed Deposit</button>
      <section className="reference-card"><div className="reference-card-head"><div><div className="reference-card-title">Recent Transactions</div><div className="reference-card-sub">Protected by Aegis Risk Engine</div></div><button className="refresh-button" onClick={refresh}>↻ <span>Refresh</span></button></div>
        {loading ? <p style={{padding:24,color:'var(--muted)'}}>Loading transactions…</p> : transactions.length === 0 ? <p style={{padding:24,color:'var(--muted)'}}>No transactions yet.</p> : transactions.slice(0,6).map((tx) => <div key={tx.tx_id} style={{display:'flex',justifyContent:'space-between',padding:'16px 22px',borderBottom:'1px solid var(--border)'}}><div><b>{tx.payee_name}</b><div className="reference-card-sub">{tx.payee_account}</div></div><div style={{textAlign:'right'}}><b>{money(tx.amount)}</b><div className={`pill ${tx.status === 'APPROVED' ? 'pill-safe' : tx.status === 'PENDING_APPROVAL' ? 'pill-pending' : 'pill-held'}`} style={{marginTop:4}}>{tx.status.replaceAll('_',' ')}</div></div></div>)}</section>
    </main>
  </div>;
}
