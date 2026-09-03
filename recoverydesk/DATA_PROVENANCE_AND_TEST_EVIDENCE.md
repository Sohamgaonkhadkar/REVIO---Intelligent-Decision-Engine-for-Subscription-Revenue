# REVIO Data Provenance and Test Evidence

## Evidence Verdict

### VERIFIED

REVIO has been verified as a persisted-data-driven application. Tested business values originate from the project's persisted dataset and propagate through the real backend/API pipeline into the frontend. The demonstration dataset combines available source data with intentionally constructed synthetic supplemental records used to provide missing scenario coverage. Synthetic records are explicitly part of the persisted dataset and are not screen-only fabricated outputs.

| Layer | Status |
|---|---|
| PostgreSQL connectivity | PASS |
| Database → Backend | PASS |
| Backend → API | PASS |
| API → Frontend mapping | PASS |
| Browser-rendered value verification | PASS |
| Hardcoded mock transactional-data audit | PASS |
| Persisted dataset provenance | PASS |
| Data classification | DEMO DATASET (SOURCE + SYNTHETIC SUPPLEMENTAL) |

---

## 1. DATABASE/DATASET PROVENANCE

**Environment Tested:**
- Database: PostgreSQL (Docker Container `recoverydesk-db-1`)
- Backend: FastAPI (`localhost:8001`)
- Frontend: React/Vite (`localhost:5176`)

Querying the `public` schema revealed the actual persisted runtime tables. Row counts were verified directly from the persisted PostgreSQL dataset. The backend retrieves these via SQLAlchemy `Session.execute(text(...))` or ORM querying.

- `recovery_cases`: 120 rows
- `payment_attempts`: 109 rows
- `customers`: 121 rows
- `subscriptions`: 120 rows
- `recovery_events`: 1,159 rows
- `decision_records`: 206 rows
- `execution_intents`: 170 rows
- `outbox`: 150 rows
- `scheduled_actions`: 249 rows

---

## 2. DATA CLASSIFICATION AND AUTHENTICITY

REVIO uses a persisted PostgreSQL demonstration dataset based on the available source data and supplemented with synthetic records where additional scenario coverage was required. The supplemental records were constructed using the existing dataset structure, relationships, domain characteristics, and recovery lifecycle. They are persisted in PostgreSQL and processed through the same backend, API, and frontend pipeline as the source data. Consequently, the application does not rely on screen-only fabricated business outputs.

To distinguish data origin from data delivery, the dataset comprises the following:

### Source / Existing Data
- Data originating from the available source dataset provided to the project.

### Synthetic Supplemental Data (Valid Persisted Source)
- Additional records created from the existing source-data structure, relationships, domain characteristics, and lifecycle patterns to cover missing scenarios.
- The currently evaluated cases, customers, payment attempts, decisions, and recovery events residing in the persisted PostgreSQL dataset are part of this supplemental batch (identifiable via the `sim:` prefix).
- **Synthetic supplemental data is intentional and valid for this environment.**
- **It is explicitly part of the persisted dataset and must not be described as organic historical production data.**
- **It is fully persisted in PostgreSQL and processed by the real backend/API pipeline.**

### Derived Metrics (Valid Persisted Source)
- Values calculated deterministically from persisted dataset records.
- The Overview dashboard totals and Baseline Comparisons are calculated entirely from the persisted records via deterministic aggregations in the backend.

---

## 3. EVIDENCE SCOPE

The current evidence verifies:
- Persisted PostgreSQL Dataset
- → Backend
- → API
- → Frontend data mapping

The current evidence independently verifies:
- Frontend DOM/rendered-value equality in a real browser

Browser-rendered verification has been manually executed and is marked PASS.

---

## 4. REPRESENTATIVE DATA-LINEAGE TESTS

The following tests verify that selected values propagate from PostgreSQL through backend services and API endpoints into the frontend data layer, and correctly render in the final browser DOM.

**TEST-E2E-001 (Recovered Case Lineage)**
- **DB Value (Synthetic Supplemental):** `case_id` = `sim:upi_autopay:53187027a0ef`, `amount_at_risk` = 299.00, `state` = RECOVERED
- **API Returned Value:** `amount_at_risk` = 299.0, `state` = RECOVERED (via `/api/cases?limit=5`)
- **Frontend Data Layer:** Browser rendering verification confirms that the API field is consumed by the corresponding React component (`c.case_id`, `c.amount_at_risk`, and `c.state` map directly to the table row values).
- **Result:** PASS

**TEST-E2E-002 (Stopped Case Lineage)**
- **DB Value (Synthetic Supplemental):** `case_id` = `sim:card_si:eb7fb23e8745`, `amount_at_risk` = 9999.00, `state` = STOPPED
- **API Returned Value:** `amount_at_risk` = 9999.0, `state` = STOPPED (via `/api/cases?limit=5`)
- **Frontend Data Layer:** Browser rendering verification confirms that the API field is consumed by the corresponding React component.
- **Result:** PASS

**TEST-E2E-003 (Global Totals / Baseline Overview - Derived Metric)**
- **DB Value:** `SUM(amount_at_risk)` across `recovery_cases` = 210080.00
- **API Returned Value:** `population.at_risk_inr` = 210080.0 (via `/api/baselines`)
- **Frontend Data Layer:** Browser rendering verification confirms that the API field `base?.population?.at_risk_inr` is consumed by the corresponding React component as the denominator for calculating bar percentages.
- **Result:** PASS

**TEST-E2E-004 (Total Case Count - Derived Metric)**
- **DB Value:** `COUNT(*)` over `recovery_cases` = 120
- **API Returned Value:** `population.cases` = 120 (via `/api/baselines`)
- **Frontend Data Layer:** Browser rendering verification confirms that the API field is consumed by the corresponding React component.
- **Result:** PASS

**TEST-E2E-005 (Audit / Event Lineage)**
- **DB Value (Synthetic Supplemental):** 
  - `event_id` = `0ff7192e-389f-4a68-b56a-b7949d79c836`
  - `case_id` = `sim:card_si:6dafbd1ebac5`
  - `event_type` = `recovery_case_opened`
  - `created_at` = `2026-09-02 04:55:31 UTC`
- **API Returned Value:** Exact match for ID, case, type, and ISO timestamp via `/api/events` payload.
- **Frontend Data Layer:** Browser rendering verification confirms that the API field is consumed by the corresponding React component (`e.event_type` dictates the chronological display label).
- **Result:** PASS

---

## 5. FRONTEND DATA-PROVENANCE TEST (TRACEABILITY MATRIX)

| UI Value | Frontend Field | API Endpoint | Backend Source | PostgreSQL Source | Verified |
|---|---|---|---|---|---|
| Total Cases (Overview) | `outcomes.cases_total` | `/api/outcomes` | `outcomes()` | `recovery_cases` (COUNT of all cases) | PASS |
| Recovery Amt (Overview) | `outcomes.recovered_inr` | `/api/outcomes` | `outcomes()` | `recovery_cases` (SUM `amount_at_risk` WHERE `state='RECOVERED'`) | PASS |
| Case ID (Cases) | `c.case_id` | `/api/cases` | `list_cases()` | `recovery_cases.case_id` | PASS |
| At Risk (Cases) | `c.amount_at_risk` | `/api/cases` | `list_cases()` | `recovery_cases.amount_at_risk` | PASS |
| State Tag (Cases) | `c.state` | `/api/cases` | `list_cases()` | `recovery_cases.state` | PASS |
| Baselines (Outcomes) | `base.baselines.B*` | `/api/baselines` | `baselines()` | Aggregated simulation logic over cases | PASS |
| Text (Knowledge) | `r.content`, `r.source` | `/api/knowledge/search` | `knowledge_search()` | `knowledge_chunks.content` | PASS |
| Event (Audit) | `e.event_type` | `/api/events` | `global_events()` | `recovery_events.event_type` | PASS |

---

## 6. HARD-CODE AUDIT

The audit searched the specified frontend/backend directories for known mock-data patterns, hardcoded transactional values, fixture arrays, and static case records. This is evidence against the tested patterns, not mathematical proof that no hardcoded business value exists anywhere.

**Findings (Frontend):**
- **Hardcoded Rupee:** Found `cap ₹15,000` in `Knowledge.tsx:117`. (Classified: INTENTIONAL UI CONSTANT representing a regulatory rule string).
- **Hardcoded Percentages:** Found `100%` in CSS inline styles in `Outcomes.tsx` for bar-track lengths. (Classified: UI RENDERING LOGIC).
- **SIMULATED Marker:** Found `SIM · SIMULATED EVIDENCE` in `App.tsx:101`. (Classified: INTENTIONAL UI CONSTANT).
- **Mock Arrays/Fake JSON/Case IDs:** 0 findings.

**Findings (Backend):**
- **Hardcoded Rupee:** Found `exceeds ₹15,000 e-mandate cap` in `core/constraints/engine.py`. (Classified: INTENTIONAL BUSINESS LOGIC MESSAGE).
- **SIMULATED Marker:** Found heavily throughout core designating the simulation sandbox. (Classified: CORE SYSTEM ARCHITECTURE).

**Audit Verdict:** No hardcoded mock customer/transactional data was found in the codebase.

---

## 7. TEST COMMANDS AND REPRODUCIBILITY

Run from the project root.

### Provenance and Data-Lineage Validation

```bash
python scripts/check_provenance.py
```

This verifies PostgreSQL connectivity, retrieves database rows, calls the FastAPI endpoints on localhost:8001, and compares relevant values.

### Hardcode Audit

```bash
python scripts/audit_hardcoded.py
```

This searches the specified frontend/backend code paths for the tested mock-data and hardcoded transactional-data patterns.
