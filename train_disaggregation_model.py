#!/usr/bin/env python
"""
Train NILM disaggregation models (Random Forest, XGBoost, Gradient Boosting,
Temporal Ensemble). Usage: python train_disaggregation_model.py
"""

import json
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor

sys.path.insert(0, ".")

from ml.feature_engineering import (
    FEATURE_COLS_DISAGG,
    TARGET_COLS_DISAGG,
    build_training_frame_disaggregation,
    build_training_frame_temporal,
)
from ml.model_registry import save_model
from database.dal import save_model_metrics, init_schema
from utils.data_loader import initialize_data

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False


def evaluate_model(y_true, y_pred) -> dict:
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


import time

def train_classic_models():
    """Train classic multi-output regressors (RF, GB, XGBoost) on full dataset."""
    print("Fetching training dataset for Energy Disaggregation...")
    df = build_training_frame_disaggregation()
    if df.empty or len(df) < 200:
        print("Insufficient training data. Run data generation first.")
        return

    # Dataset Verification
    total_records = len(df)
    consumers = df["consumer_id"].unique()
    num_consumers = len(consumers)
    counts = df["consumer_id"].value_counts()
    min_samples = counts.min()
    max_samples = counts.max()
    avg_samples = counts.mean()

    print("\n--- Training Dataset Summary ---")
    print(f"Total training records: {total_records:,}")
    print(f"Number of consumers represented: {num_consumers}")
    print(f"Minimum samples per consumer: {min_samples}")
    print(f"Maximum samples per consumer: {max_samples}")
    print(f"Average samples per consumer: {avg_samples:.1f}")

    if num_consumers < 10:
        print("WARNING: Insufficient consumer representation. Aborting.")
        return

    # Verify Appliances
    appliance_targets = [col for col in df.columns if col.startswith("target_")]
    print(f"Appliance categories represented: {len(appliance_targets)}")
    
    # Check for NaN features
    missing_vals = int(df[FEATURE_COLS_DISAGG].isna().to_numpy().sum())
    if missing_vals > 0:
        print(f"WARNING: Found {missing_vals} missing values in features. Filling with 0.")

    X = df[FEATURE_COLS_DISAGG].fillna(0).values
    y = df[TARGET_COLS_DISAGG].fillna(0).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    models = {
        "disaggregation_random_forest.pkl": MultiOutputRegressor(
            RandomForestRegressor(n_estimators=80, max_depth=12, random_state=42, n_jobs=-1)
        ),
        "disaggregation_gradient_boosting.pkl": MultiOutputRegressor(
            GradientBoostingRegressor(n_estimators=60, max_depth=5, random_state=42)
        ),
    }
    if HAS_XGB:
        models["disaggregation_xgboost.pkl"] = MultiOutputRegressor(
            XGBRegressor(n_estimators=80, max_depth=6, learning_rate=0.08, random_state=42, n_jobs=-1)
        )

    results = []
    best_name, best_r2, best_model = None, -1.0, None
    for fname, model in models.items():
        start_t = time.time()
        model.fit(X_train, y_train)
        t_time = round(time.time() - start_t, 2)
        
        pred = model.predict(X_test)
        pred = np.clip(pred, 0, None)
        row_sum = pred.sum(axis=1, keepdims=True)
        row_sum[row_sum == 0] = 1
        pred = pred / row_sum * 100

        metrics = evaluate_model(y_test, pred)
        metrics["training_time"] = t_time
        path = save_model(model, fname)
        
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
            "features": FEATURE_COLS_DISAGG,
            "targets": TARGET_COLS_DISAGG,
            "prediction_values": pred_vals,
            "ground_truth_values": gt_vals,
            "residuals": residuals,
            "absolute_errors": abs_errs
        })
        
        save_model_metrics(
            fname.replace(".pkl", ""),
            "disaggregation",
            metrics,
            len(X_train),
            details
        )
        results.append({"model": fname, "path": path, **metrics})
        print(f"Trained {fname} in {t_time}s: MAE={metrics['mae']:.2f} RMSE={metrics['rmse']:.2f} R²={metrics['r2']:.3f}")
        if metrics["r2"] > best_r2:
            best_r2 = metrics["r2"]
            best_name = fname
            best_model = model

    if best_model is not None:
        save_model(best_model, "disaggregation_model.pkl")
        print(f"Saved disaggregation_model.pkl (best: {best_name}, R²={best_r2:.3f})")

    return results



def train_all():
    init_schema()
    if initialize_data().get("message", "").startswith("Loaded"):
        print(initialize_data()["message"])

    print("=== Classic Models (RF, GB, XGBoost) ===")
    train_classic_models()


if __name__ == "__main__":
    train_all()
