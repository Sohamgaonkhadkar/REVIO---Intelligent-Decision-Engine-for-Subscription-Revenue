import { useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Download,
  Info,
  ShieldCheck,
} from "lucide-react";
import { DateRangeControl } from "../components/ConsoleShell";
import {
  ActionMix,
  BaselineComparison,
  FailurePerformance,
  MoneyMovement,
  RailPerformance,
  RevenuePulse,
  TimeDistribution,
} from "../components/charts";
import {
  EmptyState,
  NumberFlow,
  PageHeading,
  SectionHeading,
  Segmented,
  StatusMark,
} from "../components/ui";
import {
  cases,
  failureMeta,
  formatINR,
  getMetrics,
  type FailureCode,
  type Rail,
} from "../data/simulation";
import { exportFile, filterRange, interventionCost } from "../data/workspace";
import { useWorkspace } from "../state/Workspace";

export default function Outcomes() {
  const w = useWorkspace();
  const [rail, setRail] = useState<"ALL" | Rail>("ALL");
  const [failure, setFailure] = useState("ALL");
  const input = useMemo(
    () =>
      filterRange(cases, w.range).filter(
        (c) =>
          (rail === "ALL" || c.rail === rail) &&
          (failure === "ALL" || c.failureCode === failure),
      ),
    [rail, failure, w.range],
  );
  const m = getMetrics(input);
  const cost = interventionCost(input);
  const escalated = input.filter((c) => c.status === "ESCALATED");
  return (
    <>
      <PageHeading
        title="Revenue analytics"
        description="The full financial picture. Not just a better-looking recovery rate."
        actions={
          <>
            <DateRangeControl />
            <button
              className="btn"
              onClick={() => {
                exportFile("revio-synthetic-analytics.json", {
                  filters: { range: w.range, rail, failure },
                  metrics: m,
                  interventionCost: cost,
                  netRecovered: m.recovered - cost,
                });
                w.notify("Filtered synthetic analytics exported.");
              }}
            >
              <Download size={13} />
              Export report
            </button>
          </>
        }
      />
      <div className="analytics-filterbar">
        <Segmented
          label="Analytics payment rail"
          value={rail}
          onChange={setRail}
          options={[
            { value: "ALL", label: "All rails" },
            { value: "UPI AutoPay", label: "UPI AutoPay" },
            { value: "Card SI", label: "Card SI" },
          ]}
        />
        <select
          className="field"
          aria-label="Analytics failure class"
          value={failure}
          onChange={(e) => setFailure(e.target.value as FailureCode | "ALL")}
        >
          <option value="ALL">All failure classes</option>
          {Object.entries(failureMeta).map(([id, meta]) => (
            <option key={id} value={id}>
              {meta.short}
            </option>
          ))}
        </select>
        <span>{input.length} synthetic cases in view</span>
      </div>
      {!input.length ? (
        <EmptyState
          title="Nothing in this analytical slice"
          body="No synthetic failures match the selected rail, date range and failure class. Try a broader cohort."
          action={
            <button
              className="btn"
              onClick={() => {
                setRail("ALL");
                setFailure("ALL");
                w.setRange("ALL");
              }}
            >
              Reset analytics
            </button>
          }
        />
      ) : (
        <>
          <section className="analytics-position">
            <div className="analytics-net">
              <span className="eyebrow blue">Net recovered value</span>
              <NumberFlow value={m.recovered - cost} />
              <p>Recovered revenue, after modeled intervention costs.</p>
            </div>
            <div className="analytics-figures">
              <div>
                <span>Gross recovered</span>
                <NumberFlow value={m.recovered} />
                <small>
                  {input.filter((c) => c.status === "RECOVERED").length}{" "}
                  successful recoveries
                </small>
              </div>
              <div>
                <span>Intervention cost</span>
                <NumberFlow value={cost} format={(v) => formatINR(v, 2)} />
                <small>
                  {m.recovered
                    ? ((cost / m.recovered) * 100).toFixed(2)
                    : "0.00"}
                  % of recovered value
                </small>
              </div>
              <div>
                <span>Recovery efficiency</span>
                <NumberFlow
                  value={m.recoveryRate}
                  format={(v) => `${v.toFixed(1)}%`}
                />
                <small>Recovered / original value at risk</small>
              </div>
            </div>
          </section>
          <div className="analytics-trends">
            <RevenuePulse input={input} range={w.range} setRange={w.setRange} />
            <section className="analytics-timing">
              <SectionHeading
                title="Time to recovery"
                description="When a failed payment finds its way back."
              />
              <TimeDistribution input={input} />
            </section>
          </div>
          <div className="analytics-two-col">
            <section>
              <SectionHeading
                title="Not every failure is equal"
                description="Recovery performance by failure class, weighted by value."
              />
              <FailurePerformance input={input} />
            </section>
            <section>
              <SectionHeading
                title="Two rails. Different profiles."
                description="UPI AutoPay and card standing instructions."
              />
              <RailPerformance input={input} />
              <div className="analytical-observation">
                <Info size={15} />
                <p>
                  These are descriptive patterns in synthetic records, not
                  causal conclusions. Open and stopped cases remain in each
                  rate's denominator.
                </p>
              </div>
              <SectionHeading
                title="Escalation outcomes"
                description="Where an operator becomes the next best action."
              />
              {escalated.length ? (
                escalated.map((c) => (
                  <button
                    key={c.id}
                    className="analytics-escalation"
                    onClick={() => w.navigate(`case/${c.id}`)}
                  >
                    <span>
                      <StatusMark status={c.status} />
                      <small>{c.id}</small>
                    </span>
                    <strong className="financial">{formatINR(c.amount)}</strong>
                    <ArrowUpRight size={14} />
                  </button>
                ))
              ) : (
                <p className="note">
                  No escalated cases in this selected cohort.
                </p>
              )}
            </section>
          </div>
          <section className="analytics-baselines">
            <SectionHeading
              title="Intelligence should stand up to comparison."
              description="Four recovery strategies. The same risk cohort. No automatic winner."
              tag="Strategy benchmark"
            />
            <BaselineComparison rail={rail} setRail={setRail} />
          </section>
          <div className="analytics-two-col">
            <section>
              <SectionHeading
                title="The financial bridge"
                description="Every rupee moves into an explicit outcome."
              />
              <MoneyMovement
                input={input}
                onBranch={(status) =>
                  w.navigate(
                    `cases?status=${status}&range=${w.range}&rail=${encodeURIComponent(rail)}&failure=${failure}`,
                  )
                }
              />
            </section>
            <section>
              <SectionHeading
                title="The recovery action mix"
                description="Expand an action to inspect the cases behind it."
              />
              <ActionMix input={input} navigate={w.navigate} />
              <button
                className="text-link analytics-lab-link"
                onClick={() => w.navigate("lab")}
              >
                Why did the engine choose these actions?{" "}
                <ArrowRight size={12} />
              </button>
            </section>
          </div>
          <div className="analytics-method">
            <ShieldCheck size={15} />
            <p>
              <strong>Methodology, in plain sight.</strong> Cost model: recorded
              retries at INR 6, contacts at INR 1.80 and escalated reviews at
              INR 450. The same cost model is applied to the REVIO baseline.
              Baseline outcomes are fixed synthetic counterfactuals, not a
              production experiment.
            </p>
          </div>
        </>
      )}
    </>
  );
}
