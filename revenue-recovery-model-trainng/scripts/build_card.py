"""Render the dataset card, reproduce guide, and ship zip for Dataset V1."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


def render_card(manifest: dict, validation: dict, sim: dict) -> str:
    c = manifest["counts"]
    checks = "\n".join(
        f"- [{'x' if r['passed'] else ' '}] `{r['check']}` {r['detail']}"
        for r in validation["results"])
    return f"""# AI Revenue Recovery — Dataset V1 ({manifest['dataset_version']})

Generated: {manifest['generated_timestamp_utc']} · sim_version {manifest['sim_version']} ·
seed {manifest['seed']} (deterministic; same inputs → byte-identical tables)

## What this is
A synthetic dataset for the **ML with Bandit-feedback** layer of the AI Revenue Recovery
System: learning the probability that a specific recovery intervention succeeds for a
failed subscription renewal, from logged policy decisions with uncertainty-preserving
censoring semantics. It is designed for training propensity/reward models and
offline-policy evaluation (IPS/DR), NOT for production claims.

## What is DATA-DERIVED vs ASSUMED
- DATA-DERIVED (tagged in `configs/registry/assumption_registry.yaml`): the 1+3 retry
  budget, INR 15,000 recurring cap, recurring-window rule (NPCI); demographic/state/
  bank/amount calibration and per-rail failure-rate anchors (measured from the Kaggle
  UPI 2024 reference corpus, profile in `data/reference/reference_upi_profile.json` —
  note the corpus has no failure reasons, so failure *mechanics* are assumptions).
- ASSUMED: segment mix, plan prices, channel response/self-pay/callback params, support
  costs and fees, outage intensity, mandate lifecycle hazards. All are versioned in
  `configs/` and the registry with sensitivity notes.

## Tables (grain)
| table | rows | grain |
|---|---|---|
| customers | {c['customers']} | one row per customer |
| subscriptions | {c['subscriptions']} | one row per subscription (1-2 per customer) |
| payment_attempts | {c['payment_attempts']} | one row per BASE renewal attempt |
| recovery_cases | {c['recovery_cases']} | one row per failed-renewal case × logging policy |
| recovery_events | {c['recovery_events']} | one row per case event (attempts, notifications, escalations) |
| action_log | {c['action_log']} | one row per label-bearing decision (RETRY / contacts) |
| case_outcomes | {c['case_outcomes']} | one row per case with resolution + recovered amount |
| ml_datamart | {c['ml_datamart']} | one row per label-bearing decision (training unit) |

## Label semantics (read before training)
- `y` in `ml_datamart` is the bandit reward:
  - RETRY rows → 1 iff that retry attempt succeeded.
  - CONTACT rows → 1 iff a qualifying positive response (self-paid, card updated,
    reactivated) arrived within 24h of execution.
- Rows with `censored=True` had their 24h response window truncated by the case horizon;
  exclude from training, keep for censoring-aware evaluation.
- The mart deliberately contains **no** feature computable only after decision time;
  salary-day is the merchant-visible NOISY `salary_day_proxy_dom`, not the latent truth.

## No leakage rules (enforced in code)
Every feature in the mart is a function of information with `ts < decision_ts_h`.
Latent sidecar fields (intent archetype, true cash-constrained ratio, true salary day,
outage truth) exist only in `data/generated/sidecar/` and are never joined.

## Missingness & censoring
`label_success` is never missing for labeled rows; `response_kind` is NULL for RETRY
rows; `closed_ts_h` is never NULL in V1 (horizon enforced; closure may exceed the horizon by up to 72h only for the last decision's response/escalation tail).

## Provenance & logging policies
{manifest['provenance_notes']['payment_attempts']}
Logging policies: B0_NONE (no intervention; case expires), B1_PSP_PROXY (PSP-style
fixed-cadence retries: UPI +1h / card +24h, one payment link on hard failures),
B2_DOCTRINE (static hand-written doctrine: salary-cluster timing for insufficient funds,
+4h retry for technical, hard classes -> pm-update/link, high-value escalation),
B3_RANDOM_LEGAL (uniform over the feasible action set). Shared latent processes
(sufficiency, outages, mandate hazards, jitter) are keyed by seed and identical across
runs; each subscription's FIRST renewal is byte-identical across policies. Later renewals
may diverge via instrument restorations performed by recovery actions (documented
closed-loop coupling) — compare policy cohorts accordingly. This is presented as logging policies for V1;
it does not replace propensity logging with randomized exploration (noted limitation).

## Validation gate
```
{checks}
```
Full machine-readable report: `eval/validation_report.json`.

## Known limitations
""" + "\n".join(f"- {x}" for x in manifest["known_limitations"]) + """

## License & use
Synthetic data. The reference corpus is CC0; this dataset is released for research/
prototyping of payment-recovery ML. Do not use simulated recovery rates as if they were
production measurements.
"""


def render_reproduce(sim: dict) -> str:
    return f"""# Reproduce Dataset V1

```
python3 -m venv .venv && pip install -r requirements.txt
python3 scripts/run_dataset_v1.py
pytest -q
```

Determinism: master seed {sim['seed']}, sim_version stamped into every parquet + manifest.
All stochastic draws route through content-addressable keyed streams
(`recoverysim.random.keyed`), so the same inputs produce byte-identical parquet files
(verify with the sha256 hashes in `metadata_manifest.json`).

Reference data: download `skullagos5246/upi-transactions-2024-dataset` (Kaggle, CC0) into
`data/reference/` (not shipped — the 250k-row CSV is only used to build the measured
profile JSON).
"""


def make_zip(repo: Path, name: str = "AI_REVENUE_RECOVERY_DATASET_V1.zip") -> Path:
    zip_path = repo / "dist" / name
    zip_path.parent.mkdir(exist_ok=True)
    include_roots = ["configs", "data", "docs", "scripts", "src", "tests",
                     "metadata_manifest.json", "REPRODUCE.md", "requirements.txt"]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for item in include_roots:
            p = repo / item
            if p.is_file():
                z.write(p, p.relative_to(repo))
            elif p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file() and "upi_transactions_2024.csv" not in f.name \
                            and "__pycache__" not in str(f) and f.suffix != ".zip":
                        z.write(f, f.relative_to(repo))
    return zip_path


def short_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
