import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  CircleCheck,
  Clock3,
  Gauge,
  Layers3,
  LockKeyhole,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  SkipBack,
  SkipForward,
  X,
} from "lucide-react";
import {
  formatINR,
  formatTime,
  type Candidate,
  type RecoveryCase,
} from "../data/simulation";
import { costBreakdown, timeOnly } from "../data/workspace";
import { decisionStages } from "./RecoveryFlow";
import { Disclosure, NumberFlow, SectionHeading } from "./ui";

export function PlaybackControls({
  step,
  max = 4,
  playing,
  onPlay,
  onPause,
  onStep,
  onReset,
}: {
  step: number;
  max?: number;
  playing: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStep: (s: number) => void;
  onReset: () => void;
}) {
  return (
    <div className="playback-controls">
      <button className="btn primary" onClick={playing ? onPause : onPlay}>
        {playing ? <Pause size={13} /> : <Play size={12} />}
        {playing ? "Pause" : "Play decision"}
      </button>
      <div className="playback-step-controls">
        <button
          className="icon-button"
          onClick={() => onStep(step - 1)}
          disabled={step === 0}
          aria-label="Previous decision step"
        >
          <SkipBack size={14} />
        </button>
        <span>
          {String(step + 1).padStart(2, "0")}{" "}
          <i>/ {String(max + 1).padStart(2, "0")}</i>
        </span>
        <button
          className="icon-button"
          onClick={() => onStep(step + 1)}
          disabled={step === max}
          aria-label="Next decision step"
        >
          <SkipForward size={14} />
        </button>
      </div>
      <button
        className="icon-button"
        onClick={onReset}
        aria-label="Restart decision replay"
      >
        <RotateCcw size={14} />
      </button>
    </div>
  );
}

export function DecisionTrace({
  c,
  step,
  setStep,
  playing,
}: {
  c: RecoveryCase;
  step: number;
  setStep: (v: number) => void;
  playing: boolean;
}) {
  const reduced = useReducedMotion();
  const chosen = c.candidates.find((a) => a.selected)!;
  const nodePositions = [
    { x: 118, y: 92, icon: ShieldCheck },
    { x: 285, y: 169, icon: Gauge },
    { x: 145, y: 251, icon: Layers3 },
    { x: 310, y: 328, icon: Check },
    { x: 176, y: 405, icon: CircleCheck },
  ];
  const fullPath =
    "M232 17V30Q232 51 211 51H141Q118 51 118 74V92V112Q118 130 141 130H261Q285 130 285 153V169V190Q285 210 261 210H169Q145 210 145 234V251V270Q145 289 169 289H287Q310 289 310 313V328V347Q310 368 287 368H199Q176 368 176 391V405";
  const captions = [
    `${c.candidates.filter((a) => a.eligible).length} permitted candidates`,
    `${c.candidates.filter((a) => a.probability !== undefined).length} illustrative estimates`,
    chosen.expectedValue === undefined
      ? "No positive-value alternative"
      : `${formatINR(chosen.expectedValue, 2)} expected value`,
    chosen.label,
    c.status === "RECOVERED"
      ? "Recovery recorded"
      : c.status === "ACTION PENDING"
        ? "Pending / no dispatch"
        : "Control state recorded",
  ];
  return (
    <div className="decision-trace">
      <div className="trace-header">
        <span>
          <i className={playing ? "playing" : ""} />
          Recorded decision trace
        </span>
        <span className="mono">SIM / {c.id.slice(-4)}</span>
      </div>
      <svg
        viewBox="0 0 470 460"
        role="group"
        aria-label="Five-stage recorded recovery decision. Select a node to inspect its evidence."
      >
        <defs>
          <pattern
            id="labGrid"
            width="22"
            height="22"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="1" cy="1" r=".65" fill="var(--line-strong)" />
          </pattern>
        </defs>
        <rect width="470" height="460" fill="url(#labGrid)" />
        <path
          d={fullPath}
          fill="none"
          stroke="var(--line-strong)"
          strokeWidth="2"
        />
        <motion.path
          d={fullPath}
          fill="none"
          stroke="var(--blue)"
          strokeWidth="2"
          animate={{ pathLength: (step + 1) / 5 }}
          transition={{ duration: 0.45 }}
        />
        <circle cx="232" cy="17" r="4" fill="var(--blue)" />
        <path
          d="M97 92H70Q48 92 48 114V142"
          stroke="var(--red)"
          strokeOpacity=".4"
          strokeDasharray="3 4"
          fill="none"
        />
        <circle
          cx="48"
          cy="151"
          r="10"
          fill="var(--red-bg)"
          stroke="var(--red)"
          strokeWidth=".7"
        />
        <path
          d="M45 148L51 154M51 148L45 154"
          stroke="var(--red)"
          strokeWidth="1.2"
        />
        <text
          x="24"
          y="180"
          fontSize="8"
          fontFamily="Manrope Variable"
          fill="var(--red)"
        >
          {c.candidates.filter((a) => !a.eligible).length} blocked
        </text>
        {nodePositions.map((n, i) => {
          const active = step === i;
          const done = step > i;
          const Icon = n.icon;
          const textX = i % 2 ? n.x - 43 : n.x + 43;
          const anchor = i % 2 ? "end" : "start";
          return (
            <g
              key={i}
              role="button"
              tabIndex={0}
              aria-label={`${i + 1}. ${decisionStages[i]}`}
              className="trace-node"
              onClick={() => setStep(i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setStep(i);
                }
              }}
            >
              <rect
                x={n.x - 33}
                y={n.y - 33}
                width="66"
                height="66"
                rx="17"
                fill={active ? "var(--blue-light)" : "transparent"}
              />
              <rect
                x={n.x - 22}
                y={n.y - 22}
                width="44"
                height="44"
                rx="11"
                fill={active ? "#326fe8" : "var(--surface)"}
                stroke={active || done ? "var(--blue)" : "var(--line-strong)"}
                strokeWidth="1.2"
              />
              <Icon
                x={n.x - 9}
                y={n.y - 9}
                width="18"
                height="18"
                stroke={
                  active ? "white" : done ? "var(--blue)" : "var(--muted)"
                }
                strokeWidth="1.5"
              />
              <text
                x={textX}
                y={n.y - 10}
                textAnchor={anchor}
                fill={active ? "var(--blue)" : "var(--muted)"}
                fontFamily="IBM Plex Mono"
                fontSize="8"
              >
                0{i + 1}
              </text>
              <text
                x={textX}
                y={n.y + 7}
                textAnchor={anchor}
                fill={active || done ? "var(--text)" : "var(--secondary)"}
                fontFamily="Manrope Variable"
                fontWeight="700"
                fontSize="13"
              >
                {decisionStages[i]}
              </text>
              <text
                x={textX}
                y={n.y + 24}
                textAnchor={anchor}
                fill="var(--muted)"
                fontFamily="Manrope Variable"
                fontSize="8"
              >
                {captions[i]}
              </text>
            </g>
          );
        })}
        {playing && !reduced && (
          <circle r="3" fill="#82adff">
            <animateMotion path={fullPath} dur="8s" repeatCount="indefinite" />
          </circle>
        )}
      </svg>
      <div className="trace-footnote">
        <LockKeyhole size={11} />
        Read-only replay. No financial actions are executed.
      </div>
    </div>
  );
}

export function CandidateComparison({
  c,
  emphasized = true,
}: {
  c: RecoveryCase;
  emphasized?: boolean;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "eligible" | "blocked">("all");
  const candidates = [...c.candidates]
    .sort(
      (a, b) =>
        Number(b.selected) - Number(a.selected) ||
        Number(b.eligible) - Number(a.eligible) ||
        (b.expectedValue ?? -Infinity) - (a.expectedValue ?? -Infinity),
    )
    .filter(
      (a) =>
        filter === "all" || (filter === "eligible" ? a.eligible : !a.eligible),
    );
  const maxEv = Math.max(1, ...c.candidates.map((a) => a.expectedValue ?? 0));
  return (
    <section className="candidate-comparison">
      <SectionHeading
        title="The alternatives, in perspective"
        description="Every eligible option scored. Every rejected option explained."
        action={
          <div
            className="simple-tabs"
            role="group"
            aria-label="Candidate eligibility filter"
          >
            {(["all", "eligible", "blocked"] as const).map((f) => (
              <button
                key={f}
                className={filter === f ? "active" : ""}
                onClick={() => setFilter(f)}
              >
                {f === "all"
                  ? "All actions"
                  : f === "eligible"
                    ? "Permitted"
                    : "Blocked"}
              </button>
            ))}
          </div>
        }
      />
      <div className="candidate-table">
        <div className="candidate-table-head">
          <span>Candidate action</span>
          <span>Permission</span>
          <span>Success estimate</span>
          <span>Expected value</span>
          <span />
        </div>
        {candidates.map((a) => (
          <div
            key={a.id}
            className={`candidate-row-wrap ${a.selected && emphasized ? "engine-selected" : ""} ${!a.eligible ? "is-blocked" : ""}`}
          >
            <button
              className="candidate-row"
              onClick={() => setExpanded(expanded === a.id ? null : a.id)}
              aria-expanded={expanded === a.id}
            >
              <span className="candidate-name">
                <span
                  className={`candidate-action-icon ${a.selected ? "selected" : ""}`}
                >
                  {a.selected ? (
                    <Check size={13} />
                  ) : a.eligible ? (
                    <ArrowRight size={12} />
                  ) : (
                    <X size={12} />
                  )}
                </span>
                <span>
                  <strong>{a.label}</strong>
                  {a.selected && <small>Engine selected</small>}
                </span>
              </span>
              <span
                className={
                  a.eligible ? "permission-allowed" : "permission-denied"
                }
              >
                {a.eligible ? "Permitted" : "Blocked"}
              </span>
              <span className="candidate-probability">
                {a.probability === undefined ? (
                  <span className="not-scored">Not scored</span>
                ) : (
                  <>
                    <span className="probability-track">
                      <motion.i
                        initial={{ width: 0 }}
                        animate={{ width: `${a.probability * 100}%` }}
                        transition={{ duration: 0.35 }}
                      />
                    </span>
                    <strong>{Math.round(a.probability * 100)}%</strong>
                  </>
                )}
              </span>
              <span className="candidate-ev">
                <span className="financial">
                  {a.expectedValue === undefined
                    ? "Not applicable"
                    : formatINR(a.expectedValue, 2)}
                </span>
                {a.expectedValue !== undefined && (
                  <i
                    style={{
                      width: `${(Math.max(0, a.expectedValue) / maxEv) * 100}%`,
                    }}
                  />
                )}
              </span>
              <ChevronRight
                size={13}
                className={expanded === a.id ? "turn-down" : ""}
              />
            </button>
            <AnimatePresence initial={false}>
              {expanded === a.id && (
                <motion.div
                  className="candidate-evidence"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.23 }}
                >
                  <div>
                    {a.eligible ? (
                      <>
                        <p>{a.description}</p>
                        <div>
                          <span>
                            Illustrative intervention cost{" "}
                            <strong>{formatINR(a.cost, 2)}</strong>
                          </span>
                          <span>
                            Estimate source{" "}
                            <strong>Precomputed simulation snapshot</strong>
                          </span>
                        </div>
                        <p className="note">
                          {a.probability === undefined
                            ? "A terminal control action has no predictive probability or calculated EV."
                            : `${a.probability.toFixed(2)} x ${formatINR(c.amount)} - ${formatINR(a.cost, 2)} = ${formatINR(a.expectedValue ?? 0, 2)}. Estimate is uncalibrated.`}
                        </p>
                      </>
                    ) : (
                      <>
                        <span className="mono red">{a.ruleRef}</span>
                        <p>{a.denial}</p>
                        <p className="note">
                          Rejected before scoring. No probability, expected
                          value or dispatch is assigned.
                        </p>
                      </>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
      <p className="note candidate-note">
        Illustrative, uncalibrated estimates. Selecting a row inspects its
        evidence; it never changes the recorded decision.
      </p>
    </section>
  );
}

export function EconomicBreakdown({
  c,
  candidate,
}: {
  c: RecoveryCase;
  candidate?: Candidate;
}) {
  const a = candidate ?? c.candidates.find((item) => item.selected)!;
  const costs = costBreakdown(a);
  return (
    <section className="economic-breakdown">
      <SectionHeading
        title="The economics of the next move"
        description="A transparent bridge from recoverable value to expected value."
      />
      <div className="economic-layout">
        <div className="economic-bridge">
          <span className="eyebrow">Probability-weighted value</span>
          <div className="economic-equation">
            <div>
              <strong className="financial">{formatINR(c.amount)}</strong>
              <small>Recoverable amount</small>
            </div>
            <span className="equation-symbol">x</span>
            <div>
              <strong className="financial blue">
                {a.probability === undefined
                  ? "N/A"
                  : `${Math.round(a.probability * 100)}%`}
              </strong>
              <small>Illustrative estimate</small>
            </div>
          </div>
          <div className="probability-contribution">
            <span>Expected probability contribution</span>
            <NumberFlow value={(a.probability ?? 0) * c.amount} />
            <div>
              <motion.span
                animate={{ width: `${(a.probability ?? 0) * 100}%` }}
                transition={{ duration: 0.45 }}
              />
            </div>
          </div>
          <p className="note">
            This is expected financial value, not a guaranteed recovery or
            customer lifetime value. Costs below are an illustrative allocation
            of the recorded intervention cost.
          </p>
        </div>
        <div className="cost-ledger">
          <div className="cost-ledger-start">
            <span>Probability-weighted value</span>
            <strong className="financial">
              {a.probability === undefined
                ? "Not scored"
                : formatINR(a.probability * c.amount, 2)}
            </strong>
          </div>
          {costs.map((cost) => (
            <div key={cost.label}>
              <span>
                <i />
                {cost.label}
              </span>
              <strong className="financial">
                - {formatINR(cost.value, 2)}
              </strong>
            </div>
          ))}
          <div className="cost-ledger-total">
            <span>
              Final expected value<small>{a.label}</small>
            </span>
            <NumberFlow
              value={a.expectedValue ?? 0}
              format={(v) =>
                a.expectedValue === undefined
                  ? "Not applicable"
                  : formatINR(v, 2)
              }
            />
          </div>
        </div>
      </div>
    </section>
  );
}

export function RecoveryClock({ c }: { c: RecoveryCase }) {
  const failHour = Number(timeOnly(c.createdAt).split(":")[0]);
  const [hour, setHour] = useState(failHour);
  const quiet = hour >= 21 || hour < 8;
  const recovered = c.recoveredAt
    ? Number(timeOnly(c.recoveredAt).split(":")[0]) +
      Number(timeOnly(c.recoveredAt).split(":")[1]) / 60
    : null;
  return (
    <section className="recovery-clock">
      <SectionHeading
        title="The recovery window"
        description="Timing is a constraint, not an authorization."
        action={
          <span className="clock-timezone">
            <Clock3 size={12} />
            Asia/Kolkata
          </span>
        }
      />
      <div className="clock-selected-time">
        <strong className="financial">
          {hour.toString().padStart(2, "0")}:00<small>IST</small>
        </strong>
        <span className={quiet ? "quiet-label" : "allowed-label"}>
          {quiet ? "Inside quiet hours" : "Outside quiet hours"}
        </span>
      </div>
      <div className="clock-track">
        <div className="quiet-block start" />
        <div className="permitted-block" />
        <div className="quiet-block end" />
        <span
          className="clock-failure"
          style={{ left: `${(failHour / 24) * 100}%` }}
        >
          <i />
          <small>Failure</small>
        </span>
        {recovered !== null && (
          <span
            className="clock-recovery"
            style={{ left: `${(recovered / 24) * 100}%` }}
          >
            <i />
            <small>Recovered</small>
          </span>
        )}
        <motion.span
          className="clock-cursor"
          animate={{ left: `${(hour / 24) * 100}%` }}
          transition={{ duration: 0.2 }}
        />
        <input
          type="range"
          min="0"
          max="23"
          step="1"
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
          aria-label="Explore recovery hour in IST"
        />
      </div>
      <div className="clock-ticks">
        {["00:00", "06:00", "12:00", "18:00", "24:00"].map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      <div className="clock-legend">
        <span>
          <i className="allowed" />
          Policy window: 08:00 - 21:00
        </span>
        <span>
          <i />
          Quiet hours
        </span>
      </div>
      <p className="note">
        Drag the hour marker to explore the policy. Outside quiet hours is not
        permission to act: budgets, mandate state, rail availability and gateway
        checks still apply.
      </p>
    </section>
  );
}

export function AuditEvidence({ c }: { c: RecoveryCase }) {
  return (
    <section className="audit-evidence">
      <SectionHeading
        title="Every decision leaves a trace"
        description={`${c.journal.length} append-only evidence entries in the synthetic record.`}
        tag="Audit evidence"
      />
      <div className="audit-evidence-list">
        {c.journal.map((e, i) => (
          <div className="audit-evidence-entry" key={e.id}>
            <span className="audit-timeline-dot">
              {i === c.journal.length - 1 ? <Check size={10} /> : <i />}
            </span>
            <Disclosure
              title={e.summary}
              subtitle={`${formatTime(e.at)} / ${e.type}`}
              right={
                <span className="event-stage">{e.stage.toLowerCase()}</span>
              }
            >
              <dl className="evidence-fields">
                <div>
                  <dt>Journal identifier</dt>
                  <dd>{e.id}</dd>
                </div>
                <div>
                  <dt>Actor</dt>
                  <dd>{e.actor}</dd>
                </div>
                {Object.entries(e.refs).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replace(/_/g, " ")}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </Disclosure>
          </div>
        ))}
      </div>
    </section>
  );
}
