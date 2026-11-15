import {
  AnimatePresence,
  motion,
  useScroll,
  useSpring,
} from "motion/react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  CircleHelp,
  Command,
  CornerDownLeft,
  FlaskConical,
  Focus,
  LayoutGrid,
  ListFilter,
  Menu,
  Moon,
  Presentation,
  Search,
  ShieldCheck,
  Sun,
  Terminal,
  X,
} from "lucide-react";
import { cases, formatINR } from "../data/simulation";
import { connected } from '../api/runtime';
import { filterRange, rangeOptions, type TimeRange } from "../data/workspace";
import { useWorkspace } from "../state/Workspace";
import { BrandMark, Modal, SimulationBadge, Tooltip, Wordmark } from "./ui";

export const destinations = [
  {
    id: "overview",
    label: "Overview",
    description: "Money still recoverable",
    icon: LayoutGrid,
  },
  {
    id: "cases",
    label: "Recovery Cases",
    description: "Work the queue",
    icon: ListFilter,
  },
  {
    id: "outcomes",
    label: "Revenue Analytics",
    description: "What came back, what it cost",
    icon: ChartNoAxesCombined,
  },
  {
    id: "lab",
    label: "Decision Studio",
    description: "Why this move, not that one",
    icon: FlaskConical,
  },
  {
    id: "knowledge",
    label: "Knowledge & Rules",
    description: "Rules run before scores",
    icon: BookOpen,
  },
  {
    id: "audit",
    label: "Audit Trail",
    description: "Receipts, in order",
    icon: Terminal,
  },
  {
    id: "trust",
    label: "System & Trust",
    description: "What is—and isn't—connected",
    icon: ShieldCheck,
  },
];

export function ConsoleShell({ children }: { children: ReactNode }) {
  const w = useWorkspace();
  const [mobile, setMobile] = useState(false);
  const { scrollYProgress } = useScroll();
  const scrollScale = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 28,
    mass: 0.35,
  });
  useEffect(() => {
    let frame = 0;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        document.documentElement.style.setProperty(
          "--pointer-x",
          `${e.clientX}px`,
        );
        document.documentElement.style.setProperty(
          "--pointer-y",
          `${e.clientY}px`,
        );
      });
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", move);
    };
  }, []);
  const active = w.route.startsWith("case/")
    ? "cases"
    : w.route.split(/[/?]/)[0];
  const current = destinations.find((d) => d.id === active) ?? destinations[0];
  const nav = (isMobile = false) => (
    <>
      <div className="sidebar-brand">
        <button
          onClick={() => {
            w.navigate("overview");
            setMobile(false);
          }}
          aria-label="REVIO overview"
        >
          <Wordmark compact={w.collapsed && !isMobile} />
        </button>
        {isMobile && (
          <button
            className="icon-button"
            onClick={() => setMobile(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        )}
      </div>
      <div className="workspace-selector">
        <div className="workspace-symbol">
          <span /> <span /> <span /> <span />
        </div>
        <div className="sidebar-label">
          <strong>Demo workspace</strong>
          <small>Revenue operations</small>
        </div>
        <span className="workspace-local sidebar-label">SIM</span>
      </div>
      <div className="nav-label sidebar-label">Workspace</div>
      <nav aria-label="Main navigation">
        {destinations.map((d, i) => (
          <div key={d.id}>
            {i === 5 && (
              <div className="nav-label secondary sidebar-label">
                Governance
              </div>
            )}
            <button
              className={`nav-link ${active === d.id ? "active" : ""}`}
              onClick={() => {
                w.navigate(d.id);
                setMobile(false);
              }}
              aria-current={active === d.id ? "page" : undefined}
              aria-label={d.label}
            >
              <d.icon size={18} strokeWidth={1.7} />
              <span className="sidebar-label">{d.label}</span>
              {d.id === "cases" && !connected && (
                <span className="nav-count sidebar-label">
                  {
                    filterRange(cases, w.range).filter((c) =>
                      ["ACTION PENDING", "WAITING"].includes(c.status),
                    ).length
                  }
                </span>
              )}
              {d.id === "lab" && (
                <span className="nav-new sidebar-label">STUDIO</span>
              )}
              {active === d.id && (
                <motion.i
                  className="nav-active-mark"
                  layoutId={isMobile ? "mobile-nav-active" : "nav-active"}
                />
              )}
            </button>
          </div>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button
          className="tour-invitation"
          onClick={() => {
            w.startTour();
            setMobile(false);
          }}
        >
          <CircleHelp size={18} />
          <span className="sidebar-label">
            <strong>New here?</strong>
            <small>
              Start with the money <ArrowUpRight size={11} />
            </small>
          </span>
        </button>
        <div className="sidebar-system">
          <i />
          <span className="sidebar-label">Synthetic data · ready</span>
        </div>
        <button
          className="operator-profile"
          onClick={() => {
            w.navigate("trust");
            setMobile(false);
          }}
        >
          <span className="avatar">DO</span>
          <span className="sidebar-label">
            <strong>Demo Operator</strong>
            <small>Synthetic workspace</small>
          </span>
          <ChevronDown className="sidebar-label" size={13} />
        </button>
        {!isMobile && (
          <button
            className="collapse-button"
            onClick={() => w.setCollapsed(!w.collapsed)}
            aria-label={w.collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {w.collapsed ? (
              <ChevronsRight size={15} />
            ) : (
              <>
                <ChevronsLeft size={15} />
                <span>Collapse sidebar</span>
              </>
            )}
          </button>
        )}
      </div>
    </>
  );
  return (
    <div
      className={`workspace-shell ${w.collapsed ? "is-collapsed" : ""} ${w.focusMode ? "focus-mode" : ""} ${w.presentation ? "presentation-mode" : ""}`}
      data-tour-step={w.tour ?? ""}
    >
      <motion.div
        className="scroll-progress"
        style={{ scaleX: scrollScale }}
        aria-hidden="true"
      />
      <div className="pointer-aura" aria-hidden="true" />
      <aside className="sidebar">{nav()}</aside>
      <div className="workspace-body">
        {w.presentation && (
          <div className="presentation-bar">
            <Wordmark />
            <span className="presentation-title">
              Revenue intelligence, presented clearly.
            </span>
            <SimulationBadge />
            <button className="btn small" onClick={w.exitPresentation}>
              <X size={13} />
              Exit presentation
            </button>
          </div>
        )}
        <header className="workspace-header">
          <button
            className="icon-button mobile-menu"
            onClick={() => setMobile(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <button
            className="mobile-brand"
            onClick={() => w.navigate("overview")}
            aria-label="REVIO overview"
          >
            <Wordmark />
          </button>
          <div className="header-context">
            <span>
              Workspace <i>/</i> <strong>{current.label}</strong>
            </span>
            <small>{current.description}</small>
          </div>
          <button
            className="global-search"
            onClick={() => w.setCommandOpen(true)}
          >
            <Search size={15} />
            <span>Search anything...</span>
            <kbd>
              <Command size={10} /> K
            </kbd>
          </button>
          <div className="header-actions">
            <SimulationBadge />
            <Tooltip
              content={
                w.focusMode
                  ? "Turn off Focus Mode and restore atmospheric imagery"
                  : "Turn on Focus Mode to quiet imagery and emphasize data"
              }
            >
              <button
                className={`icon-button focus-button ${w.focusMode ? "active" : ""}`}
                onClick={() => w.setFocusMode(!w.focusMode)}
                aria-label={
                  w.focusMode ? "Turn off Focus Mode" : "Turn on Focus Mode"
                }
                aria-pressed={w.focusMode}
              >
                <Focus size={17} />
              </button>
            </Tooltip>
            <Tooltip content="Open a clean presentation view of the overview">
              <button
                className="icon-button presentation-button"
                onClick={w.startPresentation}
                aria-label="Start presentation mode"
              >
                <Presentation size={17} />
              </button>
            </Tooltip>
            <Tooltip
              content={`Switch to ${w.theme === "light" ? "dark" : "light"} appearance`}
            >
              <button
                className="icon-button appearance-button"
                onClick={w.toggleTheme}
                aria-label={`Switch to ${w.theme === "light" ? "dark" : "light"} theme`}
              >
                {w.theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
              </button>
            </Tooltip>
            <button
              className="icon-button compact-search"
              onClick={() => w.setCommandOpen(true)}
              aria-label="Open command search"
            >
              <Search size={17} />
            </button>
            <span className="header-avatar">DO</span>
          </div>
        </header>
        <main id="main-content" className="workspace-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="workspace-footer">
          <span>
            <BrandMark size={15} />
            Don't retry blindly.
          </span>
          <span>
            Simulation only <i /> Synthetic customers & payments <i /> No
            connected payment rails
          </span>
        </footer>
      </div>
      <AnimatePresence>
        {mobile && (
          <Modal
            className="mobile-nav drawer"
            title="REVIO navigation"
            onClose={() => setMobile(false)}
          >
            {nav(true)}
          </Modal>
        )}
      </AnimatePresence>
      <AnimatePresence>{w.commandOpen && <CommandPalette />}</AnimatePresence>
      <AnimatePresence>{w.tour !== null && <ProductTour />}</AnimatePresence>
    </div>
  );
}

export function DateRangeControl() {
  const { range, setRange } = useWorkspace();
  return (
    <label className="date-range-control">
      <span className="calendar-icon">
        <i />
        <i />
      </span>
      <select
        aria-label="Workspace date range"
        value={range}
        onChange={(e) => setRange(e.target.value as TimeRange)}
      >
        {rangeOptions.map((r) => (
          <option key={r.value} value={r.value}>
            {r.value === "ALL" ? "07 - 18 Jun, 2026" : r.label}
          </option>
        ))}
      </select>
      <ChevronDown size={13} />
    </label>
  );
}

function CommandPalette() {
  const w = useWorkspace();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const results = useMemo(() => {
    const pages = destinations.map((d) => ({
      id: d.id,
      label: d.label,
      sub: "Navigate to page",
      icon: d.icon,
      action: () => w.navigate(d.id),
    }));
    const searchable = (connected ? [] : cases).map((c) => ({
      id: c.id,
      label: c.id,
      sub: `${formatINR(c.amount)} / ${c.failureReason}`,
      icon: ListFilter,
      action: () => w.navigate(`case/${c.id}`),
    }));
    const actions = [
      {
        id: "appearance",
        label: `Switch to ${w.theme === "light" ? "dark" : "light"} appearance`,
        sub: "Workspace preference",
        icon: w.theme === "light" ? Moon : Sun,
        action: () => {
          w.toggleTheme();
          w.setCommandOpen(false);
        },
      },
      {
        id: "focus-mode",
        label: w.focusMode ? "Turn off Focus Mode" : "Turn on Focus Mode",
        sub: "Quiet imagery and emphasize financial data",
        icon: Focus,
        action: () => {
          w.setFocusMode(!w.focusMode);
          w.setCommandOpen(false);
        },
      },
      {
        id: "presentation-mode",
        label: "Start presentation mode",
        sub: "A clean, focused view of revenue intelligence",
        icon: Presentation,
        action: () => {
          w.setCommandOpen(false);
          w.startPresentation();
        },
      },
      {
        id: "tour",
        label: "Start product tour",
        sub: "A four-stop introduction to REVIO",
        icon: CircleHelp,
        action: () => {
          w.setCommandOpen(false);
          w.startTour();
        },
      },
    ];
    const q = query.toLowerCase().trim();
    if (!q)
      return [
        ...pages,
        ...searchable.filter((c) => w.recent.includes(c.id)).slice(0, 2),
        ...actions,
      ];
    return [...pages, ...searchable, ...actions]
      .filter((r) => `${r.label} ${r.sub}`.toLowerCase().includes(q))
      .slice(0, 12);
  }, [query, w]);
  useEffect(() => {
    setSelected(0);
  }, [query]);
  useEffect(() => {
    input.current?.focus();
  }, []);
  useEffect(() => {
    document
      .getElementById(`command-${selected}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selected]);
  return (
    <Modal
      className="command-palette"
      title="Global command search"
      onClose={() => w.setCommandOpen(false)}
    >
      <div className="command-input">
        <Search size={20} />
        <input
          ref={input}
          role="combobox"
          aria-label="Search commands and cases"
          aria-expanded="true"
          aria-controls="command-results"
          aria-activedescendant={
            results.length ? `command-${selected}` : undefined
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Where would you like to go?"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setSelected((s) => Math.min(results.length - 1, s + 1));
            }
            if (e.key === "ArrowUp") {
              e.preventDefault();
              setSelected((s) => Math.max(0, s - 1));
            }
            if (e.key === "Enter") {
              e.preventDefault();
              results[selected]?.action();
            }
          }}
        />
        <button onClick={() => w.setCommandOpen(false)} className="key-button">
          esc
        </button>
      </div>
      <div className="command-category">
        {query
          ? `${results.length} matching results`
          : "Quick navigation & recent cases"}
      </div>
      <div className="command-results" role="listbox" id="command-results">
        {results.length ? (
          results.map((r, i) => (
            <button
              role="option"
              aria-selected={selected === i}
              id={`command-${i}`}
              key={r.id}
              className={selected === i ? "active" : ""}
              onMouseMove={() => setSelected(i)}
              onClick={r.action}
            >
              <r.icon size={18} />
              <span>
                <strong>{r.label}</strong>
                <small>{r.sub}</small>
              </span>
              {selected === i && <CornerDownLeft size={15} />}
            </button>
          ))
        ) : (
          <div className="command-empty">
            No matching page or synthetic case. Try "lab" or "0471".
          </div>
        )}
      </div>
      <div className="command-footer">
        <span>
          <ArrowUp size={11} />
          <ArrowDown size={11} /> to navigate
        </span>
        <span>
          <CornerDownLeft size={12} /> to open
        </span>
        <span className="command-brand">REVIO COMMAND</span>
      </div>
    </Modal>
  );
}

function ProductTour() {
  const w = useWorkspace();
  const steps = [
    {
      title: "Start with what's still owed.",
      body: "Change the date range and watch the headline, chart and queue move together. One ledger, no mismatched totals.",
      target: "overview",
    },
    {
      title: "Pick a case. Any case.",
      body: "Filter by rail or failure, save the view, then open a row. The drawer gives you the short version first.",
      target: "cases",
    },
    {
      title: "Why this move? Here's the working.",
      body: "Step through rules, estimates and expected value. Scenario Playground uses fixed snapshots—no fake live model.",
      target: "lab",
    },
    {
      title: "Sometimes the old playbook wins.",
      body: "Open Card SI in the benchmark. B2 beats REVIO there, and REVIO shows it instead of hiding it.",
      target: "outcomes",
    },
  ];
  const index = w.tour ?? 0;
  const step = steps[index];
  useEffect(() => {
    const timer = setTimeout(
      () =>
        document
          .querySelector(`[data-tour="${step.target}"]`)
          ?.scrollIntoView({ block: "center", behavior: "smooth" }),
      300,
    );
    return () => clearTimeout(timer);
  }, [step.target]);
  return (
    <motion.aside
      className="product-tour"
      role="dialog"
      aria-label="Product tour"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
    >
      <div className="tour-top">
        <span>
          <BrandMark size={18} /> A quick introduction
        </span>
        <button
          className="icon-button"
          onClick={w.endTour}
          aria-label="Close product tour"
        >
          <X size={15} />
        </button>
      </div>
      <h3>{step.title}</h3>
      <p>{step.body}</p>
      <div className="tour-bottom">
        <div className="tour-dots">
          {steps.map((_, i) => (
            <i key={i} className={i === index ? "active" : ""} />
          ))}
          <small>{index + 1} / 4</small>
        </div>
        <button className="btn primary small" onClick={w.nextTour}>
          {index === 3 ? "Finish tour" : "Next stop"}
          <ArrowRight size={13} />
        </button>
      </div>
    </motion.aside>
  );
}
