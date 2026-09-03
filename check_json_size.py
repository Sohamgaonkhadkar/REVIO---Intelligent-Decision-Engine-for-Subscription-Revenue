import pandas as pd
import json
import os

df = pd.read_parquet(r"C:\Users\Soham\Documents\revenue-recovery-deployment\uploads\runtime_data\recovery_events.parquet")
json_data = df.to_json(orient="records")
print(f"recovery_events JSON size: {len(json_data) / 1024 / 1024:.2f} MB")
