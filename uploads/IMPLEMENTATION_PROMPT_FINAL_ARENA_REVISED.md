# AI Revenue Recovery Platform — Master Implementation Prompt

You are a senior full-stack product engineer and product designer. You will build the **AI Revenue Recovery platform ("RecoveryDesk")** — a REAL, working, end-to-end web application — not a mockup. You will receive this prompt plus the authoritative project documents, the trained ML artifacts, and the dataset/simulator artifacts. Work autonomously, iteratively, and verify everything before declaring done.

---

## 0. What you are building

A recovery-operations platform for Indian subscription businesses whose recurring debits fail on UPI AutoPay or card e-mandates. For each failed debit the system opens a recovery case and runs a closed, auditable loop:

```
failed payment → case → state → feasible (legal) interventions → ML probabilities
→ expected-value decision → guarded execution → observed outcome → state update
→ recover / retry / wait / stop / escalate → measured ₹ recovered → full audit trail
```

The evaluator must conclude "this is a genuinely working recovery system," not "this is a fancy dashboard." The case-detail experience is the hero of the product.

This is NOT a CRM, NOT a payment dashboard, NOT a chatbot, NOT an ML-metrics demo. Every pixel must serve the recovery narrative: understand → constrain → predict → decide → act → observe → stop → measure → audit.

---

## 1. Authoritative inputs (read first, in this order)

1. **DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_FINAL_FIXED.md** — THE strongest authority on boundaries, modules, contracts, state machine, ports, repository layout, V1 topology, and explicit technology rejections.
2. **PHASE_3C_ML_DATA_CONTRACT_AND_PHASE_C_PLAN.md** — table semantics, decision-level grain, feature universe, excluded fields, action-support caveats.
3. **Phase_3C_Model_Training.md** and **PHASE_3C3_FEATURE_ENGINEERING_AND_CLEANING.md** — final model, feature contract, cleaning decisions.
4. **PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md** and **MODEL_QUALITY_EVALUATOR_DEFENSE.md** — what the model can/cannot claim; honesty language.
5. **PHASE_1, PHASE_2, PHASE_3A, PHASE_3B, DATASET_BUILD_REPORT.md** — problem framed, intelligence boundary, baseline policies B0–B4, failure taxonomy, action space, evaluation/claim discipline.
6. Dataset V1 artifacts (parquets under `data/generated/…`) and the simulator repo (`recoverysim`) as reference for world semantics.

When documents disagree, document 1 wins on structure; documents 2–3 win on ML/data semantics; document 5 wins on product intent. Note conflicts in `DECISIONS.md`.

---

## 2. Twelve non-negotiable architecture invariants

1. Recovery state is deterministic; the FSM alone mutates case state (single writer).
2. The ConstraintEngine is the sole authority on legality; it is pure, versioned, deterministic, and invoked at decision time AND again immediately before execution.
3. ML predicts success probability for LEGAL candidates only. Never score-then-filter illegal actions. ML cannot grant permission.
4. A deterministic EV/value layer converts probabilities into one bounded choice.
5. Only the execution gateway produces external effects (simulated/PSP adapters or notifications); it executes only intents carrying a matching constraint-verdict.
6. Nothing from frontend, LLM, RAG, or operator UI can mint an action the constraint layer did not explicitly allow.
7. Everything journal-worthy is append-only (no UPDATE/DELETE of events or decisions).
8. Feature semantics are identical offline/online: one shared feature builder package, one contract/schema gates model activation.
9. SIMULATION / SANDBOX / PRODUCTION are labeled everywhere; simulated evidence is never presented as real-world recovery.
10. The model is a replaceable artifact behind a model-agnostic ScorerPort interface.
11. All hard constraints fail closed: unknown → deny; error → deny; mismatch → deny.
12. Any decision must be explainable months later from a frozen Decision Record — without asking a model to reconstruct it.

---

## 3. ML artifact integration (exact requirements)

Provided artifacts (treat as production-critical inputs):

```
models/c5/xgboost_native_categorical_c5.json            ← runtime model (native categorical XGBoost)
reports/c5_xgb_native_categorical/native_categorical_schema.joblib
                                                        ← feature order, categorical list, category vocab
reports/c5_xgb_native_categorical/best_params.json      ← metadata
reports/c5_xgb_native_categorical/native_categorical_metrics.csv
reports/c5_xgb_native_categorical/optuna_trials.csv
```

Hard requirements:

- Load the XGBoost **native JSON** artifact directly (Booster/xgb). DO NOT convert it to a pickle "for convenience."
- The schema joblib defines: exact 43-feature order, the 17 categorical columns, the 26 numeric columns, and categorical vocabulary. The runtime feature builder consumes this schema as its contract — there is ONE feature-builder implementation used by both the offline training path and the online decision path.
- Activation gate (testable): before the scorer becomes active, verify
  - runtime feature names/order == schema
  - runtime categorical columns == schema categorical columns
  - runtime category vocabulary == schema vocabulary

  Any mismatch ⇒ model activation refused, startup logs it, scorer stays in flagged fallback mode, and the Model page shows BLOCKED status.

If ML activation fails, the fallback MUST be deterministic:
→ do not fabricate p̂
→ use the configured deterministic B2/doctrine policy or other explicitly configured safe fallback
→ mark `scorer_mode=fallback`
→ journal the fallback reason
→ constraints remain authoritative
- Calibration: NO separate calibration artifact exists in this bundle. Therefore the scorer MUST record exactly: `calibration_version = null`, `mode = uncalibrated` — never pretend calibration exists. Design the ScorerPort so a future versioned calibration artifact drops in through config only (no redesign).
- Every score batch is journaled with: `model_id`, `model_version`, `calibration_version`, `training_domain` ("SIM"), `feature_schema_hash`, `scorer_mode` (active|shadow|fallback).
- Confirmed benchmark for the Model page (label it TEST-on-synthetic-split, with the simulator-domain disclaimer): PR-AUC 0.831340 · ROC-AUC 0.940206 · LogLoss 0.252191 · Brier 0.077702. Present as model quality in-domain, NEVER as production-world performance.

---

## 4. Online decision pipeline (exact order — violating this is a defect)

For each case wake (event or timer):

1. Orchestrator loads case (row lock, version check), folds new event(s) into the projection inside one transaction, journals them.
2. Candidate Generator expands the bounded vocabulary per current failure class and state: `RETRY_AT_WINDOW`, `SEND_REMINDER`, `SEND_PAYMENT_LINK`, `REQUEST_PM_UPDATE`, `WAIT_UNTIL`, `STOP_CASE`, `ESCALATE_TO_HUMAN` — with concrete legal windows/channels.
3. Constraint Engine evaluates ALL candidates → feasible set + per-candidate rule reasons + `rule_pack_hash`. Enforced families: retry budget (original + ≤3), contact cap (≤2/case) + cooldown (≥20h) + quiet hours, legal execution windows per rail, mandate status (paused/revoked ⇒ no retry), class eligibility (hard classes like `CARD_EXPIRED` / `CARD_LOST_STOLEN` / `MANDATE_CLOSED` never auto-retry; PM-update/link path instead), amount/₹15K cap behavior, opt-out suppression, terminal-state absorbency, kill-switch scopes. Unknown/unmapped failure codes default to non-retryable (fail closed).
4. Feature Builder (shared wheel + schema): synchronous per-case history catch-up (fold this case's journal tail), then contract-validated rows; as_of proof (features strictly pre-decision); excluded fields (IDs, post-decision fields, latent simulator fields, counterfactuals) rejected by construction.
5. ScorerPort scores the feasible batch only → calibrated/un-calibrated p̂ each.
6. EV Layer: `EV(a) = p̂·recoverable_value − action cost − channel cost − fatigue cost − attempt-opportunity cost`; argmax over feasible; STOP if max EV ≤ threshold; ESCALATE if value-tier/policy triggers. ALL constants come from config/registry files (`costs.yaml` etc.), never hardcoded in logic. Stamp `constants_hash`.
7. Orchestrator freezes the Decision Record (§6) and either schedules (durable due-work row) or creates an Execution Intent carrying the verdict hash.
8. Execution Gateway RE-VERIFIES constraints against CURRENT state; only then dispatches via the configured adapter with an idempotency key; mismatch ⇒ `INTERVENTION_BLOCKED` + alert event.
9. Outcomes return as events (simulated adapter today; PSP test adapters where available); the loop re-enters. Terminal states RECOVERED / STOPPED absorb.

---

## 5. Backend architecture to implement

Stack: Python + FastAPI (modular monolith) · PostgreSQL 16 (+pgvector) · one image, two runtime roles (api+workers / ops jobs via env flag) · Docker Compose.

Modular packages (mirror the architecture doc, keep separate):

- `domain` (enums/contracts) · `fsm` · `orchestrator` (claim/fold/decide; single case writer)
- `constraints` (pure engine + rule-pack loader; packs versioned YAML)
- `features` (shared wheel — the SAME code used by the training/mart path)
- `scoring` (ScorerPort + artifact loader + hash gates + doctrine fallback)
- `decision` (candidate expansion + EV) · `scheduler` (Postgres due-work table with `SELECT … FOR UPDATE SKIP LOCKED`; lease-based; kill-scope-aware parking)
- `gateway` (intents, verdict re-verify, outbox, idempotency) · `adapters` (PaymentRailPort + NotificationPort; at minimum a fully working SimRailAdapter + SimNotifyAdapter; Razorpay/Stripe test adapters behind flags if credentials exist)
- `journal` (append-only writer) · `audit` (decision records + replay service)
- `monitoring` (four categories, business-first) · `knowledge` (pgvector ingestion + retrieval) · `copilot` (flag-gated, read-only) · `admin` (config, kill switch).

Persistence model (single Postgres, clearly zoned):

```
customers · subscriptions · payment_attempts · recovery_cases (projection with
version + counters) · recovery_events (append-only journal incl. inbox events)
· decision_records (+ candidates: features, verdicts, p̂, EV, versions, hashes)
· execution_intents · outbox · scheduled_actions · psp_event_inbox (dedup keys)
· aggregates (as_of_event_id) · rule_packs · kill_flags · monitoring_series
· knowledge_docs/chunks · quarantine
```

Append-only is enforced by DB role grants (app role: INSERT/SELECT; no UPDATE/DELETE on journal/decision tables).

API surface (REST/JSON + OpenAPI; the frontend SDK is generated from it):

```
GET  /api/v1/health
GET  /api/v1/metrics/overview                      (batch economics: ₹ recovered, rates,
                                                   costs, violations — by environment)
GET  /api/v1/cases?state=&rail=&failure_class=&policy=&q=&page=
GET  /api/v1/cases/{id}                            (projection + next legal options)
GET  /api/v1/cases/{id}/timeline                   (events + decision records fused)
GET  /api/v1/cases/{id}/decisions/{decision_id}    (frozen atom)
POST /api/v1/cases/{id}/run-next-step              (advance one loop iteration; demo)
POST /api/v1/recovery/simulate-batch               (seeded batch run via Sim adapters)
GET  /api/v1/outcomes/summary?env=                 (policy vs baselines, cohorts)
GET  /api/v1/model/status                          (artifact, schema, mode=uncalibrated,
                                                   metrics, hashes, activation state)
POST /api/v1/admin/kill-switch/{scope}             + resume (re-auth; journaled)
POST /api/v1/cases/{id}/force-stop                 (reason; through constraint layer)
GET  /api/v1/knowledge/search?q=
POST /api/v1/copilot/query                         (flag-gated)
POST /api/v1/webhooks/{provider}                   (signed ingest; dedup; canonical map)
GET  /api/v1/audit/violations · /replay/{case_id}  (verification output)
```

All responses are screen-shaped DTOs; the frontend never recomputes domain logic.

Event enum (runtime, frozen v1): `payment_failed` · `payment_succeeded` · `recovery_case_opened` · `decision_required` · `candidates_generated` · `intervention_proposed` · `intervention_blocked` · `decision_made` · `retry_scheduled` · `intervention_executed` · `notification_sent` · `customer_responded` · `mandate_state_changed` · `case_escalated` · `human_decision` · `case_stopped` · `case_recovered` · `post_terminal_observed` · `kill_switch_fired` · `kill_switch_resumed`. Every event carries: `event_id`, `case_id`, `case_seq`, `actor`, `occurred_at`, `recorded_at`, `payload`, `correlation_id`, env label, and relevant version/hash fields.

State machine (deterministic, tested, absorbing terminals):

```
CASE_CREATED → OPEN_DECISION → {ACTION_PENDING, WAITING, AWAITING_CUSTOMER,
ESCALATED, STOPPED} ; ACTION_PENDING →{failed}→OPEN_DECISION / {succeeded}→RECOVERED ;
WAITING →OPEN_DECISION on timer ; AWAITING_CUSTOMER →OPEN_DECISION on response/window
expiry, →RECOVERED on self-pay/reactivation/update, →STOPPED on opt-out ;
ESCALATED →OPEN_DECISION/RECOVERED/STOPPED via human_decision ;
RECOVERED/STOPPED absorbing (post-terminal events journal as evidence only).
```

---

## 6. Decision Record (the audit atom — freeze per decision)

Persist per decision: `case_id`; timestamp; state-before; trigger ref; `candidates[]` each with `{candidate_id, action_type, window_code, channel, verdict{allowed, reasons[], rule_ids, rule_pack_hash}, feature_row(43), p_hat, ev_components, ev_inr}`; chosen + reason_code; `policy_version`; `model{id, family, version, calibration_version:null, training_domain:"SIM", mode}`; `feature_schema_hash`; `constants_hash`; env. The Case Detail "WHY?" view and the replay service render ONLY from these atoms + journal — never from LLM invention.

---

## 7. Agent boundary & Ops Copilot (LLM usage rules — strict)

The system's agentic quality is the sequential loop itself. The bounded orchestrator may expose internal tools exactly as (mirrored, server-authorized):

```
get_case · evaluate_constraints · predict_propensity · compute_ev · schedule_retry
· send_notification · offer_payment_link · wait · stop_case · escalate · write_audit
```

Every mutating tool re-checks constraints server-side. The agent can NEVER: expand the action vocabulary, bypass constraints, change policy, call PSPs directly, mutate case state directly, or authorize an illegal payment.

Ops Copilot (flag-gated, optional, read-only):

- Allowed: explain a structured decision (grounded STRICTLY in the decision atom + verdicts + journal — "computed answers rendered in language"); summarize a case; answer policy/doc questions over the knowledge index with citations; draft compliant customer message wording from validated templates with {amount, date, plan} slots.
- Forbidden: inventing explanations, citing nonexistent documents, touching any mutating API, authorizing anything.
- Degradation: with the LLM provider key absent (`COPILOT_ENABLED=false`), the whole product works identically minus the chat surface; the explanation pages still render deterministic structured explanations. This is an acceptance test, not a nicety.

---

## 8. Knowledge / RAG layer

Build the knowledge experience from the project's actual corpus (phase documents, dataset build report, model quality defense, architecture doc, curated regulatory/PSP reference excerpts, assumption registry) — ingested → parsed → chunked (heading-aware, ~400–800 tokens) → embedded (local sentence-transformers default; config-swappable) → pgvector inside Postgres; hybrid vector+BM25 retrieval; every chunk carries metadata `{source, doc_type, authority=reference, content_hash}`. Answers must cite chunk IDs for documentation/policy claims; REFUSE policy/document questions without a citation. Structured answers derived from recorded decision/event/rule data may be returned without document citations. RAG is never authority: law is the compiled rule packs. On conflict, say so visibly.

---

## 9. Frontend — information architecture & experience

Stack: React + TypeScript + Vite · TanStack Query (server-state; polling 15–60 s per surface — no realtime infra required) · generated typed API client from OpenAPI · a restrained charting library · CSS system of your choice (no heavy template kits).

You are a senior product designer first: determine the strongest layout, hierarchy, navigation, density, and motion yourself. Do NOT copy Stripe/Linear/Salesforce; design an original modern fintech/AI-operations product. Direction: strong typography, generous spacing, clear hierarchy, subtle depth, clean cards, polished tables, meaningful (not decorative) charts, restrained transitions that never block work, excellent empty/loading/error states, keyboard accessibility, responsive behavior, NO gradients-as-personality, NO neon "AI" aesthetics, NO hero banners, NO meaningless animation. The UI must feel fast while the backend processes work.

Every number on screen originates from a live API response. Environment badge (SIM / SBX / PRD) is persistent and unmissable.

Pages (improve on this structure; do not shrink it):

1. `/overview` — Recovery Dashboard. Business story first: ₹ recovered (labeled per env), recovery rate, active/recovered/stopped/escalated counts, attempts & contacts, cost, baseline comparison vs B1 (PSP-default proxy) and B2 (doctrine), constraint-violation counter (must render "0" honestly from the monitor), recovery trend chart, model status strip, environment filter. NOT a wall of KPI cards — use a recovery-trend chart + baseline comparison + case-state funnel.
2. `/cases` — filterable/searchable case table: case id, amount at risk, rail, failure class, state, retries used (x/3), contacts (x/2), next legal action, policy, updated. Row click → detail. Pagination, sensible empty states, exportable CSV.
3. `/cases/:id` — THE HERO PAGE. Structure it so an evaluator in 60 seconds sees:
   - header: case id + state chip + env chip, amount at risk, rail, failure class, amount and plan context;
   - CURRENT STATE panel: attempt history summary, retries used x/3, contacts x/2, hours since open, instrument status, constraint counters;
   - RECOVERY OPTIONS as candidate cards from the last/fresh decision: action + window/channel, P(success) %, EV ₹ breakdown, verdict chip (✓ Legal with rule references, or BLOCKED with the exact rule reason e.g. "quiet hours 21:00–08:00", "retry budget exhausted (NPCI 1+3)"); selected card highlighted as CHOSEN;
   - WHY panel: structured, readable composition of decision atom parts — Prediction vs Decision vs Constraint vs Execution rendered as four visually distinct trust layers (this separation is the product's credibility — make it obvious);
   - TIMELINE: vertical event stream fusing recovery_events + decisions + executions: time, actor, event type, payload highlights, expandable for JSON; the multi-step agentic behavior (decide → execute → observe → re-decide) must be legible from it;
   - actions for demo: "Run next step" (progress states, optimistic only where safe), "Force stop" (confirm + reason).
4. `/cases/:id/decision/:decision_id` — full decision-explanation view: all candidates, verdicts with rule IDs, probabilities, EV components, versions (model, calibration = "none — uncalibrated", schema hash, rule pack, policy, constants hash), rejected alternatives, replay button with PASS/FAIL output.
5. `/outcomes` — batch economics: ₹ recovered by policy vs B0/B1/B2 baselines (clearly labeled as which environment produced them), recovery rate, time-to-recover distribution, attempts & contacts consumed, stop-reason breakdown, escalation rate, cohort breakdowns (rail × failure class). Never fabricate improvements; if a policy loses to a baseline somewhere, show it.
6. `/model` — intelligence status: family, version, training domain=SIM disclaimer, benchmark table (test/valid/train), feature-schema state (43 features, 17 categorical, 26 numeric — live from the schema artifact), activation status (schema-check PASS/FAIL with details), calibration = "none — uncalibrated mode", artifact hashes, fallback-scorer status, mode strip. All fields from the backend, never literals in the frontend.
7. `/knowledge` — corpus browser + search with citations; authority labeling (reference vs compiled-rule); "document is reference; rule pack X governs" banners.
8. `/copilot` (flag-gated) — ask about cases/decisions/docs; answers cite decision-record fields or knowledge chunks; shows abstentions honestly; visible banner that the assistant cannot authorize actions.
9. `/admin` — rule packs + versions viewer, costs/constants viewer (registry values), kill switch with scope + reason + confirmation + re-auth, PSP adapter states, audit (violations, kill events), replay invocations.

---


## 9A. REFERENCE-ONLY DATASETS / KNOWLEDGE CORPUS

IMPORTANT:

Several datasets and external sources in the project were deliberately NOT
used as ML training rows. Preserve that separation.

Do not assume every dataset provided with the project belongs in the predictive
pipeline.

Classify project data into these distinct roles:

1. ML TRAINING DATA
2. SIMULATION CALIBRATION DATA
3. REFERENCE / KNOWLEDGE DATA
4. PSP / SANDBOX BEHAVIOR REFERENCES
5. SEALED SIMULATOR TRUTH

These roles must never be silently mixed.

### A. UPI Transactions 2024 — SIMULATION CALIBRATION

Scale: approximately 250,000 unique transaction IDs, 17 columns, Jan–Dec 2024.

Nature: synthetic/programmatically generated UPI transaction data.

Actual project role: calibration priors only.

Useful information includes:
- category-marginal amount distributions,
- bank-name weight sets,
- state distribution,
- age-band distribution,
- hour-of-day activity curve,
- transaction-type mix.

These priors feed the simulation/population assumptions.

Important:
The transaction-status field is NOT used as recovery ground truth because it
does not provide the recurring-payment failure semantics/reason codes required
by this project.

Do not:
- use the raw UPI rows as recovery-model training rows,
- describe this source as real merchant recovery data,
- use its activity peak as a mandate-execution rule,
- confuse consumer UPI activity with recurring mandate execution windows.

If the calibrated profile/artifact is available, inspect it and preserve its
provenance. Do not invent additional statistics.

### B. PROCESSOR / PSP BEHAVIOR CORPUS — SANDBOX / SEMANTICS

Relevant sources include:
- Stripe Billing/test-clock behavior,
- Razorpay subscription/test-mode behavior,
- Razorpay UPI testing references.

Role:
Executable semantics/conformance reference for sandbox adapters and the event
model.

Useful information includes:
- documented test-clock behavior,
- test payment outcomes,
- subscription pending/halted lifecycle,
- retry timing semantics,
- provider event/payload conventions.

Use this for:
- adapter fixtures,
- canonical event mappings,
- sandbox behavior tests,
- webhook/event normalization.

Do not use PSP documentation as ML training data.

### C. REGULATORY CONSTRAINT CORPUS — RULE-PACK INPUT

Relevant sources include:
- NPCI recurring-payment guidance,
- RBI e-mandate framework references,
- PSP policy documentation.

Role:
Reference source for versioned machine-readable rule packs.

Examples documented by the project include:
- 1 original debit + up to 3 retries,
- non-peak execution windows,
- notification requirements,
- ₹15,000 general cap where applicable,
- retry/contact/cooldown constraints.

Convert these into explicit versioned rule/config data where required by the
architecture.

Critical:
RAG text is never the authority for execution.
Compiled/machine-readable ConstraintEngine rule packs are authoritative.

### D. UCI DEFAULT OF CREDIT CARD CLIENTS — METHODOLOGY REFERENCE

Scale: approximately 30,000 records.

Role:
Reference for longitudinal payment-history / lag-style feature design.

Use for:
- methodology explanations,
- feature-design inspiration,
- RAG answers about payment-history modelling.

Do not:
- merge these records into Dataset V1,
- use them as recovery-model training rows,
- treat their target as recurring-payment recovery.

### E. HILLSTROM EMAIL UPLIFT — METHODOLOGY REFERENCE

Scale: approximately 64,000 records.

Role:
Reference for intervention/outcome and treatment-effect methodology.

Use for:
- explaining treatment assignment,
- explaining randomized uplift methodology,
- explaining limits of the current predictive model.

Do not use as recovery-model training data.

### F. CRITEO UPLIFT — METHODOLOGY REFERENCE

Scale: approximately 25.3 million rows.

Role:
Reference for large-scale uplift/causal-policy methodology.

Use for:
- future causal/off-policy architecture explanations,
- RAG explanations of treatment-effect learning.

Do not merge it into the recovery training dataset or infer payment semantics
from its fields.

### G. PAYSIM — SIMULATION METHODOLOGY REFERENCE

Role:
Research precedent for structural/agent-based financial simulation when
real-world financial logs are unavailable.

Use for:
- explaining simulator methodology,
- supporting design decisions around structural synthetic worlds,
- conceptual evaluation methodology.

Do not treat PaySim as this project's training dataset or as Indian recurring
payment recovery data.

### H. VENDOR RECOVERY / DUNNING DOCTRINE

Reference sources include project-approved vendor material such as:
- Finsi,
- Slicker,
- FlyCode.

Role:
- methodology/context,
- baseline B2 doctrine,
- simulator assumption bands where explicitly registered.

Vendor material is NOT ground truth.

Preserve provenance such as:
`authority = vendor_doctrine`
`provenance = ASSUMED`

Never turn a retrieved vendor statement into a regulatory fact.

### I. UCI BANK MARKETING — METHODOLOGY REFERENCE

Role:
Reference for customer/contact-response modelling concepts.

Use only for:
- outreach-response reasoning,
- contact/fatigue modelling,
- future notification-response work.

Do not use as recovery-model training data.

### J. REES46 E-COMMERCE EVENTS HISTORY — BACKGROUND REFERENCE

Scale: approximately 20M cosmetics events + approximately 900K electronics
events.

Role:
General event-stream/session-behavior reference.

Why not selected:
It is not recurring-payment failure/recovery data.

Use only as background/methodology reference if actually available.

### K. UCI ONLINE SHOPPERS PURCHASING INTENTION — BACKGROUND REFERENCE

Scale: 12,330 sessions.

Role:
Generic purchase-intention/session-propensity reference.

Why rejected:
Not recurring mandate recovery.

Do not use as recovery-model training data.

### L. DIGITAL WALLET TRANSACTIONS — BACKGROUND REFERENCE

Scale: 5,000 records.

Role:
Generic digital-payment behavior reference.

Limitation:
Contains success/failure-style information but lacks the recurring-payment
recovery semantics required by the project.

Do not use its rows as recovery labels or training data.

### M. FINANCIAL TRANSACTIONS ANALYTICS — BACKGROUND REFERENCE

Scale: approximately 1.4GB, cards/users/MCC-oriented transaction data.

Role:
Generic payment/card/user realism reference.

Limitation:
Fraud-centric rather than recurring-mandate recovery.

Do not merge into Dataset V1 or the recovery model.

### N. IBM FINANCE FACTORING — BACKGROUND REFERENCE

Scale: approximately 2.4K invoice records.

Role:
B2B late-payment/reference methodology.

Why rejected:
Different problem domain and small sample.

Do not use for recovery-model training.

### O. INVOICE PAYMENT-DATE PREDICTION — BACKGROUND REFERENCE

Scale: approximately 50K invoices.

License: CC BY-NC 4.0.

Role:
Reference for payment-date/lateness modelling.

Why rejected:
B2B invoice setting rather than recurring mandate recovery.

Do not incorporate it into production/runtime data unless the license is
explicitly compatible and documented.

### KNOWLEDGE/RAG INGESTION RULES

The Knowledge Service should use relevant reference material when it genuinely
helps an operator understand:
- a payment concept,
- methodology,
- a project decision,
- PSP behavior,
- regulatory context,
- a model limitation,
- a simulator assumption.

For every ingested reference source, record metadata such as:

`source, source_url_or_path, doc_type, role, authority, provenance, license,
content_hash`

Useful role values include:

`ML_TRAINING_DATA`
`SIMULATION_CALIBRATION`
`PSP_BEHAVIOR`
`REGULATORY_REFERENCE`
`METHODOLOGY_REFERENCE`
`VENDOR_DOCTRINE`
`BACKGROUND_DATASET`
`MODEL_DOCUMENTATION`

If a source is mentioned in project documentation but its actual file is NOT
provided to the implementation environment:
- do not pretend it is locally ingested,
- do not fabricate its schema/row count,
- do not download large datasets unnecessarily just to populate a UI,
- keep it as a documented external reference.

If the actual file IS provided:
- inspect its real schema,
- inspect row count,
- inspect relevant metadata,
- register its actual artifact/hash,
- use it only according to its defined role.

### ML / RAG SEPARATION TEST

Add a CI/test guard that ensures:

REFERENCE-ONLY DATASETS
        X
        |
        X
ML TRAINING PIPELINE

while:

REFERENCE DATA
        ↓
Knowledge ingestion
        ↓
RAG / Ops Copilot
        ↓
Grounded explanation

The predictive model may consume only:
- the approved C4 training/validation/test data,
- the approved online feature contract,
- explicitly approved decision-time features.

Reference-only datasets must never silently become model features.

Sealed simulator truth and counterfactual sidecars must remain completely
unreachable from the ML training/runtime feature path.

### DATA PROVENANCE IN THE UI

The UI may show a Data Sources / Knowledge Sources view, but it must represent
provenance truthfully.

Examples:

`UPI Transactions 2024 → Synthetic calibration prior`
NOT `ML training dataset`

`UCI / Hillstrom / Criteo / PaySim → Methodology/reference`

`PSP documentation → Sandbox/provider behavior reference`

`Regulatory material → Reference used to define compiled rule packs`

`Vendor doctrine → Assumed/vendor-derived reference`

This distinction should be visible wherever an operator inspects knowledge
sources or model-data provenance.


## 10. Demo / seed scenarios & evaluator flow

Implement a seeded demo that executes REAL logic through Sim adapters:

- "Seed demo cohort": generate a controlled batch of failed debits (e.g. 50–200 cases) covering the taxonomy: `INSUFFICIENT_FUNDS`, `BANK_TECHNICAL`, `MANDATE_PAUSED`, `MANDATE_CLOSED`, `CARD_EXPIRED`, `CARD_LOST_STOLEN`, plus rate-limit/technical variants; varied rails, amounts, tiers, banks. Different classes MUST produce visibly different legal option sets (hard classes show link/PM-update paths, not retries).
- "Run recovery simulation": advance the batch through the loop (time-boxed), showing live updates in overview/cases; outcomes economics update from the DB, not a script.

Clearly distinguish:
- **Live simulated operations**: the currently running demo cohort and its evolving state.
- **Completed batch evaluation**: a finished run whose policy/baseline metrics are frozen for comparison.

Do not present an in-progress demo cohort as the formal policy/model benchmark.
- The demo MUST include recovered, retried, waited, stopped, escalated, and blocked cases. Do not let everything recover; a credible recovery rate emerges, not 100%.

The evaluator walkthrough you must make trivially possible end-to-end:

```
dashboard → pick case → run/process step → see state → see legal options & blocked
reasons → see P(success) per legal candidate → see EV ranking → see chosen action →
execute via Sim adapter → see outcome event → see state/timeline update → see overview
economics update → open decision explanation → ask Copilot why → inspect knowledge
citations → replay the decision → see audit/violations = 0.
```

Everything on the real backend.

---

## 11. Honesty & trust requirements (hard rules)

- Environment labeling everywhere; SIM numbers carry "simulated — not production evidence" plaques wherever money/rates appear; the Model page's metrics are labeled synthetic-domain test metrics.
- Prediction / Decision / Constraint / Execution / Outcome are visually distinct layers wherever the pipeline is depicted.
- No fabricated regulations, citations, baselines, or recovery totals. If data doesn't exist for a chart, show an honest empty state, not a plausible one.
- Baselines: implement B0 (no intervention), B1 (PSP-style fixed retries), B2 (static doctrine) as runnable policies for comparison; B4/oracle stays SIM-only.

---

## 12. Testing (minimum — all must pass in CI)

Before coding, treat the API contract as a testable product boundary. Do not assume an API is correct merely because the frontend can call it. Write and execute backend API tests covering successful responses, request validation errors, authentication/authorization failures, not-found cases, conflict/idempotency cases, and representative internal failure paths. Then test the frontend against the real APIs, not mocks, for the critical user flows.

- Constraint engine: budgets/window/class/state/cap/opt-out failures expected → deny; fuzz snapshots×candidates×packs.
- Feature schema compatibility: runtime builder output == joblib schema (order, cat columns, vocab) → activation gate tested for match AND mismatch (mismatch refuses).
- Model loading: JSON artifact loads; sha verification; hash-gated activation; scorer metadata completeness incl. mode=uncalibrated.
- Decision/EV: constants from config only; argmax correctness; tie-break determinism; STOP/ESCALATE triggers; doctrine fallback path.
- FSM: exhaustive legal-transition table; absorbing terminals; counter guards.
- Idempotency: duplicate webhook ⇒ single state effect; duplicate execution intent ⇒ single logical action; outbox once-per-intent.
- Orchestrator crash-safety: forced fault mid-decision ⇒ clean replay/no half-state.
- API contracts: OpenAPI validation on responses; frontend SDK regeneration is checked.
- Failure drills (must-pass): LLM down → product fully works; model artifact missing/mismatched → flagged doctrine fallback, constraints still enforced; constraint engine exception → zero side effects; kill switch scope fire → parked/blocked effects.
- End-to-end demo script as an automated test (seed → batch → verify economics consistency between DB and API payloads shown on key screens).

---

## 13. Code quality & deployment

- Clear module boundaries (no router→adapter imports; CI boundary tests); typed Python (pydantic), typed TS (strict); small files; no duplicated business rules; configuration externalized (`configs/*.yaml`, `.env`); secrets via env only, never in frontend; no PSP calls from the browser; meaningful README with architecture recap, run instructions, demo script, tests, and a "how the evaluator walks through it" section.
- `docker compose up` must bring up: `db` (postgres+pgvector, migrations+seed), `api` (core role), `ops` (jobs role), `web` (built SPA served), with `./models` and `./reports` artifact mounts. First-run bootstrap: migrations → seed rule packs/costs/registry → schema/artifact activation gate → ready banner with demo instructions.
- V1 must NOT include: Redis, Kafka, Celery, Temporal, Kubernetes, a model server, a dedicated vector database, microservices-per-module, or any cloud-only service.

---

## 14. How to work (implementation sequence — do not dump code blindly)

Work iteratively with running verification at each step; stop and reconcile conflicts rather than papering over them; keep a `DECISIONS.md` log of every interpretation you make where the documents leave room.

- **Phase 1:** read all inputs; extract exact contracts (FSM, events, feature schema of 43/17/26, rule packs, EV constants); write the implementation plan + module map.
- **Phase 2:** backend skeleton: migrations, config loaders, journal, projection, FSM, orchestrator, scheduler; golden-replay seams; unit tests.
- **Phase 3:** constraint engine + packs (+pack hash) with fuzz tests; gateway with verdict re-verify + outbox + Sim adapters.
- **Phase 4:** shared feature package; schema activation gate; ScorerPort + JSON artifact loading + doctrine fallback; EV layer; Decision Record atoms; replay service.
- **Phase 5:** policies B0–B2; batch simulation runner (Sim environment); outcomes builder.
- **Phase 6:** stable read APIs + OpenAPI; then frontend shell + design system + SDK.
- **Phase 7:** all screens (case detail hero first), then outcomes/model/admin.
- **Phase 8:** knowledge ingestion + retrieval + page; Copilot façade (flag-gated).
- **Phase 9:** test suite incl. failure drills; performance sanity (decision p95 target <300 ms local); security pass; Docker reproducibility from clean checkout.
- **Phase 10:** full evaluator walkthrough executed end-to-end twice; fix every inconsistency; finalize README + demo script + refresh numbers throughout from live runs.

---

## 15. Hard prohibitions

NO hardcoded metrics/cases/timelines/probabilities anywhere. NO fake model inference, fake agent reasoning, fake RAG citations, fabricated regulations, or fake recovery totals. NO frontend-only "simulation." NO LLM in the decision path or any LLM authorization of payments. NO browser→PSP calls. NO scoring illegal candidates. NO latent simulator fields in features. NO claiming simulated recovery as production recovery. NO required infrastructure beyond the approved stack. A feature may be scaffolded as "planned/unavailable" only with an explicit badge; the core demo path must genuinely work.

---

## 16. Definition of Done (binary checklist)

- [ ] `docker compose up` from clean checkout → migrations, seeds, activation gate all pass.
- [ ] Seeded batch run: cases advance through the FSM; option sets differ by failure class; blocked actions show exact rule reasons; chosen actions execute via Sim adapter; outcomes and ₹ economics update on all screens from DB.
- [ ] Case Detail shows state, counter budgets, candidates with p̂+EV+verdicts, chosen action, WHY panel (four trust layers), full fused timeline, next-step live progress.
- [ ] Decision page renders frozen atoms incl. versions/hashes; replay returns PASS.
- [ ] Model page reports artifact truth incl. mode=uncalibrated and activation status.
- [ ] Baselines B0–B2 run side by side; comparison visible, losses not hidden.
- [ ] Knowledge answers cite real chunks; Copilot answers ground in decision atoms.
- [ ] `COPILOT_ENABLED=false` → full product pass; model-mismatch startup → flagged fallback; constraint fault → zero side effects; kill switch drill <60s.
- [ ] `/audit` shows compliance violations = 0 (queried, not typed).
- [ ] Full test suite green; README lets a stranger run the demo in <10 minutes.

---

**Build it like senior engineers and senior product designers who will defend every decision in front of a skeptical evaluator. Begin by reading the documents, then present your implementation plan before writing the first real code.**
