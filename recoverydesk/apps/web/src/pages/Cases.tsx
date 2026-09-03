import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { QueryState, StateChip, inr, classHuman, railHuman, ago } from "../components/ui";

function BudgetBlocks({ used, max }: { used: number, max: number }) {
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {Array.from({ length: max }).map((_, i) => (
        <div key={i} style={{ 
          width: 8, 
          height: 12, 
          background: i < used ? 'var(--ink-2)' : 'rgba(148, 163, 184, 0.15)'
        }} />
      ))}
    </div>
  );
}

const STATES = ["", "OPEN_DECISION", "ACTION_PENDING", "AWAITING_CUSTOMER", "WAITING", "ESCALATED", "RECOVERED", "STOPPED"];
const RAILS = ["", "upi_autopay", "card_si"];
const FAILURE_CLASSES = ["", "INSUFFICIENT_FUNDS", "BANK_TECHNICAL", "MANDATE_CLOSED", "RATE_LIMIT", "MANDATE_PAUSED"];

export default function Cases() {
  const nav = useNavigate();
  const [state, setState] = useState("");
  const [rail, setRail] = useState("");
  const [failureClass, setFailureClass] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const limit = 25;

  const query = useQuery({
    queryKey: ["cases", state, rail, failureClass, page, q],
    queryFn: async () => {
      const p = new URLSearchParams({ limit: String(limit), offset: String(page * limit) });
      if (state) p.set("state", state);
      if (rail) p.set("rail", rail);
      if (failureClass) p.set("failure_class", failureClass);
      if (q) p.set("q", q);
      return api(`/api/cases?${p.toString()}` as "/api/cases");
    },
    refetchInterval: 5_000,
  });

  const hasFilters = state !== "" || rail !== "" || failureClass !== "" || q !== "";
  const cases = query.data?.items ?? [];

  return (
    <div className="page-with-hero">
      <div className="page-hero-bg hero-cases" />
      <div className="page-header">
        <div className="eyebrow" style={{ marginBottom: 12, color: 'var(--ink-3)' }}>Working queue</div>
        <h1 style={{ fontSize: 32, marginBottom: 12 }}>Recovery cases</h1>
        <p style={{ color: 'var(--ink-2)', fontSize: 15 }}>Prioritized queue of failed recurring payments. Organized by money at risk and time elapsed.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {/* OPERATIONAL FILTERING BAR */}
        <div className="card" style={{ padding: '16px 24px', display: "flex", gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 24 }}>
          <input className="input" style={{ flexGrow: 1, minWidth: 280 }} placeholder="Search by customer, reference, bank or reason..."
            value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
            
          <select className="input" style={{ width: 180 }} value={state} onChange={(e) => { setState(e.target.value); setPage(0); }}>
            <option value="">All states</option>
            {STATES.filter(s => s).map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
          </select>
          
          <select className="input" style={{ width: 180 }} value={failureClass} onChange={(e) => { setFailureClass(e.target.value); setPage(0); }}>
            <option value="">All reasons</option>
            {FAILURE_CLASSES.filter(s => s).map((s) => <option key={s} value={s}>{classHuman(s)}</option>)}
          </select>
          
          <select className="input" style={{ width: 140 }} value={rail} onChange={(e) => { setRail(e.target.value); setPage(0); }}>
            <option value="">All rails</option>
            {RAILS.filter(r => r).map((s) => <option key={s} value={s}>{railHuman(s)}</option>)}
          </select>
          
          {hasFilters && (
            <button className="btn" style={{ minWidth: 80 }} onClick={() => { setQ(""); setState(""); setFailureClass(""); setRail(""); setPage(0); }}>Clear filters</button>
          )}
        </div>
        
        <div className="flex-between" style={{ paddingBottom: 16 }}>
          <div className="eyebrow text-info">
            {cases.length > 0 ? `Showing ${page * limit + 1} - ${Math.min((page + 1) * limit, query.data?.total ?? 0)} of ${query.data?.total ?? 0} cases` : ''}
          </div>
          <div className="eyebrow text-info" style={{ display: 'flex', gap: 16 }}>
            <span>VALUE IN VIEW: {inr(query.data?.items.reduce((s:number,c:any)=>s+c.amount_at_risk, 0) || 0)}</span>
          </div>
        </div>

        <QueryState q={query}>
          {(d) => {
            if (cases.length === 0) {
              return (
                <div className="state-empty" style={{ paddingTop: 80, paddingBottom: 80, background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 'var(--radius)' }}>
                  {hasFilters ? "No recovery cases match these specific filters." : "No failed payments in the system."}
                </div>
              );
            }
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {cases.map((c: any) => (
                  <div key={c.case_id} onClick={() => nav(`/cases/${c.case_id}`)} 
                       style={{ cursor: 'pointer', display: 'grid', gridTemplateColumns: '200px 1fr max-content', gap: 32, padding: '24px', border: '1px solid var(--line)', borderRadius: 'var(--radius)', background: 'var(--bg-1)', transition: 'all 0.2s ease', position: 'relative', overflow: 'hidden' }} 
                       className="hover-bg-0 case-row">
                    
                    {/* State Edge Highlight */}
                    <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, background: c.state === 'RECOVERED' ? 'var(--good)' : (c.state === 'ESCALATED' ? 'var(--warn)' : (c.state === 'STOPPED' ? 'var(--bad)' : 'var(--info)')), opacity: 0.6 }} />

                    <div style={{ paddingLeft: 12 }}>
                      <div className="eyebrow" style={{ color: 'var(--ink-3)', marginBottom: 8, display: 'block' }}>Money at risk</div>
                      <div className="num-display" style={{ fontSize: 24 }}>{inr(c.amount_at_risk)}</div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <BudgetBlocks used={c.retries_used} max={3} />
                          <span className="text-ink3" style={{ fontSize: 13, fontWeight: 500 }}>retries {c.retries_used}/3</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <BudgetBlocks used={c.contacts_sent} max={2} />
                          <span className="text-ink3" style={{ fontSize: 13, fontWeight: 500 }}>contacts {c.contacts_sent}/2</span>
                        </div>
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--ink-1)', fontSize: 16, marginBottom: 8 }}>{classHuman(c.failure_class)}</div>
                        <div className="text-ink3" style={{ fontSize: 13, display: 'flex', gap: 12, alignItems: 'center' }}>
                          <span className="chip" style={{ padding: '4px 8px', fontSize: 11 }}>{railHuman(c.rail)}</span>
                          <span style={{ fontWeight: 500 }}>{c.bank || "Bank API"}</span>
                          <span>&middot;</span>
                          <span style={{ color: 'var(--ink-1)', fontWeight: 500 }}>{c.customer?.name || "Customer Account"}</span>
                          <span>&middot;</span>
                          <span className="mono">{c.case_id.split("-")[0]}</span>
                        </div>
                      </div>
                      
                      <div style={{ marginTop: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
                        <StateChip state={c.state} />
                        <span className="text-ink3" style={{ fontSize: 13 }}>{c.state === 'RECOVERED' ? 'Successfully closed' : (c.state === 'STOPPED' ? 'Abandoned' : (c.state === 'ESCALATED' ? 'Transferred to human operator' : 'In automated recovery flow'))}</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', justifyContent: 'space-between' }}>
                      <div className="text-ink3" style={{ fontSize: 13, fontWeight: 500 }}>
                        failed {ago(c.opened_ts)}
                      </div>
                      <div className="text-info" style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
                        View details <span style={{ fontSize: 16 }}>→</span>
                      </div>
                    </div>

                  </div>
                ))}
              </div>
            );
          }}
        </QueryState>

        <div style={{ padding: '24px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
          <button className="btn" disabled={page === 0} onClick={() => { setPage((p) => Math.max(0, p - 1)); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>← Newer</button>
          <span className="eyebrow" style={{ color: 'var(--ink-3)' }}>
            Page {page + 1}
          </span>
          <button className="btn" disabled={(query.data?.items.length ?? 0) < limit || (page + 1) * limit >= (query.data?.total ?? 0)}
            onClick={() => { setPage((p) => p + 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Older →</button>
        </div>
      </div>
    </div>
  );
}
