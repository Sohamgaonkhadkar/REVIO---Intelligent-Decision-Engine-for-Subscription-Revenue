export type Rail = "UPI AutoPay" | "Card SI";
export type CaseStatus =
  | "RECOVERED"
  | "ACTION PENDING"
  | "WAITING"
  | "ESCALATED"
  | "STOPPED";
export type FailureCode =
  | "INSUFFICIENT_FUNDS"
  | "MANDATE_REVOKED"
  | "CARD_EXPIRED"
  | "BANK_TIMEOUT"
  | "RATE_LIMIT"
  | "MANDATE_EXECUTION_FAILED"
  | "AUTHENTICATION_FAILED";
export type ActionId =
  | "retry_now"
  | "retry_next_window"
  | "send_reminder"
  | "payment_link"
  | "update_payment_method"
  | "wait"
  | "escalate"
  | "stop";

export interface ConstraintState {
  retriesUsed: number;
  maxRetries: number;
  contactsUsed: number;
  maxContacts: number;
  quietHours: boolean;
  mandateEligible: boolean;
  contactCooldown: boolean;
  railAvailable: boolean;
  killSwitch: boolean;
  optOut?: boolean;
}

export interface Candidate {
  id: ActionId;
  label: string;
  description: string;
  eligible: boolean;
  denial?: string;
  ruleRef?: string;
  probability?: number;
  cost: number;
  expectedValue?: number;
  selected: boolean;
}

export interface JournalEntry {
  id: string;
  at: string;
  stage:
    | "DETECT"
    | "CONSTRAIN"
    | "PREDICT"
    | "OPTIMIZE"
    | "EXECUTE"
    | "AUDIT"
    | "OUTCOME";
  type: string;
  summary: string;
  actor: string;
  refs: Record<string, string | number>;
}

export interface RecoveryCase {
  id: string;
  customerRef: string;
  subscription: string;
  amount: number;
  rail: Rail;
  failureCode: FailureCode;
  failureReason: string;
  status: CaseStatus;
  createdAt: string;
  updatedAt: string;
  recoveredAt?: string;
  recoveryHours?: number;
  nextActionAt?: string;
  constraints: ConstraintState;
  strategy: string;
  decisionId: string;
  modelVersion: string;
  selectedAction: ActionId;
  candidates: Candidate[];
  journal: JournalEntry[];
  featureEvidence: { label: string; value: string }[];
  outcomeNote: string;
}

interface Seed {
  id: string;
  customerRef: string;
  subscription: string;
  amount: number;
  rail: Rail;
  failureCode: FailureCode;
  status: CaseStatus;
  createdAt: string;
  updatedAt: string;
  recoveredAt?: string;
  recoveryHours?: number;
  nextActionAt?: string;
  retriesUsed?: number;
  contactsUsed?: number;
  quietHours?: boolean;
  mandateEligible?: boolean;
  contactCooldown?: boolean;
  railAvailable?: boolean;
  killSwitch?: boolean;
  optOut?: boolean;
  pRetry?: number;
  pReminder?: number;
  pLink?: number;
  pUpdate?: number;
  pWait?: number;
  pEscalate?: number;
  outcomeNote: string;
}

export const failureMeta: Record<
  FailureCode,
  { label: string; short: string; class: string }
> = {
  INSUFFICIENT_FUNDS: {
    label: "Insufficient account balance",
    short: "Insufficient funds",
    class: "Customer funds",
  },
  MANDATE_REVOKED: {
    label: "UPI AutoPay mandate revoked",
    short: "Mandate revoked",
    class: "Mandate",
  },
  CARD_EXPIRED: {
    label: "Card standing instruction expired",
    short: "Card expired",
    class: "Instrument",
  },
  BANK_TIMEOUT: {
    label: "Issuing bank response timed out",
    short: "Bank timeout",
    class: "Technical",
  },
  RATE_LIMIT: {
    label: "Provider retry rate limit reached",
    short: "Rate limit",
    class: "Operational",
  },
  MANDATE_EXECUTION_FAILED: {
    label: "AutoPay mandate execution failed",
    short: "Mandate execution",
    class: "Mandate",
  },
  AUTHENTICATION_FAILED: {
    label: "Card authentication was not completed",
    short: "Authentication failed",
    class: "Authentication",
  },
};

export const actionMeta: Record<
  ActionId,
  { label: string; description: string; cost: number }
> = {
  retry_now: {
    label: "Retry now",
    description: "Dispatch an immediate debit through the original mandate.",
    cost: 6,
  },
  retry_next_window: {
    label: "Retry next window",
    description: "Retry in the next permitted salary-cycle window.",
    cost: 6,
  },
  send_reminder: {
    label: "Send reminder",
    description: "Send one contextual repayment reminder.",
    cost: 1.4,
  },
  payment_link: {
    label: "Send payment link",
    description: "Offer a customer-initiated alternate payment path.",
    cost: 2.2,
  },
  update_payment_method: {
    label: "Request method update",
    description: "Ask the customer to repair the payment instrument.",
    cost: 1.8,
  },
  wait: {
    label: "Wait & observe",
    description: "Make no contact or debit; re-evaluate next cycle.",
    cost: 0,
  },
  escalate: {
    label: "Human review",
    description: "Route to a recovery operator with full evidence.",
    cost: 450,
  },
  stop: {
    label: "Stop recovery",
    description: "Close automated intervention without another attempt.",
    cost: 0,
  },
};

const seeds: Seed[] = [
  {
    id: "RV-260618-0471",
    customerRef: "CUS-SIM-8F21",
    subscription: "Annual intelligence plan",
    amount: 2999,
    rail: "UPI AutoPay",
    failureCode: "INSUFFICIENT_FUNDS",
    status: "RECOVERED",
    createdAt: "2026-06-17T21:18:00+05:30",
    updatedAt: "2026-06-18T09:12:00+05:30",
    recoveredAt: "2026-06-18T09:12:00+05:30",
    recoveryHours: 11.9,
    retriesUsed: 1,
    pRetry: 0.84,
    pReminder: 0.47,
    pLink: 0.39,
    pUpdate: 0.12,
    pWait: 0.09,
    quietHours: true,
    outcomeNote:
      "The 09:00 IST window retry succeeded after the original 21:18 debit failed. No customer contact was consumed.",
  },
  {
    id: "RV-260618-0468",
    customerRef: "CUS-SIM-1A90",
    subscription: "Team workspace · 12 seats",
    amount: 14999,
    rail: "UPI AutoPay",
    failureCode: "BANK_TIMEOUT",
    status: "ACTION PENDING",
    createdAt: "2026-06-18T13:42:00+05:30",
    updatedAt: "2026-06-18T14:28:00+05:30",
    nextActionAt: "2026-06-18T16:00:00+05:30",
    retriesUsed: 0,
    pRetry: 0.72,
    pReminder: 0.24,
    pLink: 0.31,
    pUpdate: 0.08,
    pWait: 0.18,
    outcomeNote:
      "A technical failure is indistinguishable from a successful upstream debit until reconciliation; the next retry is held for the 16:00 window.",
  },
  {
    id: "RV-260618-0462",
    customerRef: "CUS-SIM-77C2",
    subscription: "Professional annual plan",
    amount: 24999,
    rail: "Card SI",
    failureCode: "CARD_EXPIRED",
    status: "RECOVERED",
    createdAt: "2026-06-15T08:44:00+05:30",
    updatedAt: "2026-06-15T13:16:00+05:30",
    recoveredAt: "2026-06-15T13:16:00+05:30",
    recoveryHours: 4.53,
    retriesUsed: 0,
    contactsUsed: 1,
    mandateEligible: false,
    pRetry: 0.02,
    pReminder: 0.22,
    pLink: 0.34,
    pUpdate: 0.91,
    pWait: 0.02,
    outcomeNote:
      "An instrument-update request produced a new eligible card. The expired instrument was never retried.",
  },
  {
    id: "RV-260617-0455",
    customerRef: "CUS-SIM-31D4",
    subscription: "Business monthly plan",
    amount: 8999,
    rail: "UPI AutoPay",
    failureCode: "MANDATE_REVOKED",
    status: "ESCALATED",
    createdAt: "2026-06-17T10:05:00+05:30",
    updatedAt: "2026-06-18T11:40:00+05:30",
    retriesUsed: 0,
    contactsUsed: 2,
    mandateEligible: false,
    pRetry: 0.01,
    pReminder: 0.08,
    pLink: 0.16,
    pUpdate: 0.19,
    pWait: 0.01,
    pEscalate: 0.34,
    outcomeNote:
      "Both contacts are consumed and the mandate is revoked. Automated recovery is closed; a human reviewer owns the remaining decision.",
  },
  {
    id: "RV-260617-0449",
    customerRef: "CUS-SIM-0B65",
    subscription: "Usage commitment · June",
    amount: 12999,
    rail: "UPI AutoPay",
    failureCode: "INSUFFICIENT_FUNDS",
    status: "RECOVERED",
    createdAt: "2026-06-16T22:02:00+05:30",
    updatedAt: "2026-06-17T10:02:00+05:30",
    recoveredAt: "2026-06-17T10:02:00+05:30",
    recoveryHours: 12,
    retriesUsed: 1,
    contactsUsed: 1,
    quietHours: true,
    pRetry: 0.76,
    pReminder: 0.41,
    pLink: 0.58,
    pUpdate: 0.09,
    pWait: 0.12,
    outcomeNote:
      "A reminder alone did not resolve the balance shortfall. The permitted morning retry recovered the debit.",
  },
  {
    id: "RV-260616-0441",
    customerRef: "CUS-SIM-E21A",
    subscription: "Enterprise pilot · synthetic",
    amount: 29999,
    rail: "UPI AutoPay",
    failureCode: "BANK_TIMEOUT",
    status: "RECOVERED",
    createdAt: "2026-06-14T15:11:00+05:30",
    updatedAt: "2026-06-14T15:47:00+05:30",
    recoveredAt: "2026-06-14T15:47:00+05:30",
    recoveryHours: 0.6,
    retriesUsed: 0,
    pRetry: 0.88,
    pReminder: 0.17,
    pLink: 0.29,
    pUpdate: 0.04,
    pWait: 0.31,
    outcomeNote:
      "Reconciliation confirmed no successful upstream debit. A single constrained retry succeeded 36 minutes later.",
  },
  {
    id: "RV-260616-0438",
    customerRef: "CUS-SIM-62FE",
    subscription: "Creator annual plan",
    amount: 4999,
    rail: "Card SI",
    failureCode: "AUTHENTICATION_FAILED",
    status: "WAITING",
    createdAt: "2026-06-16T18:20:00+05:30",
    updatedAt: "2026-06-18T09:20:00+05:30",
    nextActionAt: "2026-06-19T09:20:00+05:30",
    retriesUsed: 1,
    contactsUsed: 1,
    contactCooldown: true,
    pRetry: 0.12,
    pReminder: 0.16,
    pLink: 0.49,
    pUpdate: 0.32,
    pWait: 0.21,
    outcomeNote:
      "Contact cooldown prevents another message. The case waits for customer authentication rather than spending a retry.",
  },
  {
    id: "RV-260615-0429",
    customerRef: "CUS-SIM-B840",
    subscription: "Team workspace · 4 seats",
    amount: 5999,
    rail: "Card SI",
    failureCode: "CARD_EXPIRED",
    status: "RECOVERED",
    createdAt: "2026-06-13T08:52:00+05:30",
    updatedAt: "2026-06-13T19:22:00+05:30",
    recoveredAt: "2026-06-13T19:22:00+05:30",
    recoveryHours: 10.5,
    retriesUsed: 0,
    contactsUsed: 1,
    mandateEligible: false,
    pRetry: 0.01,
    pReminder: 0.18,
    pLink: 0.41,
    pUpdate: 0.82,
    pWait: 0.03,
    outcomeNote:
      "The cardholder updated expiry details after one request; no blind retry was dispatched.",
  },
  {
    id: "RV-260615-0424",
    customerRef: "CUS-SIM-991C",
    subscription: "Data export add-on",
    amount: 2499,
    rail: "UPI AutoPay",
    failureCode: "RATE_LIMIT",
    status: "ACTION PENDING",
    createdAt: "2026-06-18T12:06:00+05:30",
    updatedAt: "2026-06-18T14:30:00+05:30",
    nextActionAt: "2026-06-18T15:30:00+05:30",
    retriesUsed: 2,
    railAvailable: false,
    pRetry: 0.66,
    pReminder: 0.21,
    pLink: 0.37,
    pUpdate: 0.07,
    pWait: 0.5,
    outcomeNote:
      "Provider capacity is temporarily exhausted. Waiting is selected; the gateway will re-evaluate rail availability before any future retry.",
  },
  {
    id: "RV-260614-0417",
    customerRef: "CUS-SIM-D320",
    subscription: "Professional monthly plan",
    amount: 1999,
    rail: "UPI AutoPay",
    failureCode: "MANDATE_EXECUTION_FAILED",
    status: "STOPPED",
    createdAt: "2026-06-12T11:34:00+05:30",
    updatedAt: "2026-06-14T11:34:00+05:30",
    retriesUsed: 3,
    contactsUsed: 2,
    mandateEligible: false,
    pRetry: 0.04,
    pReminder: 0.06,
    pLink: 0.11,
    pUpdate: 0.14,
    pWait: 0,
    pEscalate: 0.01,
    outcomeNote:
      "Retry and contact budgets are exhausted. Further intervention is prohibited; the simulated case is stopped.",
  },
  {
    id: "RV-260614-0411",
    customerRef: "CUS-SIM-40AB",
    subscription: "Annual storage plan",
    amount: 7499,
    rail: "UPI AutoPay",
    failureCode: "INSUFFICIENT_FUNDS",
    status: "RECOVERED",
    createdAt: "2026-06-11T21:46:00+05:30",
    updatedAt: "2026-06-12T08:16:00+05:30",
    recoveredAt: "2026-06-12T08:16:00+05:30",
    recoveryHours: 10.5,
    retriesUsed: 2,
    quietHours: true,
    pRetry: 0.79,
    pReminder: 0.36,
    pLink: 0.44,
    pUpdate: 0.08,
    pWait: 0.11,
    outcomeNote:
      "The second retry was deliberately deferred out of quiet hours and succeeded at 08:16 IST.",
  },
  {
    id: "RV-260613-0402",
    customerRef: "CUS-SIM-C518",
    subscription: "API scale plan",
    amount: 17999,
    rail: "UPI AutoPay",
    failureCode: "RATE_LIMIT",
    status: "WAITING",
    createdAt: "2026-06-18T13:58:00+05:30",
    updatedAt: "2026-06-18T14:29:00+05:30",
    nextActionAt: "2026-06-18T17:00:00+05:30",
    retriesUsed: 1,
    railAvailable: false,
    pRetry: 0.61,
    pReminder: 0.18,
    pLink: 0.27,
    pUpdate: 0.05,
    pWait: 0.36,
    outcomeNote:
      "A wait action currently dominates because intervention during provider throttling has no permissible execution path.",
  },
  {
    id: "RV-260613-0398",
    customerRef: "CUS-SIM-21F0",
    subscription: "Business annual plan",
    amount: 9999,
    rail: "UPI AutoPay",
    failureCode: "BANK_TIMEOUT",
    status: "RECOVERED",
    createdAt: "2026-06-10T14:09:00+05:30",
    updatedAt: "2026-06-10T16:31:00+05:30",
    recoveredAt: "2026-06-10T16:31:00+05:30",
    recoveryHours: 2.37,
    retriesUsed: 1,
    pRetry: 0.81,
    pReminder: 0.2,
    pLink: 0.33,
    pUpdate: 0.04,
    pWait: 0.29,
    outcomeNote:
      "The original debit remained unreconciled for one cycle; the second permitted attempt succeeded.",
  },
  {
    id: "RV-260612-0389",
    customerRef: "CUS-SIM-AB02",
    subscription: "Team workspace · 8 seats",
    amount: 8999,
    rail: "Card SI",
    failureCode: "AUTHENTICATION_FAILED",
    status: "ESCALATED",
    createdAt: "2026-06-16T09:14:00+05:30",
    updatedAt: "2026-06-18T12:44:00+05:30",
    retriesUsed: 3,
    contactsUsed: 2,
    pRetry: 0.07,
    pReminder: 0.05,
    pLink: 0.13,
    pUpdate: 0.22,
    pWait: 0.03,
    pEscalate: 0.41,
    outcomeNote:
      "Three failed attempts and two contacts leave no automated action. Human review is the only funded intervention.",
  },
  {
    id: "RV-260612-0381",
    customerRef: "CUS-SIM-5E72",
    subscription: "Annual intelligence plan",
    amount: 4999,
    rail: "UPI AutoPay",
    failureCode: "INSUFFICIENT_FUNDS",
    status: "RECOVERED",
    createdAt: "2026-06-09T22:15:00+05:30",
    updatedAt: "2026-06-10T10:15:00+05:30",
    recoveredAt: "2026-06-10T10:15:00+05:30",
    recoveryHours: 12,
    retriesUsed: 1,
    quietHours: true,
    pRetry: 0.73,
    pReminder: 0.43,
    pLink: 0.51,
    pUpdate: 0.06,
    pWait: 0.14,
    outcomeNote:
      "The next-morning retry led the eligible candidates and succeeded. Payment links were blocked by the quiet-hours snapshot.",
  },
  {
    id: "RV-260611-0374",
    customerRef: "CUS-SIM-734B",
    subscription: "Premium support add-on",
    amount: 6999,
    rail: "Card SI",
    failureCode: "BANK_TIMEOUT",
    status: "STOPPED",
    createdAt: "2026-06-08T16:40:00+05:30",
    updatedAt: "2026-06-11T16:40:00+05:30",
    retriesUsed: 3,
    contactsUsed: 1,
    optOut: true,
    pRetry: 0.01,
    pReminder: 0,
    pLink: 0,
    pUpdate: 0,
    pWait: 0,
    pEscalate: 0.01,
    outcomeNote:
      "The retry budget is exhausted and remaining scored interventions have negative expected value. Recovery stops rather than spending another contact.",
  },
  {
    id: "RV-260610-0366",
    customerRef: "CUS-SIM-0D19",
    subscription: "Business monthly plan",
    amount: 5999,
    rail: "UPI AutoPay",
    failureCode: "MANDATE_EXECUTION_FAILED",
    status: "RECOVERED",
    createdAt: "2026-06-08T08:58:00+05:30",
    updatedAt: "2026-06-09T12:24:00+05:30",
    recoveredAt: "2026-06-09T12:24:00+05:30",
    recoveryHours: 27.43,
    retriesUsed: 0,
    contactsUsed: 1,
    mandateEligible: false,
    pRetry: 0.03,
    pReminder: 0.18,
    pLink: 0.69,
    pUpdate: 0.74,
    pWait: 0.04,
    outcomeNote:
      "Mandate repair restored eligibility before the next scheduled debit; the original mandate was not retried.",
  },
  {
    id: "RV-260609-0358",
    customerRef: "CUS-SIM-F618",
    subscription: "Professional annual plan",
    amount: 14999,
    rail: "Card SI",
    failureCode: "CARD_EXPIRED",
    status: "WAITING",
    createdAt: "2026-06-17T20:12:00+05:30",
    updatedAt: "2026-06-18T08:12:00+05:30",
    nextActionAt: "2026-06-20T08:12:00+05:30",
    retriesUsed: 0,
    contactsUsed: 2,
    mandateEligible: false,
    pRetry: 0.01,
    pReminder: 0.07,
    pLink: 0.12,
    pUpdate: 0.26,
    pWait: 0.08,
    pEscalate: 0.01,
    outcomeNote:
      "The contact budget is exhausted. Waiting avoids a prohibited message while leaving the synthetic case open.",
  },
  {
    id: "RV-260608-0349",
    customerRef: "CUS-SIM-88A1",
    subscription: "Analytics add-on",
    amount: 3999,
    rail: "UPI AutoPay",
    failureCode: "INSUFFICIENT_FUNDS",
    status: "ACTION PENDING",
    createdAt: "2026-06-18T14:02:00+05:30",
    updatedAt: "2026-06-18T14:31:00+05:30",
    nextActionAt: "2026-06-18T18:00:00+05:30",
    retriesUsed: 0,
    pRetry: 0.68,
    pReminder: 0.39,
    pLink: 0.42,
    pUpdate: 0.05,
    pWait: 0.17,
    outcomeNote:
      "A permitted retry is queued for 18:00 IST. The gateway has not authorized it yet.",
  },
  {
    id: "RV-260607-0337",
    customerRef: "CUS-SIM-4C20",
    subscription: "Enterprise sandbox plan",
    amount: 11999,
    rail: "UPI AutoPay",
    failureCode: "MANDATE_REVOKED",
    status: "STOPPED",
    createdAt: "2026-06-07T12:22:00+05:30",
    updatedAt: "2026-06-09T12:22:00+05:30",
    retriesUsed: 0,
    contactsUsed: 2,
    mandateEligible: false,
    pRetry: 0.01,
    pReminder: 0.04,
    pLink: 0.09,
    pUpdate: 0.11,
    pWait: 0,
    pEscalate: 0.01,
    outcomeNote:
      "No consent-valid mandate remains and both contacts were used. REVIO stopped rather than continuing to message.",
  },
];

export function evaluateConstraints(
  action: ActionId,
  c: ConstraintState,
): { eligible: boolean; denial?: string; ruleRef?: string } {
  const retry = action === "retry_now" || action === "retry_next_window";
  const contact =
    action === "send_reminder" ||
    action === "payment_link" ||
    action === "update_payment_method";
  if (c.killSwitch && action !== "stop" && action !== "escalate")
    return {
      eligible: false,
      denial:
        "Operational kill switch is engaged; only stop or human review remain available.",
      ruleRef: "OPS-KILL-001",
    };
  if (retry && c.retriesUsed >= c.maxRetries)
    return {
      eligible: false,
      denial: `Retry budget exhausted: ${c.retriesUsed} of ${c.maxRetries} post-debit attempts used.`,
      ruleRef: "RETRY-MAX-003",
    };
  if (retry && !c.mandateEligible)
    return {
      eligible: false,
      denial:
        "The payment instrument or mandate is not eligible for another debit.",
      ruleRef: "MANDATE-ELIG-002",
    };
  if (action === "retry_now" && c.quietHours)
    return {
      eligible: false,
      denial: "Immediate retry falls inside quiet hours (21:00–08:00 IST).",
      ruleRef: "QUIET-IST-2108",
    };
  if (retry && !c.railAvailable)
    return {
      eligible: false,
      denial:
        "Payment rail is unavailable or throttled; no retry may be dispatched.",
      ruleRef: "OPS-RAIL-004",
    };
  if (action === "retry_now" && c.contactCooldown)
    return {
      eligible: false,
      denial:
        "A 24-hour intervention cooldown is active after the last attempt.",
      ruleRef: "COOLDOWN-024",
    };
  if (contact && c.optOut)
    return {
      eligible: false,
      denial: "The recorded customer preference opts out of recovery contact.",
      ruleRef: "CONTACT-OPTOUT-001",
    };
  if (contact && c.contactsUsed >= c.maxContacts)
    return {
      eligible: false,
      denial: `Contact budget exhausted: ${c.contactsUsed} of ${c.maxContacts} contacts used.`,
      ruleRef: "CONTACT-MAX-002",
    };
  if (contact && c.quietHours)
    return {
      eligible: false,
      denial:
        "Customer contact is prohibited during quiet hours (21:00–08:00 IST).",
      ruleRef: "QUIET-IST-2108",
    };
  if (contact && c.contactCooldown)
    return {
      eligible: false,
      denial:
        "Contact cooldown is active; re-evaluation is permitted after 24 hours.",
      ruleRef: "COOLDOWN-024",
    };
  return { eligible: true };
}

function probabilityFor(action: ActionId, seed: Seed) {
  if (action === "retry_now")
    return Math.max(0.01, (seed.pRetry ?? 0.55) - 0.12);
  if (action === "retry_next_window") return seed.pRetry ?? 0.55;
  if (action === "send_reminder") return seed.pReminder ?? 0.3;
  if (action === "payment_link") return seed.pLink ?? 0.35;
  if (action === "update_payment_method") return seed.pUpdate ?? 0.2;
  if (action === "wait") return seed.pWait ?? 0.1;
  if (action === "escalate") return seed.pEscalate ?? 0.26;
  return undefined;
}

function createCandidates(seed: Seed, c: ConstraintState): Candidate[] {
  const actions: ActionId[] = [
    "retry_now",
    "retry_next_window",
    "send_reminder",
    "payment_link",
    "update_payment_method",
    "wait",
    "escalate",
    "stop",
  ];
  const preliminary = actions.map((id) => {
    const constraint = evaluateConstraints(id, c);
    const p = constraint.eligible ? probabilityFor(id, seed) : undefined;
    const cost = actionMeta[id].cost;
    return {
      id,
      ...actionMeta[id],
      ...constraint,
      probability: p,
      cost,
      expectedValue: p === undefined ? undefined : p * seed.amount - cost,
      selected: false,
    };
  });
  const ranked = preliminary
    .filter((a) => a.expectedValue !== undefined)
    .sort((a, b) => (b.expectedValue ?? 0) - (a.expectedValue ?? 0));
  let selected = ranked[0]?.id ?? "stop";
  if (seed.status === "STOPPED") selected = "stop";
  if (seed.status === "ESCALATED") selected = "escalate";
  return preliminary.map((a) => ({ ...a, selected: a.id === selected }));
}

function isoAdd(iso: string, minutes: number) {
  return new Date(new Date(iso).getTime() + minutes * 60000).toISOString();
}

function createJournal(
  seed: Seed,
  candidates: Candidate[],
  selected: Candidate,
): JournalEntry[] {
  const base = seed.createdAt;
  const permitted = candidates.filter((c) => c.eligible);
  const blocked = candidates.filter((c) => !c.eligible);
  const noDispatch = selected.id === "wait" || selected.id === "stop";
  const queued = seed.status === "ACTION PENDING" && !noDispatch;
  const executionAt =
    seed.status === "RECOVERED" &&
    seed.quietHours &&
    selected.id === "retry_next_window"
      ? isoAdd(seed.recoveredAt ?? seed.updatedAt, -12)
      : isoAdd(base, 3);
  const common = {
    decision_id: `DEC-${seed.id.slice(3)}`,
    rule_pack: "rp_in_recurring_2026.06.3",
    model_version: "xgb-recovery-32f-v0.9.4",
  };
  const entries: JournalEntry[] = [
    {
      id: `JRN-${seed.id.slice(3)}-001`,
      at: base,
      stage: "DETECT",
      type: "payment.failed",
      summary: `${failureMeta[seed.failureCode].label}; ₹${seed.amount.toLocaleString("en-IN")} placed at risk.`,
      actor: "simulation.ingestor",
      refs: {
        ...common,
        payment_ref: `PAY-SIM-${seed.id.slice(-4)}`,
        rail: seed.rail,
        failure_code: seed.failureCode,
      },
    },
    {
      id: `JRN-${seed.id.slice(3)}-002`,
      at: isoAdd(base, 1),
      stage: "CONSTRAIN",
      type: "constraints.evaluated",
      summary: `${permitted.length} actions permitted; ${blocked.length} rejected before scoring.`,
      actor: "rules.engine",
      refs: {
        ...common,
        permitted: permitted.map((c) => c.id).join(", "),
        rejected: blocked.map((c) => c.ruleRef ?? c.id).join(", ") || "none",
      },
    },
    {
      id: `JRN-${seed.id.slice(3)}-003`,
      at: isoAdd(base, 2),
      stage: "PREDICT",
      type: "model.scored",
      summary: `${permitted.filter((c) => c.probability !== undefined).length} eligible actions scored with 32 features. Probabilities are uncalibrated.`,
      actor: "xgboost.inference",
      refs: {
        ...common,
        feature_schema: "recovery-features/v3",
        feature_count: 32,
        calibration_artifact: "absent",
      },
    },
    {
      id: `JRN-${seed.id.slice(3)}-004`,
      at: isoAdd(base, 2),
      stage: "OPTIMIZE",
      type: "economics.ranked",
      summary:
        selected.id === "stop"
          ? "Stop selected by terminal recovery policy after constraint and economic review."
          : `${selected.label} selected on highest expected value among permissible scored actions.`,
      actor: "decision.optimizer",
      refs: {
        ...common,
        selected_action: selected.id,
        expected_value_inr:
          selected.expectedValue === undefined
            ? "not_applicable"
            : Math.round(selected.expectedValue * 100) / 100,
        objective: "p_recovery × amount − intervention_cost",
      },
    },
    {
      id: `JRN-${seed.id.slice(3)}-005`,
      at: executionAt,
      stage: "EXECUTE",
      type: queued
        ? "action.queued"
        : selected.id === "wait"
          ? "action.deferred"
          : selected.id === "stop"
            ? "recovery.stopped"
            : "gateway.authorized",
      summary: queued
        ? "Action queued for a future window; gateway verification and dispatch remain pending."
        : selected.id === "wait"
          ? "No intervention dispatched; next evaluation retained."
          : selected.id === "stop"
            ? "Recovery stopped without further customer contact or debit."
            : `Gateway reverified ${selected.ruleRef ?? "active rule pack"} and dispatched ${selected.label}.`,
      actor: "execution.gateway",
      refs: {
        ...common,
        gateway_check: queued
          ? "pending_not_dispatched"
          : noDispatch
            ? "not_required_no_dispatch"
            : "passed",
        idempotency_key:
          queued || noDispatch ? "not_generated" : `SIM-${seed.id}-01`,
        dispatch: queued ? "none_pending_gateway" : selected.id,
      },
    },
  ];
  if (seed.status === "RECOVERED")
    entries.push({
      id: `JRN-${seed.id.slice(3)}-006`,
      at: seed.recoveredAt ?? seed.updatedAt,
      stage: "OUTCOME",
      type: "payment.recovered",
      summary: `Simulated recovery confirmed after ${seed.recoveryHours?.toFixed(1)} hours.`,
      actor: "simulation.outcomes",
      refs: {
        ...common,
        outcome: "recovered",
        amount_inr: seed.amount,
        recovery_hours: seed.recoveryHours ?? 0,
      },
    });
  else
    entries.push({
      id: `JRN-${seed.id.slice(3)}-006`,
      at: seed.updatedAt,
      stage: "AUDIT",
      type: "case.state_changed",
      summary: seed.outcomeNote,
      actor: "simulation.outcomes",
      refs: {
        ...common,
        outcome: seed.status.toLowerCase().replace(/ /g, "_"),
        journal_mode: "append_only",
        sequence: 6,
      },
    });
  return entries;
}

function hydrate(seed: Seed): RecoveryCase {
  const constraints: ConstraintState = {
    retriesUsed: seed.retriesUsed ?? 0,
    maxRetries: 3,
    contactsUsed: seed.contactsUsed ?? 0,
    maxContacts: 2,
    quietHours: seed.quietHours ?? false,
    mandateEligible: seed.mandateEligible ?? true,
    contactCooldown: seed.contactCooldown ?? false,
    railAvailable: seed.railAvailable ?? true,
    killSwitch: seed.killSwitch ?? false,
    optOut: seed.optOut ?? false,
  };
  const candidates = createCandidates(seed, constraints);
  const selected =
    candidates.find((c) => c.selected) ?? candidates[candidates.length - 1];
  return {
    ...seed,
    constraints,
    failureReason: failureMeta[seed.failureCode].label,
    strategy: selected.label,
    decisionId: `DEC-${seed.id.slice(3)}`,
    modelVersion: "xgb-recovery-32f-v0.9.4",
    candidates,
    selectedAction: selected.id,
    journal: createJournal(seed, candidates, selected),
    featureEvidence: [
      { label: "Failure class", value: failureMeta[seed.failureCode].class },
      { label: "Payment rail", value: seed.rail },
      {
        label: "Retry budget used",
        value: `${constraints.retriesUsed} / ${constraints.maxRetries}`,
      },
      {
        label: "Amount decile",
        value:
          seed.amount >= 10000
            ? "D09 · high value"
            : seed.amount >= 5000
              ? "D07 · mid value"
              : "D04 · standard",
      },
      {
        label: "Local failure hour",
        value:
          new Intl.DateTimeFormat("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "Asia/Kolkata",
            hour12: false,
          }).format(new Date(seed.createdAt)) + " IST",
      },
      {
        label: "Instrument eligibility",
        value: constraints.mandateEligible ? "Eligible" : "Ineligible",
      },
    ],
  };
}

export const cases: RecoveryCase[] = seeds.map(hydrate);

export const modelFeatures = [
  "amount_inr",
  "amount_log",
  "amount_decile",
  "rail_upi",
  "rail_card",
  "failure_funds",
  "failure_technical",
  "failure_mandate",
  "failure_instrument",
  "failure_auth",
  "failure_rate_limit",
  "retries_used",
  "retries_remaining",
  "contacts_used",
  "contacts_remaining",
  "mandate_eligible",
  "instrument_age_days",
  "subscription_age_days",
  "prior_success_count",
  "prior_failure_count",
  "prior_recovery_rate",
  "days_since_last_success",
  "failure_hour_ist",
  "failure_day_of_week",
  "salary_window_1_5",
  "salary_window_28_31",
  "quiet_hours_flag",
  "minutes_since_failure",
  "rail_health_score",
  "provider_latency_ms",
  "customer_contactable",
  "candidate_action_id",
];

export const simulationClock = "2026-06-18T14:32:00+05:30";

export interface BaselineRow {
  id: "B0" | "B1" | "B2" | "REVIO";
  name: string;
  description: string;
  recovered: number;
  cost: number;
  color: string;
}
export const baselineSegments: Record<"ALL" | Rail, BaselineRow[]> = {
  ALL: [
    {
      id: "B0",
      name: "No intervention",
      description: "Observe organic recovery only.",
      recovered: 41982,
      cost: 0,
      color: "#65706d",
    },
    {
      id: "B1",
      name: "Provider retries",
      description: "Standard provider retry schedule.",
      recovered: 98440,
      cost: 4820,
      color: "#9a927d",
    },
    {
      id: "B2",
      name: "Static rules",
      description: "Fixed rule-based recovery sequence.",
      recovered: 99870,
      cost: 2960,
      color: "#c7a96b",
    },
    {
      id: "REVIO",
      name: "Constrained decisions",
      description: "Per-case constrained EV optimization.",
      recovered: 105491,
      cost: 1184,
      color: "#54b894",
    },
  ],
  "UPI AutoPay": [
    {
      id: "B0",
      name: "No intervention",
      description: "Observe organic recovery only.",
      recovered: 31020,
      cost: 0,
      color: "#65706d",
    },
    {
      id: "B1",
      name: "Provider retries",
      description: "Standard provider retry schedule.",
      recovered: 68440,
      cost: 3040,
      color: "#9a927d",
    },
    {
      id: "B2",
      name: "Static rules",
      description: "Fixed rule-based recovery sequence.",
      recovered: 63870,
      cost: 1840,
      color: "#c7a96b",
    },
    {
      id: "REVIO",
      name: "Constrained decisions",
      description: "Per-case constrained EV optimization.",
      recovered: 74493,
      cost: 884,
      color: "#54b894",
    },
  ],
  "Card SI": [
    {
      id: "B0",
      name: "No intervention",
      description: "Observe organic recovery only.",
      recovered: 10962,
      cost: 0,
      color: "#65706d",
    },
    {
      id: "B1",
      name: "Provider retries",
      description: "Standard provider retry schedule.",
      recovered: 30000,
      cost: 1780,
      color: "#9a927d",
    },
    {
      id: "B2",
      name: "Static rules",
      description: "Fixed rule-based recovery sequence.",
      recovered: 36000,
      cost: 1120,
      color: "#c7a96b",
    },
    {
      id: "REVIO",
      name: "Constrained decisions",
      description: "Per-case constrained EV optimization.",
      recovered: 30998,
      cost: 300,
      color: "#54b894",
    },
  ],
};

export const referenceKnowledge = [
  {
    id: "KB-001",
    title: "Why insufficient-funds retries favor morning windows",
    category: "Recovery heuristics",
    body: "In this synthetic feature set, salary-cycle and local-hour features often raise the estimated success of a deferred retry. This is contextual evidence for analysts, not permission to debit. The rules engine must still admit the action.",
    refs: ["PREDICT", "OPTIMIZE"],
  },
  {
    id: "KB-002",
    title: "Mandate revocation versus execution failure",
    category: "UPI AutoPay",
    body: "A revoked mandate removes debit eligibility and calls for instrument repair or a customer-initiated path. An execution failure may be temporary, but it does not automatically establish that another attempt is lawful or operationally safe.",
    refs: ["CONSTRAIN", "MANDATE-ELIG-002"],
  },
  {
    id: "KB-003",
    title: "Reading an uncalibrated probability",
    category: "Model interpretation",
    body: "The score ranks candidate actions in a precomputed synthetic model snapshot. There is no calibration artifact attached to this fixture. It must not be presented as a calibrated real-world frequency. Expected values in this prototype are therefore illustrative model-based estimates.",
    refs: ["PREDICT", "MODEL-TRUST"],
  },
  {
    id: "KB-004",
    title: "Why a blocked action has no probability",
    category: "Decision audit",
    body: "Constraint evaluation precedes inference. Candidates rejected by retry budgets, quiet hours, cooldowns, or mandate eligibility never reach the model and therefore have no probability or expected value.",
    refs: ["CONSTRAIN", "AUDIT"],
  },
  {
    id: "KB-005",
    title: "Intervention costs are not only gateway fees",
    category: "Unit economics",
    body: "The synthetic cost model includes message and processing costs and a larger human-review cost. It does not claim to measure brand harm or real customer lifetime value.",
    refs: ["OPTIMIZE"],
  },
  {
    id: "KB-006",
    title: "Gateway reverification closes the decision gap",
    category: "Execution safety",
    body: "A mandate, rail, or operational switch may change after optimization. The execution gateway evaluates the active rule state again immediately before dispatch and writes an idempotent journal record.",
    refs: ["EXECUTE", "AUDIT"],
  },
];

export const systemFacts = {
  environment: "Synthetic simulation only",
  model: {
    name: "XGBoost recovery ranker",
    version: "xgb-recovery-32f-v0.9.4",
    status: "Active in simulation",
    features: 32,
    schema: "recovery-features/v3",
    calibration: "No calibration artifact",
    fallback: "Deterministic eligible-action ordering",
  },
  rules: {
    pack: "rp_in_recurring_2026.06.3",
    digest: "sha256:84d1…a09c",
    verification: "Schema and signature verified in simulated manifest",
    loadedAt: "2026-06-18T14:30:00+05:30",
  },
  data: {
    store: "In-browser synthetic ledger",
    mode: "Append-only journal model",
    health: "Available locally",
    persistence: "Interface preferences only",
  },
};

export const formatINR = (value: number, decimals = 0) =>
  `₹${value.toLocaleString("en-IN", { maximumFractionDigits: decimals, minimumFractionDigits: decimals })}`;
export const formatCompactINR = (value: number) =>
  value >= 10000000
    ? `₹${(value / 10000000).toFixed(2)} Cr`
    : value >= 100000
      ? `₹${(value / 100000).toFixed(2)} L`
      : value >= 1000
        ? `₹${(value / 1000).toFixed(value >= 10000 ? 1 : 2)}k`
        : formatINR(value);
export const formatTime = (iso: string) =>
  new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso)) + " IST";

export function getMetrics(input: RecoveryCase[] = cases) {
  const atRisk = input.reduce((sum, c) => sum + c.amount, 0);
  const recoveredCases = input.filter((c) => c.status === "RECOVERED");
  const recovered = recoveredCases.reduce((sum, c) => sum + c.amount, 0);
  const outstanding = input
    .filter((c) =>
      ["ACTION PENDING", "WAITING", "ESCALATED"].includes(c.status),
    )
    .reduce((sum, c) => sum + c.amount, 0);
  const stopped = input
    .filter((c) => c.status === "STOPPED")
    .reduce((sum, c) => sum + c.amount, 0);
  const avgHours = recoveredCases.length
    ? recoveredCases.reduce((sum, c) => sum + (c.recoveryHours ?? 0), 0) /
      recoveredCases.length
    : 0;
  return {
    atRisk,
    recovered,
    outstanding,
    stopped,
    recoveryRate: atRisk ? (recovered / atRisk) * 100 : 0,
    active: input.filter((c) =>
      ["ACTION PENDING", "WAITING"].includes(c.status),
    ).length,
    escalations: input.filter((c) => c.status === "ESCALATED").length,
    avgHours,
    violations: 0,
    prevented: input.reduce(
      (sum, c) => sum + c.candidates.filter((a) => !a.eligible).length,
      0,
    ),
  };
}

export function getDailySeries(input: RecoveryCase[] = cases) {
  const days = Array.from({ length: 14 }, (_, i) => {
    const d = new Date("2026-06-05T00:00:00+05:30");
    d.setDate(d.getDate() + i);
    return d.toISOString().slice(0, 10);
  });
  let cumulativeAtRisk = 0;
  let cumulativeRecovered = 0;
  return days.map((day) => {
    const created = input.filter(
      (c) => new Date(c.createdAt).toISOString().slice(0, 10) === day,
    );
    const recovered = input.filter(
      (c) =>
        c.recoveredAt &&
        new Date(c.recoveredAt).toISOString().slice(0, 10) === day,
    );
    const atRisk = created.reduce((s, c) => s + c.amount, 0);
    const recoveredValue = recovered.reduce((s, c) => s + c.amount, 0);
    cumulativeAtRisk += atRisk;
    cumulativeRecovered += recoveredValue;
    return {
      day,
      atRisk,
      recovered: recoveredValue,
      outstanding: Math.max(0, atRisk - recoveredValue),
      cumulativeAtRisk,
      cumulativeRecovered,
    };
  });
}

export const allJournalEntries = cases
  .flatMap((c) =>
    c.journal.map((j) => ({
      ...j,
      caseId: c.id,
      amount: c.amount,
      rail: c.rail,
    })),
  )
  .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
