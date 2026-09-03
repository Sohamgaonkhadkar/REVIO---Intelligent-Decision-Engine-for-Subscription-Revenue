import pandas as pd

df = pd.read_parquet(r"C:\Users\Soham\Documents\revenue-recovery-deployment\uploads\runtime_data\action_log.parquet")

# Calculate JSON size for action_log
json_data = df.to_json(orient="records")
print(f"action_log JSON size: {len(json_data) / 1024 / 1024:.2f} MB")
