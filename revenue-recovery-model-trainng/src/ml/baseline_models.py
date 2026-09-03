# src/ml/baseline_models.py
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

def get_logistic_baseline(preprocessor):
    return Pipeline([
        ('preprocessor', preprocessor),
        ('clf', LogisticRegression(max_iter=1000, random_state=42))
    ])

def get_tree_baseline(preprocessor):
    # Native support for missing values and non-linear interactions
    return Pipeline([
        ('preprocessor', preprocessor),
        ('clf', HistGradientBoostingClassifier(random_state=42, max_iter=100))
    ])