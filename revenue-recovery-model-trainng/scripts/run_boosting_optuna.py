
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import optuna
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

try:
    from lightgbm import LGBMClassifier
except ImportError as exc:
    raise ImportError("Install LightGBM first: pip install lightgbm") from exc

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260824
TARGET = "y"
GROUP = "case_id"
CV_SPLITS = 5
XGB_TRIALS = 25
LGB_TRIALS = 25

SPLIT_DIR = ROOT / "data" / "c4_splits"
REPORT_DIR = ROOT / "reports" / "c6_boosting_optuna"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

IDS = {"customer_id", "subscription_id", "case_id"}
POLICY = {"logging_policy"}
INTERVENTIONS = {"action_type", "channel"}

def load(name):
    p = SPLIT_DIR / f"{name}.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_csv(p, low_memory=False)

def eval_metrics(y, p):
    p = np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    y = np.asarray(y)
    return {
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "log_loss": float(log_loss(y, p)),
        "brier": float(brier_score_loss(y, p)),
    }

def feature_roles(train):
    cols = [c for c in train.columns if c not in IDS | POLICY | {TARGET}]
    cat = [c for c in cols if c in INTERVENTIONS or not pd.api.types.is_numeric_dtype(train[c])]
    num = [c for c in cols if c not in cat]
    return cols, num, cat

def prep(num, cat):
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num),
        ("cat", Pipeline([
            ("imp", SimpleImputer(strategy="most_frequent")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
        ]), cat),
    ], remainder="drop")

def xgb_space(t):
    return {
        "n_estimators": t.suggest_int("n_estimators", 200, 900, step=100),
        "max_depth": t.suggest_int("max_depth", 3, 10),
        "learning_rate": t.suggest_float("learning_rate", 0.01, 0.20, log=True),
        "min_child_weight": t.suggest_int("min_child_weight", 1, 20),
        "subsample": t.suggest_float("subsample", 0.60, 1.00),
        "colsample_bytree": t.suggest_float("colsample_bytree", 0.60, 1.00),
        "gamma": t.suggest_float("gamma", 0.0, 5.0),
        "reg_alpha": t.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
        "reg_lambda": t.suggest_float("reg_lambda", 1e-3, 20.0, log=True),
    }

def lgb_space(t):
    return {
        "n_estimators": t.suggest_int("n_estimators", 200, 900, step=100),
        "learning_rate": t.suggest_float("learning_rate", 0.01, 0.20, log=True),
        "num_leaves": t.suggest_int("num_leaves", 15, 160),
        "max_depth": t.suggest_int("max_depth", 3, 12),
        "min_child_samples": t.suggest_int("min_child_samples", 20, 200, step=10),
        "subsample": t.suggest_float("subsample", 0.60, 1.00),
        "colsample_bytree": t.suggest_float("colsample_bytree", 0.60, 1.00),
        "reg_alpha": t.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
        "reg_lambda": t.suggest_float("reg_lambda", 1e-3, 20.0, log=True),
    }

def tune_xgb(X, y, groups, num, cat):
    cv = StratifiedGroupKFold(CV_SPLITS, shuffle=True, random_state=SEED)
    def objective(t):
        params = xgb_space(t)
        scores = []
        for fold, (tr, va) in enumerate(cv.split(X, y, groups)):
            pp = prep(num, cat)
            A = pp.fit_transform(X.iloc[tr])
            B = pp.transform(X.iloc[va])
            model = XGBClassifier(**params, objective="binary:logistic",
                                  eval_metric="logloss", tree_method="hist",
                                  random_state=SEED + fold, n_jobs=1)
            model.fit(A, y.iloc[tr])
            p = model.predict_proba(B)[:, 1]
            scores.append(average_precision_score(y.iloc[va], p))
            t.report(float(np.mean(scores)), fold)
            if t.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(scores))
    s = optuna.create_study(direction="maximize",
                            sampler=optuna.samplers.TPESampler(seed=SEED),
                            pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=2))
    s.optimize(objective, n_trials=XGB_TRIALS)
    return s

def tune_lgb(X, y, groups, num, cat):
    cv = StratifiedGroupKFold(CV_SPLITS, shuffle=True, random_state=SEED)
    def objective(t):
        params = lgb_space(t)
        scores = []
        for fold, (tr, va) in enumerate(cv.split(X, y, groups)):
            pp = prep(num, cat)
            A = pp.fit_transform(X.iloc[tr])
            B = pp.transform(X.iloc[va])
            model = LGBMClassifier(**params, objective="binary",
                                   random_state=SEED + fold, n_jobs=1, verbosity=-1)
            model.fit(A, y.iloc[tr])
            p = model.predict_proba(B)[:, 1]
            scores.append(average_precision_score(y.iloc[va], p))
            t.report(float(np.mean(scores)), fold)
            if t.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(scores))
    s = optuna.create_study(direction="maximize",
                            sampler=optuna.samplers.TPESampler(seed=SEED + 1),
                            pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=2))
    s.optimize(objective, n_trials=LGB_TRIALS)
    return s

def fit_final(name, params, train, valid, test, num, cat, features):
    pp = prep(num, cat)
    A = pp.fit_transform(train[features])
    B = pp.transform(valid[features])
    C = pp.transform(test[features])
    if name == "xgboost":
        model = XGBClassifier(**params, objective="binary:logistic",
                              eval_metric="logloss", tree_method="hist",
                              random_state=SEED, n_jobs=1)
    else:
        model = LGBMClassifier(**params, objective="binary",
                               random_state=SEED, n_jobs=1, verbosity=-1)
    model.fit(A, train[TARGET])
    pv = model.predict_proba(B)[:, 1]
    pt = model.predict_proba(C)[:, 1]
    return eval_metrics(valid[TARGET], pv), eval_metrics(test[TARGET], pt)

def main():
    train, valid, test = load("train"), load("validation"), load("test")
    for name, df in [("train", train), ("validation", valid), ("test", test)]:
        if TARGET not in df.columns or df[TARGET].isna().any():
            raise ValueError(f"Bad target in {name}")
    features, num, cat = feature_roles(train)
    X, y, groups = train[features], train[TARGET].astype(int), train[GROUP]

    print("=" * 80)
    print("C6 — XGBoost + LightGBM + Optuna + 5-Fold StratifiedGroupKFold")
    print("=" * 80)
    print(f"Optimization metric: PR-AUC")
    print(f"CV grouping: {GROUP}")
    print(f"Trials: XGBoost={XGB_TRIALS}, LightGBM={LGB_TRIALS}")

    xs = tune_xgb(X, y, groups, num, cat)
    ls = tune_lgb(X, y, groups, num, cat)

    xv, xt = fit_final("xgboost", xs.best_params, train, valid, test, num, cat, features)
    lv, lt = fit_final("lightgbm", ls.best_params, train, valid, test, num, cat, features)

    comparison = pd.DataFrame([
        {"model": "xgboost", "cv_pr_auc": xs.best_value, **{f"validation_{k}": v for k,v in xv.items()},
         **{f"test_{k}": v for k,v in xt.items()}},
        {"model": "lightgbm", "cv_pr_auc": ls.best_value, **{f"validation_{k}": v for k,v in lv.items()},
         **{f"test_{k}": v for k,v in lt.items()}},
    ]).sort_values("validation_pr_auc", ascending=False)

    comparison.to_csv(REPORT_DIR / "boosting_comparison.csv", index=False)
    xs.trials_dataframe().to_csv(REPORT_DIR / "xgb_optuna_trials.csv", index=False)
    ls.trials_dataframe().to_csv(REPORT_DIR / "lgb_optuna_trials.csv", index=False)

    with open(REPORT_DIR / "best_params.json", "w", encoding="utf-8") as f:
        json.dump({
            "optimization_metric": "pr_auc",
            "xgboost": {"cv_pr_auc": xs.best_value, "params": xs.best_params},
            "lightgbm": {"cv_pr_auc": ls.best_value, "params": ls.best_params},
            "selection_rule": "Primary: CV PR-AUC and validation PR-AUC. Secondary: ROC-AUC, Log Loss, Brier. Test is final report only."
        }, f, indent=2)

    print("\n" + comparison.to_string(index=False))
    print(f"\nReports: {REPORT_DIR}")

if __name__ == "__main__":
    main()
