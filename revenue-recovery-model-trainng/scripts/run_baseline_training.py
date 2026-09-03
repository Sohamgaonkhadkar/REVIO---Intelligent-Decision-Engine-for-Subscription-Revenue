import sys
import os
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
import json
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report

# Ensure imports work from the src directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.data_loader import load_datamart
from src.ml.splitting import create_leakage_safe_splits

def build_preprocessor(df, features):
    # Dynamically select numeric and categorical columns from the allowed features
    num_cols = df[features].select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    cat_cols = df[features].select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), num_cols),
            ('cat', OneHotEncoder(handle_unknown='ignore'), cat_cols)
        ])
    
    return preprocessor

def evaluate_model(model, X_test, y_test, name, out_dir="reports/baseline"):
    os.makedirs(out_dir, exist_ok=True)
    
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "pr_auc": float(average_precision_score(y_test, y_prob)),
        "report": classification_report(y_test, y_pred, output_dict=True)
    }
    
    with open(os.path.join(out_dir, f"{name}_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

if __name__ == "__main__":
    # Load the actual datamart
    df = load_datamart()
    
    # 1. Define the target variable
    # In survival/uplift formats, censored = 0 means the event (recovery) occurred.
    df['is_success'] = (df['censored'] == 0).astype(int)
    target = 'is_success'
    
    # 2. Exclude IDs, timestamps, and post-decision leakage variables
    leakage_and_ids = [
        'case_id', 'subscription_id', 'customer_id', 
        'decision_ts_h', 'exec_ts_h', 
        'logging_policy', 'censored', 'response_kind',
        'exec_delay_hours', 'exec_hour_of_day', 'exec_day_of_month', 'exec_in_salary_cluster',
        target
    ]
    
    # The remaining columns are our safe predictive features
    feature_cols = [c for c in df.columns if c not in leakage_and_ids]
    
    print("Splitting data securely by case_id...")
    train, val, test = create_leakage_safe_splits(df, group_col='case_id')
    
    X_train, y_train = train[feature_cols], train[target]
    X_test, y_test = test[feature_cols], test[target]
    
    print("Building pipelines...")
    preprocessor = build_preprocessor(train, feature_cols)
    
    lr_model = Pipeline([
        ('preprocessor', preprocessor),
        ('clf', LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced'))
    ])
    
    gb_model = Pipeline([
        ('preprocessor', preprocessor),
        ('clf', HistGradientBoostingClassifier(random_state=42, max_iter=100))
    ])
    
    print("Training Logistic Regression...")
    lr_model.fit(X_train, y_train)
    evaluate_model(lr_model, X_test, y_test, "logistic_regression")
    
    print("Training Gradient Boosting...")
    gb_model.fit(X_train, y_train)
    evaluate_model(gb_model, X_test, y_test, "gradient_boosting")
    
    print("Training complete. Metrics saved to reports/baseline/")