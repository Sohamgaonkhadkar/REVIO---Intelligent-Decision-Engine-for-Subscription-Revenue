# Arena frontend integration

The original Arena ZIP is the visual source. Its React components, complete CSS,
motion effects, typography, photographs, charts, recovery river, case drawers,
scenario comparisons, themes, command palette, focus mode, presentation mode,
tour and keyboard controls are retained in standalone simulation mode.

## Run and build

```sh
npm ci
npm run dev
npm run build
```

Build performs strict TypeScript checking and writes `spa/`, preserving the
existing FastAPI static build location. Generated output is not committed.
Photographs from the ZIP's Pexels URLs are bundled in `public/images`; the original
visible photo credits remain. Manrope and IBM Plex Mono are served locally.
React 19, Motion, Lucide, Fontsource and Tailwind 4 follow the supplied frontend.
TanStack Query is retained from the previous application for API request caching,
polling, cancellation and explicit errors. Vite is patched within version 7;
the ZIP's single-file bundler is removed so fonts and assets can be cached.

## Data boundary

The default build is **standalone educational simulation**, prominently disclosed
on every route. Its amounts, cases and predictions are authored ZIP fixtures,
not backend results. A failing backend is never replaced with those fixtures.

For the read-only backend workspace, set these public Vercel build settings:

```text
VITE_DATA_MODE=api
VITE_API_BASE_URL=https://YOUR-FASTAPI-ORIGIN
```

The origin must permit the frontend's CORS origin, or an operator can configure a
same-origin API reverse proxy and leave the base URL blank. The example origin is
a placeholder, not a deployed service. API mode uses the same luminous shell,
typography, motion, photography and theme, with dedicated evidence views. It does
not yet reproduce every rich fixture visualization against live data.

| Screen | Existing API read paths |
| --- | --- |
| Overview / Analytics | `/api/outcomes`, `/api/baselines`, `/api/events` |
| Cases | `/api/cases` with `q`, `state`, `rail`, `limit`, `offset` |
| Investigation | case detail, `/decisions`, `/intents`, `/events` |
| Decision Studio | link to recorded per-case replay, separate educational playground |
| Knowledge & Rules | `/api/constraints`, `/api/constraints/check`, `/api/knowledge`, `/api/knowledge/search` |
| Audit | `/api/events?limit=200`, per-case events up to 500 |
| System & Trust | `/health`, `/api/model` |

Recorded p-hat, EV, chosen action, rule verdicts, model/fallback metadata and exact
EV components are shown unchanged. Decisions are replayed in recorded order;
playback never executes an action. Null probabilities remain unscored. Backend
aggregate case-count recovery rates are labelled as such, distinct from the
fixture's monetary rate. Baselines retain their actual ordering, including losses.
API errors show the endpoint/status and a retry control. No browser operations key
is shipped; operational mutations remain outside this read-only integration.

## Mock-only and incompatible ZIP capabilities

| ZIP feature | Integration treatment |
| --- | --- |
| 20 synthetic cases, 120 authored journal records | Standalone fixtures only; API mode reads PostgreSQL-backed endpoints |
| Browser constraint evaluator and authored predictions | Educational only; API mode displays recorded verdicts and scores |
| Scenario sliders / recovery-window exploration | Predefined educational snapshots; never arbitrary backend inference |
| Fixed ₹6 retry / ₹1.8 contact / ₹450 escalation cost | Standalone only; API mode displays exact backend EV components |
| Proportional illustrative cost allocation | Standalone only; not substituted for backend cost components |
| Synthetic model identity / 32-field illustrative schema | Standalone only; API model metadata is shown separately |
| Fixed June 2026 time series and cohort fixtures | Standalone only; no invented live financial series |
| Rail-segmented fixture baselines | Standalone only; live endpoint provides full-population baseline results |
| Local integrity checks | Fixture consistency checks, not DB tamper verification or model activation proof |
| Saved views / CSV / rich drawers / recovery river | Original interactions preserved in standalone; API list has server search/filter/pagination and direct investigation |
| Global journal | Latest 200 API records, explicitly labelled; no claim of full-history export |

## Vercel

Project: `revio-luminous` under `gaonkhadkarsoham2006-5043`.
Repository root directory: `recoverydesk/apps/web`; build `npm run build`;
output `spa`. Explicit SPA rewrites cover UI routes only. `/api/*` and `/health`
are not rewritten to HTML. Legacy hash routes and direct nested UI paths work.

No stable backend origin was found in repository deployment configuration; the
documented local FastAPI port was not listening. This frontend release therefore
uses standalone simulation. FastAPI, PostgreSQL/pgvector, the worker, model runtime
and secure backend hosting remain required for full deployed integration.

The Vercel GitHub link was rejected because the account needs a GitHub Login
Connection. Source-file deployments through the authenticated connector are
supported; automatic Git-triggered deployments require that connection afterward.

## Verification commands

```sh
npm run build
npm run test:integrity
node tests/interactions.mjs
node tests/visual-check.mjs
```

Browser scripts use installed Chrome by default; set `PLAYWRIGHT_CHANNEL` to use
another channel. `BASE_URL` selects the local or deployed URL. The interaction
suite covers charts, replay, scenarios, drawers, clipboard, export, filtering,
saved views, themes, command palette, tour, mobile navigation and reduced motion.
Visual checks capture every main page and scan all routes at 1440, 1280, 1024,
768 and 390 pixels. Screenshots stay local in ignored `artifacts/`.

Start another dev server with `VITE_DATA_MODE=api` on port 5175 and run
`node tests/api-workflows.mjs`. This test stubs actual endpoint response shapes,
checks server query parameters, recorded values and failure isolation; it is not
a substitute for a running PostgreSQL integration test.

Backend regression attempts preserve the engine and activation gate. Constraint,
config and non-model EV checks pass. Model tests cannot activate without XGBoost;
the Windows worktree additionally exhibits artifact line-ending hash mismatches.
The original working directory exhibits the missing-XGBoost failures too. API/PG
test collection requires unavailable FastAPI dependencies and a running test DB.
These failures must not be reported as a successful complete backend regression.

## Verified integration results

- Production build and strict TypeScript check: passed.
- Fixture data integrity: 10/10 invariants passed.
- Arena interaction workflows: 20/20 groups passed locally and on the initial public deployment; no page errors.
- API contract workflows: passed against controlled responses, including search,
  pagination, recorded p-hat/EV, decision replay, intents, knowledge, audit, model
  metadata and backend failure without fixture fallback. Navigation produces no
  malformed case API paths.
- Final preview: all 8 direct routes and refresh passed; all 40 route/width
  combinations passed (1440/1280/1024/768/390); fonts and images loaded; no console
  errors, failed asset requests or horizontal overflow. `/api/outcomes` and
  `/health` returned 404, not the SPA.
- Backend targeted regression: 40 checks passed, 2 failed, 2 errored due to
  unavailable model activation. API/PG test collection was blocked by missing
  FastAPI; no stable running backend or test PostgreSQL was verified.
- Dependency audit after compatible fixes: 0 vulnerabilities.
- Backend, model, state machine, compliance and database source files: unchanged.

The ZIP's browser test text was stale in replay, drawer, tour and mobile navigation
selectors; assertions now use the actual supplied labels. Tablet hero margins and
minimum grid widths were adjusted to remove a 10px overflow while preserving the
visual composition. The API route transition key was stabilized to prevent exiting
pages from issuing requests with the next page's empty case ID.
