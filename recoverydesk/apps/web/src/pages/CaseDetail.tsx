import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";
import { QueryState, StateChip, inr, pct, ago, classHuman, railHuman, actionHuman, EvidenceDrawer } from "../components/ui";

type Candidate = {
  candidate_id: string;
  action_type?: string;
  window_code?: string | null;
  channel?: string | null;
  verdict: { allowed: boolean; reasons?: string[]; rule_ids?: string[]; hash?: string };
  p_hat?: number | null;
  ev_inr?: number | null;
  ev_components?: Record<string, number>;
};

const candHuman = (id: string) => {
  const [act, spec] = id.split("@");
  const base = actionHuman(act);
  if (!spec || spec === "next-cluster") return base;
  return `${base} · ${spec.includes("W") ? spec.replaceAll("_", "-") + " window" : spec}`;
};

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const d = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api(`/api/cases/${caseId}` as "/api/cases/{case_id}"),
    refetchInterval: 4_000,
  });
  const decisions = useQuery({
    queryKey: ["case-decisions", caseId],
    queryFn: () => api(`/api/cases/${caseId}/decisions` as "/api/cases/{case_id}/decisions"),
    refetchInterval: 4_000,
  });
  
  const latestDecisionId = decisions.data?.items?.[decisions.data.items.length - 1]?.decision_id;
  const explain = useQuery({
    queryKey: ["case-explain", caseId, latestDecisionId],
    queryFn: () => api(`/api/cases/${caseId}/decisions/${latestDecisionId}/explain` as "/api/cases/{case_id}/decisions/{decision_id}/explain"),
    enabled: !!latestDecisionId,
    refetchInterval: 10_000,
  });

  if (d.isError) return <div className="state-error">Case not found — {String(d.error.message)}</div>;
  
  const latest = decisions.data?.items?.[decisions.data.items.length - 1];
  const chosen: Candidate | undefined = latest?.candidates.find((c: Candidate) => c.candidate_id === latest.chosen.candidate_id);
  const legalCands = latest?.candidates.filter((x: Candidate) => x.verdict?.allowed) || [];
  const refusedCands = latest?.candidates.filter((x: Candidate) => !x.verdict?.allowed) || [];

  return (
    <div className="page-with-hero">
      <div className="page-hero-bg hero-casedetail" />
      <div style={{ marginBottom: 24 }}>
        <Link className="text-ink-2" style={{ fontSize: 13, fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 8, background: 'var(--bg-1)', border: '1px solid var(--line)', padding: '10px 16px', borderRadius: 'var(--radius-sm)', transition: 'var(--transition)' }} to="/cases">
          <span>&larr;</span> Back to the queue
        </Link>
      </div>

      <QueryState q={d}>
        {(c) => {
          const terminal = ["RECOVERED", "STOPPED"].includes(c.state);
          const isRecovered = c.state === "RECOVERED";
          const isStopped = c.state === "STOPPED";
          const isEscalated = c.state === "ESCALATED";
          const heroBorder = isRecovered ? 'var(--good)' : (isStopped ? 'var(--bad)' : (isEscalated ? 'var(--warn)' : 'var(--line)'));
          const heroBg = isRecovered ? 'rgba(46, 139, 112, 0.05)' : (isStopped ? 'rgba(199, 91, 91, 0.05)' : (isEscalated ? 'rgba(214, 158, 46, 0.05)' : 'var(--bg-1)'));

          return (<>
            {/* FINANCIAL HERO + CONTEXT */}
            <div className="card" style={{ marginBottom: 48, background: heroBg, borderColor: heroBorder, position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: 4, background: heroBorder, opacity: 0.8 }} />
              
              <div style={{ paddingLeft: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 12, display: 'block' }}>Money at Risk</div>
                    <div className="num-display money" style={{ fontSize: 64, marginBottom: 16 }}>
                      {inr(c.amount_at_risk)}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="mono text-ink-3" style={{ fontSize: 14, marginBottom: 8 }}>Case {c.case_id}</div>
                    <StateChip state={c.state} />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, max-content)', gap: 48, fontSize: 15, color: 'var(--ink-1)', marginBottom: 32, fontWeight: 500 }}>
                  <div>
                    <div className="eyebrow">Failure Reason</div>
                    <div>{classHuman(c.first_failure_class ?? c.failure_class)}</div>
                  </div>
                  <div>
                    <div className="eyebrow">Payment Rail</div>
                    <div>{railHuman(c.rail)}</div>
                  </div>
                  <div>
                    <div className="eyebrow">Customer</div>
                    <div>{c.customer?.name || "Unknown"}</div>
                  </div>
                  <div>
                    <div className="eyebrow">Time in flow</div>
                    <div>{ago(c.opened_ts)}</div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: 32, alignItems: 'center', marginBottom: 24 }}>
                  <div className="text-ink-2" style={{ fontSize: 13, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="eyebrow">Retry Budget</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} style={{ width: 8, height: 16, background: i < (c.retries_used ?? 0) ? 'var(--ink-2)' : 'rgba(148, 163, 184, 0.15)', borderRadius: 2 }} />
                      ))}
                    </div>
                    <span>{c.retries_used ?? 0}/3</span>
                  </div>
                  <div className="text-ink-2" style={{ fontSize: 13, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="eyebrow">Contact Budget</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {Array.from({ length: 2 }).map((_, i) => (
                        <div key={i} style={{ width: 8, height: 16, background: i < (c.contacts_sent ?? 0) ? 'var(--ink-2)' : 'rgba(148, 163, 184, 0.15)', borderRadius: 2 }} />
                      ))}
                    </div>
                    <span>{c.contacts_sent ?? 0}/2</span>
                  </div>
                </div>
                
                <div style={{ borderTop: '1px solid var(--line)', paddingTop: 16, color: 'var(--ink-3)', fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div className="eyebrow">What happens next:</div>
                  {
                    isRecovered ? <span className="text-good" style={{ fontWeight: 600 }}>This case has been fully recovered.</span> :
                    isStopped ? <span className="text-bad" style={{ fontWeight: 600 }}>Recovery halted: {c.stop_reason}.</span> :
                    isEscalated ? <span className="text-warn" style={{ fontWeight: 600 }}>Escalated for human review: {c.escalated_reason}.</span> :
                    <span style={{ color: 'var(--ink-1)', fontWeight: 500 }}>Waiting on system cycle or customer response...</span>
                  }
                </div>
              </div>
            </div>

            {latest?.fallback && (
              <div style={{ background: 'rgba(244, 63, 94, 0.05)', padding: '16px 24px', borderRadius: 'var(--radius)', border: '1px solid rgba(244, 63, 94, 0.2)', marginBottom: 24 }}>
                <div style={{ color: 'var(--bad)', fontSize: 14, fontWeight: 600 }}>Model uncalibrated/unresponsive; static doctrine applied</div>
              </div>
            )}
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 48 }}>
              {/* 1. RULES */}
              <div className="card" style={{ padding: 24, borderTop: '3px solid var(--good)' }}>
                <div className="text-ink-3" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', marginBottom: 12, textTransform: 'uppercase' }}>1 · Rules</div>
                <div className="text-ink-2" style={{ fontSize: 14, marginBottom: 16 }}>Is it allowed?</div>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--ink-1)', marginBottom: 12 }}>
                  {legalCands.length} <span style={{ fontSize: 16, color: 'var(--ink-3)' }}>of {latest?.candidates.length || 0}</span>
                </div>
                <div className="text-ink-3" style={{ fontSize: 13 }}>
                  {refusedCands.length > 0 ? `Refusals name the exact rule — ${refusedCands[0].verdict.reasons?.[0] || 'Constraint failed'}.` : 'All options permitted by doctrine.'}
                </div>
              </div>
              
              {/* 2. LIKELIHOOD */}
              <div className="card" style={{ padding: 24 }}>
                <div className="text-ink-3" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', marginBottom: 12, textTransform: 'uppercase' }}>2 · Likelihood</div>
                <div className="text-ink-2" style={{ fontSize: 14, marginBottom: 16 }}>How likely is it to work?</div>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--ink-1)', marginBottom: 12 }}>
                  {chosen?.p_hat != null ? `${(chosen.p_hat * 100).toFixed(1)}%` : "—"}
                </div>
                <div className="text-ink-3" style={{ fontSize: 13 }}>
                  Estimated only for permitted options, never for refused ones.
                </div>
              </div>
              
              {/* 3. ECONOMICS */}
              <div className="card" style={{ padding: 24, borderTop: '3px solid var(--good)' }}>
                <div className="text-ink-3" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', marginBottom: 12, textTransform: 'uppercase' }}>3 · Economics</div>
                <div className="text-ink-2" style={{ fontSize: 14, marginBottom: 16 }}>Is it worth doing?</div>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--ink-1)', marginBottom: 12 }}>
                  {chosen?.ev_inr != null ? inr(chosen.ev_inr) : "—"}
                </div>
                <div className="text-ink-3" style={{ fontSize: 13 }}>
                  Chance of recovery weighed against the money at risk.
                </div>
              </div>
              
              {/* 4. CHOICE */}
              <div className="card" style={{ padding: 24, borderTop: '3px solid var(--money)', background: 'var(--bg-2)' }}>
                <div className="text-money" style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.05em', marginBottom: 12, textTransform: 'uppercase' }}>4 · Choice</div>
                <div className="text-ink-2" style={{ fontSize: 14, marginBottom: 16 }}>What did we choose?</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--money)', marginBottom: 12, lineHeight: 1.2 }}>
                  {chosen ? candHuman(chosen.candidate_id) : (latest ? "No action" : "Evaluating...")}
                </div>
                <div className="text-ink-3" style={{ fontSize: 13 }}>
                  Because: {latest?.chosen?.reason_code ? `${latest.chosen.reason_code.toLowerCase().replace('_', ' ')}.` : 'Terminal state reached.'}
                </div>
              </div>
            </div>

            <div className="grid" style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 48, marginBottom: 64 }}>
              <div>
                <div className="card" style={{ marginBottom: 40, padding: 0, overflow: 'hidden' }}>
                  <div style={{ padding: '24px', borderBottom: '1px solid var(--line)', background: 'var(--bg-1)' }}>
                    <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8 }}>Bounded Action Set</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 className="section-title" style={{ color: 'var(--ink-1)', margin: 0, fontSize: 20 }}>Options considered</h3>
                      <div className="text-money" style={{ fontSize: 12, fontWeight: 600, border: '1px solid var(--money)', padding: '4px 12px', borderRadius: 20, background: 'rgba(201, 149, 46, 0.1)' }}>Chosen row highlighted</div>
                    </div>
                  </div>
                  <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse', background: 'var(--bg-1)' }}>
                    <thead style={{ background: 'var(--bg-0)' }}>
                      <tr>
                        <th style={{ padding: '16px 24px', color: 'var(--ink-3)', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textAlign: 'left', borderBottom: '1px solid var(--line)' }}>OPTION</th>
                        <th style={{ padding: '16px 24px', color: 'var(--ink-3)', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textAlign: 'left', borderBottom: '1px solid var(--line)' }}>PERMITTED?</th>
                        <th style={{ padding: '16px 24px', color: 'var(--ink-3)', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textAlign: 'right', borderBottom: '1px solid var(--line)' }}>CHANCE</th>
                        <th style={{ padding: '16px 24px', color: 'var(--ink-3)', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textAlign: 'right', borderBottom: '1px solid var(--line)' }}>EXPECTED VALUE</th>
                        <th style={{ padding: '16px 24px', color: 'var(--ink-3)', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textAlign: 'left', borderBottom: '1px solid var(--line)' }}>WHY</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latest?.candidates.map((cand: Candidate) => {
                        const isChosen = cand.candidate_id === latest?.chosen?.candidate_id;
                        const isRefused = !cand.verdict.allowed;
                        return (
                          <tr key={cand.candidate_id} style={{ background: isChosen ? 'var(--money-light)' : 'transparent', borderBottom: '1px solid var(--line)', opacity: isRefused ? 0.5 : 1 }}>
                            <td style={{ padding: '16px 24px', color: isChosen ? 'var(--money)' : 'var(--ink-1)', fontWeight: isChosen ? 600 : 400 }}>{candHuman(cand.candidate_id)}</td>
                            <td style={{ padding: '16px 24px' }}>
                              {cand.verdict.allowed ? 
                                <span className="chip good">yes</span> : 
                                <span className="chip bad">no</span>
                              }
                            </td>
                            <td style={{ padding: '16px 24px', textAlign: 'right', color: 'var(--ink-1)', fontFamily: 'var(--font-mono)' }}>{cand.p_hat != null && !isRefused ? pct(cand.p_hat) : "—"}</td>
                            <td style={{ padding: '16px 24px', textAlign: 'right', color: isChosen ? 'var(--money)' : 'var(--ink-1)', fontWeight: isChosen ? 700 : 400, fontFamily: 'var(--font-mono)' }}>{cand.ev_inr != null && !isRefused ? inr(cand.ev_inr) : "—"}</td>
                            <td style={{ padding: '16px 24px', color: 'var(--ink-3)', fontSize: 13 }}>
                              {cand.verdict.allowed ? (isChosen ? <span style={{color: 'var(--money)', fontWeight: 500}}>Highest expected recovery value</span> : "Permitted, lower expected value") : `Refused: ${cand.verdict.reasons?.[0] || 'Constraint failed'}`}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="section-title">Case timeline</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24, position: 'relative' }}>
                  <div style={{ position: 'absolute', top: 12, bottom: 12, left: 7, width: 2, background: 'var(--line)', zIndex: 0 }} />
                  
                  {c.timeline.map((t: any, idx: number) => {
                    const isPositive = t.event_type.includes("recovered") || t.event_type.includes("succeeded");
                    const isNegative = t.event_type.includes("blocked") || t.event_type.includes("failed") || t.event_type.includes("terminal");
                    const isWarn = t.event_type.includes("escalated");
                    const color = isPositive ? 'var(--good)' : isNegative ? 'var(--bad)' : isWarn ? 'var(--warn)' : 'var(--ink-3)';
                    const glow = isPositive ? '0 0 10px rgba(46, 139, 112, 0.4)' : isNegative ? '0 0 10px rgba(199, 91, 91, 0.4)' : 'none';
                    
                    return (
                      <div key={`${t.event_type}-${t.occurred_at}-${idx}`} style={{ display: 'flex', gap: 20, zIndex: 1, position: 'relative' }}>
                        <div style={{ width: 16, height: 16, borderRadius: '50%', background: color, border: '3px solid var(--bg-0)', marginTop: 2, boxShadow: glow }} />
                        <div>
                          <div className="text-ink3" style={{ fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
                            {new Date(t.occurred_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                          </div>
                          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-1)' }}>
                            {
                              t.event_type === "decision_made" ? "Decision made" :
                              t.event_type === "intervention_executed" ? "Recovery action dispatched" :
                              t.event_type === "attempt_failed" ? "Payment attempt declined" :
                              t.event_type === "attempt_succeeded" ? "Payment recovered" :
                              t.event_type === "case_opened" ? "Recovery case opened" :
                              t.event_type === "payment_failed" ? "Payment-failure signal received" :
                              t.event_type.replaceAll("_", " ")
                            }
                          </div>
                          <div className="text-ink2" style={{ fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
                            {
                              t.event_type === "case_opened" ? `Mandate confirmed active. Retry budget ${c.policy_id.includes('upi')? 3:1}.` :
                              t.event_type === "payment_failed" ? `${inr(c.amount_at_risk)} auto-debit declined on ${railHuman(c.rail)}.` :
                              t.event_type === "decision_made" ? `${legalCands.length} of ${latest?.candidates.length || 0} options permitted.` :
                              ""
                            }
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* TECHNICAL EVIDENCE */}
            <div style={{ borderTop: "1px solid var(--line)", paddingTop: 48 }}>
              <h3 className="section-title" style={{ color: 'var(--ink-3)' }}>Audit & Technical Evidence</h3>
              <EvidenceDrawer 
                title="View Case Details & Decision Trace" 
                record={{
                  "Case ID": c.case_id,
                  "Policy ID": c.policy_id,
                  "Opened At": c.opened_ts,
                  "Fallback mode": String(latest?.fallback ?? false)
                }}
                payload={explain.data ? explain.data : null}
              />
            </div>
          </>);
        }}
      </QueryState>
    </div>
  );
}
