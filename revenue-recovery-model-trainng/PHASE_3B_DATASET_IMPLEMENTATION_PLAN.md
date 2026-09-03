# PHASE 3B — DATASET & SIMULATOR IMPLEMENTATION PLAN

**Track 03 — AI Revenue Recovery | Failed recurring payments (UPI AutoPay + card e-mandates)**
*Converts the approved Phase 3A blueprint into an executable, milestone-by-milestone build plan for the data-generation layer. No simulator code is written here; interfaces and decisions are specified so implementation cannot drift. Inherits: 3A canonical schema (7 tables + 3 sealed sidecars), 7-state case machine, 8-class failure taxonomy, 7-action space, §8 outcome mechanism, anti-circularity controls (plausibility gates, sealed sidecars), baselines B0–B3, volume targets (~20K customers → ~26K cases).*

---

# 0. Engineering Philosophy (governs everything below)

1. **Single-process, batch-first.** No services, no databases, no network calls in Phase 3B. One package, YAML configs, Parquet in/out.
2. **Config before code.** No magic numbers in `.py` files; behavioral numbers never live outside the assumption registry.
3. **Determinism by construction.** One RNG library (NumPy `Generator`), spawnable seed streams, sorted writes, double-run hash tests.
4. **Validation is part of the build, not a phase after.** Invariants run on every simulation milestone from 100 rows upward; a red invariant halts the pipeline.
5. **Small trash early.** Milestones are designed so the hardest bugs (state machine, leakage, outcome semantics) are discovered at 100-customer scale.

---

# 1. Part 1 — Repository Structure

The proposed skeleton from the brief is directionally right (separating data/configs/src/tests/docs). Critical evaluation: `recovery/` + `world/` split is ambiguous (world *is* recovery context); `payments/` mixing charge-execution with failure generation risks coupling; we need an explicit `constraints/` home since the constraint engine is the trust core. Adopted structure:

```
revenuerecovery/
├── pyproject.toml                  # pinned deps, package metadata
├── Makefile                        # setup, test, lint, sim-smoke, sim-full, freeze
├── README.md
├── configs/
│   ├── simulation.yaml             # scale, seeds, paths, horizons  (technical knobs)
│   ├── policies.yaml               # baseline policy definitions
│   ├── costs.yaml                  # cost/fatigue parameters (with provenance tags)
│   └── registry/
│       ├── assumption_registry.yaml# the "why" — every behavioral parameter, sourced
│       ├── scenario_regimes.yaml   # pessimistic / base / optimistic / adversarial
│       └── psp_code_map.yaml       # raw PSP codes → canonical failure_class
├── src/recoverysim/
│   ├── domain/        # enums (states, actions, failure classes, event types) + pydantic row schemas
│   ├── constraints/   # RulePack loader + ConstraintEngine (feasible-action calculator)
│   ├── registry/      # AssumptionRegistry loader/validator (pydantic) + scenario resolver
│   ├── world/         # latent processes: balances, salary calendar, bank outages, mandate lifecycle, intent
│   ├── population/    # customer/subscription generators (RR-calibrated)
│   ├── payments/      # renewal scheduler + attempt executor + failure injection (raw psp codes)
│   ├── recovery/      # CaseManager (FSM), DecisionLogger, ActionExecutor
│   ├── policies/      # Policy interface, B0,B1,B2,B3 (+B4 oracle evaluator, eval-only)
│   ├── events/        # EventBus/EventLog writer (append-only, batched parquet)
│   ├── datamart/      # snapshot feature builder (as-of), label builder, mart writer
│   ├── validation/    # invariant suite, anchor reconciliation, edge-case pack, plausibility gates
│   ├── simulation/    # EventScheduler (heapq), SimulationRunner, ExperimentHarness (paired runs)
│   └── cli.py         # single entrypoint (build | simulate | mart | validate | freeze)
├── data/
│   ├── reference/     # upi_transactions_2024.parquet (+ checksum, license note)
│   ├── registry_snap/ # copies of registry YAMLs as used per dataset build (provenance)
│   ├── generated/dataset_vX.Y/  # sealed sidecars separated by subfolder `sidecar/`
│   └── eval/          # experiment reports, validation reports (json+md)
├── tests/             # unit + invariant + leakage tests (pytest)
├── scripts/           # acquire_reference.py, profile_reference.py, run_simulation.py, build_mart.py
├── notebooks/         # EDA only; no logic that isn't also in src (rule enforced in review)
└── docs/
    ├── DATASET_CARD.md
    ├── DECISIONS.md            # running decision log
    ├── FAILURE_LOG.md          # what broke + fixes (feeds challenge criterion 4)
    └── CLAIM_TEMPLATE.md       # the only allowed phrasing for results (from Phase 2 §15)
```

**Why each exists:** `domain/` centralizes vocabularies so simulator/policies/validation share one truth; `constraints/` is separate so the trust layer has a single home and can be unit-tested to death; `registry/` separates *justified* parameters from config; `sidecar/` under `generated/` keeps sealed latent/counterfactual data physically distinct (supports the import-boundary test); `docs/FAILURE_LOG.md` starts day one (the company evaluates failure recovery). `services/`, `api/`, `infra/` are deliberately absent.

---

# 2. Part 2 — Technology Stack

**MUST HAVE**

| Library | Why we need it / problem it solves |
|---|---|
| Python 3.11+ | Language; `zoneinfo` stdlib for IST handling (no pytz) |
| **NumPy** | All randomness (`np.random.Generator`, PCG64) + vectorized population draws. Single-RNG discipline is a reproducibility requirement |
| **Polars** (+ pyarrow) | Event logs hit ~400K–1M rows × multiple runs; Polars gives speed, lazy evaluation, native Parquet, and **as-of joins** — which are exactly how leakage-safe snapshot features are built. Pandas is slower, memory-heavier, and its time semantics are easier to get wrong. Pandas allowed *only* inside notebooks for quick plots |
| **Pydantic v2** | Row/domain schemas and config/registry validation → fail-fast on malformed YAML/records; doubles as living documentation of the canonical model |
| **PyYAML** | Config + registry files need comments and anchors; JSON unsuitable for human-audited assumptions |
| **pytest** | Invariants and leakage tests are product features, not chores (the audit bar requires them) |
| **ruff** | Lint+format in one; zero-cost discipline |

**NICE TO HAVE**

| Library | Why (not mandatory) |
|---|---|
| DuckDB | Ad-hoc SQL over Parquet for validation/EDA slices without loading DataFrames; skip if Polars suffices |
| matplotlib (+seaborn) | Notebook EDA figures only (anchor checks, calibration priors); never in pipeline |
| pandera | Declarative DataFrame schema checks; **fallback if pydantic-per-row proves too slow at scale — decide at Milestone 1**, choose one |

**AVOID FOR NOW** (with reasons — these are the usual overengineering traps)

| Library | Why avoided |
|---|---|
| Faker | No PII needed — ids are ints; avoids fake-name creep and a needless dep |
| Great Expectations | Heavy framework for what is ~40 pytest assertions; adds infra burden it can never repay at this scale |
| Hydra | Composition power we'll never use; pydantic+YAML layering is enough and is debuggable |
| scikit-learn / LightGBM | Phase 3C. Installing ML libs during data-build invites premature training (forbidden by the plan) |
| MLflow / W&B | Run manifests (JSON) + dataset hashes cover Phase 3B tracking; revisit only if Phase 3C needs experiment tracking |
| SQLAlchemy/Postgres/SQLite | Parquet + event-log discipline replaces a DB at this scale; zero IO contention, trivially diffable |
| APScheduler/Celery | The simulation clock is a `heapq` event queue; real schedulers only matter for the Phase-4 sandbox actuation track |
| structlog/loguru | stdlib `logging` with JSON formatter is sufficient |

---

# 3. Part 3 — Data Acquisition Plan (minimal checklist)

| # | Source | Purpose | Used directly? | Expected output after inspection |
|---|---|---|---|---|
| 1 | **UPI Transactions 2024** ([Kaggle](https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset), CC0) | Calibration priors (§3A Part 2) | Yes — as numbers in registry entries tagged `source: upi_txn_2024_synthetic` | `reports/reference_upi_profile.json` + `reference_upi_profile.md` |
| 2 | Rule documentation (NPCI/RBI/PSP: Cashfree retry table, Razorpay halt semantics, Stripe India e-mandate notes) — links already collected across Phase 1–2 | Constraint engine rule pack; baseline B1 definitions | Yes — transcribed into `configs/registry/*.yaml` with citation strings | `rule_pack_v0` with per-rule `source` fields |
| 3 | Vendor doctrine tables (Finsi/Slicker recovery corridors) | B2 static mapping + world-model prior bands | Reference-only (never point values; bands + scenario multipliers) | Doctrine entries in `assumption_registry.yaml`, tag `provenance: vendor_doctrine` |

**Nothing else is downloaded.** The acquisition script must pin: source URL, retrieval date, license string, SHA-256 of the artifact.

**First EDA on the UPI dataset (mandatory, scripted not notebooked, so it's repeatable):**
1. schema print + dtype check vs the 17 documented columns (transaction id, timestamp, transaction type, merchant_category, amount (INR), transaction_status, sender/receiver_age_group, sender_state, sender_bank/receiver_bank, device_type, network_type, fraud_flag, hour_of_day, day_of_week, is_weekend);
2. null/blank counts per column; duplicate transaction-id count;
3. per-`merchant_category` amount quantiles (p5/25/50/75/95) — these become plan-amount priors (truncated ≤ ₹15K);
4. `sender_bank` frequency shares → bank weight vector;
5. `sender_state`, `sender_age_group` shares → population priors;
6. hourly activity histogram + weekend flag check (consistency: `is_weekend` vs `day_of_week`);
7. `transaction_status` overall rate — **recorded but explicitly NOT adopted** (no failure semantics; a line in the registry says so);
8. KS-test helper functions prepared for Milestone 12 anchor checks (our simulated amounts vs these category marginals).

---

# 4. Part 4 — Implementation Order (revised milestones)

Changes vs the brief's sequence: reference-data profiling moves **before** population (it feeds priors); the constraint engine is built **alongside** the state machine (a FSM without its guards invites retrofit bugs); audit logging moves **before** policies (you cannot validate policies without an audit trail); validation milestones interleave rather than batch at the end.

| Milestone | Objective | Modules | Input | Output | Validation | Completion criteria |
|---|---|---|---|---|---|---|
| **M0 Repo & reproducibility spine** | runnable skeleton; seed discipline | cli, simulation/scheduler stub, Makefile, pyproject | — | `cli.py smoke` runs | unit: scheduler ordering; RNG stream spawn determinism | identical double-run of a 10-event toy queue |
| **M1 Domain + schemas** | one vocabulary | domain/*, pydantic rows | 3A §3/§10 | row validators + transition table T_transitions | unit: enum coverage; invalid transition rejected | all 3A entities parse; transition table reviewed vs 3A §4 |
| **M2 Config + Assumption Registry** | zero magic numbers | registry/*, configs/* | registry YAMLs | validated `SimConfig`, `AssumptionSet`, scenario resolver | unit: missing `source` field on ASSUMED param ⇒ error | loading every YAML yields typed object; scenario multipliers apply |
| **M3 Reference acquisition + profiling** | priors exist | scripts/acquire&profile | UPI dataset | `reference_upi_profile.json`; registry entries | checks: hash pinned; columns match verified schema | priors in registry; status-rate rejection note present |
| **M4 Population generator** | customers/subscriptions | population/* | registry priors | `dim_customers`, `dim_subscriptions` + `sidecar/latent_state` | anchor: KS within tolerance (amounts, banks, states); referential | 3 rows-eyeball sample + tests green |
| **M5 World model** | latent dynamics | world/* | latent_state, calendar laws | `world_calendar` (outages, ambient notices) | unit: outage never overlaps itself; salary pulse monthly; balance non-neg guard documented | 12-month latent replay plausible by inspection plots (notebook) |
| **M6 Payments: renewal + first-failure injection** | realistic failure entry | payments/* | dims + world | renewal attempts + first-failure events w/ canonical classes | anchor: overall first-attempt failure within scenario band; mix sanity | failure-class distribution reviewed; invariants I-max per attempt fields |
| **M7 CaseManager FSM + ConstraintEngine** | legal lifecycle | recovery/*, constraints/* | events from M6, rule pack | state transitions + feasibility verdicts | invariant: I1,I2,I3,I4,I11 on hand-crafted cases | every (state,action) pair explicitly allowed/blocked in test table |
| **M8 Outcome/Action executor + hazards** | actions change the world | recovery/executor, world (hazards) | feasible actions | attempt/response outcomes, state updates | unit tests on §8 gates (paused⇒retry always fails etc.) | coverage of all 7 action paths incl. STOP/ESCALATE |
| **M9 Event & audit logging** | append-only truth | events/* | everything above | `recovery_events`, `action_log` | invariants I6,I7 + audit completeness (every action ↔ verdict ↔ outcome) | rebuild case timeline from events only ⇒ equals live state (replay test) |
| **M10 Baseline policies B0–B3** | comparators exist | policies/* | tool interface | policy runs logged | unit: B1 timing matches PSP proxy spec; B2 mapping matches doctrines yaml | policies touch only the public interface (boundary test) |
| **M11 Closed-loop smoke (100 customers)** | end-to-end | simulation/*, policies | M4–M10 | first full runs | full invariant suite + replay test per policy | B0..B3 all complete without exceptions |
| **M12 Validation suite formalized** | gates executable | validation/* | M11 outputs | `validation_report.json/md` | distribution anchors (bands), edge-case pack §3A-13D | G1+G2 pass on smoke scale; failures print readable diffs |
| **M13 Scale + freeze dataset_v1.0** | production-gen | scripts/run, manifest writer | registry + scenarios | sealed dataset (incl. sidecars), manifests | invariants + anchors + T9 double-run hash equality | G3 pass: frozen tree hashed; manifest complete |
| **M14 Datamart build + leakage tests** | ML-ready rows | datamart/* | frozen dataset | `ml_datamart.parquet` + leakage report | as-of timestamp proofs; import-boundary test; maturity gate; per-slice coverage counts | G4 pass + EDA note on doctrine signatures emerging from observables |
| **M15 Docs & claim templates** | reviewability | docs/* | reports | DATASET_CARD.md, DECISIONS.md, FAILURE_LOG.md updated | checklist review | publication-ready explanation of what every number means |

**Failure-recovery note:** every milestone that revealed a real bug gets a FAILURE_LOG.md entry (symptom → root cause → fix → regression test added). This is deliverable material, not housekeeping.

---

# 5. Part 5 — Progressive Simulation Strategy

| Stage | Scale | What must be true before scaling up | New risks exposed |
|---|---|---|---|
| SMOKE | 100 customers / 2 cycles / 1 seed | All invariants green; replay test passes; eyeball-level trace review (read 3 full case timelines end-to-end) | state machine, guard logic, event payload bugs |
| SLICE | 1,000 customers / 3 cycles / 1 seed | Anchor bands hold approximately; edge-case pack green; runtime/profile acceptable (< a few min) | distribution calibration, hazard plausibility, cost accounting |
| REGRESSION | 5,000 customers / 6 cycles / 3 seeds | Seed variance of key metrics documented (waarom: CI widths already computable); all policies compared once; no invariant red | seed sensitivity, policy divergence logic, memory profile |
| FULL | 20,000 customers / 12 cycles / N seeds × 4 regimes | Gates G1–G4 all pass on staged data; freeze ONLY after this | assumption-level issues (scenario bands), final anti-leak audit |

The full dataset is generated **only after** state transitions, audit logs, stopping rules, and recovery accounting are proven at smaller scales — per the brief, enforced via gate wiring in the Makefile (`sim-full` depends on `validate`).

---

# 6. Part 6 — Module Contracts

Format: Inputs → Outputs | Responsibilities | **MUST NOT**.

| Module | Contract |
|---|---|
| **PopulationGenerator** | registry priors → `dim_*` + latent sidecar | draws customers/subscriptions/mandates; stores latent params | **MUST NOT** read outputs of world/payments; **MUST NOT** put latent fields into `dim_*` |
| **WorldModel** (balances, salary calendar, outages, mandate lifecycle, intent, fatigue) | latent_state + clock → world events + queryable latent snapshots | maintains latent truth; answers `balance_at(customer, t)`-style queries to executor; emits outage/mandate events | **MUST NOT** be importable by datamart/policies (boundary test); **MUST NOT** make decisions |
| **PaymentEngine** | schedule + dims + world → attempts + first-failure events (raw PSP codes mapped via psp_code_map) | renewal calendar; attempt outcome via §8 gates; preserves attempt counting (original=1 + retries≤3) | **MUST NOT** choose recovery actions; **MUST NOT** write case states |
| **ConstraintEngine** | (case state, candidate action, rule pack, clock) → verdict {feasible_set, per-candidate reason} | all hard rules: budgets, windows, caps, quiet hours, opt-outs, class eligibility; pure functions, no RNG | **MUST NOT** mutate anything; **MUST NOT** see sidecars or labels |
| **CaseManager (FSM)** | events + verdicts → state transitions | owns states/guards from M1 transition table; records guard evaluations | **MUST NOT** bypass transition table; **MUST NOT** compute outcomes |
| **ActionExecutor** | chosen action + world + payment engine → outcome events + state updates | executes (simulated) retries/notifications/links; computes costs & fatigue deltas | **MUST NOT** self-authorize: requires prior ConstraintEngine verdict in the action record |
| **EventLogger / AuditWriter** | domain events → append-only parquet batches + per-run manifest | ordering, schema stamping (`policy_version`, `assumptions_version`), flush discipline | **MUST NOT** overwrite/normalize past events; **MUST NOT** drop events on crash (write-then-continue) |
| **Policy (interface)** + B0/B1/B2/B3 | case snapshot + feasible set + (for learned policies later) scores → chosen action or stop | implement documented logic only; log rationale codes | **MUST NOT** import world/sidecar modules; B2 **MUST NOT** learn (it's the hand-written doctrine) |
| **SimulationRunner** | config + registry + seed tree → one closed-loop run ending in frozen artifacts | owns EventScheduler (heapq); steps world & policies; triggers validation at end | **MUST NOT** contain domain logic (delegates); **MUST NOT** swallow invariant failures |
| **DatasetBuilder** | run outputs → sealed `dataset_vX.Y/` tree + manifest + hashes | freeze discipline; registry snapshot copy; checksum file | — |
| **MartBuilder** | frozen dataset → `ml_datamart.parquet` | as-of snapshot features; labels per §8/Part 11; coverage report | **MUST NOT** mint labels for WAIT/STOP/ESCALATE; **MUST NOT** touch sidecars (assert via import-guard test) |
| **ValidationSuite** | any artifacts → `validation_report.*` | invariants, anchors, edge pack, reproducibility (re-run & compare) | **MUST NOT** auto-fix; reports only |

---

# 7. Part 7 — Configuration Design

**Files and ownership:**

- `configs/simulation.yaml` — scale (n_customers…), horizon, cycle count, paths, master seed, batch sizes. *Technical knobs only.*
- `configs/policies.yaml` — B1 per-rail retry cadence (Cashfree-style 1+3 hourly for UPI; Razorpay-style daily-until-halt for cards — each entry cites its source doc), B2 doctrine mapping (failure_class → window rules; each row cites vendor doctrine), B3 seed behavior.
- `configs/costs.yaml` — `cost_inr` and `fatigue_delta` per action (tagged ASSUMED), escalation thresholds by value tier.
- `configs/registry/assumption_registry.yaml` — one entry per behavioral param: `name, symbol/where-used, value, unit, tag∈{FACT,ASSUMED,DECISION}, source (URL or 'developer-set'), scenario_multipliers{pessimistic,base,optimistic,adversarial}, rationale`.
- `configs/registry/scenario_regimes.yaml` — the four regimes as multiplier sets; **adversarial** deliberately breaks the payday doctrine for a customer segment (weekly salaries).
- `configs/registry/psp_code_map.yaml` — raw dialect codes → canonical failure class (versioned).

**The key distinction (enforced structurally):** *Configuration answers "how much / which file / what seed"* and can change run to run. *The registry answers "why should the world behave this way"* — entries without a `source` and `rationale` fail validation, and every generated artifact stamps the registry's content hash, so a dataset can always be traced to the exact assumption set that produced it.

---

# 8. Part 8 — Data Quality & Validation (test taxonomy)

Implemented as pytest + post-run `validation_report` (dataset-scale):

1. **Schema (T1):** every table row validates against pydantic models; enums exact.
2. **Referential (T2):** every event references an existing case; attempts↔actions↔cases form a tree; sidecar keyed to real customers.
3. **State-transition legality (T3):** observed (prev,action,new) ⊆ transition table; terminals absorbing.
4. **Temporal (T4):** per-case timestamps non-decreasing; retries scheduled in future legal windows; case close after open.
5. **Accounting (T5):** recovered_amount ≤ amount_at_risk; recovered_flag ⇒ `ATTEMPT_SUCCEEDED` or qualifying self-pay before close; totals(cost, contacts, retries) equal recomputation from events.
6. **Action limits (T6):** retries ≤ 3/cycle/case; notification caps; cooldowns; quiet hours; value-tier approval gates.
7. **Terminal protection (T7):** no post-close actions; opt-out → zero further contacts.
8. **Distribution anchors (T8):** per §3A-13B — failure-rate bands, class mix, recovery decay shape, amount KS vs UPI reference, in scenario tolerance windows.
9. **Reproducibility (T9):** same config+seed double-run ⇒ identical artifact hashes.
10. **Leakage (T10):** feature builder timestamp proof; import-boundary scan (datamart/policies cannot import world/sidecar modules); mart rows only post-maturity.
11. **Label sanity (T11):** retry-recovery ≈ 0 for hard classes but > 0 via update-flows where doctrine says so; positive-rate floors per (class) present for retry-eligible classes.

---

# 9. Part 9 — Reproducibility

- **RNG:** NumPy `Generator(PCG64)` only; the stdlib `random` module is banned (CI grep). One master seed per run; `SeedSequence(master).spawn(key)` streams for: population, world, payment outcomes, notification hazards, jitter, policies that need randomness (B3). Seed tree serialized into the manifest.
- **Determinism hygiene:** `PYTHONHASHSEED=0` in Makefile; no `set` iteration affecting outputs (sorted keys at write); DataFrames sorted by (case_id, ts, event_id) before write; fixed pyarrow version pinned.
- **Versioning:** `dataset_v<MAJOR.MINOR>` folder bumping MINOR on any registry/logic change, MAJOR on schema change; dataset embeds `assumptions_version` = registry content hash; `simulator_version` = git SHA.
- **Manifest per dataset:** `{git_sha, python_version, dependency_lock_hash, master_seed_tree, config_hash, registry_hash, row_counts, artifact_hashes(blake2b), created_utc, scenario, validation_report_hash}` — doubly run at freeze time; if hashes differ, freeze is refused (T9 automated).

---

# 10. Part 10 — Dataset Output Contract

(final list after critical review; `dataset_vX.Y/` root)

| File | Purpose | Key columns | Producer | Consumer |
|---|---|---|---|---|
| `dim_customers.parquet` | merchant-observable customer records | ids, segment, age_band, state, locale, primary_rail, opt_out, fatigue | PopulationGenerator | payments/recovery/datamart |
| `dim_subscriptions.parquet` | plans + mandate metadata | sub_id, cust_id, plan_amount (≤₹15K), cadence, rail, bank, status | PopulationGenerator | payments/recovery |
| `payment_attempts.parquet` | every charge attempt incl. original debit | attempt_id, case_id, window_code, attempt_index, outcome, raw code, failure_class, ts | PaymentEngine/Executor | mart, validation |
| `recovery_cases.parquet` | case master record | case_id, sub_id, opened/closed, state, counters, amount_at_risk, resolution | CaseManager | all |
| `recovery_events.parquet` | append-only event log (audit spine) | event_id, case_id, ts, type, actor, payload_json, versions | EventLogger | validation, replay, audit UI later |
| `action_log.parquet` | decisions with full context | action_id, case_id, decision_ts, candidate_set_json (p̂,EV per candidate), verdict_json, chosen, status | DecisionLogger | mart (labels keyed here), policies review |
| `case_outcomes.parquet` | maturity-materialized labels/metrics | recovered_flag/amount/ts, time_to_recovery, resolution, counters, costs | MartBuilder (from events) | experiments, mart |
| `ml_datamart.parquet` | decision-point training rows | snapshot features + action contextuals + label + logging_policy + maturity/censor flags | MartBuilder | Phase 3C training |
| `sidecar/latent_state.parquet` | SEALED: true mechanisms | salary_day, intent, balance params, responsiveness | WorldModel/population | **no runtime consumer** |
| `sidecar/counterfactuals.parquet` | SEALED: alt-action outcomes for evaluation | case_id, action candidates, realized counterfactual outcome | Executor (eval branch) | ExperimentHarness only |
| `registry_snapshot/` | exact YAMLs used | full configs + registry | DatasetBuilder | auditors |
| `dataset_manifest.json` | provenance & hashes | §9 manifest list | DatasetBuilder | everyone |
| `validation_report.{json,md}` | gate evidence | per-invariant pass/fail + anchor diffs | ValidationSuite | reviewers |
| `../docs/DATASET_CARD.md` | human documentation | scope, tags, provenance, known limitations, honest-claim template | author | reviewers |
| `samples/case_trace_sample.csv` | 3–5 fully readable case timelines | flattened events of selected cases | scripts | demos/debug |

Removed vs the brief's sketch: nothing needed removal; **added** sidecars, registry snapshot, manifest, validation report, sample traces (audit quality is a graded dimension). CSV is banned except `samples/`.

---

# 11. Part 11 — ML Datamart Build (contract; training deferred to Phase 3C)

- **Row unit:** one per money-moving decision (`DECISION_MADE` whose chosen action ∈ {RETRY_AT_WINDOW, SEND_REMINDER, SEND_PAYMENT_LINK, REQUEST_PM_UPDATE}). WAIT/STOP/ESCALATE are excluded from the mart but remain fully audited.
- **Decision timestamp** = `action_log.decision_ts`; features computed via Polars as-of joins over history strictly `< decision_ts` (enforced by T10 test asserting the builder's query plan cannot read `ts ≥ snapshot_ts`).
- **Labels:** retry → success of that attempt; contact actions → qualifying conversion event within Δ=24h (parameterized; sensitivity runs at Δ∈{12,24,48} planned in Phase 3C); label construction keys off `action_id` so a label never mixes actions.
- **Outcome windows & censoring:** rows where the outcome window is truncated by world-end or terminal closure get `censored=True` ⇒ excluded from training, counted in the coverage report; unresolved/terminal cases without the action's outcome ⇒ no row (not a zero label).
- **Logging-policy column:** rows carry `logging_policy ∈ {B1,B2,B3-random-legal,RD-EV-preview}` because the mart-building pass intentionally mixes logging policies → guarantees legal action×timing cell coverage (3A §11) and honestly records support.
- **Leakage surface documented in DATASET_CARD:** snapshot-time feature list, proxy-noise notice (salary-window proxy is coarse — latent truth sealed), and the plausibility corridor that Phase 3C must respect.

---

# 12. Part 12 — Baseline Policies (v1 minimum set)

| Policy | Logic (encoded in `policies.yaml`, cited) | Proves |
|---|---|---|
| **B0 None** | never acts; case auto-closes at window expiry | the revenue-leak floor; denominators for uplift |
| **B1 PSP-proxy** | UPI AutoPay: original+3 retries at hourly cadence within legal execution window (Cashfree documented policy); Cards: daily retry until ~4 failures → halt (Razorpay documented lifecycle) | what a merchant gets *today for free* — the headline comparator |
| **B2 Static doctrine** | hand-written mapping from vendor-published doctrine (insufficient-funds→payday-aligned next legal window; technical→hours; hard→single notify/link path; never-retry classes stop immediately) | the "is ML worth anything over a good spreadsheet?" test — must be honestly beatable or reportable as tied |
| **B3 Random-legal** | uniform choice over feasible set each decision | sanity floor on the decision layer; mart coverage helper |
| ~~B4 oracle~~ | **deferred to checkpoint H option** (latent-peeking upper bound via sidecar) — not in v1 experiment set to avoid overcomplication | ceiling estimate, later |

All baselines consume the identical tool interface and rule pack as the future ML/agent path — no privileged shortcuts.

---

# 13. Part 13 — Development Checkpoints (pass/fail)

| CP | Name | PASS criteria (explicit) |
|---|---|---|
| A | Domain validated | M1 tests green; transition table == 3A §4; reviewer diff signed off |
| B | Population validated | M4 anchors (KS p>α on amounts/banks/states); latent/dim separation test green |
| C | Payments/failures validated | first-failure rate inside scenario band; class mix sane; attempt invariants green |
| D | State machine validated | M7 (state,action) truth table fully tested; guard evaluations logged |
| E | Closed loop works | M11: B0–B3 complete; replay test == live state for all runs |
| F | Baselines correct | B1 timing equals PSP spec in `policies.yaml`; B2 equals doctrine yaml; policy-boundary test green |
| G | Small dataset validated | M12 G1+G2 green at SMOKE/SLICE; validation_report committed |
| H | Full dataset frozen | M13: G3 green (T9 hash equality, manifest complete); optional B4 oracle run |
| I | Datamart frozen | M14: G4 green (leakage tests, maturity gate, coverage), EDA note written, claim-template check |

---

# 14. Part 14 — Definition of Done (Phase 3B)

Phase 3B is complete **iff all are true with artifact evidence**:

1. ✅ Double-run reproducibility: identical hashes (T9) at FULL scale, manifest committed.
2. ✅ Event/state validity: invariant suite I1–I12 green at FULL scale; replay test proves live state == event-log reconstruction.
3. ✅ Documented assumptions: registry has 0 entries missing `source`/`rationale`/`tag`; scenario regimes resolvable.
4. ✅ Baselines B0–B3 implemented, spec-tested, and logged through the shared interface.
5. ✅ `dataset_v1.0/` generated with all §10 artifacts including sealed sidecars.
6. ✅ Distribution anchors within scenario bands; deviations written into the report, not tuned silently.
7. ✅ Leakage: T10 tests green; plausibility corridors propagated to Phase 3C as acceptance criteria.
8. ✅ Versioning: dataset hash ↔ registry hash ↔ git SHA triangle verifiable from the manifest.
9. ✅ `ml_datamart.parquet` frozen with coverage report (per-class × action × window cell counts) and censoring accounting.
10. ✅ `DATASET_CARD.md`, `DECISIONS.md`, `FAILURE_LOG.md` current; results phrased **only** in the honest-claim template.

Not done merely because rows exist. Checkpoint I sign-off = Phase 3C unlock.

---

# 15. Part 15 — Risk Review

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Overengineering creep (services, GE, MLflow…) | Medium | High | §2 avoid-list is binding; review rule: new dependency needs written justification vs the table |
| Simulator too deterministic → model aces it | Medium | High | entropy budget: unobserved heterogeneity, jitter terms, proxy noise; plausibility corridors flag it |
| Simulator too random → flat policies, nothing to learn | Medium | High | structural gates (§8) guarantee signal; anchor bands catch collapse; doctrine-signature EDA at G4 |
| Circular evaluation (model relearns injected rules) | Medium | Critical | sealed sidecars + observability firewall + adversarial regime + "B2-tie must be reported" rule |
| Generation runtime blowup | Low-Medium | Medium | Polars/vectorization; profile at SLICE; event batching; target < 30 min FULL on laptop; cap cycles if exceeded, record decision |
| Debugging pain in event-sourced runs | Medium | Medium | replay test per case; `samples/case_trace_sample.csv`; run-scoped structured logs; deterministic seeds per stream |
| Unrealistic assumptions slip through | Medium | High | registry provenance tags; scenario bands instead of point claims; anchors reconciliation mandatory |
| Parquet nondeterminism flips hashes | Medium | Medium | sorted writes, pinned pyarrow, T9 test exactly targets this; if unfixable, hash canonical row content instead of bytes (documented switch) |
| Mart leakage via joins | Low | Critical | as-of builders + T10; row-level spot audits in EDA; import-boundary CI test |
| Scope creep toward UI/prod APIs mid-phase | Medium | Medium | phase gate: nothing beyond `docs/` and `data/eval/` presentation; Phase 4 backlog list exists to park ideas |
| Vendor-doctrine anchors prove inconsistent across sources | Medium | Medium | bands built to span source disagreement; report shows per-source bands; constants never hidden in code |

---

*End of Phase 3B plan. Implementation begins at Milestone M0. Nothing in this phase trains models, builds UI, or touches production payment APIs; the sandbox actuation track (Stripe test clocks / Razorpay test VPAs) is a Phase-4 item fed by the frozen event model.*
