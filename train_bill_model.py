#!/usr/bin/env python
"""Train bill prediction regressors. Usage: python train_bill_model.py"""

import json
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, ".")

from ml.feature_engineering import FEATURE_COLS_ANOMALY
from ml.model_registry import save_model
from database.dal import save_model_metrics, init_schema
from utils.data_loader import initialize_data, get_readings_dataframe

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

TARIFF = 8.5


def build_bill_frame() -> pd.DataFrame:
    feat = initialize_data()
    from ml.feature_engineering import build_training_frame_anomaly
    df = build_training_frame_anomaly()
    if df.empty:
        return df
    df["target_bill"] = df["daily_kwh"] * TARIFF * 1.23  # incl. surcharges simplified
    return df


def reg_metrics(y_true, y_pred) -> dict:
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_all():
    init_schema()
    initialize_data()
    from ml.feature_engineering import build_training_frame_anomaly
    df = build_training_frame_anomaly()
    if df.empty:
        return

    X = df[FEATURE_COLS_ANOMALY].fillna(0).values
    y = (df["daily_kwh"] * TARIFF * 1.23).values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        "bill_linear_regression.pkl": LinearRegression(),
        "bill_random_forest.pkl": RandomForestRegressor(n_estimators=80, random_state=42),
    }
    if HAS_XGB:
        models["bill_xgboost.pkl"] = XGBRegressor(n_estimators=80, random_state=42)

    import time
    for fname, model in models.items():
        start_t = time.time()
        model.fit(X_train, y_train)
        t_time = round(time.time() - start_t, 2)
        pred = model.predict(X_test)
        m = reg_metrics(y_test, pred)
        m["training_time"] = t_time
        save_model(model, fname)
        
        # Extract evaluation arrays for visualization (sample up to 500 points)
        flat_y = y_test.flatten()
        flat_pred = pred.flatten()
        sample_size = min(500, len(flat_y))
        
        if len(flat_y) > 500:
            indices = np.random.choice(len(flat_y), sample_size, replace=False)
        else:
            indices = np.arange(len(flat_y))
            
        gt_vals = [round(float(x), 2) for x in flat_y[indices]]
        pred_vals = [round(float(x), 2) for x in flat_pred[indices]]
        residuals = [round(p - g, 2) for p, g in zip(pred_vals, gt_vals)]
        abs_errs = [abs(r) for r in residuals]

        details = json.dumps({
            "algorithm": model.__class__.__name__,
            "artifact_name": fname,
            "model_version": "v1.0.0",
            "training_time": t_time,
            "training_samples": len(X_train),
            "testing_samples": len(X_test),
            "dataset_size": len(X_train) + len(X_test),
            "features": FEATURE_COLS_ANOMALY,
            "prediction_values": pred_vals,
            "ground_truth_values": gt_vals,
            "residuals": residuals,
            "absolute_errors": abs_errs
        })
        
        save_model_metrics(fname.replace(".pkl", ""), "bill", m, len(X_train), details)
        print(fname, m)

    save_model(models["bill_random_forest.pkl"], "bill_model.pkl")


if __name__ == "__main__":
    train_all()
