from ml.feature_engineering import build_training_frame_disaggregation, FEATURE_COLS_DISAGG, TARGET_COLS_DISAGG
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from ml.model_registry import load_model
import numpy as np

df = build_training_frame_disaggregation()
print(f"Total rows: {len(df)}")
X = df[FEATURE_COLS_DISAGG].fillna(0).values
y = df[TARGET_COLS_DISAGG].fillna(0).values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"Training rows: {len(X_train)}")
print(f"Testing rows: {len(X_test)}")

model = load_model("disaggregation_random_forest.pkl")
if model is None:
    print("Model not found")
else:
    raw_pred = model.predict(X_test)
    print("Raw pred mean sum:", np.mean(np.sum(raw_pred, axis=1)))
    
    pred = np.clip(raw_pred, 0, None)
    rs = pred.sum(axis=1, keepdims=True)
    rs[rs == 0] = 1
    pred = pred / rs * 100
    
    print("R2 score raw:", r2_score(y_test, raw_pred))
    print("R2 score norm:", r2_score(y_test, pred))
