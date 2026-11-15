import { useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  FileCheck2,
  Info,
  LockKeyhole,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import {
  Disclosure,
  EmptyState,
  PageHeading,
  SectionHeading,
} from "../components/ui";
import {
  cases,
  referenceKnowledge,
  type RecoveryCase,
} from "../data/simulation";
import { useWorkspace } from "../state/Workspace";

const rules = [
  {
    id: "RETRY-MAX-003",
    title: "Retry budget",
    summary: "Maximum 3 attempts after the original debit",
    body: "The original failure does not consume a recovery retry. After three recovery attempts, all additional debit candidates are rejected before scoring.",
    scope: "Immediate and next-window retries",
    evidence: (c: RecoveryCase) =>
      `${c.constraints.retriesUsed} of 3 retries used; ${3 - c.constraints.retriesUsed} remain.`,
  },
  {
    id: "CONTACT-MAX-002",
    title: "Contact cap",
    summary: "Maximum 2 contacts per case",
    body: "Reminders, payment links and payment-method requests share the same contact budget. One channel cannot bypass a limit exhausted through another channel.",
    scope: "Reminder, payment link, instrument update",
    evidence: (c: RecoveryCase) =>
      `${c.constraints.contactsUsed} of 2 contacts used.`,
  },
  {
    id: "QUIET-IST-2108",
    title: "Quiet hours",
    summary: "21:00 to 08:00 IST",
    body: "Immediate debits and customer contact candidates are excluded inside the quiet-hours snapshot. A permitted future window can be considered, but must be verified again before dispatch.",
    scope: "Immediate retry and customer contact",
    evidence: (c: RecoveryCase) =>
      c.constraints.quietHours
        ? "Quiet-hour restriction active at the recorded decision."
        : "Quiet-hour restriction inactive at the recorded decision.",
  },
  {
    id: "MANDATE-ELIG-002",
    title: "Instrument & mandate",
    summary: "Eligibility is a prerequisite, not a score",
    body: "An invalid instrument or revoked mandate blocks debit candidates regardless of estimated success. A permitted repair or customer-initiated path may remain available.",
    scope: "All payment retries",
    evidence: (c: RecoveryCase) =>
      c.constraints.mandateEligible
        ? "The recorded instrument is eligible."
        : "The recorded mandate or instrument is ineligible.",
  },
  {
    id: "COOLDOWN-024",
    title: "Contact cooldown",
    summary: "A 24-hour intervention pause",
    body: "An active cooldown blocks repeated customer contact and immediate retry. The same case can still be considered for deferral, stopping or a permitted later action.",
    scope: "Immediate retry and contact actions",
    evidence: (c: RecoveryCase) =>
      c.constraints.contactCooldown
        ? "A 24-hour cooldown is active."
        : "No active cooldown in this snapshot.",
  },
  {
    id: "CONTACT-OPTOUT-001",
    title: "Customer opt-out",
    summary: "Consent takes precedence over recovery",
    body: "If the synthetic contact opt-out flag is set, customer contact candidates are denied. A probability estimate or knowledge article cannot override the recorded preference.",
    scope: "All customer contact actions",
    evidence: (c: RecoveryCase) =>
      c.constraints.optOut
        ? "Customer contact opt-out is active."
        : "No contact opt-out recorded in this synthetic case.",
  },
  {
    id: "OPS-RAIL-004",
    title: "Payment rail health",
    summary: "No retry into an unavailable rail",
    body: "A throttled or unavailable provider excludes retries until the rail state can be re-evaluated. Waiting can be the highest-value permitted action.",
    scope: "All payment retries",
    evidence: (c: RecoveryCase) =>
      c.constraints.railAvailable
        ? "Rail is available in the decision snapshot."
        : "Rail is unavailable or throttled.",
  },
  {
    id: "OPS-KILL-001",
    title: "Operational kill switch",
    summary: "A deliberate stop for automatic intervention",
    body: "An engaged operational kill switch suppresses every automated intervention. Stop and human-review control paths remain. The model cannot turn the switch off.",
    scope: "Every automated intervention",
    evidence: (c: RecoveryCase) =>
      c.constraints.killSwitch
        ? "Operational kill switch is engaged."
        : "Operational kill switch is not engaged.",
  },
];

export default function Knowledge() {
  const w = useWorkspace();
  const [caseId, setCaseId] = useState(
    cases.find((c) => c.id === w.route.split("/")[1])?.id ?? cases[0].id,
  );
  const [rule, setRule] = useState(0);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All knowledge");
  const c = cases.find((item) => item.id === caseId) ?? cases[0];
  const articles = useMemo(
    () =>
      referenceKnowledge.filter(
        (k) =>
          (!query.trim() ||
            `${k.title} ${k.body} ${k.category} ${k.refs.join(" ")}`
              .toLowerCase()
              .includes(query.toLowerCase())) &&
          (category === "All knowledge" ||
            (category === "Payment rails" && k.id === "KB-002") ||
            (category === "Model & system" &&
              ["KB-003", "KB-004", "KB-006"].includes(k.id)) ||
            (category === "Recovery strategy" &&
              ["KB-001", "KB-005"].includes(k.id))),
      ),
    [query, category],
  );
  return (
    <>
      <PageHeading
        title="Knowledge & rules"
        description="A system that knows the difference between intelligence and permission."
      />
      <div className="knowledge-principle">
        <div>
          <span className="principle-icon">
            <ShieldCheck size={20} />
          </span>
          <span>
            <strong>Rules determine what may happen.</strong>
            <small>Executable guard conditions / authority</small>
          </span>
        </div>
        <span className="knowledge-separation">≠</span>
        <div>
          <span className="principle-icon reference">
            <BookOpen size={20} />
          </span>
          <span>
            <strong>Knowledge explains why it happens.</strong>
            <small>Reference context / never an override</small>
          </span>
        </div>
      </div>
      <div className="knowledge-inspector">
        <aside className="rule-navigation">
          <span className="eyebrow">The guard architecture</span>
          {rules.map((r, i) => (
            <button
              key={r.id}
              onClick={() => setRule(i)}
              className={rule === i ? "active" : ""}
            >
              <span className="rule-number">0{i + 1}</span>
              <span>
                <strong>{r.title}</strong>
                <small>{r.summary}</small>
              </span>
              <ChevronRight size={12} />
            </button>
          ))}
        </aside>
        <div className="rule-detail">
          <AnimatePresence mode="wait">
            <motion.div
              key={rule}
              initial={{ opacity: 0, y: 7 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <span className="rule-reference mono">
                <FileCheck2 size={13} />
                {rules[rule].id}
              </span>
              <h2>{rules[rule].title}</h2>
              <p>{rules[rule].body}</p>
              <dl className="rule-detail-meta">
                <div>
                  <dt>Scope</dt>
                  <dd>{rules[rule].scope}</dd>
                </div>
                <div>
                  <dt>Rule pack</dt>
                  <dd className="mono">rp_in_recurring_2026.06.3</dd>
                </div>
                <div>
                  <dt>Authority</dt>
                  <dd>Illustrative internal policy, not legal certification</dd>
                </div>
              </dl>
            </motion.div>
          </AnimatePresence>
          <div className="recorded-rule-check">
            <div className="recorded-rule-heading">
              <span>
                <LockKeyhole size={13} />
                Recorded constraint check
              </span>
              <select
                className="field"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                aria-label="Choose a case for recorded constraint inspection"
              >
                {cases.map((item) => (
                  <option key={item.id}>{item.id}</option>
                ))}
              </select>
            </div>
            <p className="rule-case-evidence">{rules[rule].evidence(c)}</p>
            <div className="rule-result-list">
              {c.candidates.map((a) => (
                <div key={a.id}>
                  <span className={a.eligible ? "permitted" : "blocked"}>
                    {a.eligible ? <Check size={12} /> : <X size={12} />}
                  </span>
                  <span>
                    <strong>{a.label}</strong>
                    <small>
                      {a.eligible
                        ? "Permitted by the recorded rule snapshot."
                        : a.denial}
                    </small>
                  </span>
                  <span className={a.eligible ? "green" : "red"}>
                    {a.eligible ? "Allowed" : "Denied"}
                  </span>
                </div>
              ))}
            </div>
            <div className="recorded-rule-footer">
              <span>
                <Info size={12} />
                Read-only fixture. No backend checks run here.
              </span>
              <button
                className="text-link"
                onClick={() => w.navigate(`case/${c.id}`)}
              >
                Open decision <ArrowUpRight size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>
      <section className="knowledge-browser">
        <SectionHeading
          title="The reference library"
          description="Useful context, without executable authority."
          action={
            <label className="search-field">
              <Search size={14} />
              <input
                className="field"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search reference knowledge"
                placeholder="Search mandates, probabilities, rules..."
              />
            </label>
          }
        />
        <div className="knowledge-category-tabs">
          {[
            "All knowledge",
            "Recovery strategy",
            "Payment rails",
            "Model & system",
            "Regulatory guidance",
          ].map((cat) => (
            <button
              key={cat}
              className={category === cat ? "active" : ""}
              onClick={() => setCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className="knowledge-articles">
          {articles.length ? (
            articles.map((a) => (
              <Disclosure
                key={a.id}
                title={a.title}
                subtitle={`${a.category} / ${a.id}`}
                right={<BookOpen size={14} />}
              >
                <p>{a.body}</p>
                <div className="article-sources">
                  <span>Source: bundled REVIO simulation documentation</span>
                  <span className="mono">{a.refs.join(" / ")}</span>
                </div>
                <button
                  className="text-link"
                  onClick={() => w.navigate("trust")}
                >
                  Read the system boundaries <ArrowRight size={12} />
                </button>
              </Disclosure>
            ))
          ) : (
            <EmptyState
              title={
                category === "Regulatory guidance"
                  ? "No external legal sources are attached"
                  : "No reference articles match"
              }
              body={
                category === "Regulatory guidance"
                  ? "These are illustrative internal recovery policies, not regulatory advice. Production integration requires authoritative, reviewed legal sources."
                  : "Try a broader term, a different category or clear your search."
              }
              action={
                category !== "Regulatory guidance" ? (
                  <button
                    className="btn"
                    onClick={() => {
                      setQuery("");
                      setCategory("All knowledge");
                    }}
                  >
                    Clear search
                  </button>
                ) : undefined
              }
            />
          )}
        </div>
      </section>
    </>
  );
}
