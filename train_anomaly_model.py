#!/usr/bin/env python
"""Train anomaly detection classifiers. Usage: python train_anomaly_model.py"""

import json
import sys

import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

sys.path.insert(0, ".")

from ml.feature_engineering import FEATURE_COLS_ANOMALY, build_training_frame_anomaly
from ml.model_registry import save_model
from database.dal import save_model_metrics, init_schema
from utils.data_loader import initialize_data

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False


def clf_metrics(y_true, y_pred) -> dict:
    if len(np.unique(y_true)) < 2 or len(np.unique(y_pred)) < 2:
        return {}
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def train_all():
    init_schema()
    initialize_data()

    df = build_training_frame_anomaly()
    if df.empty or len(df) < 50:
        print("Insufficient anomaly training data.")
        return

    X = df[FEATURE_COLS_ANOMALY].fillna(0).values
    y = df["label_anomaly"].values

    total_records = len(y)
    total_anomalies = int(np.sum(y == 1))
    total_normal = total_records - total_anomalies
    print("--- Dataset Distribution ---")
    print(f"Complete Dataset: Total={total_records}, Normal={total_normal}, Anomaly={total_anomalies}, Anomaly Pct={total_anomalies/total_records*100:.1f}%")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    train_anomalies = int(np.sum(y_train == 1))
    test_anomalies = int(np.sum(y_test == 1))
    print(f"Training Dataset: Total={len(y_train)}, Normal={len(y_train)-train_anomalies}, Anomaly={train_anomalies}, Anomaly Pct={train_anomalies/len(y_train)*100:.1f}%")
    print(f"Test Dataset: Total={len(y_test)}, Normal={len(y_test)-test_anomalies}, Anomaly={test_anomalies}, Anomaly Pct={test_anomalies/len(y_test)*100:.1f}%")

    from sklearn.metrics import confusion_matrix
    import time
    
    def get_details(model, fname, start_t, X_test, y_test, pred):
        try:
            cm = confusion_matrix(y_test, pred).tolist()
        except:
            cm = [[0,0],[0,0]]
        return json.dumps({
            "algorithm": model.__class__.__name__,
            "artifact_name": fname,
            "model_version": "v1.0.0",
            "training_time": round(time.time() - start_t, 2),
            "training_samples": len(X_train),
            "testing_samples": len(X_test),
            "dataset_size": len(X_train) + len(X_test),
            "confusion_matrix": cm,
            "features": FEATURE_COLS_ANOMALY
        })

    iso = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
    start_t = time.time()
    iso.fit(X_train)
    iso_pred = (iso.predict(X_test) == -1).astype(int)
    
    print("\nVerifying Labels Before Evaluation (Isolation Forest):")
    print("y_train unique:", np.unique(y_train, return_counts=True))
    print("y_test unique:", np.unique(y_test, return_counts=True))
    print("iso_pred unique:", np.unique(iso_pred, return_counts=True))
    
    save_model(iso, "anomaly_isolation_forest.pkl")
    iso_m = clf_metrics(y_test, iso_pred)
    if iso_m:
        details = get_details(iso, "anomaly_isolation_forest.pkl", start_t, X_test, y_test, iso_pred)
        save_model_metrics("isolation_forest", "anomaly", iso_m, len(X_train), details)
    print("Isolation Forest:", iso_m or "Not Available (Single Class)")

    rf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, class_weight="balanced")
    start_t = time.time()
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    save_model(rf, "anomaly_random_forest.pkl")
    rf_m = clf_metrics(y_test, rf_pred)
    if rf_m:
        details = get_details(rf, "anomaly_random_forest.pkl", start_t, X_test, y_test, rf_pred)
        save_model_metrics("random_forest", "anomaly", rf_m, len(X_train), details)
    print("Random Forest:", rf_m or "Not Available (Single Class)")
    if rf_m:
        print(classification_report(y_test, rf_pred, zero_division=0))

    xgb, xgb_pred, xgb_m = None, None, {}
    if HAS_XGB:
        xgb = XGBClassifier(n_estimators=80, max_depth=5, learning_rate=0.1, random_state=42)
        start_t = time.time()
        xgb.fit(X_train, y_train)
        xgb_pred = xgb.predict(X_test)
        save_model(xgb, "anomaly_xgboost.pkl")
        xgb_m = clf_metrics(y_test, xgb_pred)
        if xgb_m:
            details = get_details(xgb, "anomaly_xgboost.pkl", start_t, X_test, y_test, xgb_pred)
            save_model_metrics("xgboost", "anomaly", xgb_m, len(X_train), details)
        print("XGBoost:", xgb_m or "Not Available (Single Class)")

    # 3. Deep Learning Autoencoder (Unsupervised Reconstruction)
    X_normal = X_train[y_train == 0]
    if len(X_normal) > 10:
        ae = MLPRegressor(hidden_layer_sizes=(8, 4, 8), activation='relu', solver='adam', max_iter=500, random_state=42)
        ae.fit(X_normal, X_normal)
        save_model(ae, "autoencoder_anomaly.pkl")
        # Thresholding logic: flag the 5% worst reconstructions as anomalies
        mse = np.mean(np.square(X_test - ae.predict(X_test)), axis=1)
        ae_pred = (mse > np.percentile(mse, 95)).astype(int)
        print("Autoencoder (MLP) trained and saved.")

    candidates = [("random_forest", rf, rf_m), ("isolation_forest", iso, iso_m)]
    if xgb is not None:
        candidates.append(("xgboost", xgb, xgb_m))

    best = max(candidates, key=lambda c: c[2].get("f1", 0.0))
    save_model(best[1], "anomaly_model.pkl")
    print(f"Primary anomaly_model.pkl = {best[0]} (F1={best[2].get('f1', 0.0):.3f})")

    from models.anomaly_scanner import scan_and_persist_anomalies
    n = scan_and_persist_anomalies()
    print(f"Persisted {n} ML-detected anomalies to database")


if __name__ == "__main__":
    train_all()
