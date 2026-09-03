# DECISIONS.md — interpretation & conflict log

Running log of every interpretation made where the documents leave room, per master prompt §1/§14.
Format: ID · topic · inputs · decision · rationale · status.

---

## D-001 · Terminal-state naming: STOPPED vs CLOSED_LOST
Inputs: PHASE_3A §4 (7 states, `CLOSED_LOST` with reason) vs PHASE_4 §6.1 + master prompt §5 (`STOPPED`).
**Decision:** runtime FSM uses `STOPPED` (prompt/PHASE_4 are structure authority). 3A's closure semantics are preserved as `stop_reason ∈ {budget_exhausted, mandate_dead, opt_out, window_expired, escalation_final, ev_non_positive, human}` on `case_stopped` events — audit distinctions survive without a second terminal state.
Status: **closed.**

## D-002 · Event enum: two vocabularies in the corpus
Inputs: PHASE_3A §10 (uppercase dataset events: ATTEMPT_EXECUTED, CASE_OPENED, …) vs PHASE_4 §12.1 / prompt §5 (frozen lowercase runtime v1: payment_failed … kill_switch_resumed).
**Decision:** the runtime journal uses ONLY the frozen lowercase v1 enum; 3A's uppercase set is offline-dataset vocabulary. Mapping table documented in `core/domain/enums.py` for traceability. No third enum invented.
Status: **closed.**

## D-003 · Failure taxonomy & class eligibility at runtime
Inputs: PHASE_3A §6 (8 classes incl. AUTH_REQUIRED edge), DATASET_BUILD_REPORT (recoverysim implements 7: INSUFFICIENT_FUNDS, BANK_TECHNICAL, RATE_LIMIT, MANDATE_PAUSED, MANDATE_CLOSED, CARD_EXPIRED, CARD_LOST_STOLEN), prompt §4 (hard classes CARD_EXPIRED / CARD_LOST_STOLEN / MANDATE_CLOSED never auto-retry; PM-update/link path).
**Decision:** runtime canonical set = the recoverysim 7 (matches the dataset the model was trained on ⇒ vocab compatibility). AUTH_REQUIRED excluded from V1 (rare, AFA regime noted); any unmapped PSP code ⇒ `UNMAPPED` ⇒ non-retryable, fail closed. RETRY blocked for MANDATE_PAUSED (while paused), MANDATE_CLOSED, CARD_EXPIRED, CARD_LOST_STOLEN; reminders/links permitted (nudge/reactivation hazard), REQUEST_PM_UPDATE restricted to card/mandate-dead classes (3A §7).
Status: **closed.**

## D-004 · ML artifact bundle absent from delivered inputs
Inputs: master prompt §3 (expects 5 artifact files); filesystem search — none present.
**Decision:** implement the full activation gate (Booster load, joblib schema equality on names/order/categoricals/vocab, counts 43/17/26, sha256, training_domain=SIM); absent/mismatched ⇒ activation refused, startup journal records the reason, scorer runs flagged deterministic doctrine fallback (`scorer_mode=fallback`, `policy_id=doctrine-b2`, `calibration_version=null`, `mode=uncalibrated`), Model page shows BLOCKED with the failing checks listed. Gate tests use a **generated fixture artifact labeled test-only** — never shipped as a model, never used for product scores. Artifacts drop into `artifacts/models` + `artifacts/reports` with zero code change.
Status: **closed (revisit if artifacts are uploaded).**

## D-005 · Model benchmark numbers source when metrics CSV is absent
Inputs: prompt §3 (benchmark must be shown from backend, never frontend literals); `native_categorical_metrics.csv` not delivered; Phase_3C_Model_Training §11 has the confirmed table.
**Decision:** backend serves metrics from `configs/registry/model_benchmark.yaml` with provenance citation (Phase 3C §11) and label TEST-on-synthetic-split + simulator-domain disclaimer; when the CSV is provided it becomes the source instead. Frontend renders API fields only.
Status: **closed.**

## D-006 · Verification database: real PostgreSQL everywhere (supersedes the original SQLite note)
Inputs: PHASE_4 §18/§24 (PostgreSQL 16 + pgvector adopted; SQLite explicitly rejected); user directive (explicit): *"SQLite/sandbox mode is only for local verification. It must not replace PostgreSQL in the production architecture. All repository code, migrations, SQL semantics, API contracts, and tests must remain PostgreSQL-compatible, and the Docker Compose PostgreSQL profile is the authoritative deployment path."*
**Decision:** SQLite is **dropped entirely** — not even a dev profile. The sandbox runs a **real unprivileged PostgreSQL 16.9 + pgvector 0.8.0** (portable binaries under `/tmp/pgroot`, cluster persisted at `/home/user/pgdata`, revived by `tools/pg_up.sh`; binaries re-fetched from pinned URLs each turn since `/tmp` is not persisted). All migrations are plain PostgreSQL SQL applied by a runner tracked in `schema_migrations`; role grants (`db/roles.sql`) enforce append-only journal/decision tables and are **asserted by tests**; scheduler claiming uses real `SELECT … FOR UPDATE SKIP LOCKED`; knowledge uses real pgvector. The docker-compose Postgres 16 + pgvector profile is the authoritative deployment; sandbox and compose run the same schema, same roles, same SQL — no dialect forks anywhere.
Status: **closed (user-ratified).**

## D-007 · Embedding model default
Inputs: PHASE_4 §16 (local sentence-transformers default); sandbox 2 vCPU/1.9GB RAM (torch+model ≈ GBs, non-persistent).
**Decision:** EmbedderPort is config-swappable (`knowledge.embedder = lexical_hash | sentence_transformers`). Sandbox/compose-demo default = deterministic lexical-hash embedder (no network, no GB dependency); sentence-transformers selectable by config where resources allow. The Knowledge page renders the active embedder id from the backend — no pretense about which index is live.
Status: **closed.**

## D-008 · Exact 43-feature order/vocabulary before the joblib arrives
Inputs: Phase 3C §4 says “base contract contains 32 model inputs”; PHASE_4 §10.1a demands 43/17/26 == saved schema; joblib absent.
**Decision:** the arithmetic that fits 43 = 26 numeric + 17 categorical is base-32 (§4.1 17 numeric + §4.2 2 binary + §4.3 11 categorical + §4.4 2 intervention-categorical) + engineered-11 (§6: 6 numeric + 5 interactions), with **day_of_week treated as numeric** (26/17 split then lands exactly; as categorical it cannot). Provisional names/order/vocab live in `configs/registry/feature_contract_v3.yaml`; the runtime builder emits exactly that; **the activation gate compares against the joblib as ground truth when provided — any mismatch stays BLOCKED** (never guessed into service).
Status: **closed (confirmation deferred to artifact arrival).**

## D-009 · Sim-zone world model: reimplement, don't fake provenance
Inputs: PHASE_3A §5/§8 mechanics; DATASET_BUILD_REPORT §3 parameters (sufficiency process, Poisson(0.10)/day ≈1.5h outages, 97% silent card refresh, 0.4% lost/stolen, intent archetypes, fatigue, 336h horizon, keyed blake2b→PCG64, anchors 11.3%/7.3%/10.1% first-fail; recovery 0/35.3/49.2/50.2% for B0–B3); recoverysim source not delivered.
**Decision:** implement the Sim zone from the documented mechanics and parameters; label it `world_model=reimplemented_from_phase3A_3B_docs`; every parameter lands in the assumption registry with tags; the documented B0–B3 rates are used as plausibility bands for sanity checks, reported as bands — the reimplementation is never called “recoverysim v0.3”.
Status: **closed (revisit if recoverysim/Dataset V1 uploaded).**

## D-010 · Legal windows / quiet hours / bins concrete values
Inputs: prompt §4 example “quiet hours 21:00–08:00”, “retry budget exhausted (NPCI 1+3)”; PHASE_4 §7.1 (windows per rail, values FACT-referenced/ASSUMED); recoverysim configs not delivered (exact bins unknown).
**Decision:** rule packs define: quiet hours 21:00–08:00 IST both rails; UPI debit window 08:00–21:00 IST; card SI 08:00–21:00 IST; contact hours 09:00–21:00 IST; window bins W08_11/W11_14/W14_17/W17_21. All values registry-tagged (concept FACT-referenced; exact bins DECISION) and hash-stamped; editable via pack versioning only.
Status: **closed.**

## D-011 · B1 baseline cadence
Inputs: Phase 2 §14 / Phase 3B §12 — UPI: 1+3 hourly (Cashfree); cards: daily until ~4th failure → halt (Razorpay lifecycle).
**Decision:** encode exactly that in `policies.yaml` with source citations; hourly cadence snaps to legal windows (quiet hours cannot be violated by B1 either — it consumes attempts at the next legal slot; deviation documented in the pack notes).
Status: **closed.**

## D-012 · Knowledge corpus ingestion boundaries
Inputs: prompt §9A (roles A–O; ingestion rules; ML/RAG separation).
**Decision:** ingest the 12 delivered project documents + a curated excerpts file authored ONLY from facts already cited in them (with citations). Reference datasets (UPI 2024, UCI×4, Hillstrom, Criteo, PaySim, Rees46, wallet, fin-transactions, IBM factoring, invoice-date) are registered as **external references with truthful metadata; not ingested** (files absent — no invented schemas/row counts). PSP/regulatory materials ingested only as the cited excerpt layer (role PSP_BEHAVIOR/REGULATORY_REFERENCE, authority=reference); compiled rule packs always presented as the authority over retrieved text.
Status: **closed.**

## D-013 · Runtime roles in the sandbox
Inputs: PHASE_4 §5 (one image, roles core/ops by env flag).
**Decision:** compose runs `api` (core) and `ops` (jobs) containers from one image; the sandbox runs `RUNTIME_ROLE=all` (both loops in one process) for live preview. Role selection is env-config, not a branch.
Status: **closed.**

## D-014 · Build output directory naming
Inputs: platform constraint (snapshot excludes `build/`, `dist/`, `out/`, `node_modules/`).
**Decision:** Vite `build.outDir = "spa"` inside `apps/web/`; FastAPI serves it in the sandbox preview; compose serves it via nginx. Cosmetic, zero product impact.
Status: **closed.**

## D-015 · Charting approach
Inputs: prompt §9 (“a restrained charting library … meaningful (not decorative) charts”; original design, no template kits).
**Decision:** small custom SVG chart primitives (line/area, bar, funnel, sparkline) in the design system — original visual identity, tiny bundle, full a11y control; no heavyweight chart kit. A library can be swapped later without touching data plumbing.
Status: **closed.**

## D-016 · PSP test adapters scope
Inputs: PHASE_4 §14.2 lists RazorpayTestAdapter/StripeTestAdapter as “required”; master prompt §5 says “behind flags if credentials exist” and forbids requiring infra beyond the approved stack; no PSP credentials exist in this environment.
**Decision:** prompt wins on demo scope: ship `SimRailAdapter`/`SimNotifyAdapter` fully working + Razorpay/Stripe test adapters implemented against documented sandbox semantics with fixture-driven tests (Stripe test-clock, Razorpay subscription lifecycle), activated only by config+credentials; no network PSP dependency in the demo path. Documented as flagged adapters, badge "sandbox-ready".
Status: **closed.**

## D-017 · LLM usage surfaces
Inputs: Phase 1 §20 (LLM-assisted messaging) vs Phase 2 §17 + PHASE_4 §17 (LLM never on decision path; copilot flag-gated; deterministic templates default).
**Decision:** later docs win: deterministic template engine for all customer messaging (slots {amount, date, plan}); LLM confined to (a) optional copilot prose rendering over structured/cited facts, (b) optional message-wording draft behind a flag — both degradable to identical deterministic output. COPILOT_ENABLED=false is an acceptance-tested state.
Status: **closed.**

## D-018 · Attempt-opportunity-cost operationalization
Inputs: PHASE_4 §11.1 (`attempt_opportunity_cost(a)` “uses scarce retries”; no formula given).
**Decision:** implement as a registry constant `retry_budget_shadow_price` (₹ per retry attempt consumed, scaled by value tier) — deterministic, hash-stamped, sensitivity-multiplied. A richer expected-future-value model is registered as future work (would require off-policy estimates; deliberately not pretended).
Status: **closed.**

## D-019 · ML artifact bundle received & verified — actual schema is 32/12/20, NOT the documented 43/17/26
Inputs: uploaded `xgboost_native_categorical_c5.json` (sha256 9434606c…), `native_categorical_schema.json` (sha256 e4fd63c8…, JSON transport of the canonical `native_categorical_schema.joblib`), `best_params.json`, `native_categorical_metrics.csv`, `optuna_trials.csv` vs PHASE_4 §9.0/§10.1a and master prompt §3 (claim: 43 features / 17 categorical / 26 numeric).
**Verified facts (measured, not assumed):** model `feature_names` count = 32 and equals schema `features` list exactly in order; model `feature_types` marks exactly 12 columns `c` at the schema's `categorical_features` positions; schema `category_vocab` has 12 keys == the categorical list, each ending in `__UNKNOWN__`; numeric = 20. The 11 engineered features of Phase 3C §6 are NOT in the artifact. Metrics CSV equals the documented TEST benchmark to 6 decimals (PR-AUC 0.831340 / ROC-AUC 0.940206 / LogLoss 0.252191 / Brier 0.077702). `best_params.json`: 5-fold StratifiedGroupKFold grouped by `case_id`, n_estimators 1256.
**Decision:** the documented 43/17/26 was a planned contract extension that this artifact does not register — PHASE_4 §10.1 explicitly gates engineered features on the artifact's manifest. Runtime feature contract := the artifact schema verbatim (32 features, 12 categorical, 20 numeric, artifact vocab). Activation gate compares runtime builder output against the artifact schema (exact) — passes on equality, refuses on any mismatch. Doc-vs-artifact conflict recorded here; the schema was NOT altered to force any match.
Status: **closed.**

## D-020 · "SQLite dev profile" checklist item — remain PostgreSQL-only
Inputs: continuation checklist item 12 (keep SQLite for Arena-local verification) vs the user's earlier explicit directive and D-006 (Postgres-only; compose authoritative; real PG16+pgvector runs in this sandbox via portable binaries).
**Decision:** no SQLite profile is introduced. The earlier, stronger directive governs, and the sandbox already runs real PostgreSQL 16.9 + pgvector 0.8.0 — every verification here exercises the same SQL semantics as the compose deployment. Item 12 is satisfied a fortiori (local verification works), with zero dialect forks.
Status: **closed.**

## D-021 · Channel encoding for non-contact actions (RETRY)
Inputs: schema `channel` vocab = [SMS, WHATSAPP, EMAIL, __UNKNOWN__]; no NONE token exists; mart unavailable for direct inspection.
**Decision:** RETRY candidates carry `channel="__UNKNOWN__"` (the only in-vocab value that can represent a non-contact action; a `NONE` token would have appeared in the training vocab had it been used). Documented as an encoding interpretation; to be re-verified against the canonical mart when Dataset V1 parquets arrive.
Status: **closed (revisit on dataset arrival).**

## D-022 · Categorical code assignment = schema vocab index order
Inputs: vocab lists are in insertion (unsorted) order — e.g. rail [UPI_AUTOPAY, CARD_SI, __UNKNOWN__], bank [PNB, INDUSIND, HDFC, YES_BANK, SBI, …] — implying the training pipeline used `pd.Categorical(categories=vocab)` with exactly this order.
**Decision:** runtime encodes category → code as `vocab.index(value)` (missing → `__UNKNOWN__` index, fail-closed). Verified empirically by a distributional sanity test: scored rows must reproduce the documented label-signal ordering (BANK_TECHNICAL-RETRY ≫ INSUFFICIENT_FUNDS-RETRY, per DATASET_BUILD_REPORT §5: 88.3% vs 16.2%) — scrambled codes would collapse this structure.
Status: **closed (empirically verified in tests/test_scoring_smoke.py).**

## D-023 · Kill-switch parking evidence without minting an event type
Inputs: PHASE_4 §13 (parked rows journal `ACTION_PARKED_KILL_SWITCH`) vs frozen v1 event enum (master prompt §5, no such type).
**Decision:** the frozen 20-event enum wins (D-002 discipline). Parking evidence lives in `scheduled_actions.state='parked'` + a `monitoring_series` (compliance category) row per parked item, and the kill_switch_fired event already journaled at fire time. No new event type minted.
Status: **closed.**

## D-024 · SimClock time compression + disposable sandbox cluster
Inputs: PHASE_4 §15 (SimClock fast-forward, config not branch); sandbox realities (turn resets kill processes; snapshot restore drops empty dirs, breaking crash recovery).
**Decision:** (1) All loop code takes a Clock port; SimClock implements virtual time with `sim_time_scale` (1 real s = N sim s) so 14-day horizons play out in minutes; due_at is scheduled in REAL time via `clock.real_until(sim_dt)`; journal timestamps carry SIM virtual time (env=sim keeps evidence unmixable). WallClock serves SBX/PRD. (2) The sandbox PostgreSQL cluster is DISPOSABLE: `tools/pg_up.sh` self-repairs missing empty dirs, and the documented recovery from a wedged cluster is re-initdb + `python -m db.bootstrap` (all state regenerates from code/seeds — the durable truth is the repo, not the sandbox DB).
Status: **closed.**

## D-025 · Gateway re-verification semantics (trust layer 4, implemented)
Inputs: PHASE_4 §10; bugs found by the first E2E integration run.
**Decision:** `execute_intent` re-verifies with TWO projections of the same live rows:
  1. `snap_verify = build_snapshot(case, intent.decided_at)` — the verdict is re-evaluated AT THE DECISION TIME with CURRENT state; hash must equal the stored `verdict_hash`. Pure clock drift (hours_since_open, hour_of_day) never invalidates; state drift (opt-out, budgets, mandate, amount, kill) always does.
  2. `snap_fresh = build_snapshot(case, now)` — fresh time-legality (quiet hours, window).
Either failing ⇒ BLOCKED + `intervention_blocked` evidence + case reopened via a +1h WAIT_WAKE (no stall).
Corollaries: (a) the EXACT `candidate_id` is persisted on the intent (0005) — the hash covers it, and deriving it from action_type diverges for retries ("RETRY@W08_11" ≠ "RETRY_AT_WINDOW@W08_11", which silently blocked every legal retry); (b) `decided_at` persisted (0004); (c) the SimRail mandate_ref contract is 5-part `customer|bank|rail|mandate_status|failure_class` — a 4-part ref returns SIM_MALFORMED_REF→UNMAPPED (fail-closed, caught by tests, never in prod).
Status: **closed** (tests: test_loop_pg.py).

## D-026 · ML artifact single-sourcing (workspace storage)
Inputs: snapshot cap 128 MB; the 25 MB XGBoost JSON was stored twice (uploads/ + artifacts/models/c5/); symlinks do NOT survive workspace snapshots (observed: directory vanished on restore).
**Decision:** `configs/registry/model_artifacts.yaml:model_path` points at the authoritative `/home/user/uploads/xgboost_native_categorical_c5.json` directly (absolute path; `REPO_ROOT / abs` resolves to abs). sha256 gate unchanged (9434606c…). No duplicate copy; no symlinks for artifacts.
Status: **closed.**

## D-027 · RAG embedder identity — hashed-lexical-v1, honestly reported
Inputs: item 10 (knowledge + RAG); sandbox has no sentence-transformers (RAM limit); pgvector available.
**Decision:** Real RAG pipeline — chunk (paragraph-aware, deterministic) → embed → pgvector cosine top-k with cited sources. The embedder is a deterministic 256-dim signed hash bag-of-words (`hashed-lexical-v1`), NOT a neural model; the API and UI state this explicitly (`embedding_model` field). Never implied otherwise. Reference docs never touch ML training (separation CI-enforced).
Status: **closed** (tests: test_knowledge_pg.py).

## D-028 · Continuous loop worker (SIM world keeps moving under the UI)
Inputs: item 13 demo requirement (live polling shows real motion).
**Decision:** `apps/workers/loop_worker.py` (compose entrypoint `python -m apps.workers.loop`): claim_due → wake_case → drain intents every 1s real; SimClock continues from the last journaled sim instant (evidence stays monotonic); scale via `RD_SIM_SCALE` (default 120×). Single-writer discipline maintained (SKIP LOCKED leases).
Status: **closed.**

## D-029 · Artifact path resolution chain + compose model mount
Inputs: D-026 (single-sourcing) broke container builds (absolute sandbox path outside build context); compose copied non-existent dirs; worker module name drifted.
**Decision:** `model_artifacts.yaml` stays repo-relative; `_resolve_artifact()` falls back to `uploads/<basename>` when the repo-relative file is absent (sandbox case). Compose mounts the single model JSON read-only into the registry path (`RD_MODEL_JSON` overridable). Dockerfile copies only real dirs. `deploy/envs/dev.env` required by compose verified to exist. Docker itself unavailable in sandbox → item 14 verified at config level (tests/test_deploy_config.py); running `docker compose up` remains a host-side step.
Status: **closed.**

## D-030 · Webhook-entry first-decision wake (gap found by live E2E)
Inputs: injecting fresh failures via the real API webhook left cases in CASE_CREATED — the batch runner had always performed the first wake manually, masking the gap.
**Decision:** `ingest_payment_failure` schedules a `WAKE_NEW_CASE` scheduled_action (due immediately) whenever it OPENS a new case; the worker's claim loop performs GUARDS_PASS → first decision. Idempotent under duplicate dedup (dedup hits don't reschedule). Verified live: injected cases advanced OPEN_DECISION → AWAITING/RECOVERED under the worker while the UI polled.
Status: **closed.**

## D-031 · UI polish pass (quantitative audit) + CaseDetail TDZ crash fix
Inputs: final UI/UX review task; automated DOM audit (Playwright: WCAG contrast, overflow, tap targets, focus, typography census) because the session had no vision — review was numeric + code-level, never "looks fine by assumption".
**Found & fixed:** (1) CaseDetail crashed the whole React tree since the explain panel shipped (TDZ: `latest` referenced before initialization) — the hero page was blank below the header while API-level tests stayed green; fixed + a route-level ErrorBoundary added so any future crash degrades to an honest message instead of a blank app. (2) 5 WCAG contrast failures (ink-3/good/warn/brand-mark) → tokens darkened; audit now 0 failures across 9 surfaces. (3) Mobile horizontal overflow on every page (grid min-content + wide tables) → min-width:0, card-level scroll, overflow-wrap; page width now exactly 390px. (4) Tap targets <40px on mobile → 44px controls. (5) 11.5px type floor → 12px+; weights normalized. (6) Dashboard hero KPI (recovered ₹ leads) + Case hero header (amount + budgets) + numbered pipeline steps. (7) Restrained motion: rise/grow animations, prefers-reduced-motion honored. No backend/data changes; every number still live from the API.
Status: **closed** (audit sweep: 14/14 surfaces clean; 142-test battery green; one claim-order test flake hardened).

## D-032 · Product-experience redesign (evaluator-journey rewrite of the UI)
Inputs: active redesign task — success = a first-time evaluator understands in 30 s what RecoveryDesk solves, can follow a case end-to-end, sees legality/selection/execution/outcome distinctly, sees recovered ₹ vs baselines honestly, and it feels like a fintech product, not an admin console. Standing rules: real data only, no architecture change, remove surfaces that fail the journey test.
**Decision — removed:** Ops Copilot page (deleted; backend flag stays, no chatbot/LLM messaging anywhere), Dashboard.tsx and Model.tsx (superseded by Overview and System Status). **Consolidated:** nav 8→6 destinations (Overview · Recovery Cases · Outcomes · Knowledge & Rules ‖ System Status · Audit Trail). **Redesigned:** Cases = queue of rupee opportunities (.q-row, human failure language); CaseDetail = forensic story (dark ₹ header band with budget ledger, stopped/escalated self-explaining panels, 9-step numbered recovery journey with live re-plan highlight, four decision layers PREDICTION/CONSTRAINT/ECONOMICS/EXECUTION, chosen spotlight, "blocked by constraints — what the system refused to do", candidate table + collapsed deterministic trace); Overview = hero REVENUE AT RISK → ENGINE → RECOVERED with honest baseline chips (beats B1 +115%; B2 leads by ₹34,363 — published per evaluation rules) and zero-violations compliance; Outcomes = business proof (baseline table with methodology, attempts/contacts/TTR, by rail/class, stop reasons); Knowledge = EXECUTABLE rule pack vs REFERENCE corpus split + live read-only "can this case act right now?" engine check; System = trust surfaces (activation, benchmarks from artifact CSV, never-fabricated calibration, rule-pack hashes); Audit = WHAT/WHEN/WHY/RESULT/COMPLIANT rows with collapsed payloads. Brand mark = recovery-loop orbital arcs around ₹. **New backend to feed it (no architecture change):** /api/baselines (B0/B1/B2 vs RD, Monte-Carlo replay 48 draws/case through sim/world.py gates, methodology string in payload), /api/constraints/check (real engine, read-only), /api/outcomes extended (by_rail, budgets, escalation, TTR, action mix, compliance), /api/model benchmarks. 20 API paths; SDK regenerated.
Status: **closed** (build green; Playwright sweep 33 checks incl. API↔UI numeric parity and honest-loss copy; 142 tests green; walkthrough rewritten).

## D-033 · Two test-environment hazards found by the post-redesign suite run
Inputs: full suite re-run after the redesign failed 2 tests though no pipeline code changed.
**Root causes:** (1) `test_scoring_smoke::test_illegal_candidates_never_reach_model` called `run_decision` without `now_utc` — the default is real wall-clock, so contact actions were denied by R-CONTACT-HOURS whenever the suite ran outside 09:00–21:00 IST (latent since the test was written; the live loop always passes its sim clock). Fix: pin `now_utc=snap.now` in the test — production behavior unchanged and correct. (2) `test_loop_pg` demo cohort lives in the same PG a running loop worker polls; a live worker racing the test produced phantom post-terminal events. Fix documented in README: stop the worker before pytest; both failures reproduce deterministically under those two conditions and pass otherwise.
Status: **closed** (142/142 green with worker stopped; sweep re-run clean).


## D-034 · Final product-quality pass (runtime model proof + luminous redesign)
Inputs: final correction round — evaluator review judged the UI still admin-like/implementation-heavy; demanded runtime proof of the supplied XGBoost artifact, business-first IA, System→trust framing, dark luminous fintech visual system, live demo motion, multi-viewport QA.
**Model proof:** `scripts/verify_model_runtime.py` — 17 checks in the real app runtime: resolver path → exists → independent SHA-256 → independent Booster load (32 feats/1256 trees/binary:logistic) → 16/16 activation gate → contract order match → 12 categorical 'c'-columns → live-case inference → independent-prediction parity (max |Δp̂| = 0) → p̂ in decision atoms → EV arithmetic re-verified on 119 journaled atoms (max Δ 0.0000) → production records carry c5 model id; failure path F1–F3 (tampered schema → gate fails → doctrine-fallback flagged, constraints still deny, e.g. R-BUDGET-RETRY-1P3). Report: artifacts/reports/model_runtime_verification.md. Production artifact never touched.
**Product changes:** nav 'System Status'→'System & Trust' (EVIDENCE group, demoted); /health `ops_copilot` field removed + dead `.copilot-off` CSS deleted; `/health` migrations query fixed to schema_migrations (was silently [] → 'migrations: 0'); System & Trust = 6 trust cells (MODEL ACTIVE / SCHEMA 32-12-20 / RULE PACKS / ENV SIM / COMPLIANCE / DB) + Recovery Propensity Model block (INPUT/OUTPUT/USED BY/DOES NOT CONTROL + benchmarks) + gate/packs/fallback in collapsibles; Overview = hero (66px recovered ₹ with gold glow, at-risk, rate) + AT RISK→DECIDE→EXECUTE→RECOVER pipeline strip + honest baseline bars with meanings + timing-histogram insight (real replay evidence, direction-agnostic copy) + compliance; CaseDetail = four layers as questions (How likely? / Allowed? / Worth it? / Did we do it?); Knowledge = 5 domains + two worked questions (engine check + cited retrieval), no chunk-count headline; Audit = TIME/EVENT/ACTION/RESULT/COMPLIANT with payloads behind expandable rows; baselines replay now emits recovered_by_class + timing histograms; 120s TTL cache; visual system = dark luminous (midnight #0A111A, teal #17B896, gold #E8B75C, thin luminous borders, 2 static radial ambient glows, nav active glow, money text-shadow, ambient day/dim set once at load, prefers-reduced-motion kills all motion); dark favicon; fresh 26-case cohort via run_batch + real webhooks (8 STOPPED/8 moving/6 RECOVERED/4 ESCALATED, 0 violations).
**PG recovery this session:** snapshot restore dropped global/pg_filenode.map + WAL segments → repaired via fresh-initdb map copy + pg_resetwal (cluster rolled back to an earlier consistent on-disk point; no schema damage).
Status: **closed** (sweep 74/74 incl. 35 viewport checks, 0 console errors; pytest 142/142; verify script 17/17).


## D-035 · Final IA correction (page-value audit → nav cleanup, Outcomes labels, ambient control)
Inputs: evaluator judged UI still exposing implementation detail as product; demanded page-by-page value audit before edits, removal of the EVIDENCE nav label, System & Trust reduction, precise Outcomes labels, ambient under user control.
**Audit outcome (full table in IA_CORRECTION_REPORT.md):** all six pages kept — each answers a distinct evaluator question; nothing failed all four keep-tests. Nav: EVIDENCE group label REMOVED (organizing label, not a destination); Audit Trail + System & Trust restyled as quiet secondary items (.navlink.sub).
**Changes:** Outcomes — light-theme leftover row bg (#F0F7F4 → .rd-row gold-tint-on-dark; the reported unreadable row), precise labels everywhere (Recovered cases / Recovered ₹ / Recovery rate / Attempts / Contacts / Time to recover; class table counts-only, rail table money-only), RD row readable + leads-chip logic; Cases — internal policy-id column removed, budget meters kept; System & Trust — migration listing removed (developer diagnostics; /health retains it), "How the decision engine works" 4-step strip added above model block (Prediction → Constraints → EV → Execution); Knowledge — card titles now state the two knowledge kinds exactly ("what the system is allowed to do" / "why the practices exist"); ambient day/dim moved from hour-based to user control (toggle in sidebar, localStorage, prefers-color-scheme default, set pre-paint in index.html, never shifts mid-session); --ink-3 bumped #74889A→#7F94A7 (table headers 4.38→~4.9 on elevated surfaces); .tbl th/.eyebrow → 11px, card h3 → 12px floors.
Status: **closed** (sweep 78/78 incl. new IA checks; pytest 142/142; verify_model_runtime 19/19; environment revived after turn boundary: PG + pip + npm + browsers).
