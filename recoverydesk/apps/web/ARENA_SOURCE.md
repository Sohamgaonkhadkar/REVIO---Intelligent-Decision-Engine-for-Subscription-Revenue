# REVIO

A light-first, softly luminous blue revenue intelligence frontend. The app opens directly into an image-led financial overview, with an optional persistent deep-navy theme.

## Run

```sh
npm install
npm run dev
npm run build
```

The app requires no API keys, authentication, remote backend, or external font service. Fonts are bundled locally.

## Workspace

- Overview: a luminous photographic hero, linked cohort ranges, Revenue Pulse, Recovery River, photographic recovery stories, recorded event playback, and honest baseline comparisons.
- Recovery Cases: search, filters, saved views, keyboard row navigation, density, pagination, drawers, clipboard actions, and filtered CSV export.
- Case Investigation: eight-stage replay, permitted and blocked candidate evidence, expected-value cost allocations, recovery-window exploration, and expandable journal records.
- Decision Studio: five-stage replay with speed controls and an educational Scenario Playground using predefined snapshots, including a draggable before/after comparison.
- Revenue Analytics: timing, failure classes, payment rails, action mix, escalations, financial flow, and baselines.
- Knowledge & Rules: recorded permission snapshots and searchable internal reference documentation.
- Audit Trail and System & Trust: searchable evidence, schema and fallback disclosures, local consistency diagnostics, and JSON exports.
- Ctrl/Cmd+K command palette, collapsible sidebar, mobile navigation, persistent Focus Mode, Presentation Mode, optional four-step product tour, and reduced-motion support.

## Data Boundary

All 20 customer/payment cases, all 120 journal records, model estimates, rule snapshots, and outcomes are synthetic. No XGBoost model, PostgreSQL database, FastAPI service, or payment rail is connected. Simulation labels remain visible throughout the workspace.

Scenario Playground selects precomputed illustrative snapshots. It does not run arbitrary model inference, execute financial actions, modify cases, or provide authoritative compliance enforcement. Scores are explicitly uncalibrated.

Photography is supplied through stable Pexels CDN URLs and is credited in captions. Payment imagery is contextual only; it does not depict UPI AutoPay mandate execution or a connected banking integration.

`src/data/simulation.ts` contains the synthetic ledger. `src/data/workspace.ts` contains cohort projections, replay, cost allocations, and reporting helpers. `src/state/Workspace.tsx` manages interface state. These boundaries can be replaced with authoritative API responses in a future integration.

Baseline fixtures use the same full-batch risk cohort and change only with the rail selector. The Card SI fixture deliberately shows B2 outperforming REVIO. REVIO recovered value and modeled cost reconcile with the ledger. The analytics date selector filters cases by original failure time.

## Verification

```sh
npx tsc --noEmit
node tests/data-integrity.mjs
```

With the dev server running on port 5173:

```sh
npx playwright install --with-deps chromium
node tests/interactions.mjs
node tests/visual-check.mjs
```

Interaction tests cover linked metrics, chart inspection, replay, scenario selection, case filtering, saved views, exports, nested dialog focus behavior, command search, theme/sidebar persistence, audit evidence, diagnostics, the product tour, and mobile navigation.

The visual check captures all destinations and checks horizontal overflow at 1440, 1280, 1024, 768, and 390 pixels. Screenshots are written to `artifacts/`.
