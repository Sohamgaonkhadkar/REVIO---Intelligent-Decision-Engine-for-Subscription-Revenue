import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { QueryState, EvidenceDrawer } from "../components/ui";

export default function System() {
  const model = useQuery({ queryKey: ["model"], queryFn: () => api("/api/model"), refetchInterval: 10_000 });
  const sysHealth = useQuery({ queryKey: ["health"], queryFn: () => api("/health" as any), refetchInterval: 10_000 });

  return (
    <>
      <div className="page-header">
        <h1>System Health & Model Benchmarks</h1>
        <p>Technical diagnostic panel for the REVIO decision engine.</p>
      </div>

      <QueryState q={model}>
        {(m: any) => (
          <div className="grid two" style={{ gap: 48, gridTemplateColumns: "1fr 1fr" }}>
            <div>
              <h2 className="section-title">Model Status</h2>
              <div className="card dark" style={{ marginBottom: 32 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <div className="eyebrow">Scoring Engine</div>
                  <span className={`chip ${m.mode === 'ACTIVE' ? 'good' : 'bad'}`} style={{ background: 'transparent' }}>
                    {m.mode}
                  </span>
                </div>
                
                <div className="text-ink2" style={{ fontSize: 13, marginBottom: 8 }}>Active Model Bundle</div>
                <div className="mono text-ink1" style={{ fontSize: 14 }}>{m.model_id}</div>
                
                <div className="text-ink2" style={{ fontSize: 13, marginTop: 16, marginBottom: 8 }}>Gate Validation</div>
                <div className="text-ink3" style={{ fontSize: 13, lineHeight: 1.5 }}>
                  {m.mode === 'ACTIVE' 
                    ? "Model artifact loaded and vocabulary validation passed. Engine is using ML predictions for P_hat."
                    : `Engine is in fallback mode. Reason: ${m.fallback_reason || 'Artifact unavailable'}.`}
                </div>
              </div>

              <h2 className="section-title">Fallback Policy</h2>
              <div className="card">
                <div className="text-ink2" style={{ fontSize: 13, lineHeight: 1.5 }}>
                  {m.fallback_policy}
                </div>
              </div>
            </div>

            <div>
              <h2 className="section-title">Benchmarks & Artifacts</h2>
              {m.benchmarks && m.benchmarks.length > 0 ? (
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                  <table className="data-table">
                    <thead style={{ background: 'var(--bg-2)' }}>
                      <tr>
                        <th>METRIC</th>
                        <th className="num">SCORE</th>
                        <th>THRESHOLD</th>
                        <th>STATUS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.benchmarks.map((b: any, i: number) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 500 }}>{b.name}</td>
                          <td className="num">{b.score.toFixed(3)}</td>
                          <td className="text-ink3">{b.threshold}</td>
                          <td>
                            <span className={`chip ${b.passed ? 'good' : 'bad'}`} style={{ background: 'transparent' }}>
                              {b.passed ? 'PASS' : 'FAIL'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="card">
                  <div className="text-ink3" style={{ fontSize: 13 }}>No benchmarks available.</div>
                </div>
              )}
            </div>
          </div>
        )}
      </QueryState>

      <div style={{ marginTop: 64 }}>
        <h2 className="section-title">Diagnostics</h2>
        <QueryState q={sysHealth}>
          {(h: any) => (
            <EvidenceDrawer 
              title="API Health & Kill Switches"
              record={{
                "Status": h.status,
                "Version": h.version,
                "Worker Active": String(h.worker_active),
                "Kill Switch Status": h.kill_switch_active ? "ENGAGED" : "ARMED",
              }}
              payload={h}
            />
          )}
        </QueryState>
      </div>
    </>
  );
}
