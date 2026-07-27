"""
ML inference layer — loads joblib models for disaggregation, anomaly, billing.
Swap implementations without changing Flask routes.

Disaggregation priority:
  1. MLDisaggregator (classic multi-output regressor, 13 features)
  2. Fallback to empty dict
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ml.feature_engineering import FEATURE_COLS_ANOMALY, FEATURE_COLS_DISAGG, TARGET_COLS_DISAGG, add_categorical_features
from ml.feature_engineering import compute_daily_features
from ml.model_registry import load_model

CATEGORY_KEYS = [
    "Air Conditioner (AC)",
    "Refrigerator",
    "Lighting",
    "Television & Entertainment",
    "Washing Machine",
    "Water Heater / Geyser",
    "Fans",
    "Miscellaneous Appliances",
]

# Legacy 8-category keys for validation dashboards
LEGACY_CATEGORY_KEYS = [
    "AC", "Refrigerator", "Lighting", "TV", "Fan",
    "Washing Machine", "Water Heater", "Others",
]


_disaggregator_instance = None


def get_ml_disaggregator(model_name: str = "disaggregation_model.pkl") -> "MLDisaggregator":
    global _disaggregator_instance
    if _disaggregator_instance is None or _disaggregator_instance.model_name != model_name:
        _disaggregator_instance = MLDisaggregator(model_name)
    return _disaggregator_instance


def get_best_disaggregator():
    """
    Return the best available disaggregator.
    Priority: classic MLDisaggregator > fallback.
    """
    ml = get_ml_disaggregator()
    if ml.is_ready:
        return ml
    return ml  # Will return empty dict if not ready





class MLDisaggregator:
    """Multi-output regressor for appliance share %."""

    def __init__(self, model_name: str = "disaggregation_model.pkl"):
        self.model = load_model(model_name)
        self.model_name = model_name

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def _attach_consumer_context(self, df: pd.DataFrame) -> pd.DataFrame:
        from database.dal import query_df

        consumers = query_df("SELECT consumer_id, zone, consumer_type FROM consumer_master")
        if consumers.empty or "consumer_id" not in df:
            df["zone"] = ""
            df["consumer_type"] = ""
            return df
        return df.merge(consumers, on="consumer_id", how="left")

    def predict_from_readings(self, df: pd.DataFrame) -> Dict[str, float]:
        if not self.is_ready or df.empty:
            return {}
        try:
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["hour"] = df["timestamp"].dt.hour
            df["day_of_week"] = df["timestamp"].dt.dayofweek
            df["weekend_flag"] = (df["day_of_week"] >= 5).astype(int)
            df = add_categorical_features(self._attach_consumer_context(df))

            # Pad missing feature columns with 0 (schema migration compat)
            for col in FEATURE_COLS_DISAGG:
                if col not in df.columns:
                    df[col] = 0

            X = df[FEATURE_COLS_DISAGG].fillna(0).values
            pred = self.model.predict(X)
            pred = np.clip(pred, 0, None)
            row_sum = pred.sum(axis=1, keepdims=True)
            row_sum[row_sum == 0] = 1
            pred = pred / row_sum * 100
            weights = df["energy_kwh"].fillna(0).values.reshape(-1, 1)
            mean_pred = (pred * weights).sum(axis=0) / weights.sum() if weights.sum() > 0 else pred.mean(axis=0)
            s = mean_pred.sum() or 1
            keys = CATEGORY_KEYS if len(mean_pred) == len(CATEGORY_KEYS) else LEGACY_CATEGORY_KEYS
            return {
                keys[i]: round(float(mean_pred[i] / s * 100), 1)
                for i in range(min(len(keys), len(mean_pred)))
            }
        except Exception:
            # Model incompatible with current schema — fall back gracefully
            return {}

    def confidence_score(self, df: pd.DataFrame) -> float:
        if not self.is_ready or df.empty:
            return 0.0
        try:
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["hour"] = df["timestamp"].dt.hour
            df["day_of_week"] = df["timestamp"].dt.dayofweek
            df["weekend_flag"] = (df["day_of_week"] >= 5).astype(int)
            df = add_categorical_features(self._attach_consumer_context(df))
            for col in FEATURE_COLS_DISAGG:
                if col not in df.columns:
                    df[col] = 0
            X = df[FEATURE_COLS_DISAGG].fillna(0).values
            pred = self.model.predict(X)
            pred = np.clip(pred, 0, None)
            row_sum = pred.sum(axis=1, keepdims=True)
            row_sum[row_sum == 0] = 1
            pred = pred / row_sum * 100
            std = pred.std(axis=0).mean()
            return round(max(0.5, min(0.98, 1.0 - std / 50)), 2)
        except Exception:
            return 0.0


class MLAnomalyDetector:
    """Supervised + unsupervised anomaly models on daily features."""

    def __init__(self):
        self.rf = load_model("anomaly_random_forest.pkl")
        self.iso = load_model("anomaly_isolation_forest.pkl")
        self.xgb = load_model("anomaly_xgboost.pkl")

    def predict_daily(self, feat_row: pd.Series) -> Dict[str, Any]:
        X = feat_row[FEATURE_COLS_ANOMALY].fillna(0).values.reshape(1, -1)
        out = {"ml_rf": 0, "ml_iso": 0, "ml_xgb": 0}
        if self.rf is not None:
            out["ml_rf"] = int(self.rf.predict(X)[0]) if hasattr(self.rf, "predict") else 0
        if self.iso is not None:
            out["ml_iso"] = int(self.iso.predict(X)[0] == -1) if hasattr(self.iso, "predict") else 0
        if self.xgb is not None:
            out["ml_xgb"] = int(self.xgb.predict(X)[0]) if hasattr(self.xgb, "predict") else 0
            
        votes = sum(out.values())
        is_anomalous = 1 if votes >= 2 else (1 if votes == 1 and out["ml_rf"] else 0)
        
        out["is_anomalous"] = bool(is_anomalous)
        out["confidence"] = round(votes / 3.0, 2)
        out["explanation"] = (
            f"Flagged by {votes} ML models. " + ("High probability of tampering or leak." if votes >= 2 else "Minor deviation detected.")
        )
        return out


class MLBillPredictor:
    """Daily bill regression from feature store."""

    def __init__(self):
        self.model = load_model("bill_model.pkl")

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def predict_daily_bill(self, feat_row: pd.Series) -> Dict[str, float]:
        if not self.is_ready:
            return {}
        X = feat_row[FEATURE_COLS_ANOMALY].fillna(0).values.reshape(1, -1)
        bill = float(self.model.predict(X)[0])
        return {
            "predicted_daily_bill": round(bill, 2),
            "confidence": 0.85,
            "projected_monthly_bill": round(bill * 30, 2),
        }


def ground_truth_appliance_pct(consumer_id: str) -> Dict[str, float]:
    """Aggregate appliance ground truth to category % for consumer."""
    from database.dal import query_df

    sql = """
    SELECT appliance_name, SUM(predicted_energy_kwh) as total_kwh
    FROM appliance_predictions WHERE consumer_id = :cid
    GROUP BY appliance_name
    """
    df = query_df(sql, params={"cid": consumer_id})
    if df.empty:
        return {}

    db_mapping = dict(zip(df["appliance_name"], df["total_kwh"]))
    
    mapping = {
        "AC": db_mapping.get("Air Conditioner (AC)", 0.0),
        "Refrigerator": db_mapping.get("Refrigerator", 0.0),
        "Lighting": db_mapping.get("Lighting", 0.0),
        "TV": db_mapping.get("Television & Entertainment", 0.0),
        "Fan": db_mapping.get("Fans", 0.0),
        "Washing Machine": db_mapping.get("Washing Machine", 0.0),
        "Water Heater": db_mapping.get("Water Heater / Geyser", 0.0),
        "Others": db_mapping.get("Miscellaneous Appliances", 0.0),
    }

    s = sum(mapping.values()) or 1
    legacy = {k: round(v / s * 100, 1) for k, v in mapping.items()}
    ent = legacy.get("TV", 0) + legacy.get("Fan", 0)
    oth = (
        legacy.get("Washing Machine", 0)
        + legacy.get("Water Heater", 0)
        + legacy.get("Others", 0)
    )
    return {
        "Air Conditioner (AC)": legacy.get("AC", 0),
        "Refrigerator": legacy.get("Refrigerator", 0),
        "Lighting": legacy.get("Lighting", 0),
        "Television & Entertainment": legacy.get("TV", 0),
        "Washing Machine": legacy.get("Washing Machine", 0),
        "Water Heater / Geyser": legacy.get("Water Heater", 0),
        "Fans": legacy.get("Fan", 0),
        "Miscellaneous Appliances": legacy.get("Others", 0),
        "_legacy": legacy,
    }
