import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { QueryState, EvidenceDrawer } from "../components/ui";

const GROUPS = [
  { key: "", label: "All Events" },
  { key: "decision", label: "Decisions" },
  { key: "intervention_executed", label: "Execution" },
  { key: "attempt", label: "Attempts" },
  { key: "case_", label: "State changes" },
  { key: "notification", label: "Contact" },
  { key: "blocked", label: "Refusals" },
];

function humanEvent(e: string): string {
  if (e === "decision_made") return "Recovery option selected";
  if (e === "candidate_blocked") return "Recovery option not available";
  if (e === "intervention_proposed") return "Recovery option considered";
  if (e === "intervention_executed") return "Recovery action dispatched";
  if (e === "payment_failed") return "Payment failed";
  if (e === "attempt_succeeded") return "Payment recovered";
  if (e === "attempt_failed") return "Payment declined";
  if (e === "case_opened") return "Case opened";
  if (e === "case_recovered") return "Case recovered";
  if (e === "case_stopped") return "Case stopped";
  if (e === "case_escalated") return "Case escalated";
  if (e === "notification_sent") return "Customer notified";
  if (e === "customer_responded") return "Customer responded";
  return e.replaceAll("_", " ");
}

function resultFor(e: any): { text: string; cls: string; color: string; glow: string } {
  if (e.event_type.includes("recovered") || e.event_type.includes("succeeded")) return { text: "Recovered", cls: "good", color: "var(--good)", glow: '0 0 10px rgba(46, 139, 112, 0.4)' };
  if (e.event_type.includes("blocked")) return { text: "Refused", cls: "bad", color: "var(--bad)", glow: '0 0 10px rgba(199, 91, 91, 0.4)' };
  if (e.event_type.includes("failed")) return { text: "Failed", cls: "bad", color: "var(--bad)", glow: '0 0 10px rgba(199, 91, 91, 0.4)' };
  if (e.event_type.includes("stopped")) return { text: "Stopped", cls: "", color: "var(--ink-2)", glow: 'none' };
  if (e.event_type.includes("escalated")) return { text: "Escalated", cls: "warn", color: "var(--warn)", glow: 'none' };
  if (e.event_type.includes("decision")) return { text: "Selected", cls: "info", color: "var(--money)", glow: 'none' };
  if (e.event_type.includes("executed") || e.event_type.includes("notification")) return { text: "Dispatched", cls: "info", color: "var(--money)", glow: 'none' };
  return { text: "Recorded", cls: "", color: "var(--ink-3)", glow: 'none' };
}

function actionFor(e: any): string {
  switch (e.event_type) {
    case "decision_made":
    case "candidate_blocked":
    case "intervention_executed":
      return e.payload?.candidate_id || e.payload?.action_type || "—";
    case "attempt_succeeded":
    case "attempt_failed":
    case "payment_failed":
      return e.payload?.window_code ? `Window ${e.payload.window_code}` : "—";
    case "notification_sent":
      return e.payload?.channel ? `${e.payload.channel} reminder` : "—";
    default:
      return "—";
  }
}

export default function Audit() {
  const [g, setG] = useState("");
  const [q, setQ] = useState("");
  const events = useQuery({
    queryKey: ["events", "audit"],
    queryFn: () => api("/api/events?limit=200" as "/api/events"),
    refetchInterval: 5_000,
  });

  const matchGroup = (group: string, eventType: string) => {
    if (!group) return true;
    return eventType.includes(group);
  };

  const rows = useMemo(() => {
    const items = events.data?.items ?? [];
    const f = q.toLowerCase();
    return items.filter((e) =>
      matchGroup(g, e.event_type) &&
      (!f || e.event_type.toLowerCase().includes(f) || e.case_id.toLowerCase().includes(f)));
  }, [events.data, g, q]);

  return (
    <div className="page-with-hero">
      <div className="page-hero-bg hero-audit" />
      <div className="page-header" style={{ marginBottom: 48 }}>
        <h1 style={{ fontSize: 32, marginBottom: 12 }}>Audit Journal</h1>
        <p style={{ color: 'var(--ink-2)', fontSize: 15 }}>A strictly ordered, immutable timeline of every system action recorded with verifiable logic traces.</p>
      </div>
      
      <div style={{ display: 'flex', gap: 16, borderBottom: '1px solid var(--line)', paddingBottom: 24, marginBottom: 24, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {GROUPS.map((x) => (
            <button key={x.key} className="btn" style={{ 
              background: g === x.key ? 'rgba(232, 183, 92, 0.1)' : 'transparent', 
              color: g === x.key ? 'var(--money)' : 'var(--ink-2)', 
              border: g === x.key ? '1px solid var(--money)' : '1px solid var(--line)',
              fontWeight: 500
            }}
              onClick={() => setG(x.key)}>{x.label}</button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 'var(--radius)', padding: '0 16px' }}>
          <span style={{ color: 'var(--ink-3)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </span>
          <input className="input" style={{ width: 280, border: 'none', background: 'transparent', boxShadow: 'none' }} placeholder="Search the journal by event or case ID..." value={q}
            onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

        <QueryState q={events} empty={(x) => x.items.length === 0}>
          {() => (
            rows.length === 0 ? (
              <div className="state-empty" style={{ paddingTop: 80, paddingBottom: 80, background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 'var(--radius)' }}>
                No events found matching this criteria.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {rows.map((e) => {
                  const r = resultFor(e);
                  const isRed = r.text === "Refused" || r.text === "Failed";
                  const isGreen = r.text === "Recovered";
                  
                  return (
                    <div key={e.event_id} style={{ display: 'grid', gridTemplateColumns: '180px 1fr max-content', gap: 24, padding: '24px', border: '1px solid var(--line)', borderRadius: 'var(--radius)', background: 'var(--bg-1)', position: 'relative', overflow: 'hidden' }} className="hover-bg-0">
                      
                      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, background: r.color, opacity: 0.6 }} />

                      <div className="text-ink-3" style={{ fontSize: 13, fontWeight: 500, paddingLeft: 12 }}>
                        {new Date(e.occurred_at).toLocaleString("en-US", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: true })}
                      </div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
                        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                          <div style={{ fontWeight: 600, color: 'var(--ink-1)', fontSize: 16 }}>
                            {humanEvent(e.event_type)}
                          </div>
                        </div>
                        <div className="text-ink-2" style={{ fontSize: 14, lineHeight: 1.5 }}>
                          {actionFor(e) !== "—" ? `${actionFor(e).replaceAll("_", " ")} was recorded.` : "System state advanced."}
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <Link to={`/cases/${e.case_id}`} className="mono text-info hover-underline" style={{ fontSize: 13, letterSpacing: '0.05em' }}>
                            Case {e.case_id}
                          </Link>
                        </div>

                        {/* Evidence Drawer */}
                        <div style={{ marginTop: 16 }}>
                          <EvidenceDrawer 
                            title="VIEW TECHNICAL EVIDENCE"
                            record={{
                              "Event ID": e.event_id,
                              "Type": e.event_type,
                              "Occurred": e.occurred_at,
                              "Target Case": e.case_id
                            }}
                            payload={e.payload}
                          />
                        </div>
                      </div>

                      <div>
                        <span style={{ padding: '6px 12px', fontSize: 12, fontWeight: 600, borderRadius: 20, border: `1px solid ${isRed ? 'rgba(199, 91, 91, 0.2)' : (isGreen ? 'rgba(46, 139, 112, 0.2)' : 'var(--line)')}`, color: isRed ? 'var(--bad)' : (isGreen ? 'var(--good)' : 'var(--ink-2)'), background: isRed ? 'rgba(199, 91, 91, 0.05)' : (isGreen ? 'rgba(46, 139, 112, 0.05)' : 'transparent'), letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                          {r.text}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          )}
        </QueryState>

    </div>
  );
}
