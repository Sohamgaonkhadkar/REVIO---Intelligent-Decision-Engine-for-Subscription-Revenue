# src/ml/audit.py
import os
import json
import pandas as pd

def generate_audit(df, output_dir="reports/ml_audit", docs_dir="docs"):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)
    
    # 1. Identify Column Groups
    id_cols = [c for c in df.columns if c.endswith('_id')]
    ts_cols = [c for c in df.columns if c.endswith('_ts') or c.endswith('_ts_h')]
    
    # Potential leakage/future columns
    leakage_cols = ['case_outcome', 'recovered_amount_inr', 'resolution', 
                    'closed_ts_h', 'time_to_recovery_h', 'response_kind']
    leakage_present = [c for c in leakage_cols if c in df.columns]
    
    target_col = 'label_success' if 'label_success' in df.columns else 'recovered_flag'
    action_cols = ['action_type', 'channel']
    
    feature_cols = [c for c in df.columns if c not in id_cols + ts_cols + leakage_present + [target_col]]

    # 2. Summaries
    summary = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "missing_values": df.isnull().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum())
    }
    
    distributions = {
        "target_distribution": df[target_col].value_counts(normalize=True).to_dict() if target_col in df.columns else {},
        "action_distribution": df['action_type'].value_counts().to_dict() if 'action_type' in df.columns else {}
    }

    # 3. Write JSONs
    with open(os.path.join(output_dir, "dataset_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(output_dir, "feature_audit.json"), "w") as f:
        json.dump({"features": feature_cols, "ids": id_cols, "timestamps": ts_cols}, f, indent=2)
    with open(os.path.join(output_dir, "leakage_audit.json"), "w") as f:
        json.dump({"excluded_leakage_columns": leakage_present}, f, indent=2)
    with open(os.path.join(output_dir, "distribution_summary.json"), "w") as f:
        json.dump(distributions, f, indent=2)

    # 4. Generate Markdown
    md_content = f"""# ML Dataset Audit
    
**Row Unit:** A single recovery attempt/action taken at a specific timestamp.
**Prediction Target:** `{target_col}` (Probability of recovery given state and action).

### Excluded Columns (Leakage Risks)
{leakage_present}

### Features Available
{feature_cols}

### Recommendations
1. **Formulation:** Predict `P({target_col} | state, action)`.
2. **Splitting:** Group by `case_id` to prevent retry-leakage across train/val/test sets.
"""
    with open(os.path.join(docs_dir, "ML_AUDIT.md"), "w") as f:
        f.write(md_content)