# src/ml/metrics.py
import json
import os
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report

def evaluate_model(model, X_test, y_test, name, out_dir="reports/baseline"):
    os.makedirs(out_dir, exist_ok=True)
    
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        "roc_auc": roc_auc_score(y_test, y_prob),
        "pr_auc": average_precision_score(y_test, y_prob),
        "report": classification_report(y_test, y_pred, output_dict=True)
    }
    
    with open(os.path.join(out_dir, f"{name}_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)