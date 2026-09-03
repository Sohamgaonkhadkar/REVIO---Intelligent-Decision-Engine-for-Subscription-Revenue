import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { QueryState, inr, pct, ago } from "../components/ui";

function EngineStrip({ outcomes }: { outcomes: any }) {
  const active = (outcomes.cases_by_state?.OPEN_DECISION ?? 0) + (outcomes.cases_by_state?.ACTION_PENDING ?? 0) + (outcomes.cases_by_state?.WAITING ?? 0) + (outcomes.cases_by_state?.AWAITING_CUSTOMER ?? 0);
  const openCount = outcomes.cases_total ?? 0;
  
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: 24 }}>
      <div style={{ padding: '20px 24px' }}>
        <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Detect</div>
        <div className="num-display" style={{ fontSize: 28, color: 'var(--ink-1)', display: 'block' }}>{openCount}</div>
      </div>
      <div style={{ padding: '20px 24px', borderLeft: '1px solid var(--line)' }}>
        <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Decide</div>
        <div className="num-display text-ink1" style={{ fontSize: 28, display: 'block' }}>{active}</div>
      </div>
      <div style={{ padding: '20px 24px', borderLeft: '1px solid var(--line)' }}>
        <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Execute</div>
        <div className="num-display text-ink1" style={{ fontSize: 28, display: 'block' }}>{outcomes.compliance?.attempts_executed ?? outcomes.attempts_consumed ?? 0}</div>
      </div>
      <div style={{ padding: '20px 24px', borderLeft: '1px solid var(--line)' }}>
        <div className="eyebrow text-good" style={{ marginBottom: 8, display: 'block' }}>Recover</div>
        <div className="num-display text-good" style={{ fontSize: 28, display: 'block' }}>{inr(outcomes.recovered_inr)}</div>
      </div>
    </div>
  );
}

function BaselineComparison({ base, out }: { base: any; out: any }) {
  const p_rec = out.recovered_inr || 0;
  
  return (
    <div className="card" style={{ marginTop: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 className="section-title" style={{ margin: 0 }}>Baseline Comparison</h2>
        <Link to="/outcomes" className="chip info">View full methodology →</Link>
      </div>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 140px', alignItems: 'center', gap: 24 }}>
          <div className="text-ink1" style={{ fontSize: 14, fontWeight: 500 }}>No intervention</div>
          <div className="bar-track" style={{ height: 8, background: 'var(--track)', borderRadius: 99 }}>
             <div style={{ width: `${(base?.baselines?.B0?.recovered_inr / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99, transition: 'width 1s ease' }} />
          </div>
          <div className="num-table text-ink2" style={{ textAlign: 'right' }}>{inr(base?.baselines?.B0?.recovered_inr || 0)}</div>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 140px', alignItems: 'center', gap: 24 }}>
          <div className="text-ink1" style={{ fontSize: 14, fontWeight: 500 }}>PSP-default retries</div>
          <div className="bar-track" style={{ height: 8, background: 'var(--track)', borderRadius: 99 }}>
             <div style={{ width: `${(base?.baselines?.B1?.recovered_inr / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99, transition: 'width 1s ease' }} />
          </div>
          <div className="num-table text-ink2" style={{ textAlign: 'right' }}>{inr(base?.baselines?.B1?.recovered_inr || 0)}</div>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 140px', alignItems: 'center', gap: 24 }}>
          <div className="text-ink1" style={{ fontSize: 14, fontWeight: 500 }}>Static doctrine policy</div>
          <div className="bar-track" style={{ height: 8, background: 'var(--track)', borderRadius: 99 }}>
             <div style={{ width: `${(base?.baselines?.B2?.recovered_inr / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99, transition: 'width 1s ease' }} />
          </div>
          <div className="num-table text-ink2" style={{ textAlign: 'right' }}>{inr(base?.baselines?.B2?.recovered_inr || 0)}</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 140px', alignItems: 'center', gap: 24, background: 'rgba(46, 139, 112, 0.1)', padding: '16px', margin: '8px -16px 0', borderRadius: 8, border: '1px solid rgba(46, 139, 112, 0.2)' }}>
          <div className="text-good" style={{ fontSize: 14, fontWeight: 700 }}>Revenue Recovery</div>
          <div className="bar-track" style={{ height: 8, background: 'var(--bg-2)', borderRadius: 99 }}>
             <div style={{ width: `${(p_rec / (base?.population?.at_risk_inr || 1)) * 100}%`, height: '100%', background: 'var(--good)', borderRadius: 99, boxShadow: '0 0 10px rgba(46, 139, 112, 0.3)', transition: 'width 1s ease' }} />
          </div>
          <div className="num-table text-good" style={{ textAlign: 'right', fontWeight: 700, fontSize: 15 }}>{inr(p_rec)}</div>
        </div>
      </div>
      
      <div className="text-ink3" style={{ fontSize: 13, marginTop: 24 }}>
        Performance vs baselines on identical population. Evaluated over {(base?.population?.cases || 0).toLocaleString()} simulated cases.
      </div>
    </div>
  );
}

function LiveActivity({ events }: { events: any[] }) {
  if (!events || events.length === 0) {
    return <div className="card"><div className="text-ink3">Quiet — cases advance on worker cycles.</div></div>;
  }
  
  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 className="section-title" style={{ margin: 0 }}>Live Activity</h2>
        <Link to="/audit" className="chip info">View Audit Journal →</Link>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {events.map((e) => (
          <div key={e.event_id} style={{ display: 'grid', gridTemplateColumns: '1fr max-content', gap: 16 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-1)' }}>
                {e.event_type.replaceAll("_", " ")}
              </div>
              <div className="text-ink3" style={{ fontSize: 13, marginTop: 4 }}>
                Case <Link to={`/cases/${e.case_id}`} className="mono text-info">{e.case_id.split("-")[0]}</Link>
              </div>
            </div>
            <div className="text-ink3" style={{ fontSize: 13, fontWeight: 500 }}>
              {ago(e.occurred_at)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Overview() {
  const o = useQuery({ queryKey: ["outcomes"], queryFn: () => api("/api/outcomes"), refetchInterval: 5_000 });
  const b = useQuery({ queryKey: ["baselines"], queryFn: () => api("/api/baselines"), refetchInterval: 15_000 });
  const e = useQuery({ queryKey: ["events_overview"], queryFn: () => api("/api/events?limit=8"), refetchInterval: 5_000 });

  return (
    <QueryState q={o} empty={(x) => x.cases_total === 0}>
      {(out) => {
        const active = (out.cases_by_state?.OPEN_DECISION ?? 0) + (out.cases_by_state?.ACTION_PENDING ?? 0) + (out.cases_by_state?.WAITING ?? 0) + (out.cases_by_state?.AWAITING_CUSTOMER ?? 0);
        const stopped = out.cases_by_state?.STOPPED ?? 0;
        const escalated = out.cases_by_state?.ESCALATED ?? 0;
        const complianceV = (out.compliance?.violations_retry_budget || 0) + (out.compliance?.violations_contact_cap || 0) + (out.compliance?.violations_post_terminal || 0);
        const avg_time = out.avg_time_to_recover_h ? `${out.avg_time_to_recover_h}h` : '—';
        
        return (
          <div className="page-with-hero">
            <div className="page-hero-bg hero-overview" />
            <EngineStrip outcomes={out} />
            
            {/* HERO FINANCIAL METRICS */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 40 }}>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Still at risk</div>
                <div className="text-money num-display" style={{ fontSize: 24, display: 'block' }}>{inr(out.at_risk_inr - out.recovered_inr)}</div>
              </div>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Active cases</div>
                <div className="num-display" style={{ fontSize: 24, color: 'var(--ink-1)', display: 'block' }}>{active}</div>
              </div>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow text-warn" style={{ marginBottom: 8, display: 'block' }}>Escalated</div>
                <div className="num-display text-warn" style={{ fontSize: 24, display: 'block' }}>{escalated}</div>
                <div className="text-ink3" style={{ fontSize: 11, marginTop: 4 }}>with a human</div>
              </div>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Stopped</div>
                <div className="num-display" style={{ fontSize: 24, color: 'var(--ink-1)', display: 'block' }}>{stopped}</div>
                <div className="text-ink3" style={{ fontSize: 11, marginTop: 4 }}>closed</div>
              </div>
              <div className="card" style={{ padding: '16px', borderColor: complianceV === 0 ? 'var(--good)' : 'var(--bad)', background: complianceV === 0 ? 'rgba(46, 139, 112, 0.05)' : 'rgba(199, 91, 91, 0.05)' }}>
                <div className="eyebrow" style={{ color: complianceV === 0 ? 'var(--good)' : 'var(--bad)', marginBottom: 8, display: 'block' }}>Compliance</div>
                <div className={`num-display ${complianceV === 0 ? 'text-good' : 'text-bad'}`} style={{ fontSize: 24, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {complianceV === 0 ? "●" : "!"} {complianceV} violations
                </div>
              </div>
            </div>

            {/* SECOND ROW - NEW AVERAGE TIME METRIC */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 40 }}>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Average time to recover</div>
                <div className="num-display" style={{ fontSize: 24, color: 'var(--ink-1)', display: 'block' }}>{avg_time}</div>
              </div>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Recovery Rate</div>
                <div className="num-display" style={{ fontSize: 24, color: 'var(--ink-1)', display: 'block' }}>{pct(out.recovery_rate)}</div>
              </div>
              <div className="card" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Total cases</div>
                <div className="num-display" style={{ fontSize: 24, color: 'var(--ink-1)', display: 'block' }}>{out.cases_total}</div>
              </div>
            </div>

            <QueryState q={b}>
              {(base) => <BaselineComparison base={base} out={out} />}
            </QueryState>
            
            <div style={{ marginTop: 40, marginBottom: 40 }}>
              <QueryState q={b}>
                {(base) => {
                  const rr_timing = base?.recoverydesk?.recovery_timing_counts || {};
                  const b2_timing = base?.baselines?.B2?.recovery_timing_counts || {};
                  const max_val = Math.max(...Object.values(rr_timing as Record<string, number>), ...Object.values(b2_timing as Record<string, number>), 1);
                  
                  return (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
                      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <h2 className="section-title" style={{ margin: 0 }}>When recoveries land · REVIO</h2>
                        </div>
                        
                        <div>
                          <div style={{ display: 'flex', alignItems: 'flex-end', height: 100, gap: 8, paddingBottom: 8, borderBottom: '1px solid var(--line)' }}>
                            {Object.entries(rr_timing).map(([k, v]: [string, any]) => (
                              <div key={k} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}>
                                <div className="text-good" style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{v > 0 ? v : ''}</div>
                                <div style={{ width: '100%', background: 'var(--good)', height: (v / max_val) * 76, minHeight: v > 0 ? 4 : 0, borderRadius: '4px 4px 0 0', boxShadow: '0 -4px 12px rgba(46, 139, 112, 0.3)' }} />
                              </div>
                            ))}
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                            {Object.keys(rr_timing).map(k => <div key={k} className="text-ink3" style={{ fontSize: 11, flex: 1, textAlign: 'center' }}>{k}</div>)}
                          </div>
                        </div>
                      </div>
                      
                      <div className="card dark" style={{ padding: '24px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                          <h2 className="section-title" style={{ margin: 0, color: 'var(--ink-side-1)' }}>When recoveries land · fixed timing playbook</h2>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'flex-end', height: 100, gap: 8, paddingBottom: 8, borderBottom: '1px solid var(--line-side)' }}>
                          {Object.entries(b2_timing).map(([k, v]: [string, any]) => (
                            <div key={k} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}>
                              <div className="text-ink-side-2" style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{v > 0 ? Math.round(v) : ''}</div>
                              <div style={{ width: '100%', background: 'var(--ink-side-2)', opacity: 0.5, height: (v / max_val) * 76, minHeight: v > 0 ? 4 : 0, borderRadius: '4px 4px 0 0' }} />
                            </div>
                          ))}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                          {Object.keys(b2_timing).map(k => <div key={k} className="text-ink-side-2" style={{ fontSize: 11, flex: 1, textAlign: 'center' }}>{k}</div>)}
                        </div>
                      </div>
                    </div>
                  );
                }}
              </QueryState>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, marginTop: 40, marginBottom: 40 }}>
              <QueryState q={e}>
                {(evts) => <LiveActivity events={evts.items} />}
              </QueryState>

              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                  <h2 className="section-title" style={{ margin: 0 }}>Why payments failed</h2>
                  <div className="eyebrow">All {out.cases_total} cases</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {Object.entries(out.by_failure_class || {}).sort((a: any, b: any) => b[1].inr - a[1].inr).map(([cls, stat]: [string, any]) => (
                    <div key={cls} style={{ display: 'grid', gridTemplateColumns: '1fr max-content 40px', alignItems: 'center', gap: 16 }}>
                      <div className="text-ink1" style={{ fontSize: 14 }}>{cls.replaceAll("_", " ")}</div>
                      <div className="bar-track" style={{ height: 4, width: 80, background: 'var(--line)', borderRadius: 99 }}>
                         <div style={{ width: `${(stat.n / out.cases_total) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99 }} />
                      </div>
                      <div className="num-display" style={{ fontSize: 16, textAlign: 'right' }}>{stat.n}</div>
                    </div>
                  ))}
                </div>
                
                <div style={{ marginTop: 32, paddingTop: 24, borderTop: '1px solid var(--line)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <h2 className="section-title" style={{ margin: 0, fontSize: 16 }}>Rail breakdown</h2>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {Object.entries(out.by_rail || {}).sort((a: any, b: any) => b[1].inr - a[1].inr).map(([rail, stat]: [string, any]) => (
                      <div key={rail} style={{ display: 'grid', gridTemplateColumns: '1fr max-content 40px', alignItems: 'center', gap: 16 }}>
                        <div className="text-ink1" style={{ fontSize: 14 }}>{rail === 'upi_autopay' ? 'UPI AutoPay' : 'Card SI'}</div>
                        <div className="bar-track" style={{ height: 4, width: 80, background: 'var(--line)', borderRadius: 99 }}>
                           <div style={{ width: `${(stat.n / out.cases_total) * 100}%`, height: '100%', background: 'var(--ink-2)', borderRadius: 99 }} />
                        </div>
                        <div className="num-display" style={{ fontSize: 16, textAlign: 'right' }}>{stat.n}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      }}
    </QueryState>
  );
}
