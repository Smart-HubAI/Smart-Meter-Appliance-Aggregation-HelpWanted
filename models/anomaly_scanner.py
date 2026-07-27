"""
ML-based anomaly detection — scans feature store and populates anomalies table.
"""

import json
from typing import Dict, List

import numpy as np
import pandas as pd

from ml.feature_engineering import FEATURE_COLS_ANOMALY
from ml.model_registry import load_model
from database.dal import clear_anomalies, get_all_consumers, query_df, save_anomaly

# Only 5 utility-grade anomaly types are valid
# Others (poor_power_factor, night_usage, phantom_load, peak_hour_overconsumption)
# are converted to AI insights, not anomalies
VALID_ANOMALY_TYPES = {
    "meter_tampering",
    "consumption_drop",
    "consumption_spike",
    "voltage_issue",
    "continuous_high_load",
}

# Mapping from simulation scenarios → valid anomaly type (or None if not anomaly)
SCENARIO_TO_ANOMALY = {
    "meter_tampering": "meter_tampering",
    "sudden_drop": "consumption_drop",
    "sudden_spike": "consumption_spike",
    "voltage_fluctuation": "voltage_issue",
    "continuous_high_load": "continuous_high_load",
}


def _classify_anomaly_type(row: pd.Series, consumer: dict):
    """
    Return a valid anomaly type or None.
    Only returns one of the 5 valid types; removed types return None
    and will be converted to AI insights elsewhere.
    """
    scenario = (consumer.get("scenario") or "").lower()

    # Meter tampering (highest priority)
    if "tamper" in scenario:
        return "meter_tampering"

    # Voltage issue
    if row.get("voltage_variance", 0) > 40:
        return "voltage_issue"

    # Consumption deviation
    dev = row.get("consumption_deviation", 0)
    if dev > 60:
        return "consumption_spike"
    if dev < -50:
        return "consumption_drop"

    # Continuous high load
    if row.get("load_factor", 1) > 0.85 and row.get("daily_kwh", 0) > 25:
        return "continuous_high_load"

    # Map simulation scenario → valid anomaly (or None)
    mapped = SCENARIO_TO_ANOMALY.get(scenario)
    if mapped:
        return mapped

    # Removed types (poor_power_factor, night_usage, phantom_load, peak_hour_overconsumption)
    # are NOT returned as anomalies — they return None
    return None


def _severity_from_features(row: pd.Series) -> str:
    dev = abs(float(row.get("consumption_deviation", 0) or 0))
    if dev >= 100:
        return "critical"
    if dev >= 70:
        return "high"
    if dev >= 40:
        return "medium"
    return "low"


def scan_and_persist_anomalies() -> int:
    """Run ML anomaly models on daily features; write to anomalies table (batch-optimized)."""
    feat_df = query_df("SELECT * FROM feature_engineering")
    if feat_df.empty:
        return 0

    consumers = {c["consumer_id"]: c for c in get_all_consumers()}
    rf = load_model("anomaly_random_forest.pkl")
    xgb = load_model("anomaly_xgboost.pkl")
    iso = load_model("anomaly_isolation_forest.pkl")
    primary = load_model("anomaly_model.pkl") or rf

    clear_anomalies()
    count = 0

    # Batch predict all rows at once (100x faster than row-by-row)
    X_all = feat_df[FEATURE_COLS_ANOMALY].fillna(0).values
    primary_pred = primary.predict(X_all) if primary is not None else np.zeros(len(X_all))
    xgb_pred = xgb.predict(X_all) if xgb is not None else np.zeros(len(X_all))
    iso_pred = iso.predict(X_all) if iso is not None else np.ones(len(X_all))  # 1=normal

    votes_arr = (
        primary_pred.astype(int)
        + xgb_pred.astype(int)
        + (iso_pred == -1).astype(int)
    )
    is_anomaly_arr = (votes_arr >= 2) | ((votes_arr == 1) & (primary is not None))

    # Only process flagged rows
    flagged_indices = np.where(is_anomaly_arr)[0]

    for idx in flagged_indices:
        row = feat_df.iloc[idx]
        cid = row["consumer_id"]
        consumer = consumers.get(cid, {"consumer_id": cid, "scenario": "normal"})

        atype = _classify_anomaly_type(row, consumer)
        if atype is None:
            continue

        severity = _severity_from_features(row)
        reason = atype.replace("_", " ").title()
        if atype == "meter_tampering":
            reason = "Possible Meter Tampering"
        elif atype == "consumption_drop":
            reason = "Suspicious Consumption Drop"
        elif atype == "consumption_spike":
            reason = "Abnormal Consumption Spike"
        elif atype == "voltage_issue":
            reason = "Voltage Fluctuation Detected"
        elif atype == "continuous_high_load":
            reason = "Sustained High Load Detected"

        save_anomaly(
            cid,
            atype,
            reason,
            severity,
            json.dumps({
                "date": str(row["date"]),
                "daily_kwh": float(row["daily_kwh"]),
                "ml_votes": int(votes_arr[idx]),
            }),
        )
        count += 1

    return count
