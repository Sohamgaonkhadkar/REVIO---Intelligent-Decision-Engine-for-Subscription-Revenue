import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { PageHeading, EmptyState, NumberFlow } from "../components/ui";
import { formatINR, formatTime } from "../data/simulation";
import { useWorkspace } from "../state/Workspace";
import { readApi } from "../api/runtime";
import type {
  Baselines,
  CaseDetail,
  CaseRow,
  DecisionRecord,
  EventRecord,
  Outcomes,
  Page,
} from "../api/contracts";

function useApi<T>(path: string) {
  return useQuery({
    queryKey: ["api", path],
    queryFn: ({ signal }) => readApi<T>(path, signal),
    retry: 1,
    refetchInterval: 30000,
  });
}
function Resource<T>({
  path,
  children,
}: {
  path: string;
  children: (data: T) => React.ReactNode;
}) {
  const q = useApi<T>(path);
  if (q.isPending)
    return (
      <div className="live-surface" role="status">
        Reading recorded evidence…
      </div>
    );
  if (q.isError)
    return (
      <div className="live-surface" role="alert">
        <h2>Backend evidence unavailable</h2>
        <p>{q.error.message}</p>
        <button className="btn" onClick={() => q.refetch()}>
          Retry request
        </button>
      </div>
    );
  return (
    <>
      {q.isFetching && <small role="status">Refreshing…</small>}
      {children(q.data)}
    </>
  );
}
function Evidence({
  data,
  title = "Recorded evidence",
}: {
  data: unknown;
  title?: string;
}) {
  return (
    <details className="live-evidence">
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}
function Bars({
  values,
  money = false,
}: {
  values: Record<string, number>;
  money?: boolean;
}) {
  const max = Math.max(1, ...Object.values(values));
  return (
    <div className="live-bars">
      {Object.entries(values).map(([name, value]) => (
        <div
          key={name}
          tabIndex={0}
          title={`${name}: ${money ? formatINR(value) : value}`}
        >
          <span>{name.replace(/_/g, " ")}</span>
          <div className="live-track">
            <motion.i
              initial={{ width: 0 }}
              animate={{ width: `${(value / max) * 100}%` }}
            />
          </div>
          <strong>
            {money ? formatINR(value) : value.toLocaleString("en-IN")}
          </strong>
        </div>
      ))}
    </div>
  );
}
function OutcomesView({ overview }: { overview: boolean }) {
  const w = useWorkspace();
  return (
    <>
      <Resource<Outcomes> path="/api/outcomes">
        {(out) => (
          <>
            <section className="live-hero">
              <div>
                <span className="eyebrow">SIM / PostgreSQL evidence</span>
                <h2>
                  Every recovery.
                  <br />A considered decision.
                </h2>
                <p>Recovered revenue in the simulated backend</p>
                <div className="hero-number">
                  <NumberFlow value={out.recovered_inr} format={formatINR} />
                </div>
                <button
                  className="btn primary"
                  onClick={() => w.navigate("cases")}
                >
                  Investigate recovery cases →
                </button>
              </div>
              <img
                src="/images/recovery-workspace.jpg"
                alt="Quiet workspace in soft daylight"
              />
            </section>
            <div className="live-metrics">
              {[
                ["Revenue at risk", formatINR(out.at_risk_inr)],
                ["Cases", out.cases_total],
                [
                  "Recovery rate · case count",
                  `${(out.recovery_rate * 100).toFixed(2)}%`,
                ],
                [
                  "Average recovery time",
                  out.avg_time_to_recover_h == null
                    ? "Unavailable"
                    : `${out.avg_time_to_recover_h}h`,
                ],
              ].map(([label, value]) => (
                <div key={label}>
                  <small>{label}</small>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <section className="live-surface">
              <h2>
                {overview ? "Recovery flow" : "Recovery by failure class"}
              </h2>
              <Bars
                values={
                  overview
                    ? out.cases_by_state
                    : Object.fromEntries(
                        Object.entries(out.by_failure_class).map(([key, v]) => [
                          key,
                          v.rec_inr,
                        ]),
                      )
                }
                money={!overview}
              />
            </section>
            {!overview && (
              <>
                <section className="live-surface">
                  <h2>Recovery by payment rail</h2>
                  <Bars
                    values={Object.fromEntries(
                      Object.entries(out.by_rail).map(([key, v]) => [
                        key,
                        v.rec_inr,
                      ]),
                    )}
                    money
                  />
                </section>
                <section className="live-surface">
                  <h2>Recovery timing · case count</h2>
                  <Bars values={out.timing ?? {}} />
                  <h2>Executed action mix</h2>
                  <Bars values={out.action_mix} />
                </section>
              </>
            )}
            <section className="live-surface">
              <h2>Compliance evidence</h2>
              <Bars values={out.compliance} />
            </section>
          </>
        )}
      </Resource>
      <Resource<Baselines> path="/api/baselines">
        {(base) => (
          <section className="live-surface">
            <h2>Same population. Honest comparison.</h2>
            <p>{base.methodology}</p>
            <p>
              {base.population.cases} cases ·{" "}
              {formatINR(base.population.at_risk_inr)} at risk
            </p>
            <Bars
              values={{
                ...Object.fromEntries(
                  Object.entries(base.baselines).map(([key, value]) => [
                    key,
                    value.recovered_inr,
                  ]),
                ),
                REVIO: base.recoverydesk.recovered_inr,
              }}
              money
            />
            <Evidence
              data={base}
              title="Baseline rates, attempts, contacts and methodology"
            />
          </section>
        )}
      </Resource>
      {overview && <Journal />}
    </>
  );
}
function CasesView() {
  const w = useWorkspace();
  const [query, setQuery] = useState("");
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [rail, setRail] = useState("");
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(query);
      setOffset(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  const params = new URLSearchParams({ limit: "25", offset: String(offset) });
  if (q) params.set("q", q);
  if (state) params.set("state", state);
  if (rail) params.set("rail", rail);
  return (
    <>
      <div className="live-toolbar">
        <input
          aria-label="Search recovery cases"
          placeholder="Search case ID or failure class"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="Filter case state"
          value={state}
          onChange={(e) => {
            setState(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All states</option>
          {[
            "OPEN_DECISION",
            "ACTION_PENDING",
            "WAITING",
            "AWAITING_CUSTOMER",
            "RECOVERED",
            "STOPPED",
            "ESCALATED",
          ].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="Filter payment rail"
          value={rail}
          onChange={(e) => {
            setRail(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All rails</option>
          <option value="upi_autopay">UPI AutoPay</option>
          <option value="card_si">Card SI</option>
        </select>
      </div>
      <Resource<Page<CaseRow>> path={`/api/cases?${params}`}>
        {(data) => (
          <section className="live-surface">
            <p>{data.total} matching cases</p>
            {!data.items.length && (
              <EmptyState
                title="No matching cases"
                body="Try a different search or filter."
              />
            )}
            <div className="live-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Failure</th>
                    <th>Rail</th>
                    <th>State</th>
                    <th>At risk</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.case_id}>
                      <td>
                        <button
                          className="btn"
                          onClick={() => w.navigate(`case/${c.case_id}`)}
                        >
                          {c.case_id}
                        </button>
                      </td>
                      <td>{c.failure_class}</td>
                      <td>{c.rail}</td>
                      <td>{c.state}</td>
                      <td>{formatINR(c.amount_at_risk)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="live-toolbar">
              <button
                className="btn"
                disabled={!offset}
                onClick={() => setOffset((v) => Math.max(0, v - 25))}
              >
                Previous
              </button>
              <span>Page {offset / 25 + 1}</span>
              <button
                className="btn"
                disabled={offset + 25 >= (data.total ?? 0)}
                onClick={() => setOffset((v) => v + 25)}
              >
                Next
              </button>
            </div>
          </section>
        )}
      </Resource>
    </>
  );
}
function DecisionReplay({ items }: { items: DecisionRecord[] }) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      if (index >= items.length - 1) setPlaying(false);
      else setIndex((v) => v + 1);
    }, 1400);
    return () => clearTimeout(timer);
  }, [playing, index, items.length]);
  const item = items[Math.min(index, items.length - 1)];
  if (!item)
    return (
      <EmptyState
        title="No recorded decisions"
        body="The backend has not recorded a decision for this case."
      />
    );
  return (
    <section className="live-surface">
      <h2>Recorded decision replay</h2>
      <div className="live-toolbar">
        <button
          className="btn primary"
          onClick={() => {
            if (index === items.length - 1) setIndex(0);
            setPlaying((v) => !v);
          }}
        >
          {playing ? "Pause replay" : "Play recorded decisions"}
        </button>
        <input
          aria-label="Recorded decision"
          type="range"
          min={0}
          max={items.length - 1}
          value={index}
          onChange={(e) => {
            setPlaying(false);
            setIndex(Number(e.target.value));
          }}
        />
        <span>
          {index + 1} / {items.length}
        </span>
      </div>
      <p>
        {formatTime(item.taken_at)} ·{" "}
        {item.fallback
          ? "Fallback scorer · uncalibrated"
          : "Recorded model · uncalibrated"}
      </p>
      <Evidence
        data={item.chosen}
        title="Selected action and execution authority"
      />
      {item.candidates.map((c) => (
        <div className="live-candidate" key={c.candidate_id}>
          <strong>{c.candidate_id}</strong>
          <span>
            {c.verdict.allowed
              ? "Permitted"
              : `Blocked: ${c.verdict.reasons.join(", ")}`}
          </span>
          <span>p̂ {c.p_hat == null ? "Not scored" : c.p_hat.toFixed(4)}</span>
          <span>
            EV {c.ev_inr == null ? "Unavailable" : formatINR(c.ev_inr, 2)}
          </span>
          <Evidence
            data={c}
            title="Recorded constraints, features and exact EV components"
          />
        </div>
      ))}
      <Evidence data={item} title="Complete decision record" />
    </section>
  );
}
function Investigation({ id }: { id: string }) {
  const path = `/api/cases/${encodeURIComponent(id)}`;
  return (
    <>
      <Resource<CaseDetail> path={path}>
        {(c) => (
          <section className="live-surface">
            <h2>{c.case_id}</h2>
            <p>
              {c.state} · {c.rail} · {formatINR(c.amount_at_risk)}
            </p>
            <p>
              {c.failure_class} · {c.retries_used} retries · {c.contacts_sent}{" "}
              contacts
            </p>
            <Evidence
              data={c}
              title="Case, subscription and payment attempts"
            />
          </section>
        )}
      </Resource>
      <Resource<Page<DecisionRecord>> path={`${path}/decisions`}>
        {(d) => <DecisionReplay items={d.items} />}
      </Resource>
      <Resource<Page<Record<string, unknown>>> path={`${path}/intents`}>
        {(d) => (
          <section className="live-surface">
            <h2>Execution records</h2>
            {d.items.length ? (
              d.items.map((v, i) => (
                <Evidence
                  key={i}
                  data={v}
                  title={`Execution intent ${i + 1}`}
                />
              ))
            ) : (
              <p>No execution intents recorded.</p>
            )}
          </section>
        )}
      </Resource>
      <Journal caseId={id} />
    </>
  );
}
function Journal({ caseId }: { caseId?: string }) {
  const [q, setQ] = useState("");
  return (
    <section className="live-surface">
      <h2>Append-only audit journal</h2>
      <input
        aria-label="Search API journal"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search loaded evidence"
      />
      <Resource<Page<EventRecord>>
        path={
          caseId
            ? `/api/cases/${encodeURIComponent(caseId)}/events?limit=500`
            : "/api/events?limit=200"
        }
      >
        {(d) => (
          <>
            <p>
              {d.items.length} loaded records
              {d.total != null ? ` of ${d.total} total` : ""}. Global feed is
              the latest 200 records.
            </p>
            {d.items
              .filter((v) =>
                JSON.stringify(v).toLowerCase().includes(q.toLowerCase()),
              )
              .map((v) => (
                <Evidence
                  key={v.event_id}
                  data={v}
                  title={`${formatTime(v.occurred_at)} · ${v.event_type} · ${v.case_id ?? caseId}`}
                />
              ))}
            {!d.items.length && <p>No journal records.</p>}
          </>
        )}
      </Resource>
    </section>
  );
}
function KnowledgeView() {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [id, setId] = useState("");
  const [check, setCheck] = useState("");
  return (
    <>
      <section className="live-surface">
        <h2>Rules determine permission. Knowledge explains context.</h2>
        <Resource<Record<string, unknown>> path="/api/constraints">
          {(d) => (
            <Evidence
              data={d}
              title="Active backend rule packs, budgets and windows"
            />
          )}
        </Resource>
        <form
          className="live-toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            setCheck(id);
          }}
        >
          <input
            aria-label="Case ID for constraint check"
            minLength={3}
            required
            value={id}
            onChange={(e) => setId(e.target.value)}
            placeholder="Case ID"
          />
          <button className="btn primary">Check constraints</button>
        </form>
        {check && (
          <Resource<Record<string, unknown>>
            path={`/api/constraints/check?case_id=${encodeURIComponent(check)}`}
          >
            {(d) => (
              <Evidence data={d} title="Read-only constraint engine results" />
            )}
          </Resource>
        )}
      </section>
      <section className="live-surface">
        <h2>Reference knowledge</h2>
        <form
          className="live-toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q);
          }}
        >
          <input
            aria-label="Search backend knowledge"
            minLength={2}
            maxLength={300}
            required
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search reference corpus"
          />
          <button className="btn primary">Search knowledge</button>
        </form>
        {search ? (
          <Resource<{ results: unknown[] }>
            path={`/api/knowledge/search?q=${encodeURIComponent(search)}&k=10`}
          >
            {(d) => (
              <>
                {d.results.length ? (
                  d.results.map((v, i) => (
                    <Evidence
                      key={i}
                      data={v}
                      title={`Reference match ${i + 1}`}
                    />
                  ))
                ) : (
                  <p>No reference matches.</p>
                )}
              </>
            )}
          </Resource>
        ) : (
          <Resource<Record<string, unknown>> path="/api/knowledge">
            {(d) => (
              <Evidence
                data={d}
                title="Ingested sources and retrieval identity"
              />
            )}
          </Resource>
        )}
      </section>
    </>
  );
}
export default function LiveWorkspace({ section }: { section: string }) {
  const w = useWorkspace();
  const titles: Record<string, string> = {
    overview: "Overview",
    cases: "Recovery cases",
    case: "Case investigation",
    outcomes: "Revenue analytics",
    lab: "Decision Studio",
    knowledge: "Knowledge & rules",
    audit: "Audit trail",
    trust: "System & trust",
  };
  return (
    <>
      <PageHeading
        title={titles[section] ?? "Workspace"}
        description="SIM · API evidence from the existing REVIO backend. No real payment performance claims."
      />
      {section === "overview" || section === "outcomes" ? (
        <OutcomesView overview={section === "overview"} />
      ) : section === "cases" ? (
        <CasesView />
      ) : section === "case" ? (
        <Investigation id={w.route.split("/")[1] ?? ""} />
      ) : section === "lab" ? (
        <>
          <section className="live-surface">
            <h2>Replay recorded decisions</h2>
            <p>
              Open a backend case to inspect its decisions, constraints,
              probabilities, expected values and execution journal.
            </p>
            <button className="btn primary" onClick={() => w.navigate("cases")}>
              Choose a recorded case
            </button>
            <p>
              The standalone Scenario Playground uses fixed educational fixtures
              and never runs backend inference.
            </p>
            <a className="btn" href="?mode=simulation#/lab">
              Open educational scenarios
            </a>
          </section>
        </>
      ) : section === "knowledge" ? (
        <KnowledgeView />
      ) : section === "audit" ? (
        <Journal />
      ) : section === "trust" ? (
        <>
          <section className="live-surface">
            <h2>Backend health</h2>
            <Resource<Record<string, unknown>> path="/health">
              {(d) => <Evidence data={d} title="Health and database status" />}
            </Resource>
          </section>
          <section className="live-surface">
            <h2>Model activation and fallback</h2>
            <Resource<Record<string, unknown>> path="/api/model">
              {(d) => (
                <Evidence
                  data={d}
                  title="Actual scorer identity, activation gate and benchmarks"
                />
              )}
            </Resource>
          </section>
        </>
      ) : (
        <EmptyState
          title="Unknown route"
          body="Choose a destination in the navigation."
        />
      )}
    </>
  );
}
