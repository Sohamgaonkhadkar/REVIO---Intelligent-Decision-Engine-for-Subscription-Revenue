# RecoveryDesk

Failed-payment recovery orchestration for subscription businesses. When a recurring
debit bounces (UPI Autopay / card SI), RecoveryDesk opens a case, runs a **constrained
decision pipeline** (deterministic rules → ML propensity → expected-value economics),
executes the chosen recovery action through adapter boundaries, and journals every
step as append-only evidence — with a live operations UI on top.

**Everything in this repository runs against a simulated world (`env=sim`).**
See [§22 SIM vs real-world evidence](#22-sim-vs-real-world-evidence-disclaimer)
before quoting any number.

This README covers the whole project: the research and data strategy it is built
from (§1–§5), the implemented system (§6–§11), how to run and deploy it
(§12–§19), and every significant issue encountered along the way (§20).

---

## 0. Document map — sources of truth

Authority order (per the master prompt): **PHASE_4 > Phase_3C contract /
Model_Training > PHASE_1/2/3A/3B / DATASET_BUILD_REPORT**; conflicts are resolved
in `DECISIONS.md` — never silently.

| Document (in `/home/user/uploads/`) | What it governs |
|---|---|
| `PHASE_1_PROBLEM_AND_SOLUTION_RESEARCH.md` | the problem, the product definition, the evaluation objective |
| `PHASE_2_DATA_AND_INTELLIGENCE_STRATEGY.md` | intelligence strategy; baseline set B0/B1/B2 (§14) and the honest-reporting rule (§15) |
| `PHASE_3A_DATA_FOUNDATION_AND_SIMULATOR_BLUEPRINT.md` | data foundation + simulator mechanics (balance gates, response hazards, contact windows) |
| `PHASE_3B_DATASET_IMPLEMENTATION_PLAN.md` | dataset construction plan |
| `DATASET_BUILD_REPORT.md` | what was actually built/measured in the dataset (incl. label-signal sanity used by fallback priors) |
| `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` | exploratory findings that shaped features |
| `PHASE_3C3_FEATURE_ENGINEERING_AND_CLEANING.md` | feature engineering & cleaning rules |
| `PHASE_3C_ML_DATA_CONTRACT_AND_PHASE_C_PLAN.md` | the ML data contract; dataset roles; runtime retrieval roles; latent/counterfactual prohibitions |
| `Phase_3C_Model_Training.md` | model family, tuning, split discipline |
| `MODEL_QUALITY_EVALUATOR_DEFENSE.md` | how model quality is defended to evaluators (gates, honesty) |
| `PHASE_4_DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_FINAL_FIXED.md` | deployment architecture, invariants, knowledge/RAG §16, agent boundary §17 |
| `IMPLEMENTATION_PROMPT_FINAL_ARENA_REVISED.md` | the implementation brief |

Repo documents: `DECISIONS.md` (D-001…D-035 — every divergence and why) ·
`IMPLEMENTATION_PLAN.md` · `EVALUATOR_WALKTHROUGH.md` (click-by-click demo) ·
`NEXT_TASK_ANTIGRAVITY_RUNTIME_DATA_RETRIEVAL.md` (handoff spec for the next task) ·
`FINAL_PASS_REPORT.md`, `IA_CORRECTION_REPORT.md`, `REDESIGN_SELF_CRITIQUE.md`
(product-quality audit trail).

ML artifacts (authoritative, sha256-registered): `xgboost_native_categorical_c5.json`
(model), `native_categorical_schema.json` (transport of the canonical schema),
`best_params.json`, `optuna_trials.csv`, `native_categorical_metrics.csv`.

## 1. The problem (Phase 1)

Subscription businesses in India lose revenue to failed recurring payments —
insufficient funds around salary windows, mandate pauses/closures, bank technical
failures, card expiry/loss. RecoveryDesk turns each failure into a **recovery
case** and decides:

- **when** to act (legal time windows W08–W21 IST),
- **what** to do (retry / reminder / payment link / mandate update / wait / stop /
  escalate) and **through which channel**,
- under hard compliance: NPCI-style retry budget (1+3 per case), contact cap
  (2 per case), quiet hours 21:00–08:00 IST, ₹15,000 amount cap, opt-out honored
  immediately.

The evaluation objective (Phase 1, restated in Phase 2 §14): **measured recovered ₹**
plus recovery behaviour, compliance, explainability and auditability — never gross
recovery at any cost.

## 2. Intelligence strategy & the honest baseline set (Phase 2)

- The headline comparison is **RecoveryDesk vs B1 (PSP-default retries)** — the
  incumbent behaviour; the secondary comparison is **vs B2 (static doctrine)**.
- **We can lose and must publish losing** (Phase 2 §15). The UI therefore shows
  the baseline table in whichever direction the live numbers point, including the
  timing evidence for *why* the leader wins (see §9).
- All strategy artifacts (feature contract, rule packs, costs, fallback priors)
  are versioned, hashed and journaled with every decision.

## 3. Data foundation & the simulator (Phase 3A/3B + DATASET_BUILD_REPORT)

The world is a **documented reimplementation** of the Phase-3A simulator mechanics
(`sim/world.py` + `sim/latent.py`) — it is **not** claimed to be `recoverysim
v0.3`, and no dataset is fabricated:

- **Latent customers** (salary day, reliability, responsiveness, intent archetype)
  live in the sealed `sim_zone` schema — core code never reads them; only the
  simulator uses them to answer attempts/contacts. Baseline replay (§9) is the one
  sanctioned counterfactual reader, for evaluation only.
- Mechanics implemented per the blueprint: balance sufficiency on a 28-day payroll
  cycle, gate chain (MANDATE_PAUSED → BANK_TECHNICAL → INSUFFICIENT_FUNDS →
  jitter-fail → success), contact-response hazards with fatigue, self-pay path,
  urgency decay.
- Dataset roles follow Phase 3C exactly: `ml_datamart` (training/eval only),
  `case_outcomes` (KPI/batch eval only), `latent` sidecar (sealed),
  `counterfactuals` (eval-only). Reference documents never enter ML training
  (CI-enforced separation).

## 4. Feature engineering & the ML data contract (Phase 3C3 + Phase 3C)

- The runtime feature contract is `configs/registry/feature_contract_v3.yaml`:
  **32 features = 12 categorical + 20 numeric**, exact names and order.
- Categorical semantics use the artifact's vocabulary with `__UNKNOWN__`
  fail-closed encoding (D-021/D-022); retry candidates carry `channel=__UNKNOWN__`
  by design.
- **The measured artifact contract is authoritative (32/12/20).** The older
  documented 43/17/26 figure is a recorded discrepancy (D-019) — the artifact was
  never altered to match documentation; documentation lost.
- Feature rows are built by one shared builder (`core/features/`), validated
  against the contract before scoring; out-of-order or mismatched rows are
  refused, never coerced.

## 5. Model: training, artifact, and quality defense (Phase 3C + evaluator defense)

- **Model**: XGBoost **native categorical** (`c5`), stored as native Booster JSON
  (`xgboost_native_categorical_c5.json`, 25.4 MB, sha256 `9434606c…96ba`) — loaded
  via `xgboost.Booster`, never pickled. 1,256 trees, `binary:logistic`, 32
  features of which 12 are `"c"`-typed — matching the schema exactly.
- **Training discipline** (from the training doc + `best_params.json`/trials):
  C4 **case-grouped** split (110,385 / 23,471 / 23,567 train/valid/test), 5-fold
  StratifiedGroupKFold by case, Optuna-tuned. Measured benchmarks (from the
  artifact report CSV, never retyped): PR-AUC ≈ 0.9365 train / test 0.8313,
  ROC-AUC ≈ 0.978 train — **on the synthetic simulator split, not production
  performance**.
- **Calibration honesty**: no calibration artifact exists ⇒ every surface reports
  `uncalibrated`. Never fabricated.
- **Activation gate** (`core/scoring/gate.py`, 16 checks): schema shape, feature
  names/order, categorical columns, vocabularies, sha256 of every registered
  file, training domain, calibration policy. Any failure ⇒ scorer refuses to
  activate ⇒ **doctrine-fallback priors** (registered, data-derived from the
  dataset-build label sanity) and every decision is stamped
  `scorer_mode=fallback`. Constraints never depend on the model.
- **Runtime proof**: `scripts/verify_model_runtime.py` (§10) proves the supplied
  artifact is the live scorer — not a manifest label.

## 6. System architecture (Phase 4)

```
                    ┌─────────────────────────────── SIM WORLD ───────────────────────┐
                    │  sim/world.py (Phase-3A mechanics)   sim/latent.py (sim_zone,   │
                    │  sealed schema)   adapters/payments/sim_rail   adapters/notify  │
                    └───────────────▲───────────────────────────────▲─────────────────┘
                                    │ AttemptResult / DeliveryResult│ contact responses
┌──────────────┐   POST webhook   ┌─┴──────────────┐  intents  ┌────┴──────────┐
│ PSP / world  ├─────────────────►│  ORCHESTRATOR  │──────────►│   GATEWAY     │
└──────────────┘  psp_event_inbox │ core/          │ re-verify │ core/         │
                                 │ orchestrator/  │ verdict   │ gateway/      │
   ┌────────────┐   claim_due     │ repo, loop     │ hash +    └──────┬────────┘
   │ SCHEDULER  │◄────────────────┤ wake_case      │ fresh legality   │
   │ core/      │ SKIP LOCKED     └───────┬────────┘                  │ outcomes
   │ scheduler/ │ leases, parking         │ snapshots                ▼
   └────────────┘ kill-scope       ┌───────┴─────────┐        payment_attempts,
                    ▲              │ DECISION        │        recovery_events
                    │ wakes        │ core/decision/  │        (append-only)
                    │              │ candidates →    │
   ┌────────────────┴───┐          │ constraints →   │
   │ scheduled_actions  │          │ features(32) →  │
   └────────────────────┘          │ XGBoost p̂ → EV │
                                   └───────┬─────────┘
                                           │ decision_records
        ┌────────────── PostgreSQL 16 + pgvector (authoritative store) ──────────┐
        │ cases · events(journal) · decisions · intents · outbox · kill_flags    │
        │ monitoring_series · knowledge.sources/chunks (RAG, separated) · sim_zone│
        └──────────────────────────────────┬─────────────────────────────────────┘
                                           │ SQL only — every number queried live
                    ┌──────────────────────┴──────────────────┐
                    │ FastAPI (apps/api) — 20 paths + SPA      │
                    └──────────────────────┬──────────────────┘
                    ┌──────────────────────┴──────────────────┐
                    │ React/TS SPA (apps/web) typed SDK from   │
                    │ OpenAPI, TanStack Query polling, SIM     │
                    │ badge on every screen                    │
                    └─────────────────────────────────────────┘
```

Key invariants (all tested):

- **PostgreSQL is the single source of truth**; the UI never computes domain numbers.
- **Append-only journal** (`recovery_events`): per-case total order (`case_seq`
  under the case row lock), immutable.
- **Verdict re-verification**: the gateway rebuilds the constraint verdict at the
  decision instant (`decided_at`) with *current* state — state drift blocks; pure
  clock drift never does — plus a fresh time-legality check at execution time.
- **FSM is frozen** (15 edges); RECOVERED/STOPPED are absorbing.
- **Artifact gate** before any score is trusted (§5); fallback is loud, never silent.
- **ML / RAG separation**: knowledge retrieval and model features share nothing.

## 7. The decision pipeline (runtime)

One decision cycle, in order — the same story the Case Detail page tells:

```
payment failed → case → legal options → ML recovery probability → expected value
→ best permitted action → execution → outcome → re-plan → recovered/stopped/escalated
```

1. **Constraints first** (`core/constraints/engine.py`, pure): the compiled rule
   pack decides what is *legal* (budgets, mandate status, class gating, windows,
   quiet hours, cooldown, cap, kill scopes). Illegal candidates never reach the model.
2. **Prediction** (`core/scoring/`): the XGBoost scorer produces p̂ for legal
   candidates only (or doctrine priors in fallback, flagged).
3. **Economics** (`core/decision/ev.py`): EV = p̂ × recoverable ₹ − action/channel/
   fatigue costs − retry shadow price. Highest EV wins; ties break deterministically.
4. **Execution** (`core/gateway/`): verdict-hash re-verification + fresh legality
   → adapter dispatch → outcome fold into the journal.
5. **Re-plan**: outcomes schedule the next wake (`scheduled_actions`, SKIP LOCKED
   leases) until the case reaches RECOVERED / STOPPED / ESCALATED.

## 8. Knowledge & rules (Phase 4 §16)

- **Executable rule packs** (authoritative): compiled, hash-stamped, journaled
  per decision. Read-only live checker at `GET /api/constraints/check?case_id=`
  ("can this case act right now?" — the real engine, no side effects).
- **Reference corpus** (advisory): 12 project documents → 762 chunks, pgvector
  cosine retrieval with citations, deterministic lexical embedder
  (`hashed-lexical-v1` — identity always stated; a neural embedder exceeded
  sandbox RAM). No document can permit what the pack denies.
- No LLM/chatbot anywhere: the Ops Copilot surface was **removed from the UI**
  (D-034/035); the backend flag gate remains for a future opt-in.

## 9. Evaluation & baselines (Phase 2 §14/§15, implemented D-032)

`core/evaluation/baselines.py` computes B0/B1/B2 against the **live case
population** by seeded Monte-Carlo replay (48 draws/case/baseline) through the
same documented simulator gates — labelled *"evaluation estimate inside the SIM —
not a real-world claim"*. The payload also carries per-class recovered ₹ and
recovery-timing histograms, which the UI uses to explain *why* the leader wins
(e.g. doctrine's salary-window waits vs RecoveryDesk's early recoveries).
`GET /api/baselines` caches for 120 s (the replay is deterministic per
population). Losing comparisons ship on the front page by design.

## 10. Runtime model verification

`python3 scripts/verify_model_runtime.py` — 19 checks in the real runtime:
artifact path (app resolver) → exists → independent SHA-256 → independent Booster
load → 16/16 activation gate → contract order match → categorical config → live
inference on a real case → **independent-prediction parity (max |Δp̂| = 0)** →
p̂ in the decision atom → EV arithmetic re-verified across journaled atoms →
journal carries the true model id; plus the failure path (tampered schema /
missing artifact ⇒ gate fails ⇒ flagged doctrine fallback; constraints still
deny). Report: `artifacts/reports/model_runtime_verification.md`. The production
artifact is never touched.

## 11. The product (UI)

Six destinations, business-first (`Overview · Recovery Cases · Outcomes ·
Knowledge & Rules`, then quiet `Audit Trail · System & Trust`):

- **Overview** — hero: ₹ recovered (gold-lit) from ₹ at risk; `AT RISK → DECIDE →
  EXECUTE → RECOVER` engine strip; honest baseline bars + timing insight;
  compliance chip; live activity.
- **Recovery Cases** — a queue of rupee opportunities with human failure language
  and budget meters (no internal policy ids).
- **Case Detail** (the hero page) — money-first header + budget ledger; 9-step
  recovery journey (each step one fact); the decision in four layers phrased as
  questions (*How likely? Are we allowed? Is it worth doing? Did we do it?*);
  chosen-action spotlight; "what the system refused to do"; deterministic trace
  collapsed.
- **Outcomes** — Recovered ₹ / Recovered cases / Recovery rate / Attempts /
  Contacts / Time to recover; by failure reason (counts) and rail (money);
  stop reasons; the full honest baseline table.
- **Knowledge & Rules** — the two knowledge kinds and two worked questions
  (engine check + cited retrieval).
- **Audit Trail** — TIME · EVENT · ACTION · RESULT · COMPLIANT, payloads behind
  expandable evidence.
- **System & Trust** — six trust cells (model/schema/rule packs/environment/
  compliance/database), "how the decision engine works", technical evidence in
  collapsibles.

Design system: dark luminous fintech (midnight `#0A111A`, teal `#17B896`, money
gold `#E8B75C`), ambient glows set once at load (user-controllable, respects
`prefers-color-scheme`), `prefers-reduced-motion` honored, WCAG-checked contrast,
no horizontal overflow from 1440px down to 390px. Click-by-click tour:
`EVALUATOR_WALKTHROUGH.md`.

## 12. Prerequisites

| Tool | Version used | Needed for |
|---|---|---|
| Python | 3.12+ (developed on 3.13) | everything server-side |
| PostgreSQL | 16 with the `pgvector` extension | authoritative store |
| Node.js + npm | 20.x | frontend build / SDK generation |
| Docker + compose | any recent | deployment (§14) — optional locally |
| Playwright (chromium) | 1.49.x | `scripts/ui_sweep.mjs` only |

Python packages: `sqlalchemy psycopg[binary] pydantic pyyaml xgboost numpy fastapi uvicorn httpx pytest`.

## 13. Local setup (without Docker)

```bash
# 1. database (any PG16 + pgvector; roles handled by bootstrap)
createdb recoverydesk
export DATABASE_URL="postgresql+psycopg://<user>@127.0.0.1:5432/recoverydesk"

# 2. python env
pip install sqlalchemy "psycopg[binary]" pydantic pyyaml xgboost numpy \
            fastapi uvicorn httpx pytest

# 3. schema + rule packs (idempotent, applies all migrations)
python -m db.bootstrap

# 4. frontend (build once)
cd apps/web
npm install
npm run generate:sdk      # typed client from apps/api/openapi.json
npm run build             # outputs apps/web/spa (served by FastAPI)
cd ../..

# 5. run
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000   # API + UI at :8000
python -m apps.workers.loop                                        # continuous SIM worker (optional)
```

> **Arena-sandbox note:** the sandbox cannot run Docker and wipes `/tmp`, pip
> packages, node_modules and browser caches between sessions. `bash
> tools/pg_up.sh` restores/repairs the local PG cluster (downloads portable
> PG16.9, rebuilds pgvector, recreates directories the snapshot drops); then
> re-run `pip install …`, `npm install` and the steps above. If a snapshot
> restore ever leaves the cluster half-written (`pg_filenode.map` missing, WAL
> panics), the recorded recovery is: copy `global/pg_filenode.map` from a fresh
> `initdb`, then `pg_resetwal -D /home/user/pgdata -f` (D-034) — the cluster may
> roll back to an earlier consistent point; re-seed the demo afterwards.

## 14. Environment variables

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://rd_owner@127.0.0.1:5432/recoverydesk` | `db/engine.py` | authoritative PG DSN |
| `RD_ENV` | `sim` | API | environment badge served on every payload |
| `RD_OPS_KEY` | `rd-ops-dev` | API | value required in `X-Ops-Key` for `/api/ops/*` |
| `RD_SIM_SCALE` | `120` | worker | SIM-clock speed (sim-seconds per real second) |
| `POSTGRES_PASSWORD` | — (required) | compose | DB password |
| `APP_ENV` | `sim` | compose | environment label |
| `RUNTIME_ROLE` | `core` / `ops` | compose | same image, two roles |
| `COPILOT_ENABLED` | `false` | compose | legacy flag gate (UI surface removed; stays off) |
| `COPILOT_LLM_API_KEY` | unset | compose | optional; **no key supplied** |
| `RD_MODEL_JSON` | `/home/user/uploads/xgboost_native_categorical_c5.json` | compose | host path of the model artifact to mount read-only |

## 15. Docker Compose deployment

```bash
cp deploy/envs/dev.env.example deploy/envs/dev.env   # set POSTGRES_PASSWORD
docker compose --env-file deploy/envs/dev.env up --build
```

Services (verified at config level by `tests/test_deploy_config.py`):

| Service | Image/Build | Role | Port |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | authoritative store (+ healthcheck) | 5432 |
| `api` | repo image | bootstrap + FastAPI (`RUNTIME_ROLE=core`) | 8000 |
| `ops` | repo image | bootstrap + `python -m apps.workers.loop` (`RUNTIME_ROLE=ops`) | — |
| `web` | `nginx:1.27-alpine` | serves `apps/web/spa`, proxies `/api` → `api:8000` | 8080 |

> The sandbox has no Docker daemon — topology, commands, mounts, module
> importability, nginx SPA routing and env requirements are verified
> **statically** (8 tests). Running `docker compose up` on a Docker host is the
> only manual step.

## 16. Database & migrations

- `db/migrations/0001…0006` (init/schema + FSM/checks · sim_zone · case counters ·
  intent `decided_at` · intent `candidate_id` · knowledge/RAG store).
- Applied by `python -m db.bootstrap` — **idempotent** (`IF NOT EXISTS`), records
  applied files, seeds hashed rule packs (upi/card) and the frozen FSM/config
  registries. `db/roles.sql` defines the `rd_app`/`rd_ops` privilege split;
  `sim_zone` and `knowledge` stay privilege-separated.
- `GET /health` reports `schema_versions` (applied migrations) and DB status —
  the UI surfaces this as "Database healthy" only.
- Wiping a demo run (safe, schema preserved):
  `python -c "from db.reset_demo import wipe_operational; from db.engine import *; wipe_operational(make_sessionmaker(make_engine()))"`.

## 17. ML artifact placement & integrity

The scorer loads from paths in `configs/registry/model_artifacts.yaml`:

- **model** → `artifacts/models/c5/xgboost_native_categorical_c5.json`. If the
  repo-relative file is absent, the loader falls back to
  `<repo>/../uploads/<basename>` so a single copy suffices (D-026/D-029).
  Compose mounts it read-only (`RD_MODEL_JSON`).
- **schema / metrics / params / trials** → `artifacts/reports/c5_xgb_native_categorical/…`
- Integrity: sha256 of every registered file against `artifacts/MANIFEST.sha256`
  (model `9434606c…96ba`). The schema JSON is a **transport** of the canonical
  joblib (provenance recorded in the manifest); the measured 32/12/20 contract is
  authoritative (D-019). Mismatch ⇒ gate fails ⇒ doctrine fallback.
- **Calibration**: no artifact exists ⇒ `calibration_version=null`, reported as
  `uncalibrated` everywhere. Never fabricated.

## 18. API reference (20 paths — live OpenAPI at `/docs`)

| Method & path | Purpose |
|---|---|
| `GET /health` | db, schema versions, scorer mode + env badge |
| `GET /api/cases` | case list (`state`,`rail`,`limit`,`offset`) |
| `GET /api/cases/{id}` | case detail: state, counters, subscription, attempts, timeline |
| `GET /api/cases/{id}/decisions` | decision records incl. per-candidate atoms |
| `GET /api/cases/{id}/decisions/{did}/explain` | deterministic explanation (stored atoms only) |
| `GET /api/cases/{id}/events` | per-case append-only journal |
| `GET /api/cases/{id}/intents` | execution intents with verdict hashes + idem keys |
| `POST /api/webhooks/psp/payment_failed` | idempotent failure ingest (dedup by `dedup_key`) |
| `GET /api/model` | scorer mode, gate checks, feature contract, calibration truth, benchmarks |
| `GET /api/constraints` | hashed rule packs, budgets, windows, costs |
| `GET /api/constraints/check?case_id=` | real constraint engine, read-only ("can this case act now?") |
| `GET /api/outcomes` | recovered ₹/cases, rates, by-class/by-rail, budgets, compliance |
| `GET /api/baselines` | B0/B1/B2 vs RecoveryDesk (replay + timing/class evidence; 120 s cache) |
| `GET /api/events` | global journal tail (audit view) |
| `GET /api/knowledge` | corpus status (sources, chunks, embedder identity) |
| `GET /api/knowledge/search?q=` | deterministic pgvector cosine retrieval w/ citations |
| `POST /api/ops/cases/{id}/wake` | manual wake (**`X-Ops-Key`**; 409 if terminal) |
| `POST /api/ops/kill-switch` | fire (global/merchant/rail/rule_pack/case) (**`X-Ops-Key`**) |
| `POST /api/ops/kill-switch/resume` | resume a flag (**`X-Ops-Key`**) |
| `GET /api/ops/kill-switch` | fired flags (**`X-Ops-Key`**) |
| `GET /api/audit/scopes` | kill-flag history + monitoring counters (**`X-Ops-Key`**) |

*(21 rows: `/api/ops/kill-switch` has both GET and POST in one path.)*

## 19. Running the simulator, demo & verification

```bash
# one-shot batch: seed failures → run the real loop to quiescence → summary
python scripts/run_batch.py --cases 40 --steps 200 --fresh --scale 600

# continuous: keep the world moving under the polling UI
python -m apps.workers.loop            # RD_SIM_SCALE=120 by default

# inject fresh failures via the real API (needs an existing subscription_id)
curl -s -X POST localhost:8000/api/webhooks/psp/payment_failed \
  -H 'Content-Type: application/json' \
  -d '{"provider":"simrail","dedup_key":"demo-42","subscription_id":"sub_demo_…",
       "amount_inr":299,"failure_class":"INSUFFICIENT_FUNDS","reason_code":"SIM_IF"}'
```

Verification playbook:

1. `curl :8000/health` → `db=up`, `scorer.mode=ACTIVE`, `env=sim`.
2. Start the worker; inject a cohort; poll `GET /api/outcomes` twice ~30 s apart —
   `cases_by_state` and `recovered_inr` move.
3. Follow one case: `GET /api/cases?state=RECOVERED` → `GET /api/cases/{id}/events`
   shows `payment_failed → decision_made → … → case_recovered`.
4. Cross-check: `recovered_inr` == `SELECT sum(amount_at_risk) FROM recovery_cases
   WHERE state='RECOVERED'`.
5. Compliance sweep (printed by `run_batch.py`): retries ≤ 1+3, contacts ≤ 2,
   zero post-terminal interventions.

```bash
python -m pytest tests                      # full battery (142 tests, live PG)
python -m pytest tests/test_loop_pg.py      # orchestrator/gateway/scheduler E2E
python -m pytest tests/test_api_pg.py       # API contract matrix
python -m pytest tests/test_knowledge_pg.py # RAG + deterministic explain
python -m pytest tests/test_deploy_config.py# compose topology checks (8)
node scripts/ui_sweep.mjs                   # Playwright: API↔UI parity, honest copy,
                                            #   nav shape, 5-viewport overflow, 0 errors
python3 scripts/verify_model_runtime.py     # runtime artifact proof (§10)
```

All tests run against the real PostgreSQL instance (no mocks of domain logic).
**Stop the loop worker before `pytest tests/`** — loop tests create demo cases in
the same database a live worker polls, and a running worker races them (D-033).
The suite is deterministic otherwise (decision time is pinned in fixtures).

## 20. Issues encountered & resolutions (engineering log)

Full log with reasoning: `DECISIONS.md` (D-001…D-035). The significant ones:

**Data / model**
- **D-019 — documented vs measured contract mismatch** (43/17/26 vs 32/12/20):
  measured artifact declared authoritative; docs recorded as wrong; gate blocks
  on any mismatch instead of coercing.
- **D-021/D-022 — categorical semantics**: retry candidates encode
  `channel=__UNKNOWN__`; vocab indexing is fail-closed on unseen categories.
- **D-026/D-029 — artifact paths**: repo-relative registry with `uploads/`
  fallback so one copy serves dev + compose; model mounted read-only.

**Runtime / correctness**
- **D-030 — first-decision gap**: webhook-opened cases sat in CASE_CREATED
  because batch runs had always woken them manually; ingest now schedules
  `WAKE_NEW_CASE` (idempotent under dedup).
- **Verdict re-verification semantics**: gateway rebuilds the verdict at decision
  time with current state — state drift blocks execution, clock drift never does.
- **D-033 — two latent test hazards**: a scoring test used real wall-clock
  (failed only during IST quiet hours — now pins `now_utc`); the worker-vs-pytest
  race (now documented: stop the worker before the suite).

**Product / UI**
- **D-031 — CaseDetail TDZ crash** blanked the hero page while API tests stayed
  green; fixed + route-level ErrorBoundary; WCAG contrast, mobile overflow and
  tap-target fixes from a numeric DOM audit.
- **D-032 — evaluator-journey redesign**: nav 8→6; Copilot/Dashboard/Model pages
  removed; baselines replay (§9) added; honest-loss chips shipped.
- **D-034 — final product pass**: runtime model proof (§10); luminous dark theme;
  `/health` bug (queried a non-existent `migrations` table, silently reported 0 —
  now `schema_migrations`); Copilot remnants removed from API/CSS.
- **D-035 — IA correction**: page-value audit before edits; EVIDENCE nav label
  removed; light-theme leftover row background fixed (unreadable RecoveryDesk row);
  precise outcome labels; ambient under user control.

**Operational (sandbox)**
- **PG snapshot restores are destructive**: twice the cluster lost
  `global/pg_filenode.map` and WAL segments. Recorded recovery: fresh-initdb map
  copy + `pg_resetwal` (§13 note); torn rows afterwards (a kill flag both fired
  *and* resumed; a case whose `last_case_seq` reset below its journal max) were
  repaired via the ops API / a counter resync.
- **Session boundaries wipe runtime state** (pip, node_modules, Playwright
  browsers, processes). Revival is scripted and takes ~2 minutes.
- **RAM ceiling (2 GB)**: three Python processes (API + worker + verification)
  can thrash; run heavyweight verification with the worker stopped. The neural
  embedder was dropped for the lexical one (D-027) for the same reason.

## 21. Known limitations

- **No Docker in the sandbox** — compose verified statically; `up` needs a host.
- **RAG embedder is lexical** (`hashed-lexical-v1`) — pipeline real, identity
  always stated, never implied to be neural.
- **Simulator is a reimplementation** — never claimed to be `recoverysim v0.3`;
  no dataset fabricated.
- **Uncalibrated model** — reported as-is everywhere.
- Baselines are **evaluation estimates inside the SIM** (Monte-Carlo replay), not
  real-world claims; the methodology string ships in every surface that shows them.

## 22. SIM vs real-world evidence disclaimer

**All case data, recovery rates, and ₹ outcomes shown by this system come from a
simulated world (`env=sim`) with synthetic customers.** The propensity model was
trained on simulated recovery outcomes. Nothing here is evidence of real-world
recovery performance; the numbers demonstrate the *machinery* (decision quality,
constraint enforcement, auditability), not market results. Every screen carries
the persistent `SIM · SIMULATED EVIDENCE` badge, every API payload carries `env=sim`.

## 23. Repo map

`core/` (orchestrator · gateway · scheduler · decision · constraints · features ·
scoring · fsm · journal · knowledge · config · clock · evaluation · testing) ·
`adapters/` (payments · notify) · `sim/` (world · rng · latent) · `apps/`
(api · web · workers) · `db/` (migrations · engine · bootstrap · roles ·
reset_demo) · `scripts/` (run_batch · ingest_knowledge · gen_feature_contract ·
verify_model_runtime · ui_sweep) · `deploy/` (compose · Dockerfile · nginx ·
envs) · `configs/` (registry · costs) · `artifacts/` (MANIFEST.sha256 · reports)
· `tests/` (142) · `DECISIONS.md` (D-001…D-035) · `IMPLEMENTATION_PLAN.md` ·
`EVALUATOR_WALKTHROUGH.md` · `NEXT_TASK_ANTIGRAVITY_RUNTIME_DATA_RETRIEVAL.md`.
