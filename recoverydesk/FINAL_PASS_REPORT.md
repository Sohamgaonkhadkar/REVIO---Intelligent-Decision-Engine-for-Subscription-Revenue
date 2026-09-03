# Final Product-Quality Pass — Report

Date: 2026-08-28 (sim cohort live at time of writing). This report follows the
requested A–G structure and does not claim "tests pass ⇒ done."

---

## A. Exact proof that the supplied XGBoost JSON artifact is the live scorer

`scripts/verify_model_runtime.py` — **19/19 checks PASS** against the real
application runtime (the API's own `_scorer` object, a live case from
PostgreSQL, production journal rows). Full output: `artifacts/reports/model_runtime_verification.md`.

| # | Evidence | Result |
|---|---|---|
| 1 | Artifact path via the app's own resolver | `/home/user/uploads/xgboost_native_categorical_c5.json` (registered as `artifacts/models/c5/...`, sandbox fallback) |
| 2 | File exists | 25,407,466 bytes |
| 3 | SHA-256 computed independently (hashlib) | `9434606cd1e443e3…` — matches registry |
| 4 | Independent `xgboost.Booster` load of the same JSON | 32 features · **1,256 trees** · gbtree · `binary:logistic`; app bundle carries a real Booster, not a stub |
| 5 | Activation gate (live scorer report) | **16/16 checks pass**, reason empty |
| 6 | Feature contract ↔ artifact schema | 32 names, identical order |
| 7 | Categorical configuration | 12 'c'-typed columns in the model == 12 in the schema |
| 8 | Real inference on a live case | `sim:upi_autopay:5a89ebd3f4bb`, 2 legal candidates scored, `model_id=c5-xgboost-native-categorical v1.0.0` |
| 9 | **Independent prediction parity** — same feature rows, same vocab encoding, my own Booster | max \|Δp̂\| = **0.00e+00** (bit-identical) |
| 10 | p̂ lands in the decision record | chosen `RETRY@W11_14` p̂=0.0347 in the atom; `policy=ml-ev-v1`, `fallback=False` |
| 11 | EV layer consumes exactly that p̂ | expected_gain = p̂·₹1,499·0.75 = 39.05, ev = −1.95 (recomputed, Δ<0.01) |
| 11b | Production journal audit | **277 scored journaled atoms re-verified**: EV ≡ p̂·₹·margin − costs, max Δ = 0.0000 |
| 12 | Journal identity | 68 decision records carry `c5-xgboost-native-categorical` (0 flagged fallback; "none" records are all-candidates-denied cycles — fail-closed, honest) |

**Failure path (production artifact untouched):**
- F1 — schema-order tamper → gate fails (`feature_names_compatible`, `feature_order_compatible`) → scorer refuses activation → `doctrine-fallback`, explicit reason, decision stamped `policy=doctrine-b2, fallback=true`.
- F2 — unavailable artifact → `model_loaded` fails → fallback.
- F3 — under fallback, a budget-exhausted snapshot still denies retries (`R-BUDGET-RETRY-1P3`, 3 denied atoms). **Constraints never depend on the model.**

The manifest name is never used as proof — every link (file → hash → Booster →
DMatrix → p̂ → atom → EV → journal) is verified, and the independent-load parity
check would catch any substitution.

## B. Exact UI changes

- **New visual system** (`styles.css`, fully rewritten): midnight-charcoal `#0A111A` base with layered surfaces, dark green-teal primary `#17B896`, money gold `#E8B75C`, restrained mint `#7FE4CB`; thin luminous borders; two static radial ambient glows; gold text-glow on recovered-₹; nav active state glows (inset bar + soft shadow); elevated cards (shadow + inset top highlight); inset panels; `prefers-reduced-motion` kills all animation; ambient day/dim set **once at load** from local hour (never flips mid-session); dark-mode favicon + brand mark retuned.
- **Overview**: hero composition — 66px gold-lit **₹ recovered** → at-risk → active opportunities → rate → compliance chips; `AT RISK → DECIDE → EXECUTE → RECOVER` pipeline strip with live counts; baseline bars with *what each baseline is*; **honest chips in whichever direction the data points**; timing-histogram insight (real replay evidence) explaining the leader; supporting analytics below.
- **CaseDetail**: hero band (₹ at risk, state, reason, rail, tier, budget ledger); **9-step journey where each step reveals one fact** ("92.4% for Retry in W08–11"-style, live values); **four layers as four questions** — *How likely is it to work? / Are we allowed? / Is it worth doing? / Did we actually do it?*; chosen spotlight; "What the system refused to do"; candidate table with EV bars; deterministic trace collapsed.
- **Knowledge & Rules**: five named domains (Regulatory · PSP behaviour · Recovery doctrine · Operations · System documentation); **two worked questions** — "Can we retry this case right now?" (real engine, read-only) and "Why are quiet hours enforced?" (cited retrieval); the boundary card (decides vs explains); chunk counts demoted out of the headline.
- **Audit**: `TIME · EVENT · DECISION/ACTION · RESULT · COMPLIANT` rows; payloads/hashes behind per-row expandable evidence.
- **System & Trust**: six trust cells (MODEL ACTIVE · SCHEMA VERIFIED 32/12/20 · RULE PACKS VERIFIED · ENVIRONMENT SIMULATION · COMPLIANCE 0 VIOLATIONS · DATABASE HEALTHY); **Recovery Propensity Model** framed inside the engine (INPUT / OUTPUT / USED BY / **DOES NOT CONTROL** legality or execution) with benchmarks; full gate table, pack hashes, schema versions and the fallback path in collapsed *Technical details*.
- **Baselines**: replay now also emits per-class recovered ₹ and recovery-timing histograms; UI insight is computed from those (direction-agnostic copy); 120s TTL cache on `/api/baselines` (≈700ms → 3ms cached).

## C. Pages removed / demoted

- **Removed earlier this round and kept gone**: Ops Copilot (no page, no route, no CSS, no `/health` field — LLM messaging eliminated), Dashboard, Model page.
- **Demoted**: "System Status" → **System & Trust**, moved under an `EVIDENCE` group label below the four business destinations; technical detail collapsed inside it.
- Nav = `Overview · Recovery Cases · Outcomes · Knowledge & Rules ‖ EVIDENCE: System & Trust · Audit Trail`.

## D. Remaining bugs fixed this pass

1. `/health` queried a non-existent `migrations` table → silently reported "migrations applied: 0" (the embarrassing stat). Now queries `schema_migrations` → 6 versions, shown as "Schema ready — migrations applied in order: …".
2. Copilot remnants: `ops_copilot` field removed from `/health` (test updated to assert the env badge instead); dead `.copilot-off` CSS deleted.
3. Baseline endpoint inefficiency: 120s TTL cache (replay deterministic per population).
4. Scorer-gate depth restored (Part S-7): full 16-check gate table in a collapsible.
5. Horizontal overflow at 390px: timeline nowrap timestamps, baseline-row min grid, wide chips — fixed (all viewports now clean).
6. `verify_model_runtime.py` edge case: all-candidates-denied case produced an empty DMatrix — now scans for a case with ≥1 scoreable candidate.
7. Test env hazards (documented D-033): worker-vs-pytest race, wall-clock-dependent scoring test — both already fixed; suite re-verified green.
8. PG cluster repair after snapshot restore dropped `pg_filenode.map` + WAL: repaired via fresh-initdb map + `pg_resetwal` (cluster rolled back to an earlier consistent point; schema intact, then re-seeded).

## E. Tests / build results

- `npm run build` — green (SDK regenerated from the live 20-path OpenAPI).
- `pytest tests/` — **142/142** (worker stopped during the run, per the documented discipline).
- `node scripts/ui_sweep.mjs` — **74/74**, including 35 viewport checks and zero console/page errors; run twice against two different live populations (honest chips verified in *both* directions).
- `python3 scripts/verify_model_runtime.py` — **19/19** (report at `artifacts/reports/model_runtime_verification.md`).
- Computed-style visual-proxy audit: body bg `rgb(10,17,26)`, hero 66px with gold glow, nav active glow, 0 white surfaces, reduced-motion → transitions 0s.

## F. Viewport checks (Playwright, per page × per size)

| Size | Pages checked (/, /cases, /cases/:id, /outcomes, /knowledge, /system, /audit) |
|---|---|
| 1440×900 | no h-overflow, all content checks pass |
| 1280×800 | clean |
| 1024×768 | clean (queue/audit columns reflow via `.q-hide-m`) |
| 768×1024 | clean (sidebar intact, grids collapse) |
| 390×844 | clean (sidebar → horizontal scroll nav, pipeline wraps 2×2, chips wrap, 44px controls) |

Screenshots captured to `artifacts/reports/shots/` (overview/case/knowledge/system/audit at 1440, overview/case at 390).

## G. Remaining weaknesses I would still criticize

1. **I could not see the interface.** This session has no vision; screenshots were
   captured, but every visual claim above rests on computed styles, geometry,
   contrast math and structure — not on eyes. A human should spend five minutes
   on the preview before the stakeholder demo.
2. **On the current live population RecoveryDesk trails both baselines mid-flight**
   (RD ₹3,892 vs B1 ₹11,890 vs B2 ₹16,685 at capture time): 6 cases were still
   open when the number was computed. The chips and histograms are honest and
   the gap genuinely reflects the salary-window timing story — but a cold
   evaluator sees RD losing until the worker resolves the open cases. The demo
   should run a few minutes ahead of the evaluator.
3. **Timing-insight copy is direction-conditional** — it explains "why B2 leads"
   or "where RD wins" from the same evidence, but the phrasing is written, not
   derived; edge-case populations could make it read oddly.
4. **The 120s baseline cache** means a just-injected cohort can shift the case
   population before the comparison updates (cache, not recompute). Acceptable,
   disclosed here, but noticeable on a live demo.
5. **Ambient day/dim is time-based only** (set at load); it ignores OS light/dark
   preference beyond `color-scheme: dark`. Deliberately conservative.
6. **Sandbox reality**: PG needed manual repair this session (snapshot dropped
   cluster files); if that recurs, `tools/pg_up.sh` + `pg_resetwal` is the
   recovery path, documented in D-034.
