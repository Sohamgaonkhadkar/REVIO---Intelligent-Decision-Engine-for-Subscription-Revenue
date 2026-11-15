import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  ListFilter,
  Rows3,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { DateRangeControl } from "../components/ConsoleShell";
import {
  Budget,
  EmptyState,
  Modal,
  PageHeading,
  StatusMark,
  Tooltip,
} from "../components/ui";
import {
  cases,
  failureMeta,
  formatINR,
  formatTime,
  type RecoveryCase,
} from "../data/simulation";
import {
  ageLabel,
  exportFile,
  filterRange,
  safeRead,
  safeWrite,
  type TimeRange,
} from "../data/workspace";
import { useWorkspace } from "../state/Workspace";

interface Filters {
  search: string;
  status: string;
  rail: string;
  failure: string;
  sort: string;
}
interface Preset {
  name: string;
  filters: Filters;
}
const defaults: Filters = {
  search: "",
  status: "ALL",
  rail: "ALL",
  failure: "ALL",
  sort: "newest",
};
const statuses = [
  { value: "ALL", label: "All cases" },
  { value: "ACTIVE", label: "Active" },
  { value: "RECOVERED", label: "Recovered" },
  { value: "ESCALATED", label: "Escalated" },
  { value: "STOPPED", label: "Stopped" },
];

export default function Cases() {
  const w = useWorkspace();
  const [filters, setFilters] = useState<Filters>(() => ({
    ...defaults,
    ...safeRead("revio-blue-queue", {}),
  }));
  const [density, setDensity] = useState<"comfortable" | "compact">(() =>
    safeRead("revio-blue-density", "comfortable"),
  );
  const [page, setPage] = useState(() => safeRead("revio-blue-queue-page", 1));
  const [selected, setSelected] = useState<RecoveryCase | null>(null);
  const [presetOpen, setPresetOpen] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [presets, setPresets] = useState<Preset[]>(() =>
    safeRead("revio-blue-presets", []),
  );
  const [mobileFilters, setMobileFilters] = useState(false);
  const rowRefs = useRef<(HTMLButtonElement | null)[]>([]);
  useEffect(() => {
    const q = new URLSearchParams(w.route.split("?")[1] ?? "");
    const status = q.get("status");
    const range = q.get("range");
    const rail = q.get("rail");
    const failure = q.get("failure");
    if (status || rail || failure) {
      setFilters({
        ...defaults,
        status: status ?? "ALL",
        rail: rail && ["UPI AutoPay", "Card SI"].includes(rail) ? rail : "ALL",
        failure: failure && failure in failureMeta ? failure : "ALL",
      });
      setPage(1);
    }
    if (range && ["24H", "7D", "30D", "ALL"].includes(range))
      w.setRange(range as TimeRange);
  }, [w.route]);
  useEffect(() => {
    safeWrite("revio-blue-queue", filters);
  }, [filters]);
  useEffect(() => {
    safeWrite("revio-blue-density", density);
  }, [density]);
  useEffect(() => {
    safeWrite("revio-blue-queue-page", page);
  }, [page]);
  useEffect(() => {
    safeWrite("revio-blue-presets", presets);
  }, [presets]);
  const source = useMemo(() => filterRange(cases, w.range), [w.range]);
  const filtered = useMemo(
    () =>
      source
        .filter((c) => {
          const q = filters.search.trim().toLowerCase();
          return (
            (!q ||
              [c.id, c.customerRef, c.failureReason, c.subscription].some((s) =>
                s.toLowerCase().includes(q),
              )) &&
            (filters.status === "ALL" ||
              (filters.status === "ACTIVE" &&
                ["ACTION PENDING", "WAITING"].includes(c.status)) ||
              c.status === filters.status) &&
            (filters.rail === "ALL" || c.rail === filters.rail) &&
            (filters.failure === "ALL" || c.failureCode === filters.failure)
          );
        })
        .sort((a, b) =>
          filters.sort === "value-desc"
            ? b.amount - a.amount
            : filters.sort === "value-asc"
              ? a.amount - b.amount
              : filters.sort === "oldest"
                ? new Date(a.createdAt).getTime() -
                  new Date(b.createdAt).getTime()
                : new Date(b.createdAt).getTime() -
                  new Date(a.createdAt).getTime(),
        ),
    [source, filters],
  );
  const perPage = density === "compact" ? 12 : 8;
  const pages = Math.max(1, Math.ceil(filtered.length / perPage));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * perPage, current * perPage);
  const update = (key: keyof Filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };
  const clear = () => {
    setFilters(defaults);
    setPage(1);
  };
  const activeFilters =
    Number(filters.rail !== "ALL") +
    Number(filters.failure !== "ALL") +
    Number(!!filters.search) +
    Number(filters.status !== "ALL");
  const csv = () => {
    const header = [
      "environment",
      "case_id",
      "amount_inr",
      "status",
      "failure_reason",
      "rail",
      "selected_action",
      "retry_budget_remaining",
      "contact_budget_remaining",
      "created_at",
    ];
    const rows = filtered.map((c) => [
      "SYNTHETIC SIMULATION",
      c.id,
      c.amount,
      c.status,
      c.failureReason,
      c.rail,
      c.selectedAction,
      3 - c.constraints.retriesUsed,
      2 - c.constraints.contactsUsed,
      c.createdAt,
    ]);
    exportFile(
      "revio-filtered-synthetic-cases.csv",
      [header, ...rows]
        .map((r) =>
          r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","),
        )
        .join("\n"),
      true,
    );
    w.notify(`${filtered.length} filtered synthetic cases exported to CSV.`);
  };
  return (
    <>
      <PageHeading
        title="Recovery cases"
        description="Work the queue by money at stake, what's still allowed, and what cannot wait."
        actions={
          <>
            <DateRangeControl />
            <button
              className="btn primary"
              onClick={csv}
              disabled={!filtered.length}
            >
              <Download size={13} />
              Export cases
            </button>
          </>
        }
      />
      <div className="queue-summary">
        <span>
          <strong>{source.length}</strong> cases in the selected cohort
        </span>
        <span>
          <i className="blue-dot" />
          {
            source.filter((c) =>
              ["ACTION PENDING", "WAITING"].includes(c.status),
            ).length
          }{" "}
          active
        </span>
        <span>
          <i className="green-dot" />
          {source.filter((c) => c.status === "RECOVERED").length} recovered
        </span>
        <span>
          <i className="amber-dot" />
          {source.filter((c) => c.status === "ESCALATED").length} escalated
        </span>
        <span className="queue-risk-total">
          {formatINR(source.reduce((s, c) => s + c.amount, 0))}
          <small>original value at risk</small>
        </span>
      </div>
      <section className="case-workstation" data-tour="cases">
        <div
          className="queue-status-tabs"
          role="group"
          aria-label="Case status filter"
        >
          {statuses.map((s) => (
            <button
              key={s.value}
              onClick={() => update("status", s.value)}
              className={filters.status === s.value ? "active" : ""}
            >
              {s.label}
              <span>
                {
                  source.filter(
                    (c) =>
                      s.value === "ALL" ||
                      (s.value === "ACTIVE" &&
                        ["ACTION PENDING", "WAITING"].includes(c.status)) ||
                      s.value === c.status,
                  ).length
                }
              </span>
            </button>
          ))}
          <button
            className="saved-views-trigger"
            onClick={() => setPresetOpen(true)}
          >
            <Bookmark size={13} />
            Saved views{presets.length > 0 && <small>{presets.length}</small>}
          </button>
        </div>
        <div className="queue-toolbar">
          <label className="search-field">
            <Search size={14} />
            <input
              className="field"
              aria-label="Search recovery cases"
              placeholder="Search case ID, customer or failure..."
              value={filters.search}
              onChange={(e) => update("search", e.target.value)}
            />
          </label>
          <button
            className="btn mobile-filter-trigger"
            onClick={() => setMobileFilters(!mobileFilters)}
          >
            <SlidersHorizontal size={14} />
            Filters
          </button>
          <div className={`queue-filters ${mobileFilters ? "expanded" : ""}`}>
            <select
              className="field"
              aria-label="Filter payment rail"
              value={filters.rail}
              onChange={(e) => update("rail", e.target.value)}
            >
              <option value="ALL">All payment rails</option>
              <option>UPI AutoPay</option>
              <option>Card SI</option>
            </select>
            <select
              className="field"
              aria-label="Filter failure type"
              value={filters.failure}
              onChange={(e) => update("failure", e.target.value)}
            >
              <option value="ALL">All failure types</option>
              {Object.entries(failureMeta).map(([id, meta]) => (
                <option key={id} value={id}>
                  {meta.short}
                </option>
              ))}
            </select>
            <select
              className="field"
              aria-label="Sort recovery cases"
              value={filters.sort}
              onChange={(e) => update("sort", e.target.value)}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="value-desc">Highest value</option>
              <option value="value-asc">Lowest value</option>
            </select>
          </div>
          <Tooltip
            content={`Switch to ${density === "comfortable" ? "compact" : "comfortable"} rows`}
          >
            <button
              className={`icon-button density-button ${density === "compact" ? "active" : ""}`}
              aria-label={`Switch to ${density === "comfortable" ? "compact" : "comfortable"} density`}
              onClick={() => {
                setDensity(
                  density === "comfortable" ? "compact" : "comfortable",
                );
                setPage(1);
              }}
            >
              <Rows3 size={17} />
            </button>
          </Tooltip>
        </div>
        {activeFilters > 0 && (
          <div className="active-filter-line">
            <ListFilter size={12} />
            <span>
              {activeFilters} active filters / {filtered.length} matching cases
            </span>
            <button onClick={clear}>
              Clear all <X size={11} />
            </button>
          </div>
        )}
        <div className={`case-table ${density}`}>
          <div className="case-table-header">
            <span>Amount at risk</span>
            <span>Case / failure reason</span>
            <span>Status</span>
            <span>Payment rail</span>
            <span>Budgets left</span>
            <span>Next move</span>
            <span />
          </div>
          {visible.length ? (
            visible.map((c, i) => (
              <motion.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: i * 0.015 }}
                className={`case-row ${selected?.id === c.id ? "selected" : ""}`}
                key={c.id}
                ref={(el) => {
                  rowRefs.current[i] = el;
                }}
                onClick={() => setSelected(c)}
                aria-label={`Inspect ${c.id}, ${formatINR(c.amount)}, ${c.status.toLowerCase()}`}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                    e.preventDefault();
                    rowRefs.current[
                      Math.max(
                        0,
                        Math.min(
                          visible.length - 1,
                          i + (e.key === "ArrowDown" ? 1 : -1),
                        ),
                      )
                    ]?.focus();
                  }
                }}
              >
                <span className="case-amount financial">
                  {formatINR(c.amount)}
                  <small>{ageLabel(c.createdAt)}</small>
                </span>
                <span className="case-description">
                  <strong>{failureMeta[c.failureCode].short}</strong>
                  <span className="mono">{c.id}</span>
                </span>
                <StatusMark status={c.status} />
                <span className="case-rail">
                  <span
                    className={`rail-mark ${c.rail === "Card SI" ? "card" : ""}`}
                  >
                    {c.rail === "Card SI" ? <span /> : <i />}
                  </span>
                  {c.rail === "Card SI" ? "Card SI" : "UPI AutoPay"}
                </span>
                <span className="case-budget-numbers">
                  <span>
                    <strong>{3 - c.constraints.retriesUsed}</strong>
                    <small>/ 3 retries</small>
                  </span>
                  <span>
                    <strong>{2 - c.constraints.contactsUsed}</strong>
                    <small>/ 2 contacts</small>
                  </span>
                </span>
                <span className="case-action">
                  {c.strategy}
                  {c.nextActionAt && (
                    <small>
                      {formatTime(c.nextActionAt).split(", ")[1] ?? "Scheduled"}
                    </small>
                  )}
                </span>
                <ArrowUpRight size={14} className="case-row-arrow" />
              </motion.button>
            ))
          ) : (
            <EmptyState
              body="No synthetic cases match this combination. Broaden the search or clear your filters."
              action={
                <button className="btn" onClick={clear}>
                  Clear filters
                </button>
              }
            />
          )}
        </div>
        <div className="queue-pagination">
          <span>
            {filtered.length
              ? `${(current - 1) * perPage + 1}-${Math.min(current * perPage, filtered.length)}`
              : "0"}{" "}
            of {filtered.length} cases <i />
            {formatINR(filtered.reduce((s, c) => s + c.amount, 0))} in view
          </span>
          <div>
            <button
              className="icon-button"
              onClick={() => setPage(current - 1)}
              disabled={current === 1}
              aria-label="Previous cases page"
            >
              <ChevronLeft size={15} />
            </button>
            {Array.from({ length: pages }, (_, i) => (
              <button
                key={i}
                className={`page-number ${current === i + 1 ? "active" : ""}`}
                onClick={() => setPage(i + 1)}
                aria-label={`Cases page ${i + 1}`}
                aria-current={current === i + 1 ? "page" : undefined}
              >
                {i + 1}
              </button>
            ))}
            <button
              className="icon-button"
              onClick={() => setPage(current + 1)}
              disabled={current === pages}
              aria-label="Next cases page"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </section>
      <div className="queue-keyboard-note">
        <span>
          <kbd>↑</kbd>
          <kbd>↓</kbd>Navigate visible rows <kbd>enter</kbd>Inspect case
        </span>
        <span>Synthetic payment records. No production customers.</span>
      </div>
      <AnimatePresence>
        {selected && (
          <CaseDrawer c={selected} onClose={() => setSelected(null)} />
        )}
        {presetOpen && (
          <Modal
            className="preset-modal"
            title="Saved case filter views"
            onClose={() => setPresetOpen(false)}
          >
            <div className="modal-heading">
              <h2>Save this setup.</h2>
              <button
                className="icon-button"
                onClick={() => setPresetOpen(false)}
                aria-label="Close saved views"
              >
                <X size={17} />
              </button>
            </div>
            <p>
              Save the current search, status, rail, failure and sort. Views
              stay in this browser.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const name = presetName.trim();
                if (!name) return;
                setPresets((p) => [
                  ...p.filter((x) => x.name !== name),
                  { name, filters },
                ]);
                setPresetName("");
                w.notify(`Saved filter view: ${name}`);
              }}
            >
              <input
                className="field"
                placeholder="Name this filter view"
                aria-label="Saved filter name"
                maxLength={40}
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
              />
              <button className="btn primary" disabled={!presetName.trim()}>
                <Bookmark size={13} />
                Save view
              </button>
            </form>
            <div className="saved-view-list">
              {presets.length ? (
                presets.map((p) => (
                  <div key={p.name}>
                    <button
                      onClick={() => {
                        setFilters(p.filters);
                        setPage(1);
                        setPresetOpen(false);
                        w.notify(`Applied saved view: ${p.name}`);
                      }}
                    >
                      <Bookmark size={14} />
                      <span>
                        {p.name}
                        <small>
                          {p.filters.status === "ALL"
                            ? "All statuses"
                            : p.filters.status.toLowerCase()}{" "}
                          /{" "}
                          {p.filters.rail === "ALL"
                            ? "All rails"
                            : p.filters.rail}
                        </small>
                      </span>
                      <ArrowRight size={14} />
                    </button>
                    <button
                      className="icon-button"
                      onClick={() =>
                        setPresets((list) =>
                          list.filter((x) => x.name !== p.name),
                        )
                      }
                      aria-label={`Delete saved view ${p.name}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              ) : (
                <div className="saved-view-empty">
                  No saved views yet. Save this filter combination to start.
                </div>
              )}
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </>
  );
}

export function CaseDrawer({
  c,
  onClose,
}: {
  c: RecoveryCase;
  onClose: () => void;
}) {
  const w = useWorkspace();
  const chosen = c.candidates.find((a) => a.selected)!;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(c.id);
      w.notify("Case ID copied.");
    } catch {
      w.notify(c.id);
    }
  };
  const open = (route: string) => {
    onClose();
    w.navigate(route);
  };
  return (
    <Modal
      className="case-drawer drawer"
      title={`Quick inspection of ${c.id}`}
      onClose={onClose}
    >
      <header className="drawer-heading">
        <span>
          <span className="eyebrow blue">Recovery case</span>
          <strong className="mono">{c.id}</strong>
        </span>
        <button
          className="icon-button"
          onClick={copy}
          aria-label="Copy case ID"
        >
          <Copy size={15} />
        </button>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close case drawer"
        >
          <X size={18} />
        </button>
      </header>
      <div className="drawer-content">
        <div className="drawer-status">
          <StatusMark status={c.status} />
          <span>Synthetic case</span>
        </div>
        <h2 className="drawer-amount financial">{formatINR(c.amount)}</h2>
        <span className="note">One failed debit</span>
        <h3 className="drawer-failure">{c.failureReason}</h3>
        <div className="drawer-plan">
          {c.rail} <i />
          {c.subscription}
        </div>
        <div className="drawer-budgets">
          <Budget
            label="Retries remaining"
            used={c.constraints.retriesUsed}
            max={3}
          />
          <Budget
            label="Contacts remaining"
            used={c.constraints.contactsUsed}
            max={2}
          />
        </div>
        <div className="drawer-selected">
          <span>
            <Check size={13} />
            REVIO's call
          </span>
          <strong>{c.strategy}</strong>
          <div>
            <span>
              {chosen.probability === undefined
                ? "Unscored control"
                : `${Math.round(chosen.probability * 100)}% illustrative estimate`}
            </span>
            <strong className="financial">
              {chosen.expectedValue === undefined
                ? "N/A"
                : formatINR(chosen.expectedValue, 2)}
              <small>expected value</small>
            </strong>
          </div>
        </div>
        <p className="drawer-outcome">{c.outcomeNote}</p>
        <dl className="context-fields">
          <div>
            <dt>Original failure</dt>
            <dd>{formatTime(c.createdAt)}</dd>
          </div>
          <div>
            <dt>Latest recorded state</dt>
            <dd>{formatTime(c.updatedAt)}</dd>
          </div>
          <div>
            <dt>Permission snapshot</dt>
            <dd>
              {c.candidates.filter((a) => a.eligible).length} permitted /{" "}
              {c.candidates.filter((a) => !a.eligible).length} blocked
            </dd>
          </div>
          {c.nextActionAt && (
            <div>
              <dt>Next evaluation</dt>
              <dd>{formatTime(c.nextActionAt)}</dd>
            </div>
          )}
        </dl>
      </div>
      <footer className="drawer-footer">
        <button className="btn primary" onClick={() => open(`case/${c.id}`)}>
          See the full working <ArrowRight size={14} />
        </button>
        <button className="btn" onClick={() => open(`lab/${c.id}`)}>
          Replay in Decision Studio <ArrowUpRight size={14} />
        </button>
        <span>Read-only synthetic evidence. No live payments.</span>
      </footer>
    </Modal>
  );
}
