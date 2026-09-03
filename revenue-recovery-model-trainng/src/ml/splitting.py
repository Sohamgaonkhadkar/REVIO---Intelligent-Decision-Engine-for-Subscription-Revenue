# src/ml/splitting.py
import os
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

def create_leakage_safe_splits(df, group_col='case_id', out_dir="data/ml_splits", seed=42):
    os.makedirs(out_dir, exist_ok=True)
    
    gss_test = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_val_idx, test_idx = next(gss_test.split(df, groups=df[group_col]))
    
    df_train_val = df.iloc[train_val_idx].reset_index(drop=True)
    df_test = df.iloc[test_idx].reset_index(drop=True)
    
    gss_val = GroupShuffleSplit(n_splits=1, test_size=0.125, random_state=seed) # 0.125 of 0.8 is 0.1
    train_idx, val_idx = next(gss_val.split(df_train_val, groups=df_train_val[group_col]))
    
    df_train = df_train_val.iloc[train_idx]
    df_val = df_train_val.iloc[val_idx]
    
    df_train.to_csv(os.path.join(out_dir, "train.csv"), index=False)
    df_val.to_csv(os.path.join(out_dir, "validation.csv"), index=False)
    df_test.to_csv(os.path.join(out_dir, "test.csv"), index=False)
    
    return df_train, df_val, df_test