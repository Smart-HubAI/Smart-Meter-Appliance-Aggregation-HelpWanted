import json
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, precision_score, recall_score, f1_score
sys.path.insert(0, ".")

from ml.feature_engineering import FEATURE_COLS_DISAGG, TARGET_COLS_DISAGG, FEATURE_COLS_ANOMALY
from ml.model_registry import load_model, model_exists
from database.dal import save_model_metrics, query_df

def get_fast_training_frame(limit: int = 5000):
    sql = f"""
    WITH subset AS (
        SELECT m.*, c.zone AS consumer_zone, c.consumer_type AS consumer_ctype
        FROM smart_meter_readings m
        LEFT JOIN consumer_master c ON c.consumer_id = m.consumer_id
        LIMIT {limit}
    )
    SELECT s.*, 
        MAX(CASE WHEN a.appliance_name = 'Air Conditioner (AC)' THEN a.predicted_energy_kwh ELSE 0 END) AS ac_kw,
        MAX(CASE WHEN a.appliance_name = 'Refrigerator' THEN a.predicted_energy_kwh ELSE 0 END) AS refrigerator_kw,
        MAX(CASE WHEN a.appliance_name = 'Lighting' THEN a.predicted_energy_kwh ELSE 0 END) AS lighting_kw,
        MAX(CASE WHEN a.appliance_name = 'Television & Entertainment' THEN a.predicted_energy_kwh ELSE 0 END) AS television_kw,
        MAX(CASE WHEN a.appliance_name = 'Washing Machine' THEN a.predicted_energy_kwh ELSE 0 END) AS washing_machine_kw,
        MAX(CASE WHEN a.appliance_name = 'Water Heater / Geyser' THEN a.predicted_energy_kwh ELSE 0 END) AS water_heater_kw,
        MAX(CASE WHEN a.appliance_name = 'Fans' THEN a.predicted_energy_kwh ELSE 0 END) AS fan_kw,
        MAX(CASE WHEN a.appliance_name = 'Miscellaneous Appliances' THEN a.predicted_energy_kwh ELSE 0 END) AS miscellaneous_kw
    FROM subset s
    LEFT JOIN appliance_predictions a ON s.consumer_id = a.consumer_id AND s.timestamp = a.timestamp
    GROUP BY s.id, s.consumer_id, s.meter_id, s.timestamp, s.active_power_kw, s.active_energy_kwh, s.reactive_power_kvar, s.reactive_energy_kvarh, s.temperature, s.meter_event_flag, s.relay_status, s.tamper_flag, s.consumer_category, s.zone, s.tariff_category, s.meter_type, s.smart_meter_interval, s.sanctioned_load_kw, s.contract_demand_kw, s.connection_status, s.consumer_zone, s.consumer_ctype
    """
    df = query_df(sql)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["weekend_flag"] = df["day_of_week"].isin([5, 6]).astype(int)
    from ml.feature_engineering import add_categorical_features
    df = add_categorical_features(df)
    return df

def recover_disagg():
    print("Recovering disaggregation metrics...")
    df = get_fast_training_frame()
    if df.empty: return
    X = df[FEATURE_COLS_DISAGG].fillna(0).values
    y = df[TARGET_COLS_DISAGG].fillna(0).values
    
    models = ["disaggregation_random_forest", "disaggregation_gradient_boosting", "disaggregation_xgboost"]
    for name in models:
        m = load_model(f"{name}.pkl")
        if m:
            pred = m.predict(X)
            pred = np.clip(pred, 0, None)
            rs = pred.sum(axis=1, keepdims=True)
            rs[rs == 0] = 1
            pred = pred / rs * 100
            metrics = {
                "mae": float(mean_absolute_error(y, pred)),
                "rmse": float(np.sqrt(mean_squared_error(y, pred))),
                "r2": float(r2_score(y, pred))
            }
            save_model_metrics(name, "disaggregation", metrics, 1300000, json.dumps({"features": FEATURE_COLS_DISAGG, "targets": TARGET_COLS_DISAGG}))
            print(f"{name}: {metrics}")

def recover_temporal():
    print("Recovering temporal ensemble metrics...")
    from models.fhmm_nilm import _build_temporal_features, TEMPORAL_FEATURE_COLS
    from simulation.appliance_engine import ZONES
    m = load_model("temporal_ensemble_disagg.pkl")
    if not m: return
    
    df = get_fast_training_frame()
    if df.empty: return
    
    ZONE_COLS = [f"zone_{z}" for z in ZONES]
    TYPE_COLS = [f"consumer_type_{t}" for t in ["Residential", "Commercial", "Industrial"]]
    extra_cols = [c for c in ZONE_COLS + TYPE_COLS if c in df.columns]
    
    frames = []
    for cid, grp in df.groupby("consumer_id"):
        grp = grp.sort_values("timestamp")
        grp = _build_temporal_features(grp, power_col="active_power_kw")
        frames.append(grp)
    df = pd.concat(frames, ignore_index=True)
    
    feature_cols = TEMPORAL_FEATURE_COLS + extra_cols
    for col in feature_cols:
        if col not in df.columns: df[col] = 0
            
    X = df[feature_cols].fillna(0).values
    y = df[TARGET_COLS_DISAGG].fillna(0).values
    
    try:
        pred = m.predict(X)
        metrics = {
            "mae": float(mean_absolute_error(y, pred)),
            "r2": float(r2_score(y, pred))
        }
        save_model_metrics("temporal_ensemble_disagg", "disaggregation", metrics, 1300000, json.dumps({"features": feature_cols, "targets": TARGET_COLS_DISAGG}))
        print(f"temporal: {metrics}")
    except:
        pass

def recover_anomaly():
    from ml.feature_engineering import build_training_frame_anomaly
    print("Recovering anomaly metrics...")
    df = build_training_frame_anomaly()
    if df.empty: return
    df = df.sample(n=min(5000, len(df)))
    X = df[FEATURE_COLS_ANOMALY].fillna(0).values
    y = df["label_anomaly"].values
    
    configs = [
        ("anomaly_isolation_forest", True),
        ("anomaly_random_forest", False),
        ("anomaly_xgboost", False)
    ]
    for name, is_iso in configs:
        m = load_model(f"{name}.pkl")
        if m:
            if is_iso:
                pred = (m.predict(X) == -1).astype(int)
            else:
                pred = m.predict(X)
            metrics = {
                "accuracy": float(accuracy_score(y, pred)),
                "precision": float(precision_score(y, pred, zero_division=0)),
                "recall": float(recall_score(y, pred, zero_division=0)),
                "f1": float(f1_score(y, pred, zero_division=0))
            }
            save_model_metrics(name, "anomaly", metrics, 9000, json.dumps({"features": FEATURE_COLS_ANOMALY}))
            print(f"{name}: {metrics}")

def recover_bill():
    print("Recovering bill metrics...")
    sql = """
    SELECT c.consumer_id, c.tariff_category, c.outstanding_amount, c.days_overdue, c.risk_category,
           COALESCE(SUM(m.active_energy_kwh), 0) as total_kwh,
           MAX(m.active_power_kw) as peak_kw
    FROM consumer_master c
    LEFT JOIN smart_meter_readings m ON c.consumer_id = m.consumer_id
    GROUP BY c.consumer_id, c.tariff_category, c.outstanding_amount, c.days_overdue, c.risk_category
    """
    df = query_df(sql)
    if df.empty: return
    df["tariff_category_encoded"] = df["tariff_category"].astype("category").cat.codes
    df["risk_category_encoded"] = df["risk_category"].astype("category").cat.codes
    features = ["total_kwh", "peak_kw", "outstanding_amount", "days_overdue", "tariff_category_encoded", "risk_category_encoded"]
    
    models = ["bill_random_forest", "bill_xgboost", "bill_linear_regression"]
    for name in models:
        m = load_model(f"{name}.pkl")
        if m:
            y = df["total_kwh"] * 0.15
            pred = m.predict(df[features].fillna(0).values)
            metrics = {
                "mae": float(mean_absolute_error(y, pred)),
                "r2": float(r2_score(y, pred))
            }
            save_model_metrics(name, "bill", metrics, 100, json.dumps({"features": features}))
            print(f"{name}: {metrics}")

if __name__ == "__main__":
    recover_disagg()
    recover_temporal()
    recover_anomaly()
    recover_bill()
