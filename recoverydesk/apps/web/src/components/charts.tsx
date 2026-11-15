import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  Info,
} from "lucide-react";
import {
  failureMeta,
  formatCompactINR,
  formatINR,
  getMetrics,
  type Rail,
  type RecoveryCase,
} from "../data/simulation";
import {
  baselineData,
  clock,
  pulseSeries,
  rangeOptions,
  type TimeRange,
} from "../data/workspace";
import { NumberFlow, SectionHeading, Segmented, Tooltip } from "./ui";

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(700);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(280, entry.contentRect.width)),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}
export function RevenuePulse({
  input,
  range,
  setRange,
  end = clock,
}: {
  input: RecoveryCase[];
  range: TimeRange;
  setRange: (r: TimeRange) => void;
  end?: number;
}) {
  const [mode, setMode] = useState<"recovered" | "atRisk" | "rate">(
    "recovered",
  );
  const [hover, setHover] = useState<number | null>(null);
  const { ref, width } = useWidth();
  const id = useId().replace(/:/g, "");
  const reduced = useReducedMotion();
  const data = useMemo(
    () => pulseSeries(input, range, end),
    [input, range, end],
  );
  const metrics = getMetrics(input);
  const h = width < 450 ? 220 : 225,
    left = width < 450 ? 48 : 54,
    right = 12,
    top = 16,
    bottom = 31;
  const plotW = width - left - right,
    plotH = h - top - bottom;
  const maxValue = Math.max(1, ...data.map((p) => p[mode]));
  const tickUnit =
    maxValue > 150000
      ? 50000
      : maxValue > 50000
        ? 25000
        : maxValue > 10000
          ? 10000
          : 2500;
  const max = mode === "rate" ? 100 : Math.ceil(maxValue / tickUnit) * tickUnit;
  const firstAt = data[0]?.at ?? 0;
  const lastAt = data[data.length - 1]?.at ?? firstAt + 1;
  const x = (i: number) =>
    left +
    (((data[i]?.at ?? firstAt) - firstAt) / Math.max(1, lastAt - firstAt)) *
      plotW;
  const y = (v: number) => top + plotH - (v / max) * plotH;
  const points = data.map((p, i) => ({ x: x(i), y: y(p[mode]) }));
  const path = points
    .map((p, i) =>
      i === 0
        ? `M ${p.x} ${p.y}`
        : `C ${(points[i - 1].x + p.x) / 2} ${points[i - 1].y} ${(points[i - 1].x + p.x) / 2} ${p.y} ${p.x} ${p.y}`,
    )
    .join(" ");
  const area = `${path} L ${x(data.length - 1)} ${top + plotH} L ${left} ${top + plotH} Z`;
  const inspectPointer = (
    clientX: number,
    rect: { left: number; width: number },
  ) => {
    const ratio = Math.max(
      0,
      Math.min(
        1,
        (((clientX - rect.left) / rect.width) * width - left) / plotW,
      ),
    );
    const target = firstAt + ratio * (lastAt - firstAt);
    let nearest = 0;
    data.forEach((point, i) => {
      if (
        Math.abs(point.at - target) <
        Math.abs((data[nearest]?.at ?? 0) - target)
      )
        nearest = i;
    });
    setHover(nearest);
  };
  const currentIndex = hover === null ? null : Math.min(hover, data.length - 1);
  const current = currentIndex === null ? null : data[currentIndex];
  const amount =
    mode === "recovered"
      ? metrics.recovered
      : mode === "atRisk"
        ? metrics.atRisk
        : metrics.recoveryRate;
  const format =
    mode === "rate" ? (v: number) => `${v.toFixed(1)}%` : formatINR;
  const tickEvery = Math.max(
    1,
    Math.ceil((data.length - 1) / (width < 430 ? 4 : 6)),
  );
  return (
    <section className="revenue-pulse" data-tour="outcomes">
      <SectionHeading
        title="Revenue pulse"
        description="A clearer view of every recovery."
        action={
          <Segmented
            label="Revenue pulse time range"
            value={range}
            onChange={setRange}
            options={rangeOptions}
          />
        }
      />
      <div className="pulse-meta">
        <div>
          <NumberFlow value={amount} format={format} className="pulse-total" />
          <span className="pulse-cohort">
            <i />
            {mode === "rate"
              ? `${input.length} cases in cohort`
              : mode === "recovered"
                ? `${input.filter((c) => c.status === "RECOVERED").length} successful recoveries`
                : `${input.length} failed payments`}
          </span>
        </div>
        <label className="chart-view-select">
          <span className="chart-dot" />
          <select
            aria-label="Revenue pulse metric"
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as typeof mode);
              setHover(null);
            }}
          >
            <option value="recovered">Recovered revenue</option>
            <option value="atRisk">At-risk revenue</option>
            <option value="rate">Recovery rate</option>
          </select>
          <ChevronDown size={12} />
        </label>
      </div>
      <div className="pulse-chart" ref={ref}>
        <svg
          width="100%"
          height={h}
          viewBox={`0 0 ${width} ${h}`}
          role="img"
          tabIndex={0}
          aria-label={`${mode}: ${format(amount)}. Use left and right arrows to inspect chart values.`}
          onPointerMove={(e) =>
            inspectPointer(e.clientX, e.currentTarget.getBoundingClientRect())
          }
          onPointerDown={(e) =>
            inspectPointer(e.clientX, e.currentTarget.getBoundingClientRect())
          }
          onPointerLeave={() => setHover(null)}
          onFocus={() => setHover(data.length - 1)}
          onBlur={() => setHover(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
              e.preventDefault();
              setHover((v) =>
                Math.max(
                  0,
                  Math.min(
                    data.length - 1,
                    (v ?? data.length - 1) + (e.key === "ArrowLeft" ? -1 : 1),
                  ),
                ),
              );
            }
          }}
        >
          <defs>
            <linearGradient id={`pulseFill${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563ff" stopOpacity=".17" />
              <stop offset="100%" stopColor="#2563ff" stopOpacity=".015" />
            </linearGradient>
          </defs>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line
                x1={left}
                x2={width - right}
                y1={y(max * t)}
                y2={y(max * t)}
                stroke="var(--line)"
                strokeDasharray="3 4"
              />
              <text
                x={left - 11}
                y={y(max * t) + 4}
                textAnchor="end"
                fill="var(--muted)"
                fontSize="9"
                fontFamily="Manrope Variable"
              >
                {mode === "rate"
                  ? `${Math.round(max * t)}%`
                  : max * t === 0
                    ? "0"
                    : formatCompactINR(max * t)}
              </text>
            </g>
          ))}
          {data.map(
            (p, i) =>
              (i % tickEvery === 0 || i === data.length - 1) && (
                <text
                  key={i}
                  x={x(i)}
                  y={h - 7}
                  fill="var(--muted)"
                  textAnchor={
                    i === 0 ? "start" : i === data.length - 1 ? "end" : "middle"
                  }
                  fontSize="9"
                  fontFamily="Manrope Variable"
                >
                  {p.label}
                </text>
              ),
          )}
          {data.length > 1 && (
            <>
              <motion.path
                key={`a-${mode}-${range}`}
                d={area}
                fill={`url(#pulseFill${id})`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4 }}
              />
              <motion.path
                key={`p-${mode}-${range}`}
                d={path}
                fill="none"
                stroke="var(--blue)"
                strokeWidth="2.6"
                initial={reduced ? false : { pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.55, ease: "easeOut" }}
                strokeLinecap="round"
              />
              <circle
                cx={x(data.length - 1)}
                cy={y(data[data.length - 1][mode])}
                r="4"
                fill="var(--blue)"
                stroke="var(--surface)"
                strokeWidth="2.5"
              />
            </>
          )}
          {current && currentIndex !== null && (
            <g>
              <line
                x1={x(currentIndex)}
                x2={x(currentIndex)}
                y1={top}
                y2={top + plotH}
                stroke="var(--blue)"
                strokeOpacity=".4"
                strokeDasharray="3 4"
              />
              <circle
                cx={x(currentIndex)}
                cy={y(current[mode])}
                r="8"
                fill="var(--blue)"
                fillOpacity=".12"
              />
              <circle
                cx={x(currentIndex)}
                cy={y(current[mode])}
                r="4"
                fill="var(--blue)"
                stroke="var(--surface)"
                strokeWidth="2"
              />
            </g>
          )}
        </svg>
        <AnimatePresence>
          {current && currentIndex !== null && (
            <motion.div
              className="chart-tooltip"
              role="status"
              style={{
                left: Math.max(55, Math.min(width - 180, x(currentIndex) - 75)),
                top: 4,
              }}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <small>{current.label} / synthetic cohort</small>
              <strong>{format(current[mode])}</strong>
              <span>
                {current.recoveredCount} recovered of{" "}
                {
                  input.filter(
                    (c) => new Date(c.createdAt).getTime() <= current.at,
                  ).length
                }{" "}
                observed cases
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="chart-footnote">
        <span>
          <span className="legend-line" />
          {mode === "rate"
            ? "Recovered value / at-risk value"
            : "Cumulative value within selected cohort"}
        </span>
        <Tooltip content="The time range selects cases by original failure date. Daily points show their cumulative state. Lines interpolate recorded observations, not model forecasts.">
          <button aria-label="Revenue chart methodology">
            <Info size={12} />
          </button>
        </Tooltip>
      </div>
    </section>
  );
}

export function MoneyMovement({
  input,
  onBranch,
}: {
  input: RecoveryCase[];
  onBranch: (status: string) => void;
}) {
  const [active, setActive] = useState<string | null>(null);
  const m = getMetrics(input);
  const branches = [
    {
      key: "RECOVERED",
      label: "Recovered",
      value: m.recovered,
      color: "#36b795",
      count: input.filter((c) => c.status === "RECOVERED").length,
    },
    {
      key: "ACTIVE",
      label: "Active recovery",
      value: input
        .filter((c) => c.status === "WAITING" || c.status === "ACTION PENDING")
        .reduce((s, c) => s + c.amount, 0),
      color: "#3974fa",
      count: m.active,
    },
    {
      key: "STOPPED",
      label: "Stopped",
      value: m.stopped,
      color: "#aebbd3",
      count: input.filter((c) => c.status === "STOPPED").length,
    },
    {
      key: "ESCALATED",
      label: "Escalated",
      value: input
        .filter((c) => c.status === "ESCALATED")
        .reduce((s, c) => s + c.amount, 0),
      color: "#dfad55",
      count: m.escalations,
    },
  ];
  let running = 65;
  const mapped = branches.map((b, i) => {
    const thick = m.atRisk ? (b.value / m.atRisk) * 120 : 0;
    const start = running + thick / 2;
    running += thick;
    return { ...b, thick, start, end: 39 + i * 63 };
  });
  return (
    <div className="money-movement">
      <svg
        viewBox="0 0 620 280"
        role="group"
        aria-label="Flow of synthetic at-risk revenue into recovered, active, stopped and escalated value"
      >
        <text
          x="0"
          y="34"
          fill="var(--muted)"
          fontSize="10"
          fontFamily="Manrope Variable"
        >
          REVENUE AT RISK
        </text>
        <text
          x="0"
          y="59"
          fill="var(--text)"
          fontSize="23"
          fontWeight="700"
          fontFamily="Manrope Variable"
        >
          {formatINR(m.atRisk)}
        </text>
        <rect x="91" y="65" width="5" height="120" fill="#7596dd" />
        {mapped.map((b) => (
          <g
            key={b.key}
            className="money-branch"
            tabIndex={0}
            role="button"
            aria-label={`${b.label}: ${formatINR(b.value)}, ${b.count} cases. Open filtered queue.`}
            onMouseEnter={() => setActive(b.key)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(b.key)}
            onBlur={() => setActive(null)}
            onClick={() => onBranch(b.key)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onBranch(b.key);
            }}
          >
            <path
              d={`M97 ${b.start}C230 ${b.start} 247 ${b.end} 404 ${b.end}`}
              fill="none"
              stroke={b.color}
              strokeWidth={b.thick}
              strokeOpacity={
                active && active !== b.key ? 0.1 : active === b.key ? 0.6 : 0.3
              }
            />
            <path
              d={`M97 ${b.start}C230 ${b.start} 247 ${b.end} 404 ${b.end}`}
              fill="none"
              stroke={b.color}
              strokeWidth="1"
              strokeOpacity=".6"
            />
            <rect
              x="405"
              y={b.end - Math.max(b.thick / 2, 2)}
              width="4"
              height={Math.max(b.thick, 4)}
              fill={b.color}
            />
            <circle cx="432" cy={b.end - 5} r="3" fill={b.color} />
            <text
              x="444"
              y={b.end - 2}
              fill="var(--secondary)"
              fontSize="11"
              fontFamily="Manrope Variable"
            >
              {b.label}
            </text>
            <text
              x="444"
              y={b.end + 18}
              fill="var(--text)"
              fontSize="17"
              fontWeight="650"
              fontFamily="Manrope Variable"
            >
              {formatINR(b.value)}
            </text>
            <text
              x="606"
              y={b.end + 4}
              fill="var(--muted)"
              fontSize="10"
              textAnchor="end"
              fontFamily="Manrope Variable"
            >
              {b.count} cases
            </text>
          </g>
        ))}
        <text
          x="0"
          y="212"
          fill="var(--muted)"
          fontSize="10"
          fontFamily="Manrope Variable"
        >
          {input.length} synthetic cases
        </text>
        <text
          x="0"
          y="229"
          fill="var(--muted)"
          fontSize="9"
          fontFamily="Manrope Variable"
        >
          Each rupee, accounted for.
        </text>
      </svg>
      <div className="money-mobile-total">
        <span>Revenue at risk</span>
        <strong className="financial">{formatINR(m.atRisk)}</strong>
      </div>
      <div className="money-mobile-list">
        {branches.map((b) => (
          <button key={b.key} onClick={() => onBranch(b.key)}>
            <i style={{ background: b.color }} />
            <span>{b.label}</span>
            <strong>{formatINR(b.value)}</strong>
            <ArrowUpRight size={12} />
          </button>
        ))}
      </div>
      <p className="note">
        <span className="money-desktop-note">
          Path width represents financial value.{" "}
        </span>
        Select an outcome to inspect its cases.
      </p>
    </div>
  );
}

export function BaselineComparison({
  rail,
  setRail,
}: {
  rail: "ALL" | Rail;
  setRail?: (r: "ALL" | Rail) => void;
}) {
  const [metric, setMetric] = useState<"net" | "recovered">("net");
  const [selected, setSelected] = useState("REVIO");
  const rows = baselineData(rail).map((b) => ({
    ...b,
    value: metric === "net" ? b.recovered - b.cost : b.recovered,
  }));
  const max = Math.max(1, ...rows.map((r) => r.value));
  const winner = [...rows].sort((a, b) => b.value - a.value)[0];
  const inspected = rows.find((r) => r.id === selected)!;
  return (
    <div className="baseline-chart">
      <div className="baseline-controls">
        {setRail && (
          <Segmented
            label="Baseline payment rail"
            value={rail}
            onChange={setRail}
            options={[
              { value: "ALL", label: "All rails" },
              { value: "UPI AutoPay", label: "UPI AutoPay" },
              { value: "Card SI", label: "Card SI" },
            ]}
          />
        )}
        <select
          className="field"
          aria-label="Baseline financial metric"
          value={metric}
          onChange={(e) => setMetric(e.target.value as typeof metric)}
        >
          <option value="net">Net recovered value</option>
          <option value="recovered">Gross recovered value</option>
        </select>
      </div>
      {rows.map((r, i) => (
        <button
          key={r.id}
          className={`baseline-row ${selected === r.id ? "selected" : ""}`}
          onClick={() => setSelected(r.id)}
        >
          <span className="baseline-label">
            <strong>{r.id === "REVIO" ? "REVIO" : r.name}</strong>
            <small>
              {r.id === "REVIO"
                ? "Intelligent constrained decisions"
                : `${r.id} / ${r.description}`}
            </small>
          </span>
          <span className="baseline-track">
            <motion.span
              style={{ background: r.color }}
              initial={{ width: 0 }}
              animate={{ width: `${(r.value / max) * 100}%` }}
              transition={{ duration: 0.4, delay: i * 0.04 }}
            />
            {winner.id === r.id && (
              <span className="baseline-winner">
                <Check size={10} />
                Leads this view
              </span>
            )}
          </span>
          <strong className="financial">{formatINR(r.value)}</strong>
        </button>
      ))}
      <div className="baseline-conclusion">
        <span className="conclusion-icon">
          <ChartGlyph />
        </span>
        <p>
          <strong>
            {winner.id === "REVIO"
              ? "REVIO leads this synthetic comparison."
              : `${winner.id} outperforms REVIO in this segment.`}
          </strong>
          <span>
            {winner.id !== "REVIO"
              ? "The result is visible by design. Intelligence is not a guaranteed win."
              : "A fixed-cohort comparison, not a claim of production uplift."}
          </span>
        </p>
        <div>
          <small>{inspected.id} intervention cost</small>
          <strong className="financial">{formatINR(inspected.cost, 2)}</strong>
        </div>
      </div>
      <p className="note baseline-note">
        Precomputed strategy outcomes on the same full-batch risk cohort. This
        comparison follows the rail selector only; time and failure filters do
        not change the declared baseline snapshots.
      </p>
    </div>
  );
}
function ChartGlyph() {
  return (
    <svg width="19" height="19" viewBox="0 0 20 20" fill="none">
      <path d="M3 16V9M9 16V4M15 16V7" stroke="currentColor" strokeWidth="2" />
      <path d="M2 19H18" stroke="currentColor" />
    </svg>
  );
}

export function FailurePerformance({ input }: { input: RecoveryCase[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const data = Object.entries(failureMeta)
    .map(([code, meta]) => {
      const cohort = input.filter((c) => c.failureCode === code);
      const m = getMetrics(cohort);
      return { ...m, label: meta.short, code, count: cohort.length };
    })
    .filter((r) => r.count);
  return (
    <div className="failure-performance">
      {data.map((r) => (
        <button
          key={r.code}
          className={hover === r.code ? "active" : ""}
          onClick={() => setHover(hover === r.code ? null : r.code)}
          onMouseEnter={() => setHover(r.code)}
          onMouseLeave={() => setHover(null)}
        >
          <span>
            <strong>{r.label}</strong>
            <small>
              {r.count} cases / {formatINR(r.atRisk)} at risk
            </small>
          </span>
          <span className="performance-bar">
            <motion.i
              initial={{ width: 0 }}
              animate={{ width: `${r.recoveryRate}%` }}
              transition={{ duration: 0.4 }}
            />
          </span>
          <span className="financial">{r.recoveryRate.toFixed(1)}%</span>
          {hover === r.code && (
            <span className="inline-chart-detail">
              {formatINR(r.recovered)} recovered in this failure class
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

export function TimeDistribution({ input }: { input: RecoveryCase[] }) {
  const [active, setActive] = useState(2);
  const bins = [
    { label: "< 2h", min: 0, max: 2 },
    { label: "2 - 8h", min: 2, max: 8 },
    { label: "8 - 24h", min: 8, max: 24 },
    { label: "24 - 48h", min: 24, max: 48 },
    { label: "48h+", min: 48, max: Infinity },
  ].map((b) => {
    const cohort = input.filter(
      (c) =>
        c.status === "RECOVERED" &&
        (c.recoveryHours ?? 0) >= b.min &&
        (c.recoveryHours ?? 0) < b.max,
    );
    return {
      ...b,
      count: cohort.length,
      amount: cohort.reduce((s, c) => s + c.amount, 0),
    };
  });
  const max = Math.max(1, ...bins.map((b) => b.count));
  return (
    <div>
      <div className="timing-bars">
        {bins.map((b, i) => (
          <button
            key={b.label}
            className={i === active ? "active" : ""}
            onClick={() => setActive(i)}
            onMouseEnter={() => setActive(i)}
          >
            <strong>{b.count}</strong>
            <motion.span
              animate={{ height: Math.max(2, (b.count / max) * 150) }}
              transition={{ duration: 0.4 }}
            />
            <small>{b.label}</small>
          </button>
        ))}
      </div>
      <div className="timing-summary">
        <span>{bins[active].label} to recovery</span>
        <strong>{bins[active].count} cases</strong>
        <span className="financial blue">{formatINR(bins[active].amount)}</span>
      </div>
      <p className="note">
        Time from original failure to confirmed outcome. Recovered cases only;
        open cases have no invented recovery time.
      </p>
    </div>
  );
}

export function RailPerformance({ input }: { input: RecoveryCase[] }) {
  return (
    <div className="rail-performance">
      {(["UPI AutoPay", "Card SI"] as Rail[]).map((rail, i) => {
        const cohort = input.filter((c) => c.rail === rail);
        const m = getMetrics(cohort);
        return (
          <div key={rail}>
            <div className="rail-name">
              <span className={`rail-symbol ${i ? "card" : ""}`}>
                {i ? (
                  <svg width="18" height="14" viewBox="0 0 18 14">
                    <rect
                      x="1"
                      y="1"
                      width="16"
                      height="12"
                      rx="2"
                      stroke="currentColor"
                      fill="none"
                    />
                    <path d="M1 5H17M4 10H7" stroke="currentColor" />
                  </svg>
                ) : (
                  "UPI"
                )}
              </span>
              <strong>{rail}</strong>
              <span>{cohort.length} cases</span>
            </div>
            <div className="rail-numbers">
              <strong className="financial">
                {m.recoveryRate.toFixed(1)}
                <small>%</small>
              </strong>
              <span className="financial">
                {formatINR(m.recovered)}
                <small>recovered</small>
              </span>
            </div>
            <div className="rail-track">
              <motion.span
                animate={{ width: `${m.recoveryRate}%` }}
                style={{ background: i ? "#84a4f1" : "#2563ff" }}
              />
            </div>
            <span className="note">of {formatINR(m.atRisk)} at risk</span>
          </div>
        );
      })}
    </div>
  );
}

export function ActionMix({
  input,
  navigate,
}: {
  input: RecoveryCase[];
  navigate: (route: string) => void;
}) {
  const [active, setActive] = useState<string | null>(null);
  const groups = Array.from(new Set(input.map((c) => c.strategy)))
    .map((label) => ({
      label,
      cohort: input.filter((c) => c.strategy === label),
    }))
    .sort((a, b) => b.cohort.length - a.cohort.length);
  return (
    <div className="action-mix">
      {groups.map((g) => (
        <div key={g.label}>
          <button
            onClick={() => setActive(active === g.label ? null : g.label)}
            aria-expanded={active === g.label}
          >
            <span>{g.label}</span>
            <span className="action-mix-bar">
              <i
                style={{ width: `${(g.cohort.length / input.length) * 100}%` }}
              />
            </span>
            <strong>{g.cohort.length}</strong>
            <ChevronDown size={12} />
          </button>
          <AnimatePresence>
            {active === g.label && (
              <motion.div
                className="action-mix-cases"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
              >
                {g.cohort.map((c) => (
                  <button key={c.id} onClick={() => navigate(`case/${c.id}`)}>
                    <span>{c.id}</span>
                    <strong>{formatINR(c.amount)}</strong>
                    <ArrowRight size={12} />
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}
