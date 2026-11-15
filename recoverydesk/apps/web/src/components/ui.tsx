import {
  animate,
  AnimatePresence,
  motion,
  useReducedMotion,
} from "motion/react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Check, ChevronDown, SearchX, X } from "lucide-react";
import { createPortal } from "react-dom";
import { statusColors, statusLabels } from "../data/workspace";
import { formatINR, type CaseStatus } from "../data/simulation";

export function BrandMark({
  size = 29,
  white = false,
}: {
  size?: number;
  white?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M5 24V7H17C23 7 26 10 26 15C26 20 22 23 17 23H13"
        stroke={white ? "white" : "#0086d6"}
        strokeWidth="5"
        strokeLinecap="square"
      />
      <path
        d="M13 16L21 24L14 30"
        stroke={white ? "#aee9ff" : "#ff9e2c"}
        strokeWidth="5"
      />
      <path
        d="M5 24V16H14"
        stroke={white ? "white" : "#0086d6"}
        strokeWidth="5"
      />
    </svg>
  );
}
export function Wordmark({
  compact = false,
  white = false,
}: {
  compact?: boolean;
  white?: boolean;
}) {
  return (
    <span className={`wordmark ${white ? "white" : ""}`}>
      <BrandMark white={white} />
      {!compact && (
        <span>
          revio<span className="brand-period">.</span>
        </span>
      )}
    </span>
  );
}
export function SimulationBadge({ short = false }: { short?: boolean }) {
  return (
    <span className="simulation-badge">
      <i />
      {short ? (
        "Simulation"
      ) : (
        <>
          <span className="sim-full">Simulation environment</span>
          <span className="sim-short">Simulation</span>
        </>
      )}
    </span>
  );
}
export function NumberFlow({
  value,
  format = formatINR,
  className = "",
}: {
  value: number;
  format?: (v: number) => string;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const ref = useRef(value);
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      ref.current = value;
      return;
    }
    const controls = animate(ref.current, value, {
      duration: 0.45,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: setDisplay,
    });
    ref.current = value;
    return () => controls.stop();
  }, [value, reduced]);
  return <span className={`financial ${className}`}>{format(display)}</span>;
}
export function StatusMark({ status }: { status: CaseStatus }) {
  return (
    <span className="status-mark" style={{ color: statusColors[status] }}>
      <i style={{ background: statusColors[status] }} />
      {statusLabels[status]}
    </span>
  );
}
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  label: string;
}) {
  const id = useId();
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          className={value === o.value ? "selected" : ""}
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
        >
          {value === o.value && (
            <motion.span
              className="segment-highlight"
              layoutId={id}
              transition={{ duration: 0.2 }}
            />
          )}
          <span>{o.label}</span>
        </button>
      ))}
    </div>
  );
}
export function SectionHeading({
  title,
  description,
  action,
  tag,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  tag?: string;
}) {
  return (
    <div className="section-heading">
      <div>
        {tag && <span className="eyebrow blue">{tag}</span>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function PageHeading({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </header>
  );
}
export function Disclosure({
  title,
  subtitle,
  children,
  defaultOpen = false,
  right,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  right?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={`disclosure ${open ? "open" : ""}`}>
      <button
        className="disclosure-button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        <span>
          <strong>{title}</strong>
          {subtitle && <small>{subtitle}</small>}
        </span>
        {right}
        <ChevronDown size={16} className={open ? "rotated" : ""} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.24 }}
            className="disclosure-body"
          >
            <div>{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
export function Tooltip({
  children,
  content,
}: {
  children: ReactNode;
  content: ReactNode;
}) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();
  const show = () => {
    const r = ref.current?.getBoundingClientRect();
    if (r)
      setPos({
        x: Math.max(
          130,
          Math.min(window.innerWidth - 130, r.left + r.width / 2),
        ),
        y: r.bottom + 8,
      });
  };
  return (
    <span
      className="tooltip-trigger"
      ref={ref}
      onMouseEnter={show}
      onMouseLeave={() => setPos(null)}
      onFocus={show}
      onBlur={() => setPos(null)}
      aria-describedby={pos ? id : undefined}
    >
      {children}
      {pos &&
        createPortal(
          <div
            id={id}
            role="tooltip"
            className="custom-tooltip"
            style={{ left: pos.x, top: pos.y }}
          >
            {content}
          </div>,
          document.body,
        )}
    </span>
  );
}
export function EmptyState({
  title = "No matching records",
  body,
  action,
}: {
  title?: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <SearchX size={28} />
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}
export function Budget({
  label,
  used,
  max,
}: {
  label: string;
  used: number;
  max: number;
}) {
  return (
    <div className="budget">
      <div>
        <span>{label}</span>
        <strong>
          {max - used}
          <small> / {max} left</small>
        </strong>
      </div>
      <div className="budget-segments">
        {Array.from({ length: max }, (_, i) => (
          <i key={i} className={i < max - used ? "available" : ""} />
        ))}
      </div>
    </div>
  );
}

let modalDepth = 0;
let previousBodyOverflow = "";
export function Modal({
  children,
  onClose,
  className = "",
  title,
}: {
  children: ReactNode;
  onClose: () => void;
  className?: string;
  title: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const saved = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    saved.current = document.activeElement as HTMLElement;
    if (modalDepth === 0) previousBodyOverflow = document.body.style.overflow;
    modalDepth += 1;
    document.body.style.overflow = "hidden";
    document.querySelector(".workspace-shell")?.setAttribute("inert", "");
    const focusable = () =>
      Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input, select, a[href], [tabindex="0"]',
        ) ?? [],
      );
    const t = setTimeout(() => (focusable()[0] ?? ref.current)?.focus(), 20);
    const key = (e: KeyboardEvent) => {
      const dialogs = document.querySelectorAll('.modal[aria-modal="true"]');
      if (dialogs[dialogs.length - 1] !== ref.current) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
      }
      if (e.key === "Tab") {
        const items = focusable();
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", key);
      modalDepth -= 1;
      if (modalDepth === 0) {
        document.body.style.overflow = previousBodyOverflow;
        document.querySelector(".workspace-shell")?.removeAttribute("inert");
      }
      if (saved.current?.isConnected && !saved.current.closest("[inert]"))
        saved.current.focus();
    };
  }, []);
  return createPortal(
    <motion.div
      className={`modal-overlay ${className.includes("drawer") ? "drawer-overlay" : ""}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div
        ref={ref}
        className={`modal ${className}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        initial={
          className.includes("drawer")
            ? { x: 40, opacity: 0 }
            : { y: -12, scale: 0.985, opacity: 0 }
        }
        animate={{ x: 0, y: 0, scale: 1, opacity: 1 }}
        exit={
          className.includes("drawer")
            ? { x: 40, opacity: 0 }
            : { y: -8, opacity: 0 }
        }
        transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      >
        {children}
      </motion.div>
    </motion.div>,
    document.body,
  );
}
export function Toast({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  return (
    <motion.div
      className="toast"
      role="status"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
    >
      <span className="toast-check">
        <Check size={14} />
      </span>
      {message}
      <button
        className="icon-button"
        onClick={onClose}
        aria-label="Dismiss notification"
      >
        <X size={14} />
      </button>
    </motion.div>
  );
}
