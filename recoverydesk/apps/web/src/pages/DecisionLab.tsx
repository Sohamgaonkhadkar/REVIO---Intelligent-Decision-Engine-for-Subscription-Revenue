import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  FlaskConical,
  Info,
  LockKeyhole,
  MoveHorizontal,
} from "lucide-react";
import {
  CandidateComparison,
  DecisionTrace,
  PlaybackControls,
  RecoveryClock,
} from "../components/DecisionParts";
import { decisionStages, stageExplanation } from "../components/RecoveryFlow";
import {
  Budget,
  PageHeading,
  SectionHeading,
  Segmented,
  StatusMark,
} from "../components/ui";
import { cases, failureMeta, formatINR } from "../data/simulation";
import { scenarioSnapshots } from "../data/workspace";
import { useWorkspace } from "../state/Workspace";

export default function DecisionLab() {
  const w = useWorkspace();
  const routeId = w.route.split("/")[1]?.split("?")[0];
  const [tab, setTab] = useState<"replay" | "studio">("replay");
  const [caseId, setCaseId] = useState(
    cases.find((c) => c.id === routeId)?.id ?? cases[0].id,
  );
  const [scenario, setScenario] = useState(0);
  const [compareScenario, setCompareScenario] = useState(2);
  const [comparePosition, setComparePosition] = useState(54);
  const [speed, setSpeed] = useState(1);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const c =
    cases.find(
      (item) =>
        item.id ===
        (tab === "studio" ? scenarioSnapshots[scenario].caseId : caseId),
    ) ?? cases[0];
  const selected = c.candidates.find((a) => a.selected)!;
  const explanation = stageExplanation(c, step);
  useEffect(() => {
    setStep(0);
    setPlaying(false);
  }, [c.id, tab]);
  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      if (step >= 4) setPlaying(false);
      else setStep((s) => s + 1);
    }, 1500 / speed);
    return () => clearTimeout(timer);
  }, [step, playing, speed]);
  const changeStep = (s: number) => {
    setStep(Math.max(0, Math.min(4, s)));
    setPlaying(false);
  };
  return (
    <>
      <PageHeading
        title="Decision Studio"
        description="Why REVIO picked this move—and why the others were off the table."
        actions={
          <Segmented
            label="Decision Studio mode"
            value={tab}
            onChange={setTab}
            options={[
              { value: "replay", label: "Decision replay" },
              { value: "studio", label: "Scenario Playground" },
            ]}
          />
        }
      />
      <div className="lab-intro-bar">
        <span>
          <FlaskConical size={16} />
          <strong>
            {tab === "studio"
              ? "Scenario Playground"
              : "One case, slowed down"}
          </strong>
          {tab === "studio"
            ? "Fixed examples. No pretend live model."
            : "Step through the call REVIO actually recorded."}
        </span>
        <span className="lab-readonly">
          <LockKeyhole size={11} />
          Nothing here moves money
        </span>
      </div>
      {tab === "studio" && (
        <div className="scenario-selector">
          <div className="scenario-tabs">
            {scenarioSnapshots.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setScenario(i)}
                className={scenario === i ? "active" : ""}
              >
                <span>0{i + 1}</span>
                {s.short}
              </button>
            ))}
          </div>
          <div className="scenario-description">
            <div>
              <h2>{scenarioSnapshots[scenario].title}</h2>
              <p>{scenarioSnapshots[scenario].context}</p>
            </div>
            <span>
              <Info size={13} />
              Switching loads an authored snapshot, not model inference.
            </span>
          </div>
        </div>
      )}

      <div className="lab-workspace" data-tour="lab">
        <aside className="lab-case-context">
          <span className="eyebrow blue">01 / The case</span>
          {tab === "replay" ? (
            <label className="lab-case-select">
              <span>Pick a case</span>
              <select
                className="field"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
              >
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id} / {formatINR(item.amount)}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className="scenario-snapshot-ref mono">
              SNAPSHOT / {scenarioSnapshots[scenario].id.toUpperCase()}
            </span>
          )}
          <AnimatePresence mode="wait">
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 7 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <span className="lab-case-amount financial">
                {formatINR(c.amount)}
              </span>
              <span className="lab-case-amount-caption">
                Failed debit
              </span>
              <div className="lab-case-status">
                <StatusMark status={c.status} />
              </div>
              <dl className="context-fields">
                <div>
                  <dt>Payment rail</dt>
                  <dd>{c.rail}</dd>
                </div>
                <div>
                  <dt>Failure reason</dt>
                  <dd>{failureMeta[c.failureCode].short}</dd>
                </div>
                <div>
                  <dt>Plan</dt>
                  <dd>
                    {tab === "studio"
                      ? `${scenarioSnapshots[scenario].tenure} tenure / illustrative`
                      : c.subscription}
                  </dd>
                </div>
                {tab === "studio" && (
                  <>
                    <div>
                      <dt>Time since failure</dt>
                      <dd>{scenarioSnapshots[scenario].elapsed}</dd>
                    </div>
                    <div>
                      <dt>Recovery window</dt>
                      <dd>{scenarioSnapshots[scenario].window}</dd>
                    </div>
                  </>
                )}
              </dl>
              <div className="lab-budgets">
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
                onClick={() => w.navigate(`case/${c.id}`)}
              >
                See the full working <ArrowUpRight size={12} />
              </button>
            </motion.div>
          </AnimatePresence>
          <div className="lab-context-note">
            <BookOpen size={13} />
            <p>
              These scores were written into the fixture beforehand. They are
              not calibrated, and no model is running in your browser.
            </p>
          </div>
        </aside>
        <div className="lab-engine">
          <DecisionTrace
            c={c}
            step={step}
            setStep={changeStep}
            playing={playing}
          />
          <PlaybackControls
            step={step}
            playing={playing}
            onPlay={() => {
              if (step === 4) setStep(0);
              setPlaying(true);
            }}
            onPause={() => setPlaying(false)}
            onStep={changeStep}
            onReset={() => {
              setStep(0);
              setPlaying(false);
            }}
          />
          <div className="replay-speed-control">
            <span>Replay speed</span>
            <Segmented
              label="Decision replay speed"
              value={String(speed)}
              onChange={(value) => setSpeed(Number(value))}
              options={[
                { value: "0.75", label: "0.75×" },
                { value: "1", label: "1×" },
                { value: "1.5", label: "1.5×" },
              ]}
            />
          </div>
        </div>
        <aside className="lab-explanation">
          <div className="explanation-top">
            <span className="eyebrow blue">
              0{step + 1} / {decisionStages[step]}
            </span>
            <span>{step + 1} of 5</span>
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={`${c.id}-${step}`}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -4 }}
              transition={{ duration: 0.23 }}
            >
              <h2>{explanation.title}</h2>
              <p>{explanation.detail}</p>
              <div className="stage-fact">
                <small>{explanation.label}</small>
                <strong className={step === 2 ? "financial" : ""}>
                  {explanation.fact}
                </strong>
              </div>
              <div className="stage-candidates">
                <h3>
                  {step === 0
                    ? "What the rules knocked out"
                    : "The moves still standing"}
                </h3>
                {(step === 0
                  ? c.candidates.filter((a) => !a.eligible).slice(0, 3)
                  : c.candidates
                      .filter((a) => a.probability !== undefined)
                      .sort(
                        (a, b) =>
                          (b.expectedValue ?? 0) - (a.expectedValue ?? 0),
                      )
                      .slice(0, 3)
                ).map((a) => (
                  <div key={a.id}>
                    <span>
                      <i className={a.eligible ? "allowed" : "blocked"} />
                      {a.label}
                    </span>
                    {a.eligible ? (
                      <>
                        <strong>
                          {step === 1
                            ? `${Math.round((a.probability ?? 0) * 100)}%`
                            : formatINR(a.expectedValue ?? 0)}
                        </strong>
                        <span className="stage-candidate-bar">
                          <i
                            style={{ width: `${(a.probability ?? 0) * 100}%` }}
                          />
                        </span>
                      </>
                    ) : (
                      <small>{a.denial}</small>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
          <div className="lab-selected-summary">
            <span>REVIO chose</span>
            <strong>
              {selected.label}
              <ArrowRight size={13} />
            </strong>
          </div>
        </aside>
      </div>
      {tab === "studio" && (
        <section className="scenario-compare">
          <SectionHeading
            title="Why the answer changes"
            description="Drag the divider to compare two fixed snapshots. Different constraints can make an intelligent system choose patience, repair—or stop."
            action={
              <label className="compare-select">
                <span>Compare with</span>
                <select
                  className="field"
                  value={compareScenario}
                  onChange={(e) => setCompareScenario(Number(e.target.value))}
                  aria-label="Scenario to compare against the active scenario"
                >
                  {scenarioSnapshots.map((s, i) => (
                    <option key={s.id} value={i}>
                      {s.short}
                    </option>
                  ))}
                </select>
              </label>
            }
          />
          <div className="scenario-compare-stage">
            <ScenarioComparePanel index={scenario} side="Active scenario" />
            <div
              className="scenario-compare-overlay"
              style={{
                clipPath: `inset(0 0 0 ${comparePosition}%)`,
              }}
            >
              <ScenarioComparePanel
                index={compareScenario}
                side="Comparison"
              />
            </div>
            <div
              className="scenario-compare-handle"
              style={{ left: `${comparePosition}%` }}
              aria-hidden="true"
            >
              <span>
                <MoveHorizontal size={15} />
              </span>
            </div>
            <input
              type="range"
              min="8"
              max="92"
              value={comparePosition}
              onChange={(e) => setComparePosition(Number(e.target.value))}
              aria-label="Reveal more of the comparison scenario"
            />
          </div>
          <p className="note">
            Both sides are complete authored snapshots. The divider changes
            visibility—not the underlying case, score or recorded decision.
          </p>
        </section>
      )}
      <div className="lab-boundary">
        <Info size={13} />
        {tab === "studio"
          ? "Scenario Playground is educational. The fields above describe fixed illustrative inputs. Selecting a scenario does not mutate case records or run live inference."
          : "Replay explores an existing decision record. Play, pause and step controls do not send messages, authorize debits or change the selected action."}
      </div>
      <div className="lab-bottom">
        <CandidateComparison key={c.id} c={c} emphasized={step >= 3} />
        <RecoveryClock key={`clock-${c.id}`} c={c} />
      </div>
    </>
  );
}

function ScenarioComparePanel({
  index,
  side,
}: {
  index: number;
  side: string;
}) {
  const snapshot = scenarioSnapshots[index];
  const c = cases.find((item) => item.id === snapshot.caseId) ?? cases[0];
  const selected = c.candidates.find((a) => a.selected)!;
  const permitted = c.candidates.filter((a) => a.eligible).length;
  const blocked = c.candidates.filter((a) => !a.eligible);
  return (
    <article className="scenario-compare-panel">
      <div className="compare-panel-top">
        <span>{side}</span>
        <small className="mono">{snapshot.id.toUpperCase()}</small>
      </div>
      <h3>{snapshot.title}</h3>
      <p>{snapshot.context}</p>
      <strong className="financial compare-amount">{formatINR(c.amount)}</strong>
      <span className="compare-case-meta">
        {failureMeta[c.failureCode].short} · {c.rail}
      </span>
      <dl className="compare-metrics">
        <div>
          <dt>Permitted</dt>
          <dd>{permitted} actions</dd>
        </div>
        <div>
          <dt>Blocked</dt>
          <dd>{blocked.length} actions</dd>
        </div>
        <div>
          <dt>Preferred action</dt>
          <dd>{selected.label}</dd>
        </div>
        <div>
          <dt>Expected value</dt>
          <dd>
            {selected.expectedValue === undefined
              ? "Not applicable"
              : formatINR(selected.expectedValue, 2)}
          </dd>
        </div>
      </dl>
      {blocked[0] ? (
        <p className="compare-denial">
          <span className="mono">{blocked[0].ruleRef}</span>
          {blocked[0].denial}
        </p>
      ) : (
        <p className="compare-denial">No candidate is blocked in this snapshot.</p>
      )}
    </article>
  );
}
