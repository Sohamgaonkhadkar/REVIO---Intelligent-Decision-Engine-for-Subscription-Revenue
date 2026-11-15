import { useInView, useReducedMotion } from "motion/react";
import { useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { cases, formatINR, type RecoveryCase } from "../data/simulation";

export const decisionStages = [
  "Constraints",
  "Prediction",
  "Expected value",
  "Selection",
  "Execution",
];
export function stageExplanation(c: RecoveryCase, stage: number) {
  const chosen = c.candidates.find((a) => a.selected)!;
  const legal = c.candidates.filter((a) => a.eligible);
  const blocked = c.candidates.filter((a) => !a.eligible);
  const scored = c.candidates.filter((a) => a.probability !== undefined);
  return [
    {
      title: "Permission comes first.",
      detail: `${legal.length} candidates permitted. ${blocked.length} rejected before scoring. Retry and contact budgets, mandate eligibility, quiet hours and operational guards are checked first.`,
      fact: `${legal.length} permitted / ${blocked.length} blocked`,
      label: "Deterministic rule snapshot",
    },
    {
      title: "Estimate. Never authorize.",
      detail: `${scored.length} eligible candidates have precomputed illustrative estimates in the 32-feature model fixture. These scores are uncalibrated; no XGBoost model runs in this browser.`,
      fact:
        chosen.probability === undefined
          ? "No estimate for a control action"
          : `${Math.round(chosen.probability * 100)}% selected-action estimate`,
      label: "XGBoost-shaped simulation snapshot",
    },
    {
      title: "Make probability accountable.",
      detail: `Expected value multiplies the estimate by ${formatINR(c.amount)}, then deducts intervention cost. Only eligible, scored actions enter the economic ranking.`,
      fact:
        chosen.expectedValue === undefined
          ? "Terminal action / no calculated EV"
          : `${formatINR(chosen.expectedValue, 2)} expected value`,
      label: "Probability x value - cost",
    },
    {
      title: "The best permissible next move.",
      detail:
        chosen.id === "stop"
          ? "Terminal policy stops recovery. No remaining candidate has a positive expected value, and additional debit attempts are prohibited."
          : `${chosen.label} is the highest-value eligible action in this recorded snapshot. Exploring another candidate here does not change the historical selection.`,
      fact: chosen.label,
      label: "Recorded engine selection",
    },
    {
      title:
        chosen.id === "wait" || chosen.id === "stop"
          ? "Not acting is also a decision."
          : c.status === "ACTION PENDING"
            ? "Authorization is still pending."
            : "Guarded again at execution.",
      detail:
        chosen.id === "wait" || chosen.id === "stop"
          ? "No customer contact or payment is dispatched. The deferral or stop outcome is retained in the journal."
          : c.status === "ACTION PENDING"
            ? "A future action is recorded. The simulated gateway must reverify current constraints before authorization; nothing has been dispatched."
            : `The record includes a gateway reverification before simulated dispatch. ${c.outcomeNote}`,
      fact:
        c.status === "RECOVERED"
          ? `${formatINR(c.amount)} recovered in simulation`
          : c.status === "ACTION PENDING"
            ? "Queued / not dispatched"
            : c.status.toLowerCase(),
      label: "Execution evidence, not a payment control",
    },
  ][stage];
}

export function RecoveryFlow({ c = cases[0] }: { c?: RecoveryCase }) {
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(true);
  const root = useRef<HTMLDivElement>(null);
  const visible = useInView(root);
  const reduced = useReducedMotion();
  const selected = c.candidates.find((a) => a.selected)!;
  const nodes = [
    { x: 164, y: 143, label: "CONSTRAIN", sub: "Rules first", stage: 0 },
    { x: 296, y: 143, label: "PREDICT", sub: "32 features", stage: 1 },
    { x: 423, y: 143, label: "OPTIMIZE", sub: "Value over volume", stage: 2 },
    { x: 551, y: 95, label: "RECOVER", sub: formatINR(c.amount), stage: 4 },
  ];
  const path =
    "M24 143H144 M184 143H266 M326 143H403 M443 143H465Q487 143 487 121V117Q487 95 509 95H533";
  const signal = "M24 143H465Q487 143 487 121V117Q487 95 509 95H551";
  const explain =
    active < 0
      ? { fact: `${formatINR(c.amount)} / ${c.failureReason.toLowerCase()}.` }
      : stageExplanation(c, active);
  return (
    <div className="recovery-flow" ref={root}>
      <div className="flow-caption">
        <span>
          <i /> REVIO DECISION ENGINE
        </span>
        <span className="flow-example-label">
          RECORDED EXAMPLE / {c.id.slice(-4)}
        </span>
        <button
          onClick={() => setPlaying(!playing)}
          aria-label={playing ? "Pause recovery flow" : "Play recovery flow"}
        >
          {playing ? <Pause size={12} /> : <Play size={12} />}
        </button>
      </div>
      <svg
        viewBox="0 0 620 268"
        className="recovery-flow-svg"
        role="group"
        aria-label="Interactive synthetic recovery routing engine"
      >
        <defs>
          <pattern
            id="engineGrid"
            width="32"
            height="32"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M32 0H0V32"
              fill="none"
              stroke="white"
              strokeOpacity=".07"
              strokeWidth=".7"
            />
          </pattern>
          <linearGradient id="engineBeam" x1="0" x2="1">
            <stop stopColor="#76acff" />
            <stop offset=".5" stopColor="#dcecff" />
            <stop offset="1" stopColor="#9ef5db" />
          </linearGradient>
        </defs>
        <rect
          x="6"
          y="5"
          width="604"
          height="252"
          fill="url(#engineGrid)"
          opacity=".65"
        />
        <path
          d="M24 59H92Q117 59 117 84V118Q117 143 142 143M24 228H92Q117 228 117 203V168Q117 143 142 143"
          fill="none"
          stroke="#86b2ff"
          strokeWidth="1"
          opacity=".3"
        />
        <path
          d="M164 162V196Q164 216 185 216H252"
          fill="none"
          stroke="#ffb8bc"
          strokeOpacity=".65"
          strokeWidth="1.2"
          strokeDasharray="3 4"
        />
        <path
          d="M423 163V196Q423 216 445 216H550"
          fill="none"
          stroke="#97c1ff"
          strokeWidth="1"
          strokeOpacity=".4"
        />
        <path
          d={path}
          fill="none"
          stroke="#96c4ff"
          strokeWidth="8"
          strokeOpacity=".08"
        />
        <path
          d={path}
          fill="none"
          stroke="url(#engineBeam)"
          strokeWidth="1.6"
        />
        <g fill="#9ec8ff">
          <circle cx="24" cy="59" r="3" />
          <circle cx="24" cy="228" r="3" />
        </g>
        <g
          transform="translate(23 130)"
          role="button"
          tabIndex={0}
          aria-label="Inspect detected payment failure"
          className="engine-node"
          onMouseEnter={() => setActive(-1)}
          onFocus={() => setActive(-1)}
          onClick={() => setActive(-1)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setActive(-1);
            }
          }}
        >
          <rect
            width="27"
            height="27"
            rx="7"
            fill="#5686ff"
            stroke="#a5c5ff"
            strokeWidth=".7"
          />
          <path d="M13 6V14M13 19V20" stroke="white" strokeWidth="1.6" />
        </g>
        <text
          x="27"
          y="113"
          fill="#dce8ff"
          fontSize="10"
          fontFamily="Manrope Variable"
        >
          Failed payment
        </text>
        <text
          x="25"
          y="185"
          fill="#dce8ff"
          fontSize="10"
          fontFamily="IBM Plex Mono"
        >
          {formatINR(c.amount)}
        </text>
        {nodes.map((n) => (
          <g
            key={n.stage}
            role="button"
            tabIndex={0}
            aria-label={`Inspect ${n.label.toLowerCase()}`}
            onClick={() => setActive(n.stage)}
            onMouseEnter={() => setActive(n.stage)}
            onFocus={() => setActive(n.stage)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setActive(n.stage);
              }
            }}
            className={`engine-node ${active === n.stage ? "active" : ""}`}
          >
            <rect
              x={n.x - 33}
              y={n.y - 33}
              width="66"
              height="66"
              rx="13"
              fill="transparent"
            />
            {n.stage === 1 ? (
              <>
                <rect
                  x={n.x - 32}
                  y={n.y - 32}
                  width="64"
                  height="64"
                  rx="15"
                  fill="#336bf8"
                  stroke="#a9ccff"
                  strokeOpacity=".4"
                />
                <rect
                  x={n.x - 24}
                  y={n.y - 24}
                  width="48"
                  height="48"
                  rx="10"
                  fill="#eef5ff"
                />
                <path
                  d={`M${n.x - 10} ${n.y + 11}V${n.y - 12}H${n.x + 3}Q${n.x + 15} ${n.y - 12} ${n.x + 15} ${n.y - 2}Q${n.x + 15} ${n.y + 6} ${n.x + 3} ${n.y + 6}H${n.x - 3}L${n.x + 8} ${n.y + 17}`}
                  fill="none"
                  stroke="#2563ff"
                  strokeWidth="4"
                />
              </>
            ) : (
              <>
                <rect
                  x={n.x - 19}
                  y={n.y - 19}
                  width="38"
                  height="38"
                  rx={n.stage === 4 ? 19 : 10}
                  fill={n.stage === 4 ? "#defff0" : "#3b72f7"}
                  stroke={n.stage === 4 ? "#9cf0d0" : "#bed9ff"}
                  strokeWidth="1"
                />
                {n.stage === 0 ? (
                  <path
                    d={`M${n.x} ${n.y - 9}L${n.x + 8} ${n.y - 5}V${n.y + 1}Q${n.x + 8} ${n.y + 7} ${n.x} ${n.y + 11}Q${n.x - 8} ${n.y + 7} ${n.x - 8} ${n.y + 1}V${n.y - 5}Z`}
                    fill="none"
                    stroke="white"
                    strokeWidth="1.4"
                  />
                ) : n.stage === 2 ? (
                  <path
                    d={`M${n.x - 7} ${n.y + 7}V${n.y}M${n.x} ${n.y + 7}V${n.y - 4}M${n.x + 7} ${n.y + 7}V${n.y - 9}`}
                    stroke="white"
                    strokeWidth="2"
                  />
                ) : (
                  <path
                    d={`M${n.x - 7} ${n.y}L${n.x - 2} ${n.y + 5}L${n.x + 8} ${n.y - 5}`}
                    fill="none"
                    stroke="#0c9d71"
                    strokeWidth="2"
                  />
                )}
              </>
            )}
            <text
              x={n.x}
              y={n.y - (n.stage === 1 ? 48 : 36)}
              textAnchor="middle"
              fill="white"
              fontSize="9"
              fontWeight="700"
              letterSpacing="1.3"
              fontFamily="Manrope Variable"
            >
              {n.label}
            </text>
            <text
              x={n.x}
              y={n.y + (n.stage === 1 ? 49 : 37)}
              textAnchor="middle"
              fill="#c5d9ff"
              fontSize={n.stage === 4 ? 13 : 10}
              fontFamily={n.stage === 4 ? "IBM Plex Mono" : "Manrope Variable"}
            >
              {n.sub}
            </text>
          </g>
        ))}
        <g fill="#ffc9cc">
          <circle
            cx="261"
            cy="216"
            r="9"
            fill="#3461df"
            stroke="#e5a7bd"
            strokeWidth=".8"
          />
          <path
            d="M258 213L264 219M264 213L258 219"
            stroke="#ffc9cc"
            strokeWidth="1.3"
          />
          <text x="181" y="243" fontSize="9" fontFamily="Manrope Variable">
            Retry now / blocked
          </text>
        </g>
        <circle
          cx="551"
          cy="216"
          r="7"
          fill="#4078f4"
          stroke="#9bc3ff"
          strokeWidth="1"
        />
        <path d="M548 214V218M553 214V218" stroke="#c5d9ff" strokeWidth="1" />
        <text
          x="454"
          y="243"
          fill="#b5d0ff"
          fontSize="9"
          fontFamily="Manrope Variable"
        >
          Wait / lower expected value
        </text>
        <g
          role="button"
          tabIndex={0}
          aria-label="Inspect recorded selected action"
          className="engine-node"
          onMouseEnter={() => setActive(3)}
          onFocus={() => setActive(3)}
          onClick={() => setActive(3)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setActive(3);
            }
          }}
        >
          <rect
            x="475"
            y="147"
            width="125"
            height="30"
            rx="4"
            fill="transparent"
          />
          <text
            x="493"
            y="165"
            fill="#d8e8ff"
            fontSize="9"
            fontFamily="Manrope Variable"
          >
            {selected.label}
          </text>
        </g>
        {visible && playing && !reduced && (
          <g>
            <circle r="3.4" fill="#e4f6ff">
              <animateMotion dur="6s" repeatCount="indefinite" path={signal} />
            </circle>
            <circle r="9" fill="#d1edff" opacity=".17">
              <animateMotion dur="6s" repeatCount="indefinite" path={signal} />
            </circle>
          </g>
        )}
      </svg>
      <div className="flow-mobile-stages">
        {nodes.map((n, i) => (
          <button
            key={n.stage}
            onClick={() => setActive(n.stage)}
            className={active === n.stage ? "active" : ""}
          >
            <span>0{i + 1}</span>
            <strong>
              {n.label.toLowerCase()}
              <small>{n.sub}</small>
            </strong>
          </button>
        ))}
      </div>
      <div className="engine-inspector" aria-live="polite">
        <span className="engine-inspector-dot" />
        <strong>{active < 0 ? "Detect" : decisionStages[active]}</strong>
        <span>
          {active === 0
            ? "Rules checked. Immediate retry blocked."
            : active === 1
              ? `${Math.round((selected.probability ?? 0) * 100)}% illustrative estimate. Never an authorization.`
              : active === 2
                ? `${formatINR(selected.expectedValue ?? 0, 2)} expected value after costs.`
                : explain.fact}
        </span>
      </div>
    </div>
  );
}
