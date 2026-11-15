import {
  allJournalEntries,
  baselineSegments,
  cases,
  simulationClock,
  type Candidate,
  type RecoveryCase,
} from "./simulation";

export type TimeRange = "24H" | "7D" | "30D" | "ALL";
export const rangeOptions: { value: TimeRange; label: string }[] = [
  { value: "24H", label: "24 hours" },
  { value: "7D", label: "7 days" },
  { value: "30D", label: "30 days" },
  { value: "ALL", label: "All time" },
];
export const clock = new Date(simulationClock).getTime();
export const chronologicalEvents = [...allJournalEntries].sort(
  (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime(),
);
export const statusLabels = {
  RECOVERED: "Recovered",
  "ACTION PENDING": "Action pending",
  WAITING: "Waiting",
  ESCALATED: "Escalated",
  STOPPED: "Stopped",
};
export const statusColors = {
  RECOVERED: "#0b9b73",
  "ACTION PENDING": "#326fe8",
  WAITING: "#7e8da7",
  ESCALATED: "#c18523",
  STOPPED: "#d65c69",
};

export function safeRead<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}
export function safeWrite(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Storage may be unavailable in private browsing. */
  }
}
export const rangeStart = (range: TimeRange) =>
  range === "ALL"
    ? new Date("2026-06-07T00:00:00+05:30").getTime()
    : clock - (range === "24H" ? 1 : range === "7D" ? 7 : 30) * 86400000;
export function filterRange(input: RecoveryCase[], range: TimeRange) {
  return input.filter(
    (c) => new Date(c.createdAt).getTime() >= rangeStart(range),
  );
}

// Replay projects existing records in time. It never creates or executes a payment action.
export function ledgerAt(at: number): RecoveryCase[] {
  return cases
    .filter((c) => new Date(c.createdAt).getTime() <= at)
    .map((c) => {
      if (new Date(c.updatedAt).getTime() <= at) return c;
      return {
        ...c,
        status: "ACTION PENDING",
        recoveredAt: undefined,
        recoveryHours: undefined,
        journal: c.journal.filter((e) => new Date(e.at).getTime() <= at),
      };
    });
}

export interface PulsePoint {
  at: number;
  label: string;
  recovered: number;
  atRisk: number;
  rate: number;
  recoveredCount: number;
}
export function pulseSeries(
  input: RecoveryCase[],
  range: TimeRange,
  end = clock,
): PulsePoint[] {
  const start = rangeStart(range);
  if (end < start) return [];
  const interval = range === "24H" ? 3600000 : 86400000;
  const count = Math.max(2, Math.ceil((end - start) / interval) + 1);
  return Array.from({ length: count }, (_, i) => {
    const at = Math.min(start + i * interval, end);
    const entered = input.filter((c) => new Date(c.createdAt).getTime() <= at);
    const recoveredCases = entered.filter(
      (c) =>
        c.status === "RECOVERED" &&
        c.recoveredAt &&
        new Date(c.recoveredAt).getTime() <= at,
    );
    const recovered = recoveredCases.reduce((s, c) => s + c.amount, 0);
    const atRisk = entered.reduce((s, c) => s + c.amount, 0);
    const label = new Intl.DateTimeFormat(
      "en-IN",
      range === "24H"
        ? {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
            timeZone: "Asia/Kolkata",
          }
        : { day: "2-digit", month: "short", timeZone: "Asia/Kolkata" },
    ).format(at);
    return {
      at,
      label,
      recovered,
      atRisk,
      rate: atRisk ? (recovered / atRisk) * 100 : 0,
      recoveredCount: recoveredCases.length,
    };
  });
}

export const interventionCost = (input: RecoveryCase[]) =>
  input.reduce(
    (sum, c) =>
      sum +
      c.constraints.retriesUsed * 6 +
      c.constraints.contactsUsed * 1.8 +
      (c.status === "ESCALATED" ? 450 : 0),
    0,
  );
export const baselineData = (rail: "ALL" | "UPI AutoPay" | "Card SI") =>
  baselineSegments[rail].map((b, i) => ({
    ...b,
    color: ["#bdccea", "#8cabea", "#587fd7", "#2563ff"][i],
    cost:
      b.id === "REVIO"
        ? interventionCost(
            cases.filter((c) => rail === "ALL" || c.rail === rail),
          )
        : b.cost,
  }));
export const ageLabel = (at: string) => {
  const h = Math.max(0, (clock - new Date(at).getTime()) / 3600000);
  return h < 1
    ? `${Math.round(h * 60)}m ago`
    : h < 24
      ? `${Math.floor(h)}h ago`
      : `${Math.floor(h / 24)}d ago`;
};
export const dateOnly = (at: string | number) =>
  new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(at));
export const timeOnly = (at: string | number) =>
  new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(new Date(at));

export function exportFile(name: string, data: unknown, csv = false) {
  const url = URL.createObjectURL(
    new Blob(
      [
        csv
          ? String(data)
          : JSON.stringify(
              { environment: "SYNTHETIC SIMULATION", data },
              null,
              2,
            ),
      ],
      { type: csv ? "text/csv;charset=utf-8" : "application/json" },
    ),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

export const scenarioSnapshots = [
  {
    id: "window",
    caseId: cases[0].id,
    title: "The right recovery window",
    short: "Insufficient funds",
    context: "A late-night failure meets a permitted morning retry.",
    elapsed: "3 minutes",
    window: "Next day, 09:00 IST",
    tenure: "14 months",
  },
  {
    id: "instrument",
    caseId: cases[2].id,
    title: "Repair before retry",
    short: "Expired card",
    context: "An expired instrument makes another blind debit the wrong move.",
    elapsed: "3 minutes",
    window: "Daytime contact window",
    tenure: "26 months",
  },
  {
    id: "budget",
    caseId: cases[9].id,
    title: "Knowing when to stop",
    short: "Budget exhausted",
    context: "No positive-value permitted intervention remains.",
    elapsed: "48 hours",
    window: "No further intervention",
    tenure: "8 months",
  },
  {
    id: "rail",
    caseId: cases[11].id,
    title: "Patience has a value",
    short: "Recovery window unavailable",
    context: "A wait action wins while the payment rail is unavailable.",
    elapsed: "31 minutes",
    window: "Re-evaluate at 17:00 IST",
    tenure: "19 months",
  },
  {
    id: "mandate",
    caseId: cases[16].id,
    title: "Repair the mandate first",
    short: "Paused mandate",
    context:
      "A mandate execution failure makes instrument repair more valuable than another debit attempt.",
    elapsed: "29 hours",
    window: "Repair, then next scheduled debit",
    tenure: "11 months",
  },
  {
    id: "human",
    caseId: cases[3].id,
    title: "A deliberate human handoff",
    short: "Mandate revoked",
    context: "A revoked mandate and exhausted contacts call for review.",
    elapsed: "25 hours",
    window: "Operator review queue",
    tenure: "21 months",
  },
];

// Cost allocation is illustrative and sums exactly to the recorded intervention cost.
export function costBreakdown(candidate: Candidate) {
  const weights =
    candidate.id === "escalate"
      ? [0.88, 0.02, 0.04, 0.06]
      : [0.4, 0.3, 0.1, 0.2];
  const labels = [
    "Action cost",
    "Channel cost",
    "Fatigue allowance",
    "Attempt opportunity cost",
  ];
  const values = weights.map((w) => Math.round(candidate.cost * w * 100) / 100);
  values[3] =
    Math.round(
      (candidate.cost - values.slice(0, 3).reduce((a, b) => a + b, 0)) * 100,
    ) / 100;
  return labels.map((label, i) => ({ label, value: values[i] }));
}
