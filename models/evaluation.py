"""
Model evaluation — compare predictions vs ground truth for validation dashboard.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    r2_score,
)

from ml.feature_engineering import (
    FEATURE_COLS_ANOMALY,
    FEATURE_COLS_DISAGG,
    TARGET_COLS_DISAGG,
    build_training_frame_anomaly,
    build_training_frame_disaggregation,
)
from ml.model_registry import load_model
from models.anomaly_detector import AnomalyDetector
from models.disaggregation import EnergyDisaggregator
from models.ml_inference import MLAnomalyDetector, get_ml_disaggregator, ground_truth_appliance_pct
from utils.data_loader import get_readings_dataframe


# Cache for validation and AI dashboard results
_validation_cache = None
_validation_cache_time = None
_ai_cache = None
_ai_cache_time = None
_CACHE_TTL = 600  # 10 minutes


def get_dataset_stats() -> dict:
    """Get actual dataset statistics from the database."""
    from database.dal import query_df
    stats = {}
    try:
        row = query_df("SELECT COUNT(*) AS total FROM smart_meter_readings").iloc[0]
        stats["total_readings"] = int(row["total"])
    except Exception:
        stats["total_readings"] = 0
    try:
        row = query_df("SELECT COUNT(DISTINCT consumer_id) AS cnt FROM smart_meter_readings").iloc[0]
        stats["total_consumers"] = int(row["cnt"])
    except Exception:
        stats["total_consumers"] = 0
    try:
        row = query_df("SELECT COUNT(*) AS cnt FROM feature_engineering").iloc[0]
        stats["total_features"] = int(row["cnt"])
    except Exception:
        stats["total_features"] = 0
    try:
        dr = query_df("SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts FROM smart_meter_readings").iloc[0]
        stats["date_range_start"] = str(dr["min_ts"])[:10] if dr["min_ts"] else ""
        stats["date_range_end"] = str(dr["max_ts"])[:10] if dr["max_ts"] else ""
    except Exception:
        stats["date_range_start"] = ""
        stats["date_range_end"] = ""
    try:
        feat = query_df("SELECT COUNT(*) AS cnt FROM feature_engineering").iloc[0]
        stats["training_samples"] = int(feat["cnt"])
        stats["train_samples"] = int(feat["cnt"] * 0.8)
        stats["test_samples"] = int(feat["cnt"] * 0.2)
    except Exception:
        stats["training_samples"] = 0
        stats["train_samples"] = 0
        stats["test_samples"] = 0
    return stats


def get_unified_model_metrics(task: str | None = None) -> List[Dict[str, Any]]:
    """
    Return a standardized metric object for all models in the database.
    If task is provided, filter by task.
    """
    from database.dal import get_model_metrics
    import json
    
    raw = get_model_metrics(task)
    
    expected = {
        "disaggregation": ["random_forest", "gradient_boosting", "xgboost"],
        "anomaly": ["isolation_forest", "random_forest", "xgboost"],
        "bill": ["linear_regression", "xgboost"]
    }
    
    grouped: Dict[str, Dict[str, Any]] = {}
    
    tasks_to_process = [task] if task else expected.keys()
    for t in tasks_to_process:
        for name in expected.get(t, []):
            grouped[f"{t}_{name}"] = {
                "model_name": name,
                "task": t,
                "algorithm": "Unknown",
                "trained": False,
                "evaluation_available": False,
                "status": "Not Available",
                "r2": None,
                "accuracy": None,
                "rmse": None,
                "mae": None,
                "precision": None,
                "recall": None,
                "f1": None,
                "dataset_size": 0,
                "training_samples": 0,
                "testing_samples": 0,
                "validation_split": 0,
                "training_time": None,
                "version": "v1.0.0",
                "artifact_name": f"{t}_{name}.pkl",
                "training_date": None,
                "confusion_matrix": None,
                "details_json": {}
            }
            
    for m in raw:
        t = m.get("task")
        if not t:
            continue
        name = m["model_name"].replace(f"{t}_", "").replace(".pkl", "")
        key = f"{t}_{name}"
        
        if key not in grouped:
            grouped[key] = {
                "model_name": name,
                "task": t,
                "algorithm": "Unknown",
                "trained": True,
                "evaluation_available": True,
                "status": "Active",
                "r2": None,
                "accuracy": None,
                "rmse": None,
                "mae": None,
                "precision": None,
                "recall": None,
                "f1": None,
                "dataset_size": m.get("samples", 0),
                "training_samples": 0,
                "testing_samples": 0,
                "validation_split": 0,
                "training_time": None,
                "version": "v1.0.0",
                "artifact_name": f"{t}_{name}.pkl",
                "training_date": m.get("trained_at"),
                "confusion_matrix": None,
                "details_json": {}
            }
        else:
            grouped[key]["trained"] = True
            grouped[key]["evaluation_available"] = True
            grouped[key]["status"] = "Active"
            grouped[key]["dataset_size"] = m.get("samples", grouped[key]["dataset_size"])
            grouped[key]["training_date"] = m.get("trained_at", grouped[key]["training_date"])
            
        metric_key = m["metric_name"]
        val = m["metric_value"]
        if metric_key in ["r2", "accuracy", "rmse", "mae", "precision", "recall", "f1", "training_time"]:
            grouped[key][metric_key] = round(float(val), 3)
            
        details = m.get("details_json") or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except:
                details = {}
                
        if details:
            grouped[key]["details_json"] = details
            
            # Dynamically extract every field from details_json to make it available to frontend
            for k, v in details.items():
                grouped[key][k] = v
                
            grouped[key]["algorithm"] = details.get("algorithm", grouped[key]["algorithm"])
            grouped[key]["version"] = details.get("model_version", grouped[key]["version"])
            grouped[key]["artifact_name"] = details.get("artifact_name", grouped[key]["artifact_name"])
            
            if grouped[key].get("testing_samples") and grouped[key].get("dataset_size"):
                # If training_samples wasn't explicitly saved, calculate it
                if not grouped[key].get("training_samples"):
                    grouped[key]["training_samples"] = grouped[key]["dataset_size"] - grouped[key]["testing_samples"]
                grouped[key]["validation_split"] = round(grouped[key]["testing_samples"] / grouped[key]["dataset_size"], 2)
    results = list(grouped.values())
    for r in results:
        if r["training_date"]:
            r["training_date"] = str(r["training_date"])
    return results


def evaluate_disaggregation_models() -> Dict[str, Any]:
    """Return disaggregation metrics exclusively from the database."""
    models = get_unified_model_metrics("disaggregation")
    return {
        "models": models, 
        "categories": [
            "Air Conditioner (AC)", "Refrigerator", "Lighting",
            "Television & Entertainment", "Washing Machine",
            "Water Heater / Geyser", "Fans", "Miscellaneous Appliances",
        ],
    }


def evaluate_bill_models() -> Dict[str, Any]:
    """Return bill prediction metrics exclusively from the database."""
    models = get_unified_model_metrics("bill")
    return {"models": models}


def evaluate_anomaly_models() -> Dict[str, Any]:
    """Return anomaly metrics exclusively from the database."""
    models = get_unified_model_metrics("anomaly")
    
    matrices = {}
    for mod in models:
        name = mod["model_name"]
        if mod.get("confusion_matrix"):
            matrices[name] = mod["confusion_matrix"]
        else:
            matrices[name] = "Confusion matrix not available. Retrain the anomaly model to generate it."

    return {"models": models, "confusion_matrices": matrices}


def build_validation_dashboard() -> Dict[str, Any]:
    from database.dal import query_df

    consumer_ids = query_df(
        "SELECT consumer_id FROM consumer_master ORDER BY consumer_id LIMIT 20"
    )["consumer_id"].tolist()

    # Bulk fetch predictions for these consumers
    if consumer_ids:
        cids_tuple = tuple(consumer_ids)
        app_df = query_df(f"SELECT consumer_id, appliance_name, predicted_energy_kwh FROM appliance_predictions WHERE consumer_id IN {cids_tuple}")
        
        # Group ML predictions by consumer
        ml_preds = {}
        if not app_df.empty:
            for cid, group in app_df.groupby("consumer_id"):
                app_sums = group.groupby("appliance_name")["predicted_energy_kwh"].sum()
                tot_pred = app_sums.sum()
                ml_preds[cid] = (app_sums / tot_pred * 100).to_dict() if tot_pred > 0 else {}
    else:
        ml_preds = {}

    # Build per_consumer results
    per_consumer = []
    for cid in consumer_ids:
        # Rule-based requires timestamp data which is heavy; limit to 1 per page load if necessary,
        # but for now, we'll gracefully omit rule-based to prevent N+1 timeout, or return an empty dict
        gt = ground_truth_appliance_pct(cid)
        gt_display = {k: v for k, v in gt.items() if not k.startswith("_")}
        
        per_consumer.append({
            "consumer_id": cid,
            "rule": {},  # Removed to prevent 120s timeout from repeated dataframe loading
            "ml": ml_preds.get(cid, {}),
            "ground_truth": gt_display,
        })

    result = {
        "disaggregation": evaluate_disaggregation_models(),
        "anomaly": evaluate_anomaly_models(),
        "bill": evaluate_bill_models(),
        "per_consumer": per_consumer,
        "dataset_stats": get_dataset_stats(),
    }
    return result


def build_ai_dashboard() -> Dict[str, Any]:
    from database.dal import get_model_metrics

    metrics = get_model_metrics()
    disagg_db = get_unified_model_metrics("disaggregation")
    anom_db = get_unified_model_metrics("anomaly")
    bill_db = get_unified_model_metrics("bill")

    result = {
        "stored_metrics": metrics,
        "disaggregation_eval": {"models": disagg_db},
        "anomaly_eval": {"models": anom_db},
        "bill_eval": {"models": bill_db},
        "models_ready": {
            "disaggregation": load_model("disaggregation_model.pkl") is not None,
            "anomaly": load_model("anomaly_model.pkl") is not None,
            "bill": load_model("bill_model.pkl") is not None,
        },
        "dataset_stats": get_dataset_stats(),
    }
    return result
