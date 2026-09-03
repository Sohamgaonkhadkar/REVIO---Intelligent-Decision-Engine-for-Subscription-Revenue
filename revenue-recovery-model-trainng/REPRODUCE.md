# Reproduce Dataset V1

```
python3 -m venv .venv && pip install -r requirements.txt
python3 scripts/run_dataset_v1.py
pytest -q
```

Determinism: master seed 20260823, sim_version stamped into every parquet + manifest.
All stochastic draws route through content-addressable keyed streams
(`recoverysim.random.keyed`), so the same inputs produce byte-identical parquet files
(verify with the sha256 hashes in `metadata_manifest.json`).

Reference data: download `skullagos5246/upi-transactions-2024-dataset` (Kaggle, CC0) into
`data/reference/` (not shipped — the 250k-row CSV is only used to build the measured
profile JSON).
