import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { QueryState, inr, pct } from "../components/ui";

function getProvenanceLabel(source: string) {
  const s = source.toLowerCase();
  if (s.includes('rbi') || s.includes('npci') || s.includes('legal')) return { label: 'Regulatory Input', cls: 'warn' };
  if (s.includes('playbook') || s.includes('doctrine')) return { label: 'Recovery Doctrine', cls: 'good' };
  if (s.includes('psp') || s.includes('gateway')) return { label: 'PSP Behavior', cls: 'info' };
  if (s.includes('architecture') || s.includes('model')) return { label: 'System Doc', cls: '' };
  return { label: 'Operations', cls: '' };
}

export default function Knowledge() {
  const [caseId, setCaseId] = useState("");
  const [checkCase, setCheckCase] = useState("");
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");

  const cons = useQuery({ queryKey: ["constraints"], queryFn: () => api("/api/constraints"), refetchInterval: 30_000 });
  const check = useQuery({
    queryKey: ["constraint-check", checkCase],
    queryFn: () => api(`/api/constraints/check?case_id=${encodeURIComponent(checkCase)}` as "/api/constraints/check"),
    enabled: checkCase.length >= 8,
    refetchInterval: 10_000,
  });
  const search = useQuery({
    queryKey: ["knowledge-search", submitted],
    queryFn: () => api(`/api/knowledge/search?q=${encodeURIComponent(submitted)}&k=5` as "/api/knowledge/search"),
    enabled: submitted.length >= 2,
  });
  const openCases = useQuery({ 
    queryKey: ["cases", "dropdown", "knowledge"], 
    queryFn: () => api("/api/cases?limit=200") 
  });

  return (
    <div className="page-with-hero">
      <div className="page-hero-bg hero-knowledge" />
      <div className="page-header" style={{ marginBottom: 48 }}>
        <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8 }}>BOUNDED AND REFERENCE</div>
        <h1>Knowledge & rules</h1>
        <p>
          Recovery rules decide what may happen to a case. Reference guidance gives the reasoning and boundaries behind those rules.
        </p>
      </div>

      <div className="grid two" style={{ gap: 32, gridTemplateColumns: "1fr 1fr", display: "grid" }}>
        
        {/* ---------------- LEFT: RECOVERY RULES ---------------- */}
        <div className="card dark" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: 32 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 8 }}>
              <h2 className="section-title" style={{ color: 'var(--money)', margin: 0, fontSize: 13, letterSpacing: '0.05em' }}>DECIDES</h2>
              <div className="text-ink-1" style={{ fontSize: 20, fontWeight: 600 }}>Recovery rules - what the system is allowed to do</div>
            </div>
          </div>
          
          <div style={{ marginBottom: 24, display: 'flex', gap: 12 }}>
            <select 
              className="input" 
              style={{ flexGrow: 1, padding: '14px 16px', background: 'var(--bg-1)', color: 'var(--ink-1)', border: '1px solid var(--line)' }}
              value={caseId} 
              onChange={(e) => {
                setCaseId(e.target.value);
              }}
            >
              <option value="" disabled style={{ color: '#888' }}>Search cases...</option>
              {(openCases.data?.items ?? []).map((c: any) => (
                <option key={c.case_id} value={c.case_id} style={{ color: '#000' }}>
                  {c.case_id} - ₹{c.amount_at_risk}
                </option>
              ))}
            </select>
            <button className="btn" style={{ background: 'var(--money)', color: 'var(--bg-0)', fontWeight: 600, border: 'none', padding: '0 24px' }} onClick={() => setCheckCase(caseId)} disabled={!caseId}>Check</button>
          </div>
          
          {checkCase.length >= 8 && (
            <QueryState q={check}>
              {(ck) => (
                <div style={{ overflow: 'hidden', marginBottom: 32, border: '1px solid var(--line)', borderRadius: 'var(--radius)' }}>
                  <table className="data-table" style={{ background: 'transparent' }}>
                    <thead style={{ background: 'var(--bg-1)' }}>
                      <tr>
                        <th style={{ color: 'var(--ink-3)', borderBottom: '1px solid var(--line)' }}>ACTION</th>
                        <th style={{ color: 'var(--ink-3)', borderBottom: '1px solid var(--line)' }}>PERMITTED NOW?</th>
                        <th style={{ color: 'var(--ink-3)', borderBottom: '1px solid var(--line)' }}>RULE REASON</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ck.results.map((r: any) => (
                        <tr key={r.candidate}>
                          <td style={{ fontWeight: 500, fontSize: 13, color: 'var(--ink-1)', borderBottom: '1px solid var(--line)' }}>{r.candidate.split('@')[0]}</td>
                          <td style={{ borderBottom: '1px solid var(--line)' }}>
                            <span className={`chip ${r.allowed ? "good" : "bad"}`} style={{ background: r.allowed ? 'rgba(111, 191, 143, 0.1)' : 'rgba(224, 122, 107, 0.1)', color: r.allowed ? 'var(--good)' : 'var(--bad)', border: `1px solid ${r.allowed ? 'rgba(111, 191, 143, 0.2)' : 'rgba(224, 122, 107, 0.2)'}` }}>{r.allowed ? "yes" : "no"}</span>
                          </td>
                          <td className="text-ink-3" style={{ fontSize: 13, borderBottom: '1px solid var(--line)' }}>{r.reasons?.[0] ?? r.rule_ids?.join(" · ") ?? "legal"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </QueryState>
          )}
          
          <div style={{ marginTop: 'auto' }}>
            <QueryState q={cons}>
              {(c) => (<>
                <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius)', border: '1px solid var(--line-side)' }}>
                  <div className="eyebrow" style={{ color: 'var(--ink-side-2)', marginBottom: 16 }}>Global Constraint Engine Rules</div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <span className="chip info">retries ≤ 1+3 / case</span>
                    <span className="chip info">contacts ≤ 2 / case</span>
                    <span className="chip info">quiet 21:00–08:00 IST</span>
                    <span className="chip info">cap ₹15,000</span>
                    <span className="chip info">legal windows W08–W21</span>
                    <span className="chip info">cooldown 20h</span>
                  </div>
                  <div className="text-ink-side-2" style={{ marginTop: 20, lineHeight: 1.6, fontSize: 13 }}>
                    <span style={{ color: 'var(--ink-side-1)', fontWeight: 600 }}>{c.rule_packs.length} active rule packs.</span> Every decision journals the pack it ran under. Violations are structurally impossible — the engine denies, the gateway re-verifies.
                  </div>
                </div>
              </>)}
            </QueryState>
          </div>
        </div>

        {/* ---------------- RIGHT: REFERENCE GUIDANCE ---------------- */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: 32 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 8 }}>
              <h2 className="section-title" style={{ color: 'var(--money)', margin: 0, fontSize: 13, letterSpacing: '0.05em' }}>EXPLAINS</h2>
              <div className="text-ink-1" style={{ fontSize: 20, fontWeight: 600 }}>Reference guidance - why the practices exist</div>
            </div>
          </div>
          
          <div style={{ marginBottom: 32, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {["Quiet hours", "Mandate pause", "Cooldowns", "Contact limits", "Escalation policy", "PSP reasons"].map(topic => (
              <button
                key={topic}
                className={`btn ${submitted === topic.toLowerCase() ? 'primary' : ''}`}
                onClick={() => setSubmitted(topic.toLowerCase())}
              >
                {topic}
              </button>
            ))}
          </div>
          
          {submitted.length >= 2 && (
            <QueryState q={search}>
              {(s) => {
                if (s.results.length === 0) {
                  return <div className="state-empty" style={{ background: 'transparent', border: '1px dashed var(--line)' }}>No reference guidance found for "{submitted}".</div>;
                }
                
                function parseGuidance(content: string) {
                  let cleaned = content;
                  cleaned = cleaned.replace(/#+\s+Revenue Recovery Reference Guidance\s*#*/gi, '').trim();
                  
                  let title = "Guidance";
                  const titleMatch = cleaned.match(/^#+\s+(.+)$/m);
                  if (titleMatch) {
                    title = titleMatch[1].trim();
                    cleaned = cleaned.replace(titleMatch[0], '').trim();
                  }
                  
                  cleaned = cleaned.replace(/^#+\s+/gm, '');
                  return { title, body: cleaned };
                }

                const parsed = s.results.map((r: any) => ({ ...r, ...parseGuidance(r.content) }));
                const uniqueResults = [];
                const seen = new Set();
                for (const r of parsed) {
                  if (!seen.has(r.body)) {
                    seen.add(r.body);
                    uniqueResults.push(r);
                  }
                }

                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {uniqueResults.map((r: any, i: number) => (
                      <GuidanceItem key={i} result={r} />
                    ))}
                  </div>
                );
              }}
            </QueryState>
          )}
          
        </div>
      </div>
    </div>
  );
}

function GuidanceItem({ result }: { result: any }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = result.body.length > 200;
  const displayBody = expanded ? result.body : (isLong ? result.body.slice(0, 200) + '...' : result.body);

  return (
    <div style={{ padding: '24px 0', borderBottom: '1px solid var(--line)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', marginBottom: 12 }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink-1)', marginBottom: 4 }}>
          {result.title}
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Reference guidance
        </div>
      </div>
      
      <div className="text-ink-2" style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap', maxWidth: '600px' }}>
        {displayBody}
      </div>
      
      {isLong && !expanded && (
        <button 
          className="btn" 
          style={{ background: 'transparent', padding: 0, marginTop: 12, color: 'var(--money)', fontWeight: 600, border: 'none', cursor: 'pointer' }} 
          onClick={() => setExpanded(true)}
        >
          Read full guidance ↓
        </button>
      )}
      
      <div style={{ marginTop: 24, fontSize: 12, color: 'var(--ink-3)' }}>
        Source: {result.source.replace(".md", "").replaceAll("_", " ")}
      </div>
    </div>
  );
}
