import { Component, type ReactNode } from "react";
import { Outlet, NavLink, Link } from "react-router-dom";

/* REVIO geometric mark */
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="REVIO">
      <defs>
        <linearGradient id="brandBlueGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#7DD3FC" />
          <stop offset="100%" stopColor="#2563EB" />
        </linearGradient>
        <filter id="brandGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.5" result="blur"/>
          <feMerge>
            <feMergeNode in="blur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      <path d="M5 21L11 3H15L9 21Z" fill="url(#brandBlueGrad)" filter="url(#brandGlow)" />
      <path d="M11 21L14 12H18L15 21Z" fill="#F8FAFC" />
    </svg>
  );
}

class RouteBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  render() {
    if (this.state.err) return (
      <div className="state-error" style={{ padding: 60 }}>
        This view encountered an error: {String(this.state.err.message).slice(0, 200)}
        <div className="tiny" style={{ marginTop: 10 }}>
          The recovery system is unaffected. <a className="plain" href="/">Return to Overview</a>.
        </div>
      </div>
    );
    return this.props.children;
  }
}

export default function App() {
  return (
    <div className="shell">
      {/* Sidebar Navigation (Desktop) */}
      <aside className="side">
        <Link to="/" style={{ textDecoration: "none" }} className="brand">
          <div>
            <BrandMark size={44} />
          </div>
          <div className="brand-name">
            <span className="brand-title">REVIO</span>
            <span className="brand-desc">Intelligent Revenue Recovery</span>
          </div>
        </Link>
        
        <NavLink to="/" end className={({ isActive }) => `navlink${isActive ? " active" : ""}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
          Overview
        </NavLink>
        <NavLink to="/cases" className={({ isActive }) => `navlink${isActive ? " active" : ""}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
          Recovery Cases
        </NavLink>
        <NavLink to="/outcomes" className={({ isActive }) => `navlink${isActive ? " active" : ""}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
          Outcomes
        </NavLink>
        <NavLink to="/knowledge" className={({ isActive }) => `navlink${isActive ? " active" : ""}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
          Knowledge & Rules
        </NavLink>
        <NavLink to="/audit" className={({ isActive }) => `navlink${isActive ? " active" : ""}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          Audit
        </NavLink>

        <div className="side-footer">
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main">
        {/* Mobile Header (Hidden on Desktop) */}
        <div className="mobile-header">
          <div><BrandMark size={20} /></div>
          <div className="brand-name">
            <span className="brand-title" style={{ fontSize: 16 }}>REVIO</span>
            <span className="brand-desc" style={{ fontSize: 8 }}>Intelligent Revenue Recovery</span>
          </div>
          <div className="env-badge mobile-badge" title="Simulated evidence">
            <span style={{ color: 'var(--money)' }}>●</span> SIM
          </div>
        </div>

        <div className="main-content pb-nav" style={{ position: 'relative' }}>
          {/* Desktop Top Right Badge */}
          <div className="desktop-badge" style={{ position: 'absolute', top: 48, right: 48, zIndex: 10 }}>
            <div className="env-badge" title="Simulated evidence">
              <span style={{ color: 'var(--money)' }}>●</span> SIM · SIMULATED EVIDENCE
            </div>
          </div>
          
          <RouteBoundary>
            <Outlet />
          </RouteBoundary>
        </div>
        
        {/* Mobile Bottom Navigation */}
        <nav className="bottom-nav">
          <NavLink to="/" end className="bottom-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            <span>Overview</span>
          </NavLink>
          <NavLink to="/cases" className="bottom-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
            <span>Cases</span>
          </NavLink>
          <NavLink to="/outcomes" className="bottom-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            <span>Outcomes</span>
          </NavLink>
          <NavLink to="/knowledge" className="bottom-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
            <span>Rules</span>
          </NavLink>
          <NavLink to="/audit" className="bottom-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span>Audit</span>
          </NavLink>
        </nav>
      </main>
    </div>
  );
}
