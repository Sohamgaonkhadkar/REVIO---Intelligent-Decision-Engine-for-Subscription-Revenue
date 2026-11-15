import { useState } from "react";
import { motion } from "motion/react";
import {
  ArrowUpRight,
  Check,
  CircleCheck,
  Cpu,
  Database,
  Download,
  FileCheck2,
  Globe2,
  Layers3,
  Play,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  Disclosure,
  PageHeading,
  SectionHeading,
  SimulationBadge,
} from "../components/ui";
import {
  allJournalEntries,
  cases,
  getMetrics,
  modelFeatures,
  systemFacts,
} from "../data/simulation";
import { exportFile } from "../data/workspace";
import { runDiagnostics } from "../data/diagnostics";
import { useWorkspace } from "../state/Workspace";

export default function Trust() {
  const w = useWorkspace();
  const [diagnostics, setDiagnostics] = useState<ReturnType<
    typeof runDiagnostics
  > | null>(null);
  const m = getMetrics();
  return (
    <>
      <PageHeading
        title="System & trust"
        description="Clarity about every capability. Honesty about every boundary."
        actions={
          <button
            className="btn"
            onClick={() => {
              exportFile("revio-synthetic-system-manifest.json", {
                ...systemFacts,
                featureSchema: modelFeatures,
                runtime:
                  "Frontend simulation / no model or database connection",
                diagnostics,
              });
              w.notify("Synthetic system manifest exported.");
            }}
          >
            <Download size={13} />
            Export manifest
          </button>
        }
      />
      <div className="trust-banner">
        <span className="trust-banner-icon">
          <ShieldCheck size={30} />
        </span>
        <div>
          <SimulationBadge />
          <h2>
            Designed to be understood.
            <br />
            Built to be constrained.
          </h2>
          <p>
            A local frontend prototype. No real customers, payment actions,
            model inference or backend connections.
          </p>
        </div>
        <div className="trust-local-status">
          <i />
          <span>
            Local workspace available
            <small>Authoritative services not connected</small>
          </span>
        </div>
      </div>
      <section className="trust-status-grid">
        {[
          {
            label: "Model scorer",
            state: "Metadata sample only",
            note: "XGBoost / 32 declared features",
            icon: Cpu,
            color: "blue",
          },
          {
            label: "Feature schema",
            state: `${modelFeatures.length} fields available`,
            note: "Inspectable local schema definition",
            icon: Layers3,
            color: "green",
          },
          {
            label: "Rule pack",
            state: "Illustrative snapshot",
            note: "Internal policy; no certification",
            icon: FileCheck2,
            color: "blue",
          },
          {
            label: "Compliance record",
            state: `${m.violations} recorded violations`,
            note: `${m.prevented} candidates blocked before scoring`,
            icon: ShieldCheck,
            color: "green",
          },
          {
            label: "Database connection",
            state: "Not connected",
            note: "PostgreSQL is not accessible here",
            icon: Database,
            color: "muted",
          },
          {
            label: "Production connectivity",
            state: "No external services",
            note: "No API keys or payment integrations",
            icon: Globe2,
            color: "muted",
          },
        ].map((s) => (
          <div key={s.label}>
            <s.icon size={19} />
            <span>{s.label}</span>
            <strong className={s.color}>{s.state}</strong>
            <small>{s.note}</small>
          </div>
        ))}
      </section>
      <div className="trust-detail-grid">
        <section>
          <SectionHeading
            title="A probability is not permission."
            description="Model capability, with its limits kept in view."
            tag="Model transparency"
          />
          <dl className="context-fields">
            <div>
              <dt>Declared model version</dt>
              <dd className="mono">{systemFacts.model.version}</dd>
            </div>
            <div>
              <dt>Input schema</dt>
              <dd className="mono">recovery-features/v3</dd>
            </div>
            <div>
              <dt>Scoring in this browser</dt>
              <dd>None / precomputed illustrative estimates</dd>
            </div>
            <div>
              <dt>Calibration artifact</dt>
              <dd className="red">Not available</dd>
            </div>
            <div>
              <dt>Authorization capability</dt>
              <dd>None. A model cannot authorize payment actions.</dd>
            </div>
          </dl>
          <Disclosure
            title="Inspect all 32 input features"
            subtitle="Ordered schema / no customer data"
          >
            <div className="feature-schema">
              {modelFeatures.map((f, i) => (
                <div key={f}>
                  <small>{String(i + 1).padStart(2, "0")}</small>
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </Disclosure>
        </section>
        <section>
          <SectionHeading
            title="The fallback is explicit."
            description="Scorer state must never be silently ambiguous."
            tag="Fallback & execution"
          />
          <div className="fallback-state">
            <span className="fallback-indicator" />
            <div>
              <strong>Fallback sample: armed, not active</strong>
              <p>
                The declared fallback is deterministic eligible-action ordering
                when the backend scorer is unavailable. This browser has no
                scorer service, so neither genuine model inference nor a backend
                fallback is running.
              </p>
            </div>
          </div>
          <Disclosure
            title="Why execution rechecks constraints"
            subtitle="A decision can age before it is dispatched"
            defaultOpen
          >
            <p>
              Mandates, budgets, rail health and operational controls can change
              after action selection. A real execution gateway must reverify
              authoritative state immediately before dispatch and record the
              check under an idempotency key.
            </p>
          </Disclosure>
          <Disclosure
            title="Rule manifest and signature boundary"
            subtitle={systemFacts.rules.pack}
          >
            <p>
              The rule-pack identifier and digest in the bundled data are
              simulated metadata. No cryptographic signature has been verified
              against an authoritative artifact in this prototype.
            </p>
            <span className="mono">
              Sample digest: {systemFacts.rules.digest}
            </span>
          </Disclosure>
        </section>
      </div>
      <section className="trust-diagnostics">
        <SectionHeading
          title="Trust, with something to inspect."
          description="Actual local checks against the bundled ledger, not a decorative health indicator."
          action={
            <button
              className="btn primary"
              onClick={() => setDiagnostics(runDiagnostics())}
            >
              <Play size={12} />
              Run local diagnostics
            </button>
          }
        />
        {diagnostics ? (
          <>
            <div className="diagnostic-summary">
              <CircleCheck size={19} />
              <strong>
                {diagnostics.filter((d) => d.passed).length} of{" "}
                {diagnostics.length} invariants passed
              </strong>
              <span>Checked in memory / no remote calls</span>
            </div>
            <div className="diagnostic-grid">
              {diagnostics.map((d, i) => (
                <motion.div
                  key={d.label}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, delay: i * 0.025 }}
                >
                  <span
                    className={d.passed ? "diagnostic-pass" : "diagnostic-fail"}
                  >
                    {d.passed ? <Check size={13} /> : <X size={13} />}
                  </span>
                  <span>
                    <strong>{d.label}</strong>
                    <small>{d.detail}</small>
                  </span>
                </motion.div>
              ))}
            </div>
          </>
        ) : (
          <div className="diagnostics-idle">
            <ShieldCheck size={24} />
            <span>
              <strong>Evidence, not assumptions.</strong>
              <p>
                Check journal uniqueness, permitted selections, EV arithmetic,
                cost allocations and financial reconciliation.
              </p>
            </span>
            <span className="mono">
              {cases.length} cases / {allJournalEntries.length} evidence entries
            </span>
          </div>
        )}
      </section>
      <section className="trust-integrations">
        <SectionHeading
          title="An honest integration boundary"
          description="The data layer is replaceable. The services are not connected today."
        />
        <div className="integration-columns">
          <div>
            <span className="integration-icon">
              <Database size={20} />
            </span>
            <h3>What exists here</h3>
            <p>
              A deterministic synthetic ledger, precomputed decision snapshots
              and local interface preferences. Exports are generated in your
              browser. Theme, sidebar, recent cases and queue views persist
              locally.
            </p>
          </div>
          <div>
            <span className="integration-icon">
              <Globe2 size={20} />
            </span>
            <h3>What belongs to the backend</h3>
            <p>
              Authoritative PostgreSQL records, FastAPI services, XGBoost
              inference, verified rule-pack state and guarded financial
              execution. None of these services are contacted by this prototype.
            </p>
          </div>
        </div>
        <Disclosure
          title="Inspect future REST response boundaries"
          subtitle="Documented concepts / all disconnected"
        >
          <div className="endpoint-list">
            {[
              "/api/outcomes",
              "/api/baselines",
              "/api/cases",
              "/api/cases/{id}",
              "/api/cases/{id}/decisions",
              "/api/events",
              "/api/constraints",
              "/api/constraints/check",
              "/api/knowledge/search",
              "/api/model",
              "/health",
            ].map((endpoint) => (
              <div key={endpoint}>
                <span>GET</span>
                <code>{endpoint}</code>
                <small>Not connected</small>
              </div>
            ))}
          </div>
        </Disclosure>
        <button className="text-link" onClick={() => w.navigate("audit")}>
          Inspect the synthetic journal <ArrowUpRight size={12} />
        </button>
      </section>
    </>
  );
}
