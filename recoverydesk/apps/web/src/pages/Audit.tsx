import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  Download,
  Search,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { EmptyState, PageHeading } from "../components/ui";
import { allJournalEntries, cases, formatTime } from "../data/simulation";
import { exportFile, timeOnly, dateOnly } from "../data/workspace";
import { useWorkspace } from "../state/Workspace";
import { runDiagnostics } from "../data/diagnostics";

export default function Audit() {
  const w = useWorkspace();
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("ALL");
  const [caseId, setCaseId] = useState("ALL");
  const [order, setOrder] = useState("newest");
  const [limit, setLimit] = useState(15);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const filtered = useMemo(
    () =>
      allJournalEntries
        .filter(
          (e) =>
            (stage === "ALL" || e.stage === stage) &&
            (caseId === "ALL" || e.caseId === caseId) &&
            (!query.trim() ||
              `${e.id} ${e.caseId} ${e.type} ${e.actor} ${e.summary} ${Object.values(e.refs).join(" ")}`
                .toLowerCase()
                .includes(query.toLowerCase())),
        )
        .sort(
          (a, b) =>
            (new Date(a.at).getTime() - new Date(b.at).getTime()) *
            (order === "newest" ? -1 : 1),
        ),
    [query, stage, caseId, order],
  );
  useEffect(() => {
    setLimit(15);
    setExpanded(null);
  }, [query, stage, caseId, order]);
  return (
    <>
      <PageHeading
        title="Audit trail"
        description="The evidence is part of the product. Every step has a record."
        actions={
          <>
            <button
              className="btn"
              onClick={() => {
                const check = runDiagnostics().find(
                  (d) => d.label === "Unique, chronological evidence",
                );
                setVerified(check?.passed ?? false);
              }}
            >
              <ShieldCheck size={13} />
              Check integrity
            </button>
            <button
              className="btn primary"
              onClick={() => {
                exportFile("revio-synthetic-audit.json", filtered);
                w.notify(
                  `${filtered.length} filtered journal records exported.`,
                );
              }}
            >
              <Download size={13} />
              Export journal
            </button>
          </>
        }
      />
      <div className="audit-summary">
        <span className="audit-summary-icon">
          <Terminal size={24} />
        </span>
        <div>
          <h2>An append-only story.</h2>
          <p>
            Recorded synthetic evidence, from the first failure to the final
            outcome.
          </p>
        </div>
        <span>
          <strong>{allJournalEntries.length}</strong>journal entries
        </span>
        <span>
          <strong>{cases.length}</strong>case records
        </span>
        <span className="audit-readonly">
          <LockIcon />
          Read-only ledger
        </span>
      </div>
      <AnimatePresence>
        {verified !== null && (
          <motion.div
            className={`integrity-result ${verified ? "pass" : "fail"}`}
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <ShieldCheck size={17} />
            <span>
              <strong>
                {verified
                  ? "Local structural checks passed."
                  : "A structural inconsistency was found."}
              </strong>{" "}
              Unique journal IDs and chronology were checked in memory. This is
              not cryptographic verification or backend attestation.
            </span>
            <button className="text-link" onClick={() => w.navigate("trust")}>
              All diagnostics <ArrowUpRight size={12} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="audit-filters">
        <label className="search-field">
          <Search size={14} />
          <input
            className="field"
            aria-label="Search audit evidence"
            placeholder="Search events, references, actors or evidence..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          className="field"
          aria-label="Audit stage filter"
          value={stage}
          onChange={(e) => setStage(e.target.value)}
        >
          <option value="ALL">All stages</option>
          {[
            "DETECT",
            "CONSTRAIN",
            "PREDICT",
            "OPTIMIZE",
            "EXECUTE",
            "AUDIT",
            "OUTCOME",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          className="field"
          aria-label="Audit case filter"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
        >
          <option value="ALL">All case references</option>
          {cases.map((c) => (
            <option key={c.id}>{c.id}</option>
          ))}
        </select>
        <select
          className="field"
          aria-label="Audit chronological order"
          value={order}
          onChange={(e) => setOrder(e.target.value)}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>
      <div className="audit-match-count">
        <span>{filtered.length} matching records</span>
        <span>Asia/Kolkata / synthetic journal</span>
      </div>
      <section className="audit-ledger">
        <div className="audit-table-head">
          <span>Recorded at</span>
          <span>Event / action</span>
          <span>Case reference</span>
          <span>Result / compliance</span>
          <span />
        </div>
        {filtered.length ? (
          filtered.slice(0, limit).map((e) => (
            <div
              className={`audit-ledger-entry ${expanded === e.id ? "expanded" : ""}`}
              key={e.id}
            >
              <button
                className="audit-ledger-row"
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                aria-expanded={expanded === e.id}
              >
                <time>
                  <strong>{timeOnly(e.at)}</strong>
                  <span>{dateOnly(e.at)} 2026</span>
                </time>
                <span className="audit-event">
                  <span
                    className={`audit-event-icon ${e.stage === "OUTCOME" ? "success" : ""}`}
                  >
                    {e.stage === "OUTCOME" ? (
                      <Check size={12} />
                    ) : (
                      <Terminal size={12} />
                    )}
                  </span>
                  <span>
                    <strong>{e.type}</strong>
                    <small>
                      {String(
                        e.refs.selected_action ?? e.refs.dispatch ?? e.actor,
                      ).replace(/_/g, " ")}
                    </small>
                  </span>
                </span>
                <span className="mono audit-case-ref">{e.caseId}</span>
                <span className="audit-event-result">
                  <strong>
                    {e.stage === "CONSTRAIN"
                      ? "Constraints evaluated"
                      : e.stage === "OUTCOME"
                        ? "Recovery confirmed"
                        : e.stage === "PREDICT"
                          ? "Eligible candidates only"
                          : e.stage === "EXECUTE"
                            ? String(
                                e.refs.gateway_check ?? "Recorded",
                              ).replace(/_/g, " ")
                            : "Evidence recorded"}
                  </strong>
                  <small>{e.stage.toLowerCase()} / synthetic</small>
                </span>
                <ChevronDown
                  size={14}
                  className={expanded === e.id ? "rotated" : ""}
                />
              </button>
              <AnimatePresence initial={false}>
                {expanded === e.id && (
                  <motion.div
                    className="audit-expanded"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.24 }}
                  >
                    <div>
                      <section>
                        <span className="eyebrow blue">
                          The recorded explanation
                        </span>
                        <p>{e.summary}</p>
                        <span className="mono">{e.id}</span>
                        <small>
                          {formatTime(e.at)} / {e.actor}
                        </small>
                        <button
                          className="text-link"
                          onClick={() => w.navigate(`case/${e.caseId}`)}
                        >
                          Open full investigation <ArrowUpRight size={12} />
                        </button>
                      </section>
                      <dl className="evidence-fields">
                        {Object.entries(e.refs).map(([key, value]) => (
                          <div key={key}>
                            <dt>{key.replace(/_/g, " ")}</dt>
                            <dd>{String(value)}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))
        ) : (
          <EmptyState
            body="No journal entry matches the current search and filters."
            action={
              <button
                className="btn"
                onClick={() => {
                  setQuery("");
                  setStage("ALL");
                  setCaseId("ALL");
                }}
              >
                Clear filters
              </button>
            }
          />
        )}
      </section>
      {limit < filtered.length && (
        <div className="audit-load-more">
          <button className="btn" onClick={() => setLimit((l) => l + 15)}>
            Load {Math.min(15, filtered.length - limit)} more records{" "}
            <ChevronDown size={13} />
          </button>
          <span>
            {Math.min(limit, filtered.length)} / {filtered.length} records shown
          </span>
        </div>
      )}
    </>
  );
}
function LockIcon() {
  return (
    <svg width="13" height="14" viewBox="0 0 14 16" fill="none">
      <rect x="2" y="7" width="10" height="8" rx="2" stroke="currentColor" />
      <path d="M4 7V4C4 0 10 0 10 4V7M7 10V12" stroke="currentColor" />
    </svg>
  );
}
