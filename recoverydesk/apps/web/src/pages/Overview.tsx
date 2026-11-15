import {
  AnimatePresence,
  motion,
  useReducedMotion,
} from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  CircleCheck,
  Clock3,
  Download,
  Layers2,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  TrendingUp,
  X,
} from "lucide-react";
import { DateRangeControl } from "../components/ConsoleShell";
import {
  BaselineComparison,
  MoneyMovement,
  RevenuePulse,
} from "../components/charts";
import { HERO_IMAGE, PhotoStories } from "../components/PhotoStories";
import { RecoveryFlow } from "../components/RecoveryFlow";
import {
  NumberFlow,
  PageHeading,
  SectionHeading,
  Tooltip,
} from "../components/ui";
import {
  allJournalEntries,
  cases,
  formatINR,
  getMetrics,
  type Rail,
} from "../data/simulation";
import {
  chronologicalEvents,
  dateOnly,
  exportFile,
  timeOnly,
} from "../data/workspace";
import { useWorkspace } from "../state/Workspace";

export default function Overview() {
  const w = useWorkspace();
  const m = useMemo(() => getMetrics(w.cohort), [w.cohort]);
  const [rail, setRail] = useState<"ALL" | Rail>("ALL");
  const recoveredCount = w.cohort.filter(
    (c) => c.status === "RECOVERED",
  ).length;
  const heroRef = useRef<HTMLElement>(null);
  const reducedMotion = useReducedMotion();
  const featured = cases[0];
  const featuredSelected = featured.candidates.find((a) => a.selected)!;
  const featuredPermitted = featured.candidates.filter((a) => a.eligible).length;
  const featuredBlocked = featured.candidates.filter((a) => !a.eligible).length;
  const [heroStage, setHeroStage] = useState(0);
  const [heroHeld, setHeroHeld] = useState(false);
  useEffect(() => {
    if (reducedMotion || heroHeld) return;
    const timer = setInterval(
      () => setHeroStage((stage) => (stage + 1) % 4),
      2600,
    );
    return () => clearInterval(timer);
  }, [reducedMotion, heroHeld]);
  const moveHeroLight = (e: React.PointerEvent<HTMLElement>) => {
    const node = heroRef.current;
    if (!node || reducedMotion) return;
    const rect = node.getBoundingClientRect();
    const x = (e.clientX - rect.left) / Math.max(1, rect.width) - 0.5;
    const y = (e.clientY - rect.top) / Math.max(1, rect.height) - 0.5;
    node.style.setProperty("--hero-x", `${(x * 14).toFixed(2)}px`);
    node.style.setProperty("--hero-y", `${(y * 10).toFixed(2)}px`);
    node.style.setProperty("--hero-nx", `${(x * -8).toFixed(2)}px`);
    node.style.setProperty("--hero-ny", `${(y * -6).toFixed(2)}px`);
    node.style.setProperty(
      "--hero-glow-x",
      `${(((e.clientX - rect.left) / Math.max(1, rect.width)) * 100).toFixed(1)}%`,
    );
    node.style.setProperty(
      "--hero-glow-y",
      `${(((e.clientY - rect.top) / Math.max(1, rect.height)) * 100).toFixed(1)}%`,
    );
  };
  const exportSnapshot = () => {
    exportFile("revio-synthetic-overview.json", {
      range: w.range,
      asOf: new Date(w.at).toISOString(),
      metrics: m,
      cases: w.cohort.map((c) => ({
        id: c.id,
        amount: c.amount,
        status: c.status,
      })),
    });
    w.notify("Synthetic overview snapshot exported.");
  };
  return (
    <>
      <PageHeading
        title="Overview"
        description="Money is still sitting in failed debits. Start there."
        actions={
          <>
            <DateRangeControl />
            <button
              className="btn primary"
              onClick={w.replay ? w.stopReplay : w.startReplay}
            >
              {w.replay ? <X size={13} /> : <Play size={12} />}
              {w.replay ? "Exit replay" : "Replay the ledger"}
            </button>
          </>
        }
      />
      <AnimatePresence>
        {w.replay && (
          <motion.div
            className="simulation-playback"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <div>
              <Activity size={15} />
              <strong>Replaying the ledger</strong>
              <span>
                {dateOnly(w.at)}, {timeOnly(w.at)} IST
              </span>
              <span>
                {w.cursor + 1} / {chronologicalEvents.length} recorded events
              </span>
            </div>
            <progress max={chronologicalEvents.length} value={w.cursor + 1} />
            <div>
              <button
                className="icon-button"
                onClick={w.toggleReplay}
                aria-label={
                  w.playing ? "Pause simulation" : "Resume simulation"
                }
              >
                {w.playing ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <button
                className="icon-button"
                onClick={w.restartReplay}
                aria-label="Restart simulation"
              >
                <RotateCcw size={14} />
              </button>
            </div>
            <p>
              Historical synthetic events only. All headline metrics and charts
              reflect this replay position.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <section
        className="overview-hero luminous-hero"
        data-tour="overview"
        ref={heroRef}
        onPointerMove={moveHeroLight}
        onPointerLeave={() => {
          heroRef.current?.style.setProperty("--hero-x", "0px");
          heroRef.current?.style.setProperty("--hero-y", "0px");
          heroRef.current?.style.setProperty("--hero-nx", "0px");
          heroRef.current?.style.setProperty("--hero-ny", "0px");
        }}
      >
        <div className="hero-aurora" aria-hidden="true" />
        <div className="hero-copy">
          <motion.div
            initial={reducedMotion ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="hero-eyebrow">
              <span />
              FAILED DEBITS · RECOVERY QUEUE
            </div>
            <h2>
              Don’t hit retry.
              <br />
              <span>Make it count.</span>
            </h2>
            <p>
              REVIO checks what is allowed, scores only those options, then
              picks the move most likely to pay for itself. That’s the whole
              trick.
            </p>
          </motion.div>
          <motion.div
            className="hero-financial luminous-metric"
            initial={reducedMotion ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.14 }}
          >
            <span className="hero-financial-label">Money brought back</span>
            <div>
              <NumberFlow value={m.recovered} className="hero-number" />
              <span className="hero-recovery-check">
                <Check size={14} />
              </span>
            </div>
            <span className="hero-metric-caption">
              <span>SIMULATED OUTCOMES</span>
              <i />
              {recoveredCount} payments recovered
            </span>
          </motion.div>
          <motion.div
            className="hero-actions"
            initial={reducedMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.24 }}
          >
            <button className="btn primary" onClick={() => w.navigate("lab")}>
              See how REVIO decides <ArrowUpRight size={14} />
            </button>
            <button className="btn glass-btn" onClick={() => w.navigate("cases")}>
              Work the queue
            </button>
          </motion.div>
        </div>

        <div className="hero-visual">
          <motion.figure
            className="hero-photo-wrap"
            initial={
              reducedMotion
                ? false
                : { opacity: 0.25, clipPath: "inset(0 0 0 22%)" }
            }
            animate={{ opacity: 1, clipPath: "inset(0 0 0 0%)" }}
            transition={{ duration: 0.9, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          >
            <img
              src={HERO_IMAGE}
              alt="Close-up of a smartphone being used for a contactless payment at a modern payment terminal"
              loading="eager"
              fetchPriority="high"
              decoding="async"
            />
            <span className="hero-photo-sheen" aria-hidden="true" />
            <figcaption>
              Payment technology · Photograph by Anna Shvets / Pexels
            </figcaption>
          </motion.figure>

          <button
            className={`hero-chip chip-detected ${heroStage === 0 ? "active" : ""}`}
            onMouseEnter={() => {
              setHeroStage(0);
              setHeroHeld(true);
            }}
            onFocus={() => {
              setHeroStage(0);
              setHeroHeld(true);
            }}
            onClick={() => w.navigate(`case/${featured.id}`)}
          >
            <span>It failed</span>
            <strong>
              {formatINR(featured.amount)} · {featured.rail}
            </strong>
            <small>{featured.failureReason}</small>
          </button>
          <button
            className={`hero-chip chip-evaluation ${heroStage === 1 ? "active" : ""}`}
            onMouseEnter={() => {
              setHeroStage(1);
              setHeroHeld(true);
            }}
            onFocus={() => {
              setHeroStage(1);
              setHeroHeld(true);
            }}
            onClick={() => w.navigate(`lab/${featured.id}`)}
          >
            <span>What can we try?</span>
            <strong>
              {featuredPermitted} allowed · {featuredBlocked} off the table
            </strong>
            <small>Rules run before any score</small>
          </button>
          <button
            className={`hero-chip chip-value ${heroStage === 2 ? "active" : ""}`}
            onMouseEnter={() => {
              setHeroStage(2);
              setHeroHeld(true);
            }}
            onFocus={() => {
              setHeroStage(2);
              setHeroHeld(true);
            }}
            onClick={() => w.navigate(`lab/${featured.id}`)}
          >
            <span>Best-value move</span>
            <strong>{featuredSelected.label}</strong>
            <small>
              {featuredSelected.expectedValue === undefined
                ? "No score needed for this call"
                : `${formatINR(featuredSelected.expectedValue, 2)} after costs`}
            </small>
          </button>
          <button
            className={`hero-chip chip-outcome ${heroStage === 3 ? "active" : ""}`}
            onMouseEnter={() => {
              setHeroStage(3);
              setHeroHeld(true);
            }}
            onFocus={() => {
              setHeroStage(3);
              setHeroHeld(true);
            }}
            onClick={() => w.navigate(`case/${featured.id}`)}
          >
            <span>Result</span>
            <strong>
              <Check size={13} /> Money recovered
            </strong>
            <small>Written to the record · {featured.id}</small>
          </button>

          <div className="hero-flow-glass">
            <RecoveryFlow />
          </div>
        </div>

        <div className="hero-bottom">
          <span>
            <ShieldCheck size={13} />
            Checked twice. Written down once. Nothing improvised.
          </span>
          <span className="hero-bottom-sim">
            Simulation environment · No live payment rails
          </span>
        </div>
      </section>

      <section className="overview-metrics" aria-label="Financial summary">
        <Metric
          title="Money at risk"
          value={m.atRisk}
          icon={<ArrowUpRight size={14} />}
          caption={`${w.cohort.length} failed debits in this view`}
        />
        <Metric
          title="Yet to come back"
          value={m.outstanding}
          icon={<Layers2 size={14} />}
          caption={`${m.active + m.escalations} cases still open`}
        />
        <Metric
          title="Share recovered"
          value={m.recoveryRate}
          format={(n) => `${n.toFixed(1)}%`}
          icon={<TrendingUp size={14} />}
          caption="Weighted by rupees, not case count"
          rate={m.recoveryRate}
        />
        <Metric
          title="In play now"
          value={m.active}
          format={(n) => Math.round(n).toString().padStart(2, "0")}
          icon={<Activity size={14} />}
          caption={`${m.escalations} waiting on a person`}
          onClick={() => w.navigate("cases?status=ACTIVE")}
        />
      </section>

      <PhotoStories />

      <div className="overview-analytics">
        <RevenuePulse
          input={w.cohort}
          range={w.range}
          setRange={w.setRange}
          end={w.at}
        />
        <IntelligenceInsights />
      </div>

      <div className="overview-secondary-grid">
        <section className="movement-section">
          <SectionHeading
            title="Where did the money go?"
            description="Follow each rupee to the outcome it actually reached."
            action={
              <button
                className="icon-button"
                onClick={exportSnapshot}
                aria-label="Export money movement snapshot"
              >
                <Download size={15} />
              </button>
            }
          />
          <MoneyMovement
            input={w.cohort}
            onBranch={(s) => w.navigate(`cases?status=${s}&range=${w.range}`)}
          />
        </section>
        <ActivityFeed />
      </div>

      <section className="strategy-section">
        <SectionHeading
          title="REVIO vs. the old playbooks"
          description="Same failed debits, four ways of handling them. REVIO doesn't always win—and it says so."
          action={
            <button
              className="text-link"
              onClick={() => w.navigate("outcomes")}
            >
              Full revenue analytics <ArrowRight size={13} />
            </button>
          }
        />
        <BaselineComparison rail={rail} setRail={setRail} />
      </section>
      <div className="overview-integrity-note">
        <ShieldCheck size={14} />
        <p>
          The honesty bit: every customer and outcome here is synthetic. No
          bank, PSP or production model is connected.{" "}
          <button onClick={() => w.navigate("trust")}>
            See what's simulated <ArrowUpRight size={11} />
          </button>
        </p>
      </div>
    </>
  );
}

function Metric({
  title,
  value,
  format,
  icon,
  caption,
  rate,
  onClick,
}: {
  title: string;
  value: number;
  format?: (n: number) => string;
  icon: React.ReactNode;
  caption: string;
  rate?: number;
  onClick?: () => void;
}) {
  return (
    <div className="overview-metric">
      <div className="metric-title">
        {title}
        <span>{icon}</span>
      </div>
      <div className="metric-value-row">
        <NumberFlow value={value} format={format} />
        {onClick && (
          <button
            className="metric-open"
            onClick={onClick}
            aria-label="View active recovery cases"
          >
            <ArrowUpRight size={15} />
          </button>
        )}
      </div>
      {rate !== undefined ? (
        <div className="metric-progress">
          <motion.i
            animate={{ width: `${rate}%` }}
            transition={{ duration: 0.45 }}
          />
        </div>
      ) : null}
      <span className="metric-caption">{caption}</span>
    </div>
  );
}

function IntelligenceInsights() {
  const w = useWorkspace();
  const m = getMetrics(w.cohort);
  const technical = getMetrics(
    w.cohort.filter((c) => c.failureCode === "BANK_TIMEOUT"),
  );
  const times = w.cohort
    .filter((c) => c.status === "RECOVERED")
    .sort(
      (a, b) =>
        new Date(a.recoveredAt!).getTime() - new Date(b.recoveredAt!).getTime(),
    )
    .map((c) => c.recoveryHours ?? 0);
  const timingPath = times
    .map(
      (t, i) =>
        `${i ? "L" : "M"}${2 + (i / Math.max(1, times.length - 1)) * 62} ${25 - (t / Math.max(1, ...times)) * 22}`,
    )
    .join(" ");
  const activeValue = w.cohort
    .filter((c) => c.status === "WAITING" || c.status === "ACTION PENDING")
    .reduce((s, c) => s + c.amount, 0);
  return (
    <aside className="intelligence-insights">
      <div className="intelligence-title">
        <span className="intelligence-symbol">
          <svg width="17" height="17" viewBox="0 0 20 20" fill="none">
            <path
              d="M3 13L8 8L11 11L17 4M11 4H17V10M3 4V17H17"
              stroke="currentColor"
              strokeWidth="1.4"
            />
          </svg>
        </span>
        <h2>Worth a closer look</h2>
        <Tooltip content="These are patterns in the synthetic cases you selected. They describe what happened; they don't prove why.">
          <button aria-label="About these patterns">
            <InfoIcon />
          </button>
        </Tooltip>
      </div>
      <div className="insight-lead">
        <span className="eyebrow">From this batch of cases</span>
        <p>
          <strong>
            {technical.atRisk
              ? `${technical.recoveryRate.toFixed(1)}%`
              : "No data"}
          </strong>
          {technical.atRisk
            ? " of bank-timeout value was recovered in this cohort."
            : " for bank-timeout cases in this range."}
        </p>
        <span>
          A bank timeout is not an empty account. It shouldn't get the same
          treatment.
        </span>
        <button onClick={() => w.navigate("outcomes")} className="text-link">
          Open the breakdown <ArrowRight size={12} />
        </button>
      </div>
      <div className="insight-mini-row">
        <span className="insight-line-icon">
          <Clock3 size={16} />
        </span>
        <div>
          <strong>{m.avgHours.toFixed(1)} hours</strong>
          <span>Typical time to get paid</span>
        </div>
        <svg
          width="66"
          height="27"
          viewBox="0 0 66 27"
          fill="none"
          role="img"
          aria-label="Recorded recovery durations in chronological order"
        >
          <path d={timingPath} stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </div>
      <button
        className="insight-mini-row actionable"
        onClick={() => w.navigate("cases?status=ACTIVE")}
      >
        <span className="insight-line-icon">
          <ArrowDownLeft size={16} />
        </span>
        <div>
          <strong>{formatINR(activeValue)} still waiting</strong>
          <span>{m.active} cases—not finished, not written off</span>
        </div>
        <ArrowUpRight size={13} />
      </button>
      <div className="constraint-health">
        <ShieldCheck size={16} />
        <span>
          <strong>{m.violations} rule breaches</strong>
          <small>{m.prevented} moves stopped before scoring</small>
        </span>
        <CircleCheck size={13} />
      </div>
    </aside>
  );
}
function InfoIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke="currentColor" />
      <path d="M8 7V11M8 4.5V5" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function ActivityFeed() {
  const w = useWorkspace();
  const ids = new Set(w.cohort.map((c) => c.id));
  const events = allJournalEntries
    .filter((e) => ids.has(e.caseId) && new Date(e.at).getTime() <= w.at)
    .slice(0, 5);
  return (
    <section className="activity-section">
      <SectionHeading
        title="Latest movement"
        description="Newest first. Open any line to see the case behind it."
        action={
          <button className="text-link" onClick={() => w.navigate("audit")}>
            View all <ArrowUpRight size={12} />
          </button>
        }
      />
      <div className="activity-feed">
        <AnimatePresence initial={false}>
          {events.map((e) => (
            <motion.button
              layout
              key={e.id}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="feed-row"
              onClick={() => w.navigate(`case/${e.caseId}`)}
            >
              <span
                className={`feed-icon ${e.stage === "OUTCOME" ? "success" : ""}`}
              >
                {e.stage === "OUTCOME" ? (
                  <Check size={13} />
                ) : e.stage === "CONSTRAIN" ? (
                  <ShieldCheck size={13} />
                ) : (
                  <Activity size={13} />
                )}
              </span>
              <span>
                <strong>
                  {e.type === "payment.recovered"
                    ? "Payment recovered"
                    : e.type === "payment.failed"
                      ? "Failure detected"
                      : e.stage === "CONSTRAIN"
                        ? "Constraints evaluated"
                        : e.stage === "PREDICT"
                          ? "Candidate estimates recorded"
                          : e.stage === "OPTIMIZE"
                            ? "Best permitted action selected"
                            : e.stage === "EXECUTE"
                              ? "Execution state recorded"
                              : "Recovery state updated"}
                </strong>
                <small>
                  {e.caseId} <i />
                  {formatINR(e.amount)}
                </small>
              </span>
              <time>
                {timeOnly(e.at)}
                <small>{dateOnly(e.at)}</small>
              </time>
            </motion.button>
          ))}
        </AnimatePresence>
        {events.length === 0 && (
          <p className="feed-empty">No recorded events in this cohort yet.</p>
        )}
      </div>
      <div className="feed-caption">
        <i />
        {w.replay
          ? "Replaying the synthetic event journal"
          : "Synthetic event journal / not a live payment feed"}
      </div>
    </section>
  );
}
