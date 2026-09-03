# Final Information-Architecture + Product-Quality Correction — Report

Structure follows the requested A–L. The page-by-page value audit (PART 1) was
performed **before** any edit; it is section A and it drove every decision below.

---

## A. Page-by-page value audit (performed first, drives everything else)

Keep-tests: (1) helps user understand recovery · (2) helps evaluator validate the
solution · (3) provides meaningful trust/evidence · (4) enables a real product workflow.

| Page / section | Purpose | User question it answers | Product? | Evaluator? | Duplicates? | Verdict | Where its important info lives |
|---|---|---|---|---|---|---|---|
| **Overview** (hero, engine strip, baselines, insight, activity) | 30-second business story | "How much at risk/recovered? Compared to what? Compliant?" | Yes | Yes (₹ objective) | — | **KEEP** (entry point) | — |
| Overview · failure-class list | context for the queue | "why do payments fail here?" | mild | mild | partially (Outcomes has it with rates) | **DEMOTE** below the fold (kept: supports the story) | — |
| **Recovery Cases** (queue) | the work queue | "what needs recovering right now?" | Yes | Yes | — | **KEEP** | — |
| Cases · policy-id column | internal strategy label | none a user has | No | No | duplicates Case Detail policy chip | **REMOVE** (done) | Case Detail (human-language chip) |
| **Case Detail** (hero, journey, four layers, refusal table, evidence) | the product's hero | "why this action, was it legal, what happened?" | Yes | Yes (explainability) | — | **KEEP** | — |
| Case Detail · deterministic trace | byte-stable proof | "can I replay this decision?" | No | Yes | no | **KEEP COLLAPSED** (evidence, not primary) | — |
| **Outcomes** | business proof | "did it actually recover money?" | Yes | Yes (primary objective) | — | **KEEP** | — |
| Outcomes · baseline table + timing | honest comparison | "vs a normal retry strategy?" | Yes | Yes (Phase-2 §14/§15) | partially (Overview chips) | **KEEP both** (Overview = summary, here = full table; labelled differently) | — |
| **Knowledge & Rules** | two kinds of system knowledge | "what may the system do, and why?" | Yes | Yes (architecture boundary) | — | **KEEP** (reframed) | — |
| Knowledge · chunk/file counts | implementation metadata | none | No | No | — | **REMOVE from headline** (done; embedder id only, in context) | — |
| **Audit Trail** | journal as human evidence | "what exactly did it do? compliant?" | Yes | Yes (auditability) | — | **KEEP** | — |
| Audit · raw payloads | forensic depth | "prove it" | No | Yes | no | **KEEP expandable per row** | — |
| **System & Trust** · 6 trust cells | compact trust | "is it healthy/active/compliant?" | Yes | Yes | partially (sidebar env pill, Overview compliance chip — but gate/benchmark depth is unique) | **KEEP, demoted to quiet nav** | — |
| System & Trust · engine explainer | how decisions are made | "how does it choose?" | Yes | mild | overlaps Case Detail layers (there: per-case; here: in general) | **KEEP as compact 4-step strip** (added) | — |
| System & Trust · model block + benchmarks | model evidence | "is the model real and measured?" | No | Yes | no (unique) | **KEEP**, benchmarks visible, gate expandable | — |
| System & Trust · migration listing | developer diagnostics | none | No | No | — | **REMOVE** (done; `/health` retains it for API consumers) | `/health` |
| System & Trust · rule-pack hashes | integrity evidence | "were rules tampered?" | No | Yes | no | **KEEP collapsed** | — |
| **EVIDENCE nav label** | organizing label | — | — | — | — | **REMOVE** (a label is not a destination; done) | — |
| Copilot / chatbot | — | — | — | — | — | already gone (verified: no page/route/CSS/health field) | — |

Audit conclusion: no page failed all four keep-tests, so nothing was deleted this
round — instead: one label removed, one column removed, one listing removed, counts
demoted, and two pages restyled as quiet secondary destinations. The architecture's
five responsibilities (prediction / legality / EV / execution / audit) already map to
*layers inside Case Detail*, not to separate pages — the IA now reflects that.

## B. Pages kept
Overview · Recovery Cases · Case Detail (hero) · Outcomes · Knowledge & Rules · Audit Trail · System & Trust (quiet).

## C. Pages merged
None merged wholesale (the audit found no full duplicates). Merged *content*:
- trust summary already appears contextually — sidebar footer (SIM pill + model active) and Overview compliance chip — so nobody navigates anywhere to learn "database healthy".
- "How the decision engine works" (new on System & Trust) deliberately repeats Case Detail's four layers *in general form* — one is the pattern, the other the instance.

## D. Pages demoted
- **Audit Trail** and **System & Trust**: quiet secondary nav style (12.5px, muted; `.navlink.sub`), listed after the four product destinations — no grouping label.
- Overview's failure-class list stays below the fold as supporting analytics.

## E. Pages removed
None this round (Copilot/Dashboard/Model were already removed in prior rounds and
verified absent: no routes, no `.copilot-off` CSS, no `/health` field, no console mentions).

## F. Where removed content went
- **EVIDENCE label** → nowhere (organizing chrome, not information).
- **Cases policy-id column** → Case Detail hero chip (human language: "ML + EV strategy").
- **System migration listing** → `/health` (`schema_versions`), which the API already exposes; the UI no longer surfaces developer diagnostics.
- **Knowledge chunk/file counts headline** → contextual mention of the embedder identity only.

## G. Visual improvements
- **The unreadable Outcomes RecoveryDesk row is fixed**: the light-theme leftover `#F0F7F4` row background (near-white behind off-white text in the dark theme) is replaced by `.rd-row` — 7% gold tint over dark, gold-tinted border, off-white text (computed ratio ≈ 11:1), bold ₹ in money gold.
- Contrast bump: `--ink-3` #74889A → #7F94A7 — table headers/eyebrows on elevated surfaces went from 4.38:1 (fail for small text) to ≈4.9:1; all eight accent/_status colours verified 7.6–11.6:1 on surfaces.
- Type floors raised: table headers and eyebrows 10.5px → 11px, card titles → 12px.
- Ambient control: hour-based switching **replaced** by a small sidebar toggle (persisted, respects `prefers-color-scheme` as the default, set pre-paint, never shifts while working; reduced-motion untouched).
- Nav active state, selected rows, and money glow retained — no new glow added (nothing extra glows).

## H. Bugs fixed
1. Outcomes RD row contrast (the reported bug — root cause: leftover light-theme inline style).
2. Table-header contrast on elevated surfaces (token bump).
3. Internal policy ids in the Cases queue (removed).
4. Migration listing on System & Trust (removed; misleading-implementation-statistic class).
5. EVIDENCE group label (removed).
6. Hour-based ambient switching (replaced with explicit user control per PART 13).
7. Environment revived after the session boundary (PG, pip deps, node_modules, Playwright browsers — no data loss: 26 cases intact).

## I. Model-runtime proof (re-run this round)
`scripts/verify_model_runtime.py` — **19/19 PASS** against the live runtime:
supplied `xgboost_native_categorical_c5.json` → resolver path → independent SHA-256
(`9434606cd1e4…`) → independent Booster (32 feats / 1,256 trees / `binary:logistic`) →
16/16 activation gate → live-case inference → **independent-prediction parity
max |Δp̂| = 0.00e+00** → p̂ in the decision atom → EV arithmetic re-verified on **180
journaled atoms (max Δ 0.0000)** → journal carries `c5-xgboost-native-categorical` ×28,
zero misflagged. Failure path F1–F3 re-verified (gate refuses → doctrine-fallback
flagged → constraints still deny, e.g. `R-BUDGET-RETRY-1P3`). Report:
`artifacts/reports/model_runtime_verification.md`.

## J. Test results
- `vite build` — green.
- `pytest tests/` — **142/142**, 0 failures.
- `node scripts/ui_sweep.mjs` — **78/78** (run twice), including the new IA checks
  (no EVIDENCE label, exactly 2 quiet secondary destinations, precise Outcomes
  labels, RD-row dark-highlight assertion), 35 viewport checks, zero console errors.

## K. Screenshot / viewport review
Fresh captures in `artifacts/reports/shots/` (overview / case / knowledge / outcomes /
system / audit at 1440×900; overview + case at 390×844). **Honesty note: this session
has no vision — I could not look at the PNGs.** Everything stated about the rendering
comes from the Playwright DOM/computed-style audits above (contrast ratios computed
per pair, per-element color/background assertions, overflow measurements at
1440/1280/1024/768/390). A human glance at the seven screenshots is the one remaining
cheap verification I'd still do before a stakeholder demo.

## L. Remaining weaknesses
1. **No human eyes on the final render** (see K) — same constraint as before, stated rather than hidden.
2. The live cohort still has open cases mid-flight; baseline comparisons read worst
   in the first minutes after seeding (disclosed by the UI, but demo timing matters).
3. "How the decision engine works" (System & Trust) and the four layers (Case Detail)
   overlap conceptually — intentional (pattern vs instance) but a critic could call it redundancy.
4. The ambient toggle is functional but visually minimal; no tooltips.
5. Sandbox fragility: every turn boundary wipes pip/npm/browser state and has twice
   damaged the PG cluster — revival is scripted (`tools/pg_up.sh`, README runbook),
   but a cold start still costs minutes.

---

## PART 18 self-test (first-time evaluator, no code knowledge)

1. **What problem does this solve?** Overview hero: "failed-payment recovery" brand, ₹ recovered from ₹ at risk. ✓
2. **How much at risk?** Hero line + chip. ✓
3. **How much recovered?** The 66px gold number. ✓
4. **How does it choose an action?** Engine strip + System & Trust "how the engine works" + Case Detail journey steps 3–5. ✓
5. **Why legal?** Journey step 3 (permitted/blocked counts) + "What the system refused to do" + layer 2 ("Are we allowed to do it?"). ✓
6. **Why selected?** Layer 3 + chosen spotlight (p̂, EV, reason code). ✓
7. **Did it execute?** Layer 4 + Execution & attempts table. ✓
8. **What happened afterward?** Journey step 8 + audit timeline. ✓
9. **Can I prove it?** Audit Trail rows + collapsed payloads + deterministic trace. ✓
10. **Is the ML actually live?** Sidebar "Model active" + System & Trust MODEL ACTIVE cell + (deep) 19-check runtime script. ✓
11. **What if the model fails?** System & Trust collapsed "if the model cannot run" — fallback named, flagged, constraints unaffected. ✓
12. **Vs a normal retry strategy?** Overview baseline bars + Outcomes full table, honest in both directions. ✓

All twelve are answerable from Overview → Case Detail → Outcomes (with System & Trust
one quiet click away for 10–11). The hierarchy was left as-is where it already
answered, and corrected where it didn't.
