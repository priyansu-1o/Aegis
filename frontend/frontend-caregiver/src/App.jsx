import PendingList from './components/PendingList';
import './index.css';

function App() {
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
              Trusted Contact
            </p>
          </div>

          {/* Live indicator — shows backend is connected */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'var(--color-status-safe-text)',
                boxShadow: '0 0 0 3px rgba(52,199,89,0.25)',
                animation: 'pulse 2s infinite',
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: 'var(--color-on-dark-soft)',
                letterSpacing: '0.04em',
              }}
            >
              Live
            </span>
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

export default App;