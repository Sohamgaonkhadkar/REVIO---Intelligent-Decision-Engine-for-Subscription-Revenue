import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { QueryState, inr, pct } from "../components/ui";
import { ReactNode } from "react";
import { Link } from "react-router-dom";

const INFO_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--ink-3)' }}>
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="16" x2="12" y2="12"></line>
    <line x1="12" y1="8" x2="12.01" y2="8"></line>
  </svg>
);

function MetricCard({ title, value, info, money = false, highlight = false }: { title: string; value: ReactNode; info: string; money?: boolean; highlight?: boolean }) {
  return (
    <div className="card" style={{ padding: '24px', background: highlight ? 'rgba(46, 139, 112, 0.05)' : 'var(--bg-1)', border: highlight ? '1px solid var(--good)' : '1px solid var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div className={highlight ? "text-good" : "text-ink-3"} style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>{title}</div>
        <div title={info} style={{ cursor: 'help' }}>{INFO_ICON}</div>
      </div>
      <div className={`num-display ${money ? 'money' : ''}`} style={{ fontSize: 36, fontWeight: 700, color: money ? undefined : 'var(--ink-1)' }}>
        {value}
      </div>
      <div className="text-ink-3" style={{ fontSize: 13, marginTop: 12, lineHeight: 1.4 }}>
        {info}
      </div>
    </div>
  );
}

export default function Outcomes() {
  const o = useQuery({
    queryKey: ["outcomes"], queryFn: () => api("/api/outcomes"), refetchInterval: 5_000,
  });
  const b = useQuery({
    queryKey: ["baselines"], queryFn: () => api("/api/baselines"), refetchInterval: 60_000,
  });

  return (
    <div className="page-with-hero">
      <div className="page-hero-bg hero-outcomes" />
      <div className="page-header" style={{ marginBottom: 48 }}>
        <h1 style={{ fontSize: 32, marginBottom: 12 }}>Results & Strategy Evaluation</h1>
        <p style={{ color: 'var(--ink-2)', fontSize: 15 }}>Measured recovery outcomes and baseline comparison for the current cycle. Computed over the identical population using deterministic Monte-Carlo replay.</p>
      </div>

      <QueryState q={o} empty={(x) => x.cases_total === 0}>
        {(x) => {
          const escalatedRate = x.cases_total > 0 ? (x.cases_by_state?.ESCALATED ?? 0) / x.cases_total : 0;
          return (
            <>
              {/* RESULTS GRID - 2x2 */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 48 }}>
                <MetricCard 
                  title="RECOVERED" 
                  value={inr(x.recovered_inr)}
                  info={`of ${inr(x.at_risk_inr)} at risk`}
                  money
                  highlight
                />
                <MetricCard 
                  title="RECOVERY RATE" 
                  value={pct(x.recovery_rate)}
                  info="recovered rupees ÷ rupees at risk"
                />
                <MetricCard 
                  title="AVERAGE TIME TO RECOVER" 
                  value={<>{x.avg_time_to_recover_h ?? "—"}<span style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink-3)' }}>h</span></>}
                  info="from case opening"
                />
                <MetricCard 
                  title="ESCALATION RATE" 
                  value={pct(escalatedRate)}
                  info="cases sent to human agents"
                />
              </div>

              {/* BASELINE CHART */}
              <QueryState q={b} empty={(bb) => bb.population.cases === 0}>
                {(bb) => {
                  const base = bb;
                  const p_rec = x.recovered_inr || 0;
                  return (
                    <div className="card" style={{ marginBottom: 48, padding: '32px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                        <h2 className="section-title" style={{ margin: 0, fontSize: 24 }}>Baseline comparison</h2>
                      </div>
                      
                      <div style={{ display: 'grid', gap: 20 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 140px', alignItems: 'center', gap: 24 }}>
                          <div className="text-ink1" style={{ fontSize: 15, fontWeight: 500 }}>No intervention</div>
                          <div className="bar-track" style={{ height: 12, background: 'var(--track)', borderRadius: 99 }}>
                             <div style={{ width: `${(base?.baselines?.B0?.recovered_inr / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99, transition: 'width 1s ease' }} />
                          </div>
                          <div className="num-table text-ink2" style={{ textAlign: 'right', fontSize: 16 }}>{inr(base?.baselines?.B0?.recovered_inr || 0)}</div>
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 140px', alignItems: 'center', gap: 24 }}>
                          <div className="text-ink1" style={{ fontSize: 15, fontWeight: 500 }}>PSP-default retries</div>
                          <div className="bar-track" style={{ height: 12, background: 'var(--track)', borderRadius: 99 }}>
                             <div style={{ width: `${(base?.baselines?.B1?.recovered_inr / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99, transition: 'width 1s ease' }} />
                          </div>
                          <div className="num-table text-ink2" style={{ textAlign: 'right', fontSize: 16 }}>{inr(base?.baselines?.B1?.recovered_inr || 0)}</div>
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 140px', alignItems: 'center', gap: 24 }}>
                          <div className="text-ink1" style={{ fontSize: 15, fontWeight: 500 }}>Static doctrine policy</div>
                          <div className="bar-track" style={{ height: 12, background: 'var(--track)', borderRadius: 99 }}>
                             <div style={{ width: `${(base?.baselines?.B2?.recovered_inr / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99, transition: 'width 1s ease' }} />
                          </div>
                          <div className="num-table text-ink2" style={{ textAlign: 'right', fontSize: 16 }}>{inr(base?.baselines?.B2?.recovered_inr || 0)}</div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 140px', alignItems: 'center', gap: 24, background: 'rgba(46, 139, 112, 0.05)', padding: '24px', margin: '16px -24px 0', borderRadius: 8, border: '1px solid rgba(46, 139, 112, 0.2)' }}>
                          <div className="text-good" style={{ fontSize: 15, fontWeight: 700 }}>Revenue Recovery</div>
                          <div className="bar-track" style={{ height: 12, background: 'var(--bg-2)', borderRadius: 99 }}>
                             <div style={{ width: `${(p_rec / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--good)', borderRadius: 99, boxShadow: '0 0 12px rgba(46, 139, 112, 0.4)', transition: 'width 1s ease' }} />
                          </div>
                          <div className="num-table text-good" style={{ textAlign: 'right', fontWeight: 700, fontSize: 18 }}>{inr(p_rec)}</div>
                        </div>
                      </div>
                    </div>
                  );
                }}
              </QueryState>
              
              {/* WHAT RECOVERY COST */}
              <div style={{ marginBottom: 48 }}>
                <h2 className="section-title" style={{ marginBottom: 24 }}>What recovery cost</h2>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24 }}>
                  <MetricCard 
                    title="PAYMENT ATTEMPTS MADE" 
                    value={x.attempts_consumed ?? x.compliance?.attempts_executed ?? 0}
                    info=""
                  />
                  <MetricCard 
                    title="ATTEMPT SUCCESS" 
                    value={pct((x.recovered_inr > 0 ? (x.cases_by_state?.RECOVERED ?? 0) : 0) / Math.max(1, x.attempts_consumed ?? x.compliance?.attempts_executed ?? 1))}
                    info=""
                  />
                  <MetricCard 
                    title="CUSTOMER CONTACTS SENT" 
                    value={x.contacts_consumed ?? 0}
                    info=""
                  />
                </div>
              </div>

              {/* CHARTS */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <h2 className="section-title" style={{ margin: 0 }}>Failure reason</h2>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {Object.entries(x.by_failure_class || {}).sort((a: any, b: any) => b[1].inr - a[1].inr).map(([cls, stat]: [string, any]) => (
                      <div key={cls} style={{ display: 'grid', gridTemplateColumns: '1fr max-content 40px', alignItems: 'center', gap: 16 }}>
                        <div className="text-ink1" style={{ fontSize: 14 }}>{cls.replaceAll("_", " ")}</div>
                        <div className="bar-track" style={{ height: 4, width: 80, background: 'var(--line)', borderRadius: 99 }}>
                           <div style={{ width: `${(stat.n / x.cases_total) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99 }} />
                        </div>
                        <div className="num-display" style={{ fontSize: 16, textAlign: 'right' }}>{stat.n}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <h2 className="section-title" style={{ margin: 0 }}>Rail</h2>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {['upi_autopay', 'card_si'].map((rail: string) => {
                      const stat = x.by_rail?.[rail] || { n: 0 };
                      return (
                        <div key={rail} style={{ display: 'grid', gridTemplateColumns: '1fr max-content 40px', alignItems: 'center', gap: 16 }}>
                          <div className="text-ink1" style={{ fontSize: 14 }}>{rail === 'upi_autopay' ? 'UPI AutoPay' : 'Card SI'}</div>
                          <div className="bar-track" style={{ height: 4, width: 80, background: 'var(--line)', borderRadius: 99 }}>
                             <div style={{ width: `${(stat.n / x.cases_total) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99 }} />
                          </div>
                          <div className="num-display" style={{ fontSize: 16, textAlign: 'right' }}>{stat.n}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </>
          );
        }}
      </QueryState>
    </div>
  );
}
