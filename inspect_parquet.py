import pandas as pd
import pyarrow.parquet as pq
import os
import json

data_dir = r"C:\Users\Soham\Documents\revenue-recovery-deployment\uploads\runtime_data"
files = [
    "customers.parquet",
    "subscriptions.parquet",
    "payment_attempts.parquet",
    "recovery_cases.parquet",
    "recovery_events.parquet",
    "action_log.parquet"
]

results = {}

for f in files:
    filepath = os.path.join(data_dir, f)
    if not os.path.exists(filepath):
        continue
    
    file_size = os.path.getsize(filepath)
    df = pd.read_parquet(filepath)
    
    schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
    row_count = len(df)
    
    cardinalities = {}
    null_rates = {}
    
    for col in df.columns:
        if "id" in col.lower() or "seq" in col.lower():
            cardinalities[col] = df[col].nunique()
            null_rates[col] = df[col].isnull().sum() / row_count if row_count > 0 else 0

    results[f] = {
        "file_size_bytes": file_size,
        "row_count": row_count,
        "schema": schema,
        "key_cardinalities": cardinalities,
        "key_null_rates": null_rates
    }

with open("parquet_inspection.json", "w") as out:
    json.dump(results, out, indent=2)

print("Done inspecting.")
