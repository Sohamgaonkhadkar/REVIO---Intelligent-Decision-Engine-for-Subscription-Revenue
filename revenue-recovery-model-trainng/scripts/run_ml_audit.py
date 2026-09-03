# scripts/run_ml_audit.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.data_loader import load_datamart
from src.ml.audit import generate_audit

if __name__ == "__main__":
    df = load_datamart()
    generate_audit(df)
    print("Audit complete. Check docs/ML_AUDIT.md and reports/ml_audit/")