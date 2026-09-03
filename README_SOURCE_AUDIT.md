# README Source Audit

Every factual claim in `README.md` is traced to a specific source in the repository. This document maps sections to their authoritative references, enabling independent verification.

---

## Methodology

Each section below lists the claims made and the file or code location that substantiates them. Where a claim synthesises multiple sources, all sources are listed. Where a claim cannot be fully verified from the repository, this is noted.

---

## Section 1: Executive Summary

| Claim | Source | Verification |
|---|---|---|
| UPI AutoPay debit failure rates 55–90% (Aug 2025) | `PHASE_1_PROBLEM_AND_SOLUTION_RESEARCH.md` §11, citing NPCI data | Phase 1 document reference |
| Typical-month 8–15% UPI, 2–8% card | `DATASET_BUILD_REPORT.md` §2 (calibration targets from vendor literature) | Dataset build report, tagged vendor-marketing |
| NPCI 1+3 retry budget | `DATASET_BUILD_REPORT.md` §2 (NPCI recurring-payment rules, tagged FACT) | Regulatory source |
| Four-layer separation (Rules/Model/Economics/Decision) | `recoverydesk/core/decision/ev.py`, `core/constraints/engine.py`, `core/scoring/port.py` | Source code structure |
| Project lifecycle phases | `revenue-recovery-model-trainng/` directory listing; Phase 1–4 documents | Repository structure |

## Section 2: Problem Definition

| Claim | Source |
|---|---|
| Failure heterogeneity and categories | `PHASE_1_PROBLEM_AND_SOLUTION_RESEARCH.md` §4–§7 |
| BANK_TECHNICAL 88% retry success | `DATASET_BUILD_REPORT.md` §5 (label-signal sanity) |
| INSUFFICIENT_FUNDS 16% retry success | `DATASET_BUILD_REPORT.md` §5 |
| NPCI 1+3 constraint | `DATASET_BUILD_REPORT.md` §2 (NPCI source, tagged FACT) |
| Salary-cycle correlation | `PHASE_3A_DATA_FOUNDATION_AND_SIMULATOR_BLUEPRINT.md` (balance sufficiency model) |

## Section 3: Proposed Solution

| Claim | Source |
|---|---|
| Pipeline stages (ingest → constraint → score → EV → execute → journal) | `recoverydesk/core/orchestrator/`, `core/decision/ev.py`, `core/constraints/engine.py`, `core/gateway/` |
| 7 action types | `recoverydesk/core/domain/enums.py` class `ActionType` |
| Fallback mode with doctrine priors | `recoverydesk/core/scoring/port.py`, DECISIONS D-004 |
| EV formula | `recoverydesk/core/decision/ev.py` lines 68–89 |
| Verdict re-verification at gateway | `recoverydesk/DECISIONS.md` D-025 |

## Section 4: System Architecture

| Claim | Source |
|---|---|
| Architecture diagram | `recoverydesk/README.md` §6 (verified against source code modules) |
| PostgreSQL single source of truth | DECISIONS D-006, `recoverydesk/db/engine.py` |
| Append-only journal | `recoverydesk/db/migrations/0001_init.sql` lines 76–97, `db/roles.sql` |
| Verdict re-verification | `recoverydesk/core/gateway/`, DECISIONS D-025 |
| FSM 15 edges, frozen | `recoverydesk/core/fsm/` |
| Artifact gate | `recoverydesk/core/scoring/gate.py` |
| ML/RAG separation | DECISIONS D-012, source code inspection |

## Section 5: End-to-End Workflow

| Claim | Source |
|---|---|
| Webhook deduplication | `recoverydesk/db/migrations/0001_init.sql` (`psp_event_inbox`, `dedup_key UNIQUE`) |
| SKIP LOCKED scheduling | `recoverydesk/core/scheduler/`, `0001_init.sql` lines 156–171 |
| CaseSnapshot construction | `recoverydesk/core/features/snapshot.py` |
| 32-element feature vector | `recoverydesk/configs/registry/feature_contract_v3.yaml` |
| 16-check activation gate | `recoverydesk/core/scoring/gate.py` |

## Section 6: Data Acquisition and Dataset Construction

| Claim | Source |
|---|---|
| CC0 Kaggle dataset, 250k rows | `DATASET_BUILD_REPORT.md` §2 |
| Bank shares (SBI 25.1%, HDFC 15.0%) | `DATASET_BUILD_REPORT.md` §0 (step 0, profiled) |
| 95% success column not usable | `DATASET_BUILD_REPORT.md` §2 ("Its 95% success column was not usable for failure modelling") |
| recoverysim v0.3.0 | `DATASET_BUILD_REPORT.md` §0 header |
| 20,000 customers, population parameters | `DATASET_BUILD_REPORT.md` §3 (Step 2) |
| Balance sufficiency, outage Poisson(0.10) | `DATASET_BUILD_REPORT.md` §3 (Step 2) |
| Determinism via blake2b→PCG64 | `DATASET_BUILD_REPORT.md` §3 (Step 4) |
| Calibration: UPI 11.3%, card 7.3% | `DATASET_BUILD_REPORT.md` §3 (Step 5) |
| Dataset row counts (264,936 attempts, etc.) | `DATASET_BUILD_REPORT.md` §4 |
| 34/34 validation checks | `DATASET_BUILD_REPORT.md` §5 |
| Four logging policies B0–B3 | `DATASET_BUILD_REPORT.md` §3 (Step 3) |

## Section 7: Exploratory Data Analysis

| Claim | Source |
|---|---|
| All EDA findings | `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` (verbatim) |
| Kruskal-Wallis H=14799.693 | `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` §1 |
| Largest within-state spread 0.460 in BANK_TECHNICAL | `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` §4 |
| hour_of_day spread 0.284 | `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` §5 |
| amount_inr median y=1: 299, y=0: 599 | `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` §13 |
| 4 collinear pairs | `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md` §15 |

## Section 8: Feature Engineering

| Claim | Source |
|---|---|
| 32 features, 20 numeric, 12 categorical | `configs/registry/feature_contract_v3.yaml`, DECISIONS D-019 |
| Feature names and order | `feature_contract_v3.yaml` `features:` list |
| __UNKNOWN__ fail-closed encoding | `feature_contract_v3.yaml` `channel_for_non_contact_actions`, DECISIONS D-021/D-022 |
| 43/17/26 discrepancy | DECISIONS D-019 |

## Section 9: Model Development and Training

| Claim | Source |
|---|---|
| P(Y=1 | X, A) formulation | `Phase_3C_Model_Training.md` §1 |
| C4 split sizes (110,385/23,471/23,567) | `Phase_3C_Model_Training.md` §2 |
| 0 overlapping cases across splits | `Phase_3C_Model_Training.md` §2 |
| Positive rate ~22.8% | `Phase_3C_Model_Training.md` §2 |
| XGBoost test PR-AUC 0.831340 | `Phase_3C_Model_Training.md` §16, confirmed by `native_categorical_metrics.csv` |
| CatBoost test PR-AUC 0.829801 | `Phase_3C_Model_Training.md` §12 |
| 1,256 trees, binary:logistic | DECISIONS D-019 (`best_params.json`: n_estimators 1256) |
| 5-fold StratifiedGroupKFold | DECISIONS D-019 (`best_params.json`) |
| Artifact SHA-256 9434606c...96ba | `recoverydesk/artifacts/MANIFEST.sha256`, DECISIONS D-019 |

## Section 10: Model Evaluation and Validation

| Claim | Source |
|---|---|
| PR-AUC as primary metric | `Phase_3C_Model_Training.md` §8 |
| Label-signal sanity numbers | `DATASET_BUILD_REPORT.md` §5 |
| verify_model_runtime.py 19 checks | DECISIONS D-034, `scripts/verify_model_runtime.py` |
| max |Δp̂| = 0 | DECISIONS D-034 |
| No calibration artifact | DECISIONS D-005 |
| 16-check activation gate | `core/scoring/gate.py` |

## Section 11: Decision Architecture

| Claim | Source |
|---|---|
| Constraint rule IDs and effects | `recoverydesk/core/constraints/engine.py` (rule functions) |
| EV formula components | `recoverydesk/core/decision/ev.py` lines 68–89 |
| constants_hash stamped on decisions | `ev.py` lines 163–164, `decision_records` schema |
| Deterministic tie-breaking | `ev.py` lines 100–103 |
| Stop thresholds per tier | `ev.py` lines 126, `configs/costs.yaml` |

## Section 12: Recovery State Machine

| Claim | Source |
|---|---|
| 8 states | `recoverydesk/db/migrations/0001_init.sql` lines 46–48 (CHECK constraint) |
| RECOVERED/STOPPED absorbing | `0001_init.sql` lines 64–68 (terminal constraint) |
| stop_reason required for STOPPED | `0001_init.sql` lines 64–68 (chk_terminal_reason) |
| D-001 naming decision | `DECISIONS.md` D-001 |

## Section 13: Backend Architecture

| Claim | Source |
|---|---|
| Module listing | `recoverydesk/core/` directory structure |
| Module responsibilities | Source code inspection of each module |

## Section 14: Frontend Architecture

| Claim | Source |
|---|---|
| 7 pages | `recoverydesk/apps/web/src/pages/` (7 .tsx files) |
| Data sources per page | Source code inspection, `apps/api/main.py` endpoint mapping |
| Design system colours | DECISIONS D-034, `apps/web/src/index.css` |

## Section 15: Database and Data Model

| Claim | Source |
|---|---|
| All table definitions | `recoverydesk/db/migrations/0001_init.sql` through `0007_history_schema.sql` |
| Append-only enforcement | `recoverydesk/db/roles.sql` |
| 7 migration files | `recoverydesk/db/migrations/` directory listing |
| SIM zone separation | `0002_sim_zone.sql` |
| Knowledge zone | `0006_knowledge.sql` |

## Section 16: Knowledge, Rules and Governance

| Claim | Source |
|---|---|
| Executable vs advisory distinction | DECISIONS D-012 |
| 762 chunks | `recoverydesk/README.md` §8 (verified at ingestion time) |
| hashed-lexical-v1 embedder | DECISIONS D-027 |
| Copilot removed from UI | DECISIONS D-034, D-035 |
| COPILOT_ENABLED=false tested | DECISIONS D-017 |

## Section 17: Execution Architecture

| Claim | Source |
|---|---|
| Double-invocation of constraints | `core/constraints/engine.py` docstring, DECISIONS D-025 |
| decided_at persistence | `0004_intent_decided_at.sql` |
| candidate_id persistence | `0005_intent_candidate_id.sql` |
| verdict_hash re-verification | `core/gateway/`, DECISIONS D-025 |

## Section 18: Auditability and Data Provenance

| Claim | Source |
|---|---|
| Append-only enforcement by roles.sql | `db/roles.sql`, `tests/test_pg_schema.py` (asserted by tests) |
| 20-type frozen event enum | `core/domain/enums.py` class `EventType` (20 members) |
| decision_records schema | `0001_init.sql` lines 102–120 |
| API queries PostgreSQL at request time | `apps/api/main.py` (every endpoint uses `sm.begin()`) |

## Section 20: Baselines and Outcome Measurement

| Claim | Source |
|---|---|
| B0/B1/B2 definitions | `Phase_2_DATA_AND_INTELLIGENCE_STRATEGY.md` §14 |
| Monte-Carlo replay (48 draws) | `core/evaluation/baselines.py`, DECISIONS D-032 |
| 120s cache | `apps/api/main.py` (baselines endpoint) |
| "We can lose and must publish losing" | `Phase_2_DATA_AND_INTELLIGENCE_STRATEGY.md` §15 |

## Section 21: Technology Stack

| Claim | Source |
|---|---|
| All technology choices | `requirements.txt`, `package.json`, `docker-compose.yml`, source imports |

## Section 23: Deployment and Runtime

| Claim | Source |
|---|---|
| Docker Compose services | `recoverydesk/deploy/docker-compose.yml` |
| Environment variables | `recoverydesk/README.md` §14, `apps/api/main.py` |

## Section 24: Testing and Verification

| Claim | Source |
|---|---|
| 142 tests | `recoverydesk/README.md` §19 (verified count) |
| Test file listing | `recoverydesk/tests/` directory |
| verify_model_runtime.py checks | DECISIONS D-034, script source |
| Worker/pytest race | DECISIONS D-033 |

## Section 25: Dataset / Synthetic Data Policy

| Claim | Source |
|---|---|
| CC0 license | `DATASET_BUILD_REPORT.md` §2 |
| Source dataset limitations | `DATASET_BUILD_REPORT.md` §2 |
| Calibrated simulation methodology | `DATASET_BUILD_REPORT.md` §3 |
| SIM badge on all surfaces | `apps/api/main.py` (`_env_badge()`), UI inspection |

---

## Unverifiable Claims

The following claims reference external information that cannot be independently verified from repository contents alone:

1. **NPCI failure rate percentages** (55–90% August 2025): Cited from Phase 1 research, which references NPCI public data. The original NPCI publication is not included in the repository.
2. **PSP retry cadence details** (Cashfree hourly, Razorpay daily): Referenced from Phase 2 / PSP documentation. The original PSP documents are not included.
3. **Vendor-marketing failure rate bands** (8–15% UPI, 2–8% card): Used as calibration targets. Labelled as vendor-marketing in the assumption registry; original vendor publications not included.

These external references are documented with their provenance and confidence level in `configs/registry/assumption_registry.yaml` using FACT / DATA-DERIVED / ASSUMED / DECISION tags.
