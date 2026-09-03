# src/ml/features.py
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline

def build_preprocessor(df, exclude_cols):
    features = [c for c in df.columns if c not in exclude_cols]
    
    num_cols = df[features].select_dtypes(include=['int64', 'float64']).columns.tolist()
    cat_cols = df[features].select_dtypes(include=['object', 'category']).columns.tolist()
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), num_cols),
            ('cat', OneHotEncoder(handle_unknown='ignore'), cat_cols)
        ])
    
    return preprocessor, features