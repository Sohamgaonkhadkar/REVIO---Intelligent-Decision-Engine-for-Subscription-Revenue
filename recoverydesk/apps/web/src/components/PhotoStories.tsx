import {
  AnimatePresence,
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import { useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CircleCheck,
  Gauge,
  Layers3,
  ShieldCheck,
} from "lucide-react";
import { cases, failureMeta, formatINR } from "../data/simulation";
import { useWorkspace } from "../state/Workspace";

export const HERO_IMAGE =
  "/images/recovery-workspace.jpg";
const PHONE_IMAGE =
  "/images/payment-context.jpg";
const SERVER_IMAGE =
  "/images/infrastructure.jpg";
const ARCHITECTURE_IMAGE =
  "/images/architecture.jpg";

export function ParallaxImage({
  src,
  alt,
  credit,
  className = "",
  eager = false,
}: {
  src: string;
  alt: string;
  credit: string;
  className?: string;
  eager?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [18, -18]);
  return (
    <motion.figure
      ref={ref}
      className={`parallax-image ${className}`}
      initial={reduced ? false : { opacity: 0.35, clipPath: "inset(0 0 12% 0)" }}
      whileInView={{ opacity: 1, clipPath: "inset(0 0 0% 0)" }}
      viewport={{ once: true, amount: 0.28 }}
      transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
    >
      <motion.img
        src={src}
        alt={alt}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
        fetchPriority={eager ? "high" : "low"}
        style={reduced ? undefined : { y, scale: 1.09 }}
      />
      <span className="image-light" aria-hidden="true" />
      <figcaption>{credit}</figcaption>
    </motion.figure>
  );
}

const intelligenceSteps = [
  {
    title: "Rules",
    heading: "If it isn't allowed, it doesn't happen.",
    body: "Three retries. Two contacts. No calls at night. If the mandate is dead, the debit is off the table—whatever the score says.",
    icon: ShieldCheck,
  },
  {
    title: "Probability",
    heading: "A score is a clue, not a green light.",
    body: "Only the allowed moves get an estimate from the 32-feature fixture. The numbers are illustrative and uncalibrated, so REVIO treats them as ranking help—not truth.",
    icon: Gauge,
  },
  {
    title: "Economics",
    heading: "Worth doing? Do the maths.",
    body: "A likely recovery can still be a bad deal once you price the retry, the message and the customer's patience. Expected value keeps that honest.",
    icon: Layers3,
  },
  {
    title: "Execution",
    heading: "Checked again at the door.",
    body: "Things change between choosing a move and making it. The gateway checks the guard state again, then writes down what happened.",
    icon: CircleCheck,
  },
];

export function PhotoStories() {
  const w = useWorkspace();
  const [failureIndex, setFailureIndex] = useState(0);
  const [step, setStep] = useState(0);
  const failureCases = [cases[0], cases[2], cases[9]];
  const activeCase = failureCases[failureIndex];
  const selected = activeCase.candidates.find((a) => a.selected)!;
  const StepIcon = intelligenceSteps[step].icon;

  return (
    <div className="photo-stories">
      <section className="photo-story story-failure">
        <ParallaxImage
          src={PHONE_IMAGE}
          alt="A smartphone and payment card resting in soft daylight, representing a recurring digital payment"
          credit="Photograph by Ivan S / Pexels"
          className="story-media story-media-left"
        />
        <div className="story-copy">
          <span className="eyebrow blue">When a debit fails</span>
          <h2>A declined debit isn't a lost customer.</h2>
          <p>
            Maybe the salary lands tomorrow. Maybe the card expired last month.
            Maybe the bank simply dropped the request. REVIO reads the failure
            before it touches the customer again.
          </p>
          <div
            className="story-case-tabs"
            role="group"
            aria-label="Choose a failure story"
          >
            {failureCases.map((c, i) => (
              <button
                key={c.id}
                className={failureIndex === i ? "active" : ""}
                onClick={() => setFailureIndex(i)}
                aria-pressed={failureIndex === i}
              >
                {failureMeta[c.failureCode].short}
              </button>
            ))}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeCase.id}
              className="failure-transform"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.28 }}
            >
              <div className="failure-note">
                <span>The debit failed</span>
                <strong className="financial">{formatINR(activeCase.amount)}</strong>
                <small>
                  {activeCase.failureReason} · {activeCase.rail}
                </small>
              </div>
              <span className="transform-arrow">
                <ArrowRight size={16} />
              </span>
              <div className="case-note">
                <span>REVIO opened a case</span>
                <strong>{selected.label}</strong>
                <small className="mono">{activeCase.id}</small>
              </div>
            </motion.div>
          </AnimatePresence>
          <button
            className="text-link"
            onClick={() => w.navigate(`case/${activeCase.id}`)}
          >
            See what happened next <ArrowUpRight size={13} />
          </button>
          <p className="story-context-note">
            This photograph is context, not evidence. It is not a UPI AutoPay
            mandate debit, and no live bank is connected here.
          </p>
        </div>
      </section>

      <section className="photo-story story-intelligence">
        <div className="story-copy">
          <span className="eyebrow blue">Why not just retry?</span>
          <h2>Because “try again” is not a strategy.</h2>
          <div className="intelligence-step-list">
            {intelligenceSteps.map((item, i) => (
              <button
                key={item.title}
                className={step === i ? "active" : ""}
                onClick={() => setStep(i)}
                aria-pressed={step === i}
              >
                <span>0{i + 1}</span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.heading}</small>
                </span>
                <ArrowRight size={14} />
              </button>
            ))}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              className="intelligence-detail"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.24 }}
            >
              <StepIcon size={19} />
              <p>{intelligenceSteps[step].body}</p>
            </motion.div>
          </AnimatePresence>
          <button className="btn primary" onClick={() => w.navigate("lab")}>
            Try the Decision Studio <ArrowRight size={14} />
          </button>
        </div>
        <div className="story-media-wrap">
          <ParallaxImage
            src={SERVER_IMAGE}
            alt="Blue-illuminated server infrastructure representing the systems behind financial decisioning"
            credit="Photograph by Panumas Nikhomkhai / Pexels"
            className="story-media story-media-right"
          />
          <svg
            className="story-decision-path"
            viewBox="0 0 520 360"
            aria-hidden="true"
          >
            <path d="M28 284 C130 268 142 190 238 178 S390 112 492 66" />
            <circle cx="28" cy="284" r="5" />
            <circle cx="238" cy="178" r="5" />
            <circle cx="492" cy="66" r="5" />
          </svg>
          {["Rules", "Estimate", "Economics", "Execution"].map((label, i) => (
            <span
              key={label}
              className={`story-path-chip chip-${i} ${step === i ? "active" : ""}`}
            >
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="recovery-journey-band">
        <ParallaxImage
          src={ARCHITECTURE_IMAGE}
          alt="Blue sky reflected through modern architectural glass"
          credit="Photograph by Brett Sayles / Pexels"
          className="journey-band-media"
        />
        <div className="journey-band-panel">
          <span className="eyebrow blue">The short version</span>
          <h2>Failed debit in. Money back—when the facts allow it.</h2>
          <div className="journey-band-steps">
            {[
              ["01", "Debit failed"],
              ["02", "Options checked"],
              ["03", "Move chosen"],
              ["04", "Result written down"],
            ].map(([number, label]) => (
              <span key={number}>
                <small>{number}</small>
                {label}
              </span>
            ))}
          </div>
          <button className="btn primary" onClick={() => w.navigate("lab")}>
            Watch one decision <ArrowRight size={14} />
          </button>
        </div>
      </section>
    </div>
  );
}
