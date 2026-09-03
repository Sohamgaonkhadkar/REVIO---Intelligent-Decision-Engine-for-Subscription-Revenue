# Next Task: Antigravity Runtime Data Retrieval

**Handoff type:** planning/implementation specification — no code in the current
repository changes as part of *writing* this document.
**Implementer:** Antigravity (separate workspace/session).
**Source documents (authoritative, in priority order):**
`PHASE_4_DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_FINAL_FIXED.md` (§16
Knowledge/RAG, §17 Agent/Ops Copilot boundary, C12 façade) >
`PHASE_3C_ML_DATA_CONTRACT_AND_PHASE_C_PLAN.md` (runtime data-contract block,
dataset roles, latent/counterfactual prohibitions) > `DECISIONS.md` (D-001…D-030)
> `IMPLEMENTATION_PLAN.md`. Conflicts → record in `DECISIONS.md`, never silently.

---

## 1. Current system status

RecoveryDesk is complete and verified. Do **not** redesign or re-implement any of it:

- Full loop works E2E: UI → typed SDK → FastAPI → domain → PostgreSQL → ML →
  constraints → EV → execution → events → UI.
- **142 tests passing**; API numbers match direct SQL checks exactly.
- Real native-categorical XGBoost artifact ACTIVE (32/12/20 contract, sha256-gated)
  — and **runtime-proven** by `scripts/verify_model_runtime.py` (19 checks:
  artifact → sha256 → independent Booster → gate → inference → p̂ → decision
  record → EV → journal, plus the fallback failure path). Report:
  `artifacts/reports/model_runtime_verification.md`. Re-run it after any change.
- Knowledge/RAG layer implemented (pgvector, `hashed-lexical-v1` lexical embedder,
  D-027) with cited retrieval.
- **Ops Copilot removed from the UI entirely** (D-032/034/035) — no chatbot page,
  no LLM messaging, no `/health` copilot field. The backend flag gate remains for
  a future opt-in surface; the bounded read-only tool registry below is the
  surviving (correct) boundary either way.
- Docker Compose config-verified; `docker compose up` must run on a Docker host.
- Live operational model in PostgreSQL: `customers`, `subscriptions`,
  `payment_attempts`, `recovery_cases`, `recovery_events` (append-only journal),
  `decision_records`, `execution_intents`, `scheduled_actions`, `outbox`,
  `kill_flags`, `monitoring_series`, `knowledge.*`, sealed `sim_zone.*`
  (migrations `db/migrations/0001…0006`).

**This task adds runtime/agent retrieval over six existing Parquet datasets.**
It does not touch the decision pipeline, constraints, EV, ML artifacts, schema
semantics, frontend behavior, or APIs' existing contracts.

### What changed since this handoff was written (still non-goals to alter)

- The API is now **20 paths** (was 19): `GET /api/baselines` (Phase-2 §14
  comparison, Monte-Carlo replay + timing/class evidence, 120 s TTL cache) and
  `GET /api/constraints/check?case_id=` (read-only live constraint engine) were
  added. Both are **precedents for this task**: bounded, read-only, typed,
  honesty-labelled surfaces over authoritative stores.
- The UI was redesigned twice (D-032 luminous product redesign; D-035 IA
  correction) — six destinations, honest baseline presentation front-and-center.
  See `README.md` §11 and `EVALUATOR_WALKTHROUGH.md`.
- `/health` now reports `schema_versions` (bug fix, D-034) and no copilot field.
- Decision log is D-001…D-035; read the D-033 entry before running the test
  battery (stop the loop worker first).

## 2. Why this task is being done

The bounded agent/ops tools (`get_case`, `get_timeline`, …) currently answer from
the live operational PostgreSQL store. Six **existing Parquet datasets** carry the
same operational roles for dataset-built history and must become available to the
runtime/agent retrieval layer so operator questions can be answered with
structured context (case state, payment history, event timelines, prior actions)
without expanding LLM context, without granting SQL access, and without ever
mixing ML-training or evaluation data into runtime retrieval.

## 3. The six datasets and their exact runtime purpose

Quoting the Phase 3C runtime data-contract block **verbatim** (customers →
live customer context; subscriptions → subscription/payment state; …):

```text
customers
    → live customer context

subscriptions
    → subscription/payment state

payment_attempts
    → payment/retry history

recovery_cases
    → case state

recovery_events
    → event stream / replay / audit

action_log
    → decision audit and experiment log
```

Explicit mapping to agent needs:

| Dataset | Runtime retrieval purpose (Phase 3C role) |
|---|---|
| `customers.parquet` | live customer context (segment, geography, locale, opt-out) |
| `subscriptions.parquet` | subscription/payment state (plan, rail, mandate status) |
| `payment_attempts.parquet` | payment/retry history (attempts, windows, outcomes, PSP codes) |
| `recovery_cases.parquet` | current recovery-case state (status, budgets used, amounts) |
| `recovery_events.parquet` | chronological event history — replay and audit context |
| `action_log.parquet` | prior action/decision/audit context |

**These six datasets are NOT additional ML training data.** Their purpose is
structured runtime/context retrieval for the bounded agent/ops tools. Nothing in
this task feeds the model, features, or EV constants.

## 4. Datasets that must NOT be used as runtime agent context

Phase 3C assigns these roles; they are prohibited for decision-time retrieval:

```text
case_outcomes
    → KPIs and batch evaluation

ml_datamart
    → model training/evaluation

latent sidecar   (latent_customers — "Hidden simulator truth — Never train on")
    → simulation validation only
```

- `ml_datamart` → **ML training/evaluation only.**
- `case_outcomes` → **KPI/batch evaluation, not decision-time retrieval.**
- `latent` simulator sidecar → **sealed simulation-validation data only.**
- `counterfactuals` → **evaluation only** ("Future counterfactual outcomes are
  evaluation-only and must not enter ordinary training" — Phase 3C).

**No path — loader, index, embedder, tool, or prompt assembler — may expose these
prohibited sources as runtime agent context.** Importers must fail closed if asked
to ingest them into any retrieval surface.

## 5. Parquet canonical-source policy

- The **source Parquet files remain the canonical data format**. Never modify
  them, never re-export them, never convert the canonical source permanently to
  anything else.
- Workspace-compatible **compact JSON representations are a transport/runtime
  compatibility layer only** — created only where necessary for transfer into the
  receiving environment, and only with the minimum fields retrieval needs.
- Do **NOT**: convert the canonical source permanently to JSON; create unnecessary
  duplicate copies; convert everything to CSV; dump all operational rows into RAG
  embeddings; or put entire tables into LLM prompts.

## 6. The 25 MB workspace constraint

The receiving workspace has **≈25 MB available** and does not accept the supplied
Parquet files directly. Therefore:

- Parquet stays canonical on the source side.
- Only compact, selective JSON extracts enter the workspace (§7).
- Target: **the complete runtime JSON bundle comfortably below 25 MB, with margin
  left for the application/workspace** — i.e., aim for a small fraction of 25 MB,
  not "just under" it.

## 7. Compact JSON transport strategy

1. **Inspect first** (§8): row counts, columns, Parquet file sizes, cardinalities,
   and which fields the retrieval tools actually need.
2. Extract **only those fields**, as compact JSON records
   (short keys acceptable only if a documented key map ships alongside; prefer
   readable keys), keyed for lookup (`case_id`, `customer_id`,
   `subscription_id`, `decision_id`, timestamps as ISO-8601 UTC).
3. **Do NOT blindly convert full Parquet tables to JSON.** If a table is too large
   for selective extract within budget, load it **through the existing PostgreSQL
   operational model** instead (source-side → PG import), and let retrieval be
   indexed SQL — JSON then only covers what PG cannot host in the receiving
   environment.
4. Prefer, in order: selective columns → compact JSON records → database-side
   filtering/aggregation → indexed PostgreSQL retrieval → case/customer/
   subscription keyed lookups → **pagination for long event histories**.
5. Every extract records provenance: source file, sha256, row count, extraction
   date, field list — so no one can mistake the extract for the canonical source.

## 8. Dataset inspection requirements (before any field decisions)

**Do not invent column names.** Antigravity must inspect the actual Parquet schema
of each of the six files first and record, per dataset: schema (name/type per
column), row count, file size, distinct-key cardinalities, null rates for
candidate lookup keys, and the minimum field set the tools in §10 require. This
inspection table is a required deliverable before implementation.

## 9. Structured retrieval architecture

Preserve the existing agent boundary exactly (Phase 4 §17):

```text
operator question
        ↓
read-only agent tool            (bounded registry; no free-form SQL)
        ↓
bounded structured query        (keyed lookup / filtered range / aggregate)
        ↓
minimal relevant records        (pagination + row caps; never whole tables)
        ↓
structured DTO                  (typed, versioned)
        ↓
agent/LLM rendering             (Copilot surface — currently disabled)
```

- The LLM must **not** receive unrestricted SQL access.
- The LLM must **not** receive entire tables (row caps + pagination are part of
  the tool contracts).
- Retrieval is read-only; see §17 for the non-negotiables.
- Where a dataset corresponds to an existing PostgreSQL operational table, import/
  use it **through that existing model** rather than building a parallel store.

## 10. Agent tool mapping

The existing Phase 4 §17.2 read-only registry (verbatim): `get_case(case_id)`,
`get_timeline(case_id)`, `get_decision_record(decision_id)`,
`explain_verdict(decision_id, candidate)`, `search_knowledge(query, top_k)`,
`get_model_status()`, `get_outcome_report(batch)`.
Copilot cannot: authorize/execute actions; modify constraints/config; mutate case
state; call PSPs; bypass policy; invent actions.

Dataset → tool wiring (tools stay bounded; each returns a typed DTO):

| Tool | Backing datasets | Bounded access pattern |
|---|---|---|
| `get_case(case_id)` | `recovery_cases` + `customers` + `subscriptions` | keyed lookup by `case_id` → join to customer/subscription context; single case bundle |
| `get_timeline(case_id)` | `recovery_events` (+ `payment_attempts` markers) | `case_id` + `case_seq` ordering, newest/oldest window, **paginated** |
| `get_decision_record(decision_id)` | `action_log` (+ `recovery_events` context) | keyed lookup; returns the stored record/atoms only |
| `explain_verdict(decision_id, candidate)` | `action_log` verdict atoms | stored verdict + rule ids + hashes; **no re-derivation, no invention** |
| `search_knowledge(query, top_k)` | `knowledge.*` only | pgvector/BM25 over reference documents — **never operational rows** |
| `get_model_status()` | gate/config state (unchanged) | no dataset wiring |
| `get_outcome_report(batch)` | existing aggregates (`/api/outcomes`, `/api/baselines` are the live precedents) | batch evaluation surface; stays evaluation-only |

## 11. Temporal / leakage rules

- **Historical retrieval must respect the time at which a decision occurred.**
  When explaining an earlier decision, the agent must not use future: outcomes,
  retries, state transitions, later events, or future customer responses.
- Every historical tool call takes (or derives) an **as-of timestamp**; event and
  attempt queries filter `occurred_at ≤ as_of` (event `case_seq` ordering must
  agree with the timestamp filter).
- **Decision explanations prefer the stored decision record and verdict atoms**
  already produced by the system (rule ids, hashes, p̂, EV components,
  deterministic trace) — these are immutable and inherently as-of-decision.
- Leakage checks are tests, not intentions (§14).

## 12. RAG vs operational-data boundary

Strict separation (existing architecture; D-027):

```text
Operational datasets  → structured PostgreSQL/Parquet retrieval (keyed, bounded)
Knowledge documents   → pgvector/BM25 knowledge retrieval (cited)
```

**Do NOT embed operational transaction rows into the knowledge index.** Routing
examples (exact behavior questions must follow):

- "Why was this case blocked?" → decision/verdict/structured retrieval
- "What happened to this case?" → case + event timeline retrieval
- "How many retries were already used?" → case/payment-attempt retrieval
- "What does the quiet-hours policy say?" → knowledge/RAG retrieval with citations

## 13. Implementation sequence for Antigravity

Do not redesign the existing architecture. Sequence:

1. Inspect all six Parquet schemas and sizes (deliver the §8 table).
2. Determine minimum retrieval fields per tool.
3. Create compact workspace-compatible JSON only where required (§7).
4. Preserve Parquet as canonical source (§5) with provenance records.
5. Import/use the data through the existing PostgreSQL operational model where
   appropriate (no parallel stores).
6. Add/adjust indexes only where genuinely needed (keyed lookups, timeline
   ordering) — no speculative indexing.
7. Connect the bounded read-only tools (§10) — no new authorities.
8. Return typed structured DTOs (versioned; documented).
9. Keep RAG and operational retrieval separate (§12).
10. Add focused retrieval tests (§14).
11. Verify temporal safety (as-of filtering).
12. Verify no leakage from prohibited datasets (§4).
13. Verify no mutation capability through retrieval tools (§17).

## 14. Testing requirements

Focused tests must cover, at minimum:

- customer lookup by case
- subscription lookup by case
- payment history retrieval
- chronological event retrieval
- action history retrieval
- correct case↔customer relationship
- pagination/limits (long histories; row caps)
- missing-record handling (typed not-found, never empty-success)
- temporal/deadline filtering (as-of correctness)
- unrelated-case isolation (one case's query cannot return another's rows)
- sidecar/counterfactual inaccessibility from every retrieval path
- read-only agent tools (registry is exactly the bounded set)
- no mutation through retrieval (all tool paths; DB-level verification)
- no full-table LLM context loading (assert row caps on every tool response)

Plus one **end-to-end verification**:

```text
Case → retrieval → structured context → agent/read tool → UI/Copilot surface
```

…without affecting the existing recovery decision pipeline (the 142-test battery
must still pass unchanged).

## 15. Definition of done

- §8 inspection table delivered; field choices traceable to it.
- Six datasets retrievable **only** through the bounded read-only tools, as typed
  DTOs, within row caps; Parquet provably canonical (unmodified; provenance
  recorded).
- Workspace stays within budget (report the final bundle size).
- All §14 tests pass; prohibited-source leakage tests prove the negative.
- Existing 142 tests pass unchanged; decision pipeline untouched.
- RAG index contains zero operational rows; knowledge search results unchanged.
- Documented in `DECISIONS.md` (new entries; no edits to closed decisions).

## 16. Known constraints / non-goals

- **Non-goals:** enabling the Ops Copilot (no LLM key — remains disabled);
  modifying schema semantics, ML artifacts, feature definitions, constraint
  engine, EV constants, gateway, frontend behavior, or existing APIs; adding
  write paths of any kind; new architecture.
- The Copilot surface may render structured tool output when enabled later, but
  no LLM key will be supplied for this task.
- Sandbox/receiving-workspace limits (≈25 MB) may force PG-hosted retrieval over
  JSON extracts for the largest tables — that is the preferred outcome, not a
  failure.
- The six Parquet datasets are historical/dataset-built; live PG operational data
  remains authoritative for current cases. Where both exist, retrieval must
  prefer live PG and clearly label dataset-sourced context.

## 17. Non-negotiable safety (restated verbatim from the task contract)

The retrieval layer does **NOT**:

- authorize actions
- execute payment actions
- modify case state
- modify constraints
- expand candidate actions
- bypass the ConstraintEngine
- bypass the Execution Gateway
- modify ML feature definitions
- inject retrieved operational rows directly into the ML model

ML remains:

```text
shared feature builder → contract validation → ScorerPort → probability → EV
```

Agent/runtime retrieval remains separate.
