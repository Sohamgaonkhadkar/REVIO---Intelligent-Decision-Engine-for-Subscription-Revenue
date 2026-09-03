# src/ml/data_loader.py
import pandas as pd
import os

def load_datamart(base_path="data/generated_csv"):
    mart_path = os.path.join(base_path, "ml_datamart.csv")
    if not os.path.exists(mart_path):
        raise FileNotFoundError(f"Datamart not found at {mart_path}")
    return pd.read_csv(mart_path)