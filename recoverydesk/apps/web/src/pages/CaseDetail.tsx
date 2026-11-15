import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Copy,
  Download,
  FlaskConical,
  ShieldCheck,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import {
  AuditEvidence,
  CandidateComparison,
  EconomicBreakdown,
  PlaybackControls,
  RecoveryClock,
} from "../components/DecisionParts";
import { stageExplanation } from "../components/RecoveryFlow";
import { Budget, EmptyState, StatusMark } from "../components/ui";
import {
  cases,
  failureMeta,
  formatINR,
  formatTime,
  type RecoveryCase,
} from "../data/simulation";
import { exportFile } from "../data/workspace";
import { useWorkspace } from "../state/Workspace";

export default function CaseDetail() {
  const w = useWorkspace();
  const id = w.route.split("/")[1];
  const c = cases.find((item) => item.id === id);
  return c ? (
    <Investigation key={c.id} c={c} />
  ) : (
    <EmptyState
      title="This case is not in the synthetic ledger"
      body="Select one of the twenty available simulation records from the recovery queue."
      action={
        <button className="btn primary" onClick={() => w.navigate("cases")}>
          Open recovery cases
        </button>
      }
    />
  );
}
function Investigation({ c }: { c: RecoveryCase }) {
  const w = useWorkspace();
  const [step, setStep] = useState(5);
  const [playing, setPlaying] = useState(false);
  const selected = c.candidates.find((a) => a.selected)!;
  const stages = [
    "Payment failed",
    "Case opened",
    "Constraints",
    "Model estimates",
    "Expected value",
    "Action selected",
    selected.id === "stop"
      ? "Stop recorded"
      : selected.id === "wait"
        ? "Deferral recorded"
        : c.status === "ACTION PENDING"
          ? "Awaiting gateway"
          : "Execution",
    "Outcome",
  ];
  const explanation =
    step < 2
      ? {
          title:
            step === 0
              ? "A failure becomes a financial opportunity."
              : "Context makes the case.",
          detail:
            step === 0
              ? `${formatINR(c.amount)} failed on ${c.rail} at ${formatTime(c.createdAt)}. ${c.failureReason}.`
              : `Case ${c.id} brings the instrument, subscription, customer reference and decision-time budgets together before any candidate is evaluated.`,
          fact: c.failureReason,
        }
      : step === 7
        ? {
            title: "The outcome, preserved.",
            detail: c.outcomeNote,
            fact: c.status.toLowerCase(),
          }
        : stageExplanation(c, step - 2);
  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      if (step >= 7) setPlaying(false);
      else setStep((s) => s + 1);
    }, 1200);
    return () => clearTimeout(timer);
  }, [step, playing]);
  const changeStep = (s: number) => {
    setStep(Math.min(7, Math.max(0, s)));
    setPlaying(false);
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(c.id);
      w.notify("Case reference copied to clipboard.");
    } catch {
      w.notify(`Case reference: ${c.id}`);
    }
  };
  return (
    <>
      <div className="investigation-breadcrumb">
        <button onClick={() => w.navigate("cases")}>
          <ArrowLeft size={14} />
          Recovery cases
        </button>
        <span>/</span>
        <span className="mono">{c.id}</span>
        <div>
          <button className="btn small" onClick={copy}>
            <Copy size={12} />
            Copy ID
          </button>
          <button
            className="btn small"
            onClick={() => {
              exportFile(`${c.id}-synthetic-evidence.json`, c);
              w.notify("Complete synthetic case evidence exported.");
            }}
          >
            <Download size={12} />
            Export evidence
          </button>
        </div>
      </div>
      <header className="investigation-header">
        <div className="investigation-primary">
          <div className="investigation-overline">
            <span className="eyebrow blue">Case investigation</span>
            <StatusMark status={c.status} />
          </div>
          <h1 className="financial">{formatINR(c.amount)}</h1>
          <span className="investigation-amount-label">
            Failed recurring payment
          </span>
          <div className="investigation-context">
            <span>{c.rail}</span>
            <i />
            <span>{failureMeta[c.failureCode].short}</span>
          </div>
          <p>{c.outcomeNote}</p>
        </div>
        <div className="investigation-summary">
          <div className="chosen-action">
            <ShieldCheck size={19} />
            <div>
              <small>THE RECORDED NEXT MOVE</small>
              <h2>{selected.label}</h2>
              <span>
                {selected.expectedValue === undefined
                  ? "Terminal control decision"
                  : `${formatINR(selected.expectedValue, 2)} estimated expected value`}
              </span>
            </div>
          </div>
          <div className="investigation-budgets">
            <Budget
              label="Retry budget"
              used={c.constraints.retriesUsed}
              max={3}
            />
            <Budget
              label="Contact budget"
              used={c.constraints.contactsUsed}
              max={2}
            />
          </div>
          <button
            className="text-link"
            onClick={() => w.navigate(`lab/${c.id}`)}
          >
            <FlaskConical size={13} />
            Explore in Decision Studio <ArrowUpRight size={13} />
          </button>
        </div>
      </header>
      <section className="journey-section">
        <div className="section-heading">
          <div>
            <h2>The recovery journey</h2>
            <p>One payment. Every decision, in sequence.</p>
          </div>
          <PlaybackControls
            step={step}
            max={7}
            playing={playing}
            onPlay={() => {
              if (step === 7) setStep(0);
              setPlaying(true);
            }}
            onPause={() => setPlaying(false)}
            onStep={changeStep}
            onReset={() => changeStep(0)}
          />
        </div>
        <div className="investigation-journey">
          {stages.map((label, i) => (
            <button
              key={i}
              className={`${step === i ? "active" : ""} ${step > i ? "complete" : ""}`}
              onClick={() => changeStep(i)}
              aria-current={step === i ? "step" : undefined}
            >
              <span className="journey-node">
                {String(i + 1).padStart(2, "0")}
              </span>
              <strong>{label}</strong>
            </button>
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            className="journey-explanation"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <span className="journey-step-label">0{step + 1}</span>
            <div>
              <h3>{explanation.title}</h3>
              <p>{explanation.detail}</p>
            </div>
            <span className="journey-fact">{explanation.fact}</span>
          </motion.div>
        </AnimatePresence>
        <p className="note journey-note">
          Read-only replay of precomputed synthetic evidence. No new financial
          action is executed.
        </p>
      </section>
      <div className="investigation-candidates">
        <CandidateComparison c={c} emphasized={step >= 4} />
      </div>
      <div className="investigation-economics">
        <EconomicBreakdown c={c} />
        <RecoveryClock c={c} />
      </div>
      <div className="investigation-evidence-grid">
        <AuditEvidence c={c} />
        <aside className="case-metadata">
          <h3>Decision context</h3>
          <dl className="context-fields">
            <div>
              <dt>Customer reference</dt>
              <dd className="mono">{c.customerRef}</dd>
            </div>
            <div>
              <dt>Subscription</dt>
              <dd>{c.subscription}</dd>
            </div>
            <div>
              <dt>Original failure</dt>
              <dd>{formatTime(c.createdAt)}</dd>
            </div>
            <div>
              <dt>Decision reference</dt>
              <dd className="mono">{c.decisionId}</dd>
            </div>
            <div>
              <dt>Declared model fixture</dt>
              <dd className="mono">{c.modelVersion}</dd>
            </div>
            <div>
              <dt>Feature schema</dt>
              <dd>32 fields / recovery-features-v3</dd>
            </div>
            <div>
              <dt>Calibration artifact</dt>
              <dd className="red">Not available</dd>
            </div>
          </dl>
          <button className="text-link" onClick={() => w.navigate("trust")}>
            Model & system disclosures <ArrowUpRight size={12} />
          </button>
        </aside>
      </div>
    </>
  );
}
