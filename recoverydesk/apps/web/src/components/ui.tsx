import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

export function QueryState<T>({ q, children, empty }: {
  q: UseQueryResult<T>; children: (data: T) => ReactNode; empty?: (data: T) => boolean;
}) {
  if (q.isPending) return <div className="state-loading"><span className="spin" /> Loading…</div>;
  if (q.isError) return <div className="state-error">
    Unable to load — {String(q.error.message)}. Retrying automatically.</div>;
  if (empty?.(q.data)) return <div className="state-empty">No data available yet.</div>;
  return <>{children(q.data)}</>;
}

/* ---- State vocabulary: At risk / Recovering / Recovered / Stopped / Escalated ---- */
const STATE_DISPLAY: Record<string, { label: string; cls: string }> = {
  RECOVERED: { label: "Recovered", cls: "good" },
  STOPPED: { label: "Stopped", cls: "" },
  ESCALATED: { label: "Escalated", cls: "bad" },
  AWAITING_CUSTOMER: { label: "Awaiting", cls: "warn" },
  ACTION_PENDING: { label: "Recovering", cls: "info" },
  OPEN_DECISION: { label: "At risk", cls: "warn" },
  WAITING: { label: "Recovering", cls: "info" },
  CASE_CREATED: { label: "At risk", cls: "warn" },
};
export function StateChip({ state }: { state: string }) {
  const d = STATE_DISPLAY[state] ?? { label: state.replaceAll("_", " ").toLowerCase(), cls: "" };
  return <span className={`chip ${d.cls}`.trim()}>{d.label}</span>;
}

/* ---- Human language for failure classes ---- */
const CLASS_HUMAN: Record<string, string> = {
  INSUFFICIENT_FUNDS: "Insufficient funds",
  BANK_TECHNICAL: "Bank technical failure",
  MANDATE_PAUSED: "Mandate paused",
  MANDATE_CLOSED: "Mandate revoked",
  CARD_EXPIRED: "Card expired",
  CARD_LOST_STOLEN: "Card lost / stolen",
  RATE_LIMIT: "PSP rate limit",
  UNMAPPED: "Unclassified failure",
};
export const classHuman = (c: string) => CLASS_HUMAN[c] ?? c.replaceAll("_", " ").toLowerCase();

/* ---- Policy display ---- */
const POLICY_HUMAN: Record<string, string> = {
  "ml-ev-v1": "Recovery model",
  "doctrine-b2": "Timing playbook",
};
export const policyHuman = (p: string | null | undefined) =>
  p ? (POLICY_HUMAN[p] ?? p) : "—";

/* ---- Action display ---- */
const ACTION_HUMAN: Record<string, string> = {
  RETRY_AT_WINDOW: "Retry during permitted window",
  SEND_REMINDER: "Send payment reminder",
  SEND_PAYMENT_LINK: "Send payment link",
  REQUEST_PM_UPDATE: "Request payment method update",
  WAIT_UNTIL: "Wait for better moment",
  STOP_CASE: "Stop recovery",
  ESCALATE_TO_HUMAN: "Escalate to human review",
};
export const actionHuman = (a: string) => ACTION_HUMAN[a] ?? a.replaceAll("_", " ").toLowerCase();

/* ---- Rail display ---- */
export const RAIL_HUMAN: Record<string, string> = {
  upi_autopay: "UPI Autopay", card_si: "Card e-mandate",
};
export const railHuman = (r: string) => RAIL_HUMAN[r] ?? r;

/* ---- Formatters ---- */
export const inr = (n: number | null | undefined) =>
  n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`;

export const pct = (x: number | null | undefined) =>
  x == null ? "—" : `${(x * 100).toFixed(1)}%`;

export const ago = (iso: string) => {
  const s = (Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 1000;
  if (!isFinite(s)) return iso.slice(0, 16).replace("T", " ");
  if (s < 90) return `${Math.max(1, Math.round(s))}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400 * 2) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};

export const at = (iso: string | null | undefined) =>
  iso ? iso.slice(0, 19).replace("T", " ") + " UTC" : "—";

/* ---- Evidence Drawer (D.3 Two-Level Disclosure) ---- */
export function EvidenceDrawer({ title, record, payload }: {
  title: string;
  record: Record<string, string | number | null | undefined>;
  payload: any;
}) {
  return (
    <details className="evidence-drawer">
      <summary>{title}</summary>
      <div className="evidence-content">
        <div className="evidence-grid">
          {Object.entries(record).map(([k, v]) => (
            v !== undefined && (
              <div key={k} style={{ display: 'contents' }}>
                <div className="evidence-key">{k}</div>
                <div className="evidence-value">{v == null ? "null" : String(v)}</div>
              </div>
            )
          ))}
        </div>
        
        {payload && (
          <details style={{ marginTop: 24 }}>
            <summary className="eyebrow" style={{ cursor: 'pointer', padding: '8px 0', borderBottom: '1px dashed var(--line)' }}>
              Raw Payload
            </summary>
            <pre className="evidence-raw">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </details>
  );
}
