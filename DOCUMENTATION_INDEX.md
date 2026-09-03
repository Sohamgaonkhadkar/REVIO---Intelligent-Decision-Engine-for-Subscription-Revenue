# Documentation Index

Complete map of all documentation in the REVIO project repository.

---

## Root-Level Documents

| Document | Purpose | Authority |
|---|---|---|
| [`README.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/README.md) | **Master project documentation.** Full lifecycle from problem research to deployment. | Authoritative project overview |
| [`README_SOURCE_AUDIT.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/README_SOURCE_AUDIT.md) | Section-to-source traceability for README.md | Verification reference |
| [`DOCUMENTATION_INDEX.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/DOCUMENTATION_INDEX.md) | This file. Documentation map. | Navigation reference |

---

## Offline Pipeline: Research, Data, and Model Training

Located in `revenue-recovery-model-trainng/`:

### Phase 1: Problem Definition

| Document | Content |
|---|---|
| [`PHASE_1_PROBLEM_AND_SOLUTION_RESEARCH.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_1_PROBLEM_AND_SOLUTION_RESEARCH.md) | Problem definition, market analysis, candidate solution research, competitive landscape, regulatory constraints, evaluation criteria |

### Phase 2: Intelligence Strategy

| Document | Content |
|---|---|
| [`PHASE_2_DATA_AND_INTELLIGENCE_STRATEGY.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_2_DATA_AND_INTELLIGENCE_STRATEGY.md) | Data sourcing strategy, baseline definitions (B0/B1/B2), honest-reporting policy, intelligence architecture |

### Phase 3A/3B: Data Foundation and Simulator

| Document | Content |
|---|---|
| [`PHASE_3A_DATA_FOUNDATION_AND_SIMULATOR_BLUEPRINT.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_3A_DATA_FOUNDATION_AND_SIMULATOR_BLUEPRINT.md) | Simulator mechanics blueprint: population, latent state, balance sufficiency, outage model, response hazards, constraint compliance |
| [`PHASE_3B_DATASET_IMPLEMENTATION_PLAN.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_3B_DATASET_IMPLEMENTATION_PLAN.md) | Dataset implementation plan: table schemas, build pipeline, validation contract |
| [`DATASET_BUILD_REPORT.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/DATASET_BUILD_REPORT.md) | What was actually built: sources, 7-step build, calibration results, file inventory, key numbers, limitations |

### Phase 3C: EDA, Feature Engineering, Model Training

| Document | Content |
|---|---|
| [`PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md) | Exploratory data analysis: statistical associations, nonlinear effects, collinearity, anomaly review |
| [`PHASE_3C3_FEATURE_ENGINEERING_AND_CLEANING.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_3C3_FEATURE_ENGINEERING_AND_CLEANING.md) | Feature engineering decisions, cleaning pipeline, preprocessing |
| [`PHASE_3C_ML_DATA_CONTRACT_AND_PHASE_C_PLAN.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_3C_ML_DATA_CONTRACT_AND_PHASE_C_PLAN.md) | ML data contract: grain definition, feature roles, leakage rules, excluded variables |
| [`Phase_3C_Model_Training.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/Phase_3C_Model_Training.md) | Model training methodology: baselines, XGBoost/CatBoost/LightGBM experiments, ensemble architecture, evaluation metrics, final benchmarks |
| [`MODEL_QUALITY_EVALUATOR_DEFENSE.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/MODEL_QUALITY_EVALUATOR_DEFENSE.md) | How to defend model quality to evaluators: what was done, what was not, and why 0.831 PR-AUC is a valid benchmark |

### Phase 4: Deployment Architecture

| Document | Content |
|---|---|
| [`PHASE_4_DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_FINAL_FIXED.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/revenue-recovery-model-trainng/PHASE_4_DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_FINAL_FIXED.md) | Complete deployment architecture: invariants, runtime zones, knowledge/RAG, agent boundaries, simulator world model |

---

## Online Pipeline: Deployment and Runtime

Located in `recoverydesk/`:

### System Documentation

| Document | Content |
|---|---|
| [`README.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/README.md) | Deployment-specific README: architecture, setup, API reference, configuration, testing, known issues |
| [`DECISIONS.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/DECISIONS.md) | D-001 through D-035: every interpretation, conflict resolution, and engineering decision with reasoning |
| [`EVALUATOR_WALKTHROUGH.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/EVALUATOR_WALKTHROUGH.md) | Click-by-click demonstration guide for evaluators |
| [`DATA_PROVENANCE_AND_TEST_EVIDENCE.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/DATA_PROVENANCE_AND_TEST_EVIDENCE.md) | Data provenance verification: traceability from database to frontend |

### Implementation and Quality Records

| Document | Content |
|---|---|
| [`IMPLEMENTATION_PLAN.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/IMPLEMENTATION_PLAN.md) | Original implementation plan |
| [`FINAL_PASS_REPORT.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/FINAL_PASS_REPORT.md) | Final quality pass report |
| [`IA_CORRECTION_REPORT.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/IA_CORRECTION_REPORT.md) | Information architecture correction audit |
| [`REDESIGN_SELF_CRITIQUE.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/REDESIGN_SELF_CRITIQUE.md) | Product redesign self-critique |
| [`NEXT_TASK_ANTIGRAVITY_RUNTIME_DATA_RETRIEVAL.md`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/NEXT_TASK_ANTIGRAVITY_RUNTIME_DATA_RETRIEVAL.md) | Handoff specification for runtime data retrieval task |

### Configuration and Registry

| File | Content |
|---|---|
| [`configs/registry/feature_contract_v3.yaml`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/configs/registry/feature_contract_v3.yaml) | Authoritative feature contract (32 features, 20 numeric, 12 categorical) |
| [`configs/registry/model_artifacts.yaml`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/configs/registry/model_artifacts.yaml) | Model artifact paths and SHA-256 hashes |
| [`configs/registry/model_benchmark.yaml`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/configs/registry/model_benchmark.yaml) | Model benchmark metrics (from Phase 3C) |
| [`configs/costs.yaml`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/configs/costs.yaml) | EV constants: action costs, channel costs, fatigue curve, shadow prices, stop thresholds |
| [`artifacts/MANIFEST.sha256`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/artifacts/MANIFEST.sha256) | Integrity checksums for all registered artifacts |

### Database

| File | Content |
|---|---|
| [`db/migrations/0001_init.sql`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/db/migrations/0001_init.sql) | Core schema: 14 tables, constraints, indexes |
| [`db/migrations/0002_sim_zone.sql`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/db/migrations/0002_sim_zone.sql) | Sealed simulator state schema |
| [`db/migrations/0003–0007`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/db/migrations/) | Case counters, intent fields, knowledge schema, history schema |
| [`db/roles.sql`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/db/roles.sql) | Privilege grants: append-only enforcement for journal tables |

### Deployment

| File | Content |
|---|---|
| [`deploy/docker-compose.yml`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/deploy/docker-compose.yml) | Authoritative deployment topology (4 services) |
| [`deploy/Dockerfile`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/deploy/Dockerfile) | Application image definition |
| [`deploy/nginx.conf`](file:///c:/Users/Soham/Documents/revenue-recovery-deployment/recoverydesk/deploy/nginx.conf) | SPA serving and API proxy |

---

## Reading Order

For a first-time reader evaluating the complete project:

1. **Root `README.md`** — system overview, architecture, and lifecycle
2. **Phase 1** — why this problem matters
3. **Phase 2** — intelligence strategy and baseline philosophy
4. **Dataset Build Report** — how the training data was constructed
5. **Phase 3C Model Training** — model progression and final benchmarks
6. **`recoverydesk/DECISIONS.md`** — every engineering decision and conflict resolution
7. **`recoverydesk/EVALUATOR_WALKTHROUGH.md`** — click-by-click demo
8. **`recoverydesk/README.md`** — deployment-specific setup and API reference
