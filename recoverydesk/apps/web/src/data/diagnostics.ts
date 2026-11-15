import {
  allJournalEntries,
  cases,
  getMetrics,
  modelFeatures,
} from "./simulation";
import { baselineData, costBreakdown, interventionCost } from "./workspace";

export function runDiagnostics() {
  const candidates = cases.flatMap((c) => c.candidates);
  const metrics = getMetrics();
  return [
    {
      label: "32 unique model schema fields",
      passed: modelFeatures.length === 32 && new Set(modelFeatures).size === 32,
      detail: "Declared schema only; no model artifact is loaded.",
    },
    {
      label: "Unique, chronological evidence",
      passed:
        new Set(allJournalEntries.map((e) => e.id)).size ===
          allJournalEntries.length &&
        cases.every((c) =>
          c.journal.every(
            (e, i) => !i || new Date(e.at) >= new Date(c.journal[i - 1].at),
          ),
        ),
      detail: `${allJournalEntries.length} journal IDs and ${cases.length} case sequences checked locally.`,
    },
    {
      label: "Blocked candidates remain unscored",
      passed: candidates
        .filter((a) => !a.eligible)
        .every(
          (a) => a.probability === undefined && a.expectedValue === undefined,
        ),
      detail: `${candidates.filter((a) => !a.eligible).length} denied candidates carry no estimate or EV.`,
    },
    {
      label: "One permissible selection per case",
      passed: cases.every(
        (c) =>
          c.candidates.filter((a) => a.selected).length === 1 &&
          c.candidates.find((a) => a.selected)?.eligible,
      ),
      detail: "Selection cardinality and recorded eligibility verified.",
    },
    {
      label: "Expected-value arithmetic reconciles",
      passed: cases.every((c) =>
        c.candidates.every(
          (a) =>
            a.expectedValue === undefined ||
            (a.probability !== undefined &&
              Math.abs(a.expectedValue - (a.probability * c.amount - a.cost)) <
                0.001),
        ),
      ),
      detail:
        "Probability x recoverable value - intervention cost recalculated.",
    },
    {
      label: "Cost allocations sum to intervention cost",
      passed: candidates.every(
        (a) =>
          Math.abs(costBreakdown(a).reduce((s, b) => s + b.value, 0) - a.cost) <
          0.001,
      ),
      detail: "Action, channel, fatigue and opportunity allocations checked.",
    },
    {
      label: "Financial ledger balances",
      passed:
        metrics.atRisk ===
        metrics.recovered + metrics.outstanding + metrics.stopped,
      detail: "At-risk value equals recovered, open and stopped value.",
    },
    {
      label: "REVIO baseline matches the ledger",
      passed:
        baselineData("ALL").find((b) => b.id === "REVIO")?.recovered ===
          metrics.recovered &&
        baselineData("ALL").find((b) => b.id === "REVIO")?.cost ===
          interventionCost(cases),
      detail: "Both recovered value and modeled costs reconcile.",
    },
    {
      label: "Non-terminal selections maximize permitted EV",
      passed: cases
        .filter((c) => c.status !== "STOPPED")
        .every(
          (c) =>
            c.candidates.find((a) => a.selected)?.expectedValue ===
            Math.max(...c.candidates.map((a) => a.expectedValue ?? -Infinity)),
        ),
      detail: "Recorded selections compared with every eligible candidate.",
    },
    {
      label: "Stopped cases have no positive-EV alternative",
      passed: cases
        .filter((c) => c.status === "STOPPED")
        .every((c) => c.candidates.every((a) => (a.expectedValue ?? 0) <= 0)),
      detail: "Terminal policy remains consistent with available economics.",
    },
  ];
}
