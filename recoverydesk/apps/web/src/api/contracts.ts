/** Read models from apps/api/main.py. Domain records are displayed without recomputing decisions. */
export interface CaseRow {
  case_id: string;
  state: string;
  failure_class: string;
  rail: string;
  amount_at_risk: number;
  retries_used: number;
  contacts_sent: number;
  opened_ts: string;
  close_ts: string | null;
  policy_id: string;
}
export interface CaseDetail extends CaseRow {
  subscription: Record<string, unknown> | null;
  attempts: Record<string, unknown>[];
  customer_opted_out: boolean;
  timeline: Record<string, unknown>[];
}
export interface CandidateRecord {
  candidate_id: string;
  action_type: string;
  window_code?: string;
  channel?: string;
  verdict: { allowed: boolean; reasons: string[]; rule_ids: string[] };
  p_hat: number | null;
  ev_inr: number | null;
  ev_components: Record<string, number> | null;
  feature_row: Record<string, unknown> | null;
}
export interface DecisionRecord {
  decision_id: string;
  decision_seq: number;
  taken_at: string;
  candidates: CandidateRecord[];
  chosen: Record<string, unknown>;
  model: Record<string, unknown>;
  rule_pack: Record<string, unknown>;
  fallback: boolean;
}
export interface EventRecord {
  event_id: string;
  case_id?: string;
  case_seq: number;
  event_type: string;
  occurred_at: string;
  actor: string;
  payload: Record<string, unknown>;
}
export interface Page<T> {
  items: T[];
  total?: number;
  env?: string;
}
export interface Outcomes {
  recovered_inr: number;
  at_risk_inr: number;
  cases_total: number;
  recovery_rate: number;
  cases_by_state: Record<string, number>;
  compliance: Record<string, number>;
  by_failure_class: Record<
    string,
    { n: number; rec: number; inr: number; rec_inr: number }
  >;
  by_rail: Record<
    string,
    { n: number; rec: number; inr: number; rec_inr: number }
  >;
  timing: Record<string, number>;
  action_mix: Record<string, number>;
  avg_time_to_recover_h: number | null;
}
export interface Baselines {
  methodology: string;
  population: { cases: number; at_risk_inr: number };
  baselines: Record<
    string,
    {
      recovered_inr: number;
      recovery_rate: number;
      attempts: number;
      contacts: number;
    }
  >;
  recoverydesk: { recovered_inr: number; recovery_rate: number };
}
