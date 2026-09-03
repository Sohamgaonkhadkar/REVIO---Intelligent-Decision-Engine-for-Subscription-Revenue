# RecoveryDesk — Implementation Plan (Phase 1 deliverable)

Version 1.0 · Status: **plan for approval** · No production code written yet.

Inputs read (in the authority order mandated by the master prompt): `PHASE_4_DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_FINAL_FIXED.md` (structure authority), `PHASE_3C_ML_DATA_CONTRACT_AND_PHASE_C_PLAN.md` + `Phase_3C_Model_Training.md` + `PHASE_3C3_FEATURE_ENGINEERING_AND_CLEANING.md` (ML semantics), `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` + `MODEL_QUALITY_EVALUATOR_DEFENSE.md` (honesty language), `PHASE_1/2/3A/3B` + `DATASET_BUILD_REPORT.md` (problem framing, baselines, taxonomy, world semantics), plus the attached `IMPLEMENTATION_PROMPT_FINAL_ARENA_REVISED.md` (verified identical in substance to the issued prompt).

**Two input gaps discovered (they shape this plan):**
1. **ML artifacts were NOT delivered** (`models/c5/xgboost_native_categorical_c5.json`, `reports/c5_xgb_native_categorical/*.joblib/json/csv`). The filesystem was searched. Per the spec's own fail-closed law, the activation gate will refuse → scorer runs in flagged deterministic **doctrine fallback** (`scorer_mode=fallback`, `policy_id=doctrine-b2`), Model page shows **BLOCKED** with the exact failing checks. The gate is built complete (joblib schema compare, sha256, native-categorical load) so the artifacts **drop in with zero code change**. Everything else in the product works identically.
2. **Dataset V1 parquets and the `recoverysim` repo were NOT delivered.** The Sim-zone world model (SimRailAdapter/SimNotifyAdapter + batch runner) will be **reimplemented from the documented Phase 3A §5/§6/§7/§8 mechanics and the DATASET_BUILD_REPORT parameters** (sufficiency process, Poisson(0.10)/day·~1.5h outages, mandate lifecycle incl. 97% silent card refresh & 0.4% lost/stolen, intent archetypes, fatigue, keyed blake2b→PCG64 determinism, 336h horizon). It is labeled as a reimplementation, never as "recoverysim v0.3", and every parameter lands in the assumption registry with provenance tags.

---

## 1. Frozen contracts extracted from the documents (build targets)

### 1.1 Case FSM (PHASE_4 §6 — structure authority; supersedes 3A's `CLOSED_LOST`, see DECISIONS D-001)
```
CASE_CREATED → OPEN_DECISION
OPEN_DECISION → {ACTION_PENDING (execute-now, verdict ok), WAITING (WAIT chosen),
                 AWAITING_CUSTOMER (contact executed, response window set),
                 ESCALATED (tier/rule trigger), STOPPED (EV≤threshold | budgets | class | opt-out)}
WAITING → OPEN_DECISION (timer wake)
ACTION_PENDING → OPEN_DECISION (attempt failed) | RECOVERED (succeeded)
AWAITING_CUSTOMER → OPEN_DECISION (response/window expiry) | RECOVERED (self-pay/reactivate/update)
                  | STOPPED (opt-out)
ESCALATED → OPEN_DECISION | RECOVERED | STOPPED (via human_decision)
RECOVERED, STOPPED: absorbing — later events journal as post_terminal_observed (evidence only)
```
Guards: verdict-allowed + legal window at execution + budgets; AWAITING wake scheduled atomically; counters (retries ≤3, contacts ≤2, cooldown ≥20h, quiet hours) enforced at decision AND execution; single writer (Orchestrator), one DB transaction per transition (journal append + projection version bump), optimistic `expected_version`.

### 1.2 Runtime event enum (frozen v1 — PHASE_4 §12.1, lowercase; the 3A uppercase enum is offline-only)
`payment_failed · payment_succeeded · recovery_case_opened · decision_required · candidates_generated · intervention_proposed · intervention_blocked · decision_made · retry_scheduled · intervention_executed · notification_sent · customer_responded · mandate_state_changed · case_escalated · human_decision · case_stopped · case_recovered · post_terminal_observed · kill_switch_fired · kill_switch_resumed`
Event contract: `{event_id (uuidv7), case_id, case_seq, merchant_id, occurred_at, recorded_at, actor, event_type, payload, rule_pack_hash?, policy_id?, model_version?, feature_contract_hash?, idempotency_key?, correlation_id, env}`. Producer ownership enforced by the journal writer API.

### 1.3 Failure taxonomy (recoverysim `domain.py` 7-class set, per DATASET_BUILD_REPORT)
`INSUFFICIENT_FUNDS` (retry helps, payday-timed) · `BANK_TECHNICAL` (hours-scale retry) · `RATE_LIMIT` (longer-wait retry) · `MANDATE_PAUSED` (no retry while paused; nudge/reactivation path; k unresponsive → stop `mandate_dead`) · `MANDATE_CLOSED` (never retry; single compliant notice+link → stop) · `CARD_EXPIRED` (never retry; PM-update/link) · `CARD_LOST_STOLEN` (never retry; PM-update/alert path). `AUTH_REQUIRED` excluded from V1 runtime (3A edge case); **UNMAPPED → non-retryable (fail closed)**.

### 1.4 Bounded action vocabulary (Phase 3A §7, frozen)
`RETRY_AT_WINDOW(w)` · `SEND_REMINDER(channel)` · `SEND_PAYMENT_LINK` · `REQUEST_PM_UPDATE` · `WAIT_UNTIL(t)` · `STOP_CASE(reason)` · `ESCALATE_TO_HUMAN`. Channels: `email · sms · whatsapp` (sim + stubs; email adapter real-able in SBX). Window bins (config-owned, DECISION-tagged): `W08_11, W11_14, W14_17, W17_21` IST; quiet hours 21:00–08:00 IST; contact hours 09:00–21:00 IST.

### 1.5 Constraint rule families (engine is pure, versioned, double-invoked)
retry budget 1+3 (FACT) · contacts ≤2/case + cooldown ≥20h (DECISION) · quiet hours + per-rail legal windows · mandate status (paused/revoked ⇒ no retry) · class eligibility (hard classes never auto-retry; PM-update only for card/mandate-dead classes) · ₹15,000 cap/AFA behavior (FACT) · opt-out suppression · terminal absorbency · kill-switch scopes (global/merchant/rail/pack/case) · unknown ⇒ deny. Verdict: `{candidate_id, allowed, reasons[], rule_ids[], rule_pack_hash, evaluated_at}`. Rule packs: `configs/registry/rule_packs/upi_autopay_v1.yaml`, `card_si_v1.yaml` (+ hash).

### 1.6 Online decision pipeline order (exact, prompt §4)
wake → row-lock case + fold events + journal → candidate generation (bounded) → constraint evaluation (ALL candidates) → shared feature builder (sync per-case catch-up, as_of proof, exclusions) → ScorerPort scores **feasible batch only** → EV layer (argmax, STOP/ESCALATE rules) → freeze Decision Record → schedule (due-work) or Execution Intent (verdict hash) → gateway re-verify vs CURRENT state → adapter dispatch (idempotency key) → outcome events → loop. Terminals absorb.

### 1.7 EV formula (PHASE_4 §11 — every constant from `configs/costs.yaml` + registry, `constants_hash` stamped)
```
EV(a) = p̂_a · (amount_at_risk × margin_factor) − cost_action(a) − cost_channel(a.channel)
        − fatigue_cost(contacts_before) − attempt_opportunity_cost(a)
choice = argmax (tie-break: earliest legal window, then candidate_id — deterministic)
STOP if max EV ≤ stop_threshold(value_tier); ESCALATE on tier/repeat-failure/mandate-dead triggers
```
Provenance tags {FACT, DATA-DERIVED, ASSUMED, DECISION} on every constant; scenario multipliers (pessimistic/base/optimistic/adversarial) pre-registered; config-lint test fails on any constant not in registry (no hardcoded policy numbers).

### 1.8 Feature contract (Phase 3C §4 base-32 + §6 engineered-11 = 43: 26 numeric / 17 categorical)
Numeric (26): amount_inr, customer_tenure_days, subscription_age_days, prior_cycles_seen, prior_successes, prior_success_rate, prior_failed_cases_before, prior_recovered_cases_before, retries_used_before, contacts_sent_before, hours_since_open, decision_seq, hour_of_day, day_of_month, hours_to_next_cluster_slot, salary_day_proxy_dom, amount_inr_log1p, day_of_week, retry_intensity, contact_intensity, prior_successes_log1p, prior_failures_log1p, salary_distance_abs, amount_per_prior_cycle, instrument_fixed, in_salary_cluster.
Categorical (17): rail, bank_name, segment, plan_tier, value_tier, first_failure_class, failure_class_at_decision, age_band, state, locale_pref, action_type, channel, failure_action, rail_action, salary_action, failure_channel, rail_channel.
Excluded (rejected by construction): IDs, y, logging_policy, post-decision/exec fields (exec_*, response_kind, censored), terminal summaries, latent simulator state, counterfactuals. Provisional order/vocab live in `configs/registry/feature_contract_v3.yaml`; **the joblib schema is the gate's ground truth when provided** (D-008). `feature_as_of_event_id < decision_event_id` proof per row.

### 1.9 Model artifact & activation gate (PHASE_4 §9/§10.1a/§19b.1)
Load `xgboost_native_categorical_c5.json` via `xgboost.Booster` directly (no pickle conversion). Gate: artifact loadable · schema joblib loadable · counts 43/17/26 · runtime names/order == schema · categorical set == schema · category vocab == schema · sha256 vs manifest · training_domain recorded SIM. Any mismatch ⇒ activation refused, startup logs it, scorer = flagged fallback, Model page = BLOCKED. `calibration_version = null`, `mode = uncalibrated` — recorded exactly (never pretended). ScorerPort designed so a versioned calibration artifact drops in via config only. Every ScoreBatch journals model_id/version, calibration_version, training_domain="SIM", feature_schema_hash, scorer_mode. Confirmed benchmark served by the backend from `configs/registry/model_benchmark.yaml` (doc-sourced citation, D-005) labeled TEST-on-synthetic-split: PR-AUC 0.831340 · ROC-AUC 0.940206 · LogLoss 0.252191 · Brier 0.077702 (train/valid also available). Fallback = B2 doctrine policy through the SAME EV path (`policy_id=doctrine-b2`); fallback reason journaled.

### 1.10 Baselines & batch economics (Phase 2 §14, Phase 3B §12)
`B0` no intervention (floor) · `B1` PSP-proxy (UPI: 1+3 hourly per Cashfree doc; card: daily until ~4th failure → halt per Razorpay lifecycle) · `B2` static doctrine (class → window mapping; hard → single notify/link; never-retry → stop) · `B3` random-legal (ablation/coverage) — `B4` oracle stays SIM-only/deferred. Batch runner: frozen seeded world (common random numbers across policies — paired comparison), outcomes materialized to `case_outcomes`-equivalent tables; `/outcomes` renders policy vs baselines with environment labels; losses shown, never hidden. Plausibility anchors from DATASET_BUILD_REPORT (B1 35.3% / B2 49.2% / B3 50.2% recovery) are reference bands for the reimplemented world, documented as such — not tuned targets presented as measured facts.

### 1.11 Storage zones (single Postgres in deployment; prompt §5 table list)
`customers · subscriptions · payment_attempts · recovery_cases (projection, version+counters) · recovery_events (append-only) · decision_records (+candidate atoms) · execution_intents · outbox · scheduled_actions · psp_event_inbox (dedup) · aggregates (as_of_event_id) · rule_packs · kill_flags · monitoring_series · knowledge_docs/chunks · quarantine`. App role grants: INSERT/SELECT only on journal/decision tables (roles.sql; append-only enforced at DB level in the Postgres profile).

### 1.12 API surface (REST/JSON, OpenAPI-first; screen-shaped DTOs — frontend never recomputes domain logic)
Exactly the endpoints in the master prompt §5 (health, metrics/overview, cases list/detail/timeline/decision, run-next-step, simulate-batch, outcomes/summary, model/status, kill-switch + resume, force-stop, knowledge/search, copilot/query (flag-gated), webhooks/{provider}, audit/violations + replay/{case_id}) + auth, admin rule-packs/constants, monitor series.

---

## 2. Repository layout (adapts PHASE_4 §25; module boundaries CI-guarded)

```
recoverydesk/
├── apps/
│   ├── api/            # FastAPI app: routers only (ingest, cases, decisions, outcomes,
│   │                   #  model, admin, monitor, knowledge, copilot, webhooks, audit)
│   ├── workers/        # role-selected loops: orchestrator-wake, scheduler-claim,
│   │                   #  gateway-dispatch, outbox, aggregates, monitors  (RUNTIME_ROLE)
│   └── web/            # React+TS+Vite SPA · TanStack Query · generated SDK · custom SVG charts
├── core/               # pure domain — imports NO adapters/LLM/knowledge (import-graph tests)
│   ├── domain/         # enums, contracts, DTOs (pydantic)
│   ├── fsm/            # transition table + guards (exhaustively tested)
│   ├── constraints/    # pure engine + rule-pack loader (+pack hash)
│   ├── features/       # SHARED feature wheel (offline mart + online builder, one code path)
│   ├── scoring/        # ScorerPort, artifact loader, hash/schema gates, doctrine fallback
│   ├── decision/       # candidate generator, EV layer, policies B0–B3 (+doctrine fallback)
│   ├── orchestrator/   # claim/fold/decide single-writer loop; case projection
│   ├── scheduler/      # due-work table, leases, kill-scope parking
│   ├── gateway/        # intents (verdict_hash required by type), re-verify, outbox, idempotency
│   ├── journal/        # append-only writer (producer-owned types) + inbox
│   ├── audit/          # decision-record repo + replay service
│   └── monitor/        # 4-category series builders (business first)
├── adapters/
│   ├── payments/       # PaymentRailPort: sim_rail (full world model) + razorpay/stripe test
│   │                   #  adapters behind flags (fixture-driven, no credentials in sandbox)
│   └── notify/         # NotificationPort: sim_notify + email (SBX) + sms/wa stubs
├── sim/                # sim-zone world model (documented 3A mechanics, seeded, deterministic)
│   └── (latent state sealed: unreachable from core.features — import-graph test)
├── knowledge/          # ingestion (heading-aware chunker), embedder port, hybrid retrieval
├── copilot/            # flag-gated read-only façade (structured answers w/o LLM; LLM renders only)
├── configs/            # runtime.yaml, costs.yaml, feature_contract_v3.yaml, model_benchmark.yaml,
│                       #  rule_packs/*, psp_code_map/*, assumption_registry.yaml, scenario_regimes.yaml,
│                       #  knowledge_corpus.yaml
├── db/                 # migrations (single schema) + roles.sql (append-only grants, PG profile)
├── training/           # offline mart builder + training-side entrypoint (imports core.features ONLY)
├── scripts/            # seed_demo.py, run_batch.py, gen_sdk.py, acceptance.py
├── tests/              # unit · property(fuzz) · contract · boundary(import-graph) · drills · e2e
├── deploy/             # docker-compose.yml (db pg16+pgvector, api, ops, web) · Dockerfile · envs/
├── docs/               # README (run+demo+evaluator walkthrough) · DECISIONS.md · dataset/authority notes
└── artifacts/          # ./models + ./report mounts (provided artifacts land here; gate reads them)
```

## 3. Environment & verification strategy (this sandbox vs deployment)

| Concern | Deployment target (evaluator machine) | This sandbox (verification + live preview) |
|---|---|---|
| OS processes | `docker compose up` → db+api+ops+web, migrations+seed+activation gate on boot | direct run: uvicorn (role=all) + built SPA served by FastAPI, live preview URL |
| Database | **PostgreSQL 16 + pgvector only** (compose), roles.sql grants | **SQLite dev profile, explicitly labeled** (no Docker/PG/sys-install possible here; D-006). Same schema/migrations via SQLAlchemy 2.0; SKIP LOCKED→serialized claim tx; pgvector→exact cosine scan + FTS5 BM25 (O(10⁴) chunks, trivial). All PG-specific tests marked pg-only and run in the compose profile |
| ML scorer | artifact mounts ./models ./reports | gate runs; absent ⇒ flagged doctrine fallback (the designed path) |
| LLM copilot | flag + key | COPILOT_ENABLED=false default → deterministic surfaces; acceptance drill runs here |
| Frontend | nginx serves built SPA | Vite build to `apps/web/spa` (snapshot-safe dir), FastAPI StaticFiles |

Honesty invariant: the SQLite profile is a **dev/verification label** shown in the env badge chain (SIM · dev-store), never presented as the production topology; the compose stack is the authoritative deployment and is fully written + documented even though it cannot execute here.

## 4. Knowledge corpus plan (roles never mixed; no fabricated ingestion)
- **Ingested (real files, real chunks):** the 12 project documents (doc_type=project_document, authority=reference) + a curated `REGULATORY_AND_PSP_EXCERPTS.md` authored from facts **already cited** in the phase docs (NPCI 1+3, quiet/non-peak windows, ₹15K cap, pre-debit notice, Cashfree/Razorpay retry behavior) — each entry carries its source citation and tag {FACT/FACT-referenced/ASSUMED/VENDOR_DOCTRINE}. No bulk downloading of PSP docs; no pretend-ingested datasets.
- **Registered as external references only (file absent ⇒ not ingested, no invented schema/rows):** UPI Transactions 2024 (SIMULATION_CALIBRATION; the two documented priors—SBI 25.1%/HDFC 15.0% bank shares, category price points—are cited from the build report), UCI Default/Hillstrom/Criteo/PaySim/UCI Bank Marketing/Rees46/Online Shoppers/Digital Wallet/FinTransactions/IBM Factoring/Invoice Date (METHODOLOGY/BACKGROUND), PSP docs (PSP_BEHAVIOR). Data Sources page renders this table truthfully from `knowledge_corpus.yaml`.
- **ML/RAG separation test (CI):** reference-only sources have no code path into `core.features`/`training/`; sim latent/counterfactual state unreachable from feature/scoring paths (import-graph + exclusion-list tests). Predictive pipeline may consume only the approved C4-derived contract features.
- Retrieval: hybrid vector (config-swappable embedder; deterministic lexical-hash default in sandbox — D-007) + BM25 (tsvector / FTS5); every doc/chunk carries `{source, doc_type, role, authority, provenance, license, content_hash}`; answers cite chunk IDs or abstain; “rule pack X governs” banners wherever regulatory text is shown.

## 5. Demo & evaluator walkthrough wiring (prompt §10 → concrete surfaces)
Seeded demo cohort (150–200 cases; taxonomy-covering; rails 70/30 UPI/card; banks per documented UPI priors; varied tiers/amounts ≤ ₹15K): MUST include recovered, retried, waited, stopped, escalated, and blocked-visible cases; hard classes show link/PM-update paths (never retries); blocked cards show exact rule reasons (“retry budget exhausted (NPCI 1+3)”, “quiet hours 21:00–08:00 IST”, “mandate paused — retry cannot succeed”).
`POST /recovery/simulate-batch` runs a REAL closed loop through Sim adapters; live cohort state updates on /overview and /cases from the DB; completed batch evaluations (B0/B1/B2/RD-EV on the frozen seed, common random numbers) are frozen separately and labeled — an in-progress demo is never presented as the formal benchmark.
Walkthrough (dashboard → case → run-next-step → options/p̂/EV/verdicts → execute → outcome → timeline → economics → decision page → copilot-why → knowledge citations → replay PASS → violations=0) is automated as `scripts/acceptance.py` and documented in README for a stranger in <10 minutes.

## 6. Build milestones (maps to prompt §14; each has a hard verification gate)

| # | Milestone | Exit gate (verified by running code, not claims) |
|---|---|---|
| M0 | repo skeleton, configs, migrations, domain enums, FSM transition table | config-lint (no unregistered constants), FSM exhaustive-transition test green |
| M1 | journal + inbox + projection + orchestrator claim/fold + scheduler (leases, parking) | crash-safety test: fault mid-decision ⇒ clean replay, no half-state; duplicate webhook ⇒ single effect |
| M2 | constraint engine + rule packs + verdict hashes + kill switch scopes | property-fuzz (snapshots × candidates × packs); every family deny-path proven; mutation spot-checks |
| M3 | gateway (re-verify, outbox, idempotency) + sim adapters (world model) + webhook ingest (signed, dedup, canonical map) | bypass drill (stale verdict hash ⇒ INTERVENTION_BLOCKED, zero effects); adapter world invariants (3A §13 I1–I12 subset) |
| M4 | shared feature wheel + feature_contract_v3 + as_of/exclusion proofs + ScorerPort + activation gate + doctrine fallback + EV layer + Decision Record atoms + replay | gate match/mismatch tests (fixture artifact, labeled test-only); EV argmax/tie/STOP/ESCALATE tests; replay PASS on golden cases; decision p95 < 300ms local |
| M5 | policies B0–B3 + batch simulation runner + outcomes/aggregates + monitoring (4 categories) | batch run: economics consistent DB↔API; baselines side-by-side; violations counter honest 0 |
| M6 | read APIs stable → OpenAPI → generated typed SDK → frontend shell + design system | OpenAPI contract tests on responses; SDK regeneration diff = clean |
| M7 | all screens (case-detail hero first), then outcomes/model/admin/audit | every number traceable to a live API response; empty/loading/error states |
| M8 | knowledge ingestion + retrieval + page; copilot façade (flag-gated) | citations real; copilot-off drill: full product pass |
| M9 | failure drills (LLM down / artifact mismatch / constraint exception / kill-switch <60s), security pass, full pytest | all drills green in-sandbox |
| M10 | README + evaluator walkthrough executed twice end-to-end; numbers refreshed from live runs | acceptance script green twice; DoD checklist ticked honestly |

## 7. Testing map (prompt §12 → suites in `tests/`)
- **Constraints:** unit per family + Hypothesis fuzz on (snapshot × candidate × pack) trios; unknown/errored pack ⇒ deny-all (fail closed).
- **Feature schema:** runtime builder output vs schema artifact — match activates, mismatch refuses (both tested with a generated fixture clearly labeled test-only; the real gate awaits the real joblib).
- **Model loading:** JSON artifact loads via Booster; sha256; metadata completeness incl. `calibration_version=null, mode=uncalibrated`.
- **Decision/EV:** constants resolved from registry only (lint); argmax + deterministic tie-break; STOP/ESCALATE triggers; doctrine fallback path.
- **FSM:** exhaustive legal-transition table; absorbing terminals; counter guards; post-terminal events are evidence-only.
- **Idempotency:** duplicate webhook ⇒ one effect; duplicate intent ⇒ one logical action; outbox once-per-intent (intent_id = blake2b(case_id, decision_seq, action_type, window_code)).
- **Orchestrator crash-safety:** injected faults mid-decision ⇒ rollback + clean replay.
- **API contract:** success/validation/404/409/auth/conflict + representative internal-failure paths; OpenAPI response validation.
- **Failure drills:** LLM off ⇒ product intact; artifact missing/mismatched ⇒ flagged fallback, constraints still enforced; constraint-engine exception ⇒ zero side effects; kill-switch scope ⇒ parked/blocked.
- **E2E demo script:** seed → batch → DB↔API economics consistency on key screens.
- **Boundary:** import-graph (core ↛ adapters/llm/sim-latent/knowledge); ML/RAG separation; append-only (PG grants test in pg profile).

## 8. Honesty & trust surfaces (baked into design, not sprinkled after)
Env badge (SIM/SBX/PRD + dev-store marker) persistent; “simulated — not production evidence” plaques wherever ₹/rates appear; Prediction vs Decision vs Constraint vs Execution as four visually distinct trust layers (case detail WHY panel, decision page, pipeline diagrams); Model page shows synthetic-domain benchmark + training_domain=SIM + uncalibrated + activation BLOCKED/PASS truthfully; baselines rendered even where RD loses; empty states instead of plausible fabrications; claim-template language (Phase 2 §15) in outcomes copy.

## 9. Open items for you (blocking only #1 and #2 in the sense of product completeness, not construction)
1. **Upload the ML artifact bundle** (`models/c5/xgboost_native_categorical_c5.json`, `reports/c5_xgb_native_categorical/native_categorical_schema.joblib`, `best_params.json`, `native_categorical_metrics.csv`, `optuna_trials.csv`) → gate activates the real model; until then the system runs the designed fallback and says so.
2. **Ops Copilot LLM key** (optional) → else COPILOT_ENABLED=false and the deterministic explanation surfaces carry the product.
3. Optional: Dataset V1 parquets / recoverysim repo — would let me align the sim world bit-for-bit; otherwise the documented-mechanics reimplementation stands (D-009).
