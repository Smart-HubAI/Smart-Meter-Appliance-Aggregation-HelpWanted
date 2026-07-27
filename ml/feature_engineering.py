"""
Feature store builder — daily features from smart_meter_readings for ML training.
"""

from typing import List, Tuple

import numpy as np
import pandas as pd

from simulation.appliance_engine import CONSUMER_FRIENDLY_APPLIANCES
ZONES = ["Metro Zone", "Industrial Hub", "Suburban", "Commercial District"]
from database.dal import insert_features, query_df
from utils.data_loader import get_readings_dataframe


def compute_daily_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute feature row per consumer per day."""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date.astype(str)

    rows = []
    for (cid, date), g in df.groupby(["consumer_id", "date"]):
        daily_kwh = g["active_energy_kwh"].sum()
        peak_load = g["active_power_kw"].max()
        avg_load = g["active_power_kw"].mean()
        load_factor = avg_load / peak_load if peak_load > 0 else 0

        night = g[g["timestamp"].dt.hour.isin(list(range(0, 6)) + [23])]
        night_ratio = night["active_energy_kwh"].sum() / daily_kwh if daily_kwh > 0 else 0

        # Real power factor from meter readings
        pf_avg = g["power_factor"].mean() if "power_factor" in g.columns and g["power_factor"].notna().any() else 0.95
        volt_var = g["voltage"].var() if "voltage" in g.columns else 0

        rows.append({
            "consumer_id": cid,
            "date": date,
            "daily_kwh": round(daily_kwh, 3),
            "average_load": round(avg_load, 3),
            "peak_load": round(peak_load, 3),
            "load_factor": round(load_factor, 3),
            "night_usage_ratio": round(night_ratio, 3),
            "power_factor_average": round(pf_avg, 3),
            "voltage_variance": round(volt_var or 0, 3),
            "consumption_deviation": 0.0,
        })

    feat = pd.DataFrame(rows)
    if feat.empty:
        return feat

    for cid in feat["consumer_id"].unique():
        mask = feat["consumer_id"] == cid
        median_kwh = feat.loc[mask, "daily_kwh"].median()
        feat.loc[mask, "consumption_deviation"] = (
            (feat.loc[mask, "daily_kwh"] - median_kwh) / median_kwh * 100
            if median_kwh > 0 else 0
        )
    return feat


def build_feature_store() -> int:
    """Rebuild features table from smart_meter_readings."""
    df = get_readings_dataframe()
    feat = compute_daily_features(df)
    if feat.empty:
        return 0

    tuples: List[Tuple] = [
        (
            r.consumer_id, r.date, r.daily_kwh, r.average_load, r.peak_load,
            r.load_factor, r.night_usage_ratio, r.power_factor_average,
            r.voltage_variance, r.consumption_deviation,
        )
        for r in feat.itertuples()
    ]
    insert_features(tuples)
    return len(tuples)


def build_training_frame_disaggregation() -> pd.DataFrame:
    """Interval-level frame with features + appliance % targets."""
    sql = """
    WITH subset AS (
        SELECT m.*, c.zone AS consumer_zone, c.consumer_type AS consumer_ctype
        FROM smart_meter_readings m
        LEFT JOIN consumer_master c ON c.consumer_id = m.consumer_id
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
    GROUP BY s.id, s.consumer_id, s.meter_id, s.timestamp, s.active_power_kw, s.active_energy_kwh, s.reactive_power_kvar, s.reactive_energy_kvarh, s.apparent_power_kva, s.power_factor, s.temperature, s.meter_event_flag, s.relay_status, s.tamper_flag, s.consumer_category, s.zone, s.tariff_category, s.meter_type, s.smart_meter_interval, s.sanctioned_load_kw, s.contract_demand_kw, s.connection_status, s.consumer_zone, s.consumer_ctype
    """
    df = query_df(sql)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["weekend_flag"] = (df["day_of_week"] >= 5).astype(int)
    df = add_categorical_features(df)

    app_sum = (
        df["ac_kw"] + df["refrigerator_kw"] + df["lighting_kw"] + df["television_kw"]
        + df["washing_machine_kw"] + df["water_heater_kw"] + df["fan_kw"] + df["miscellaneous_kw"]
    ).replace(0, np.nan)

    valid_mask = app_sum > 0
    print(f"Removing {(~valid_mask).sum()} zero-appliance rows")
    df = df[valid_mask].copy()
    app_sum = app_sum[valid_mask]

    df["target_Air Conditioner (AC)"] = (df["ac_kw"] / app_sum * 100).fillna(0)
    df["target_Refrigerator"] = (df["refrigerator_kw"] / app_sum * 100).fillna(0)
    df["target_Lighting"] = (df["lighting_kw"] / app_sum * 100).fillna(0)
    df["target_Television & Entertainment"] = (df["television_kw"] / app_sum * 100).fillna(0)
    df["target_Washing Machine"] = (df["washing_machine_kw"] / app_sum * 100).fillna(0)
    df["target_Water Heater / Geyser"] = (df["water_heater_kw"] / app_sum * 100).fillna(0)
    df["target_Fans"] = (df["fan_kw"] / app_sum * 100).fillna(0)
    df["target_Miscellaneous Appliances"] = (df["miscellaneous_kw"] / app_sum * 100).fillna(0)

    return df



def build_training_frame_anomaly() -> pd.DataFrame:
    """Daily features + binary anomaly label from ground_truth_anomalies."""
    feat = query_df("SELECT * FROM feature_engineering")
    gt = query_df("SELECT consumer_id, CAST(detected_at AS DATE) AS date, true AS is_anomaly FROM anomaly_detection WHERE is_ground_truth = true")
    if feat.empty:
        return feat

    gt_days = set(zip(gt["consumer_id"], pd.to_datetime(gt["date"]).dt.strftime('%Y-%m-%d'))) if not gt.empty else set()
    
    # We must explicitly convert feat's date as well to drop the timestamp
    feat["date_str"] = pd.to_datetime(feat["date"]).dt.strftime('%Y-%m-%d')
    feat["label_anomaly"] = feat.apply(
        lambda r: 1 if (r["consumer_id"], r["date_str"]) in gt_days else 0, axis=1
    )
    feat.drop(columns=["date_str"], inplace=True)
    return feat


FEATURE_COLS_ANOMALY = [
    "daily_kwh", "average_load", "peak_load", "load_factor",
    "night_usage_ratio", "power_factor_average", "voltage_variance",
    "consumption_deviation",
]

ZONE_FEATURES = [f"zone_{z}" for z in ZONES]
TYPE_FEATURES = [f"consumer_type_{t}" for t in ["Residential", "Commercial", "Industrial"]]


def add_categorical_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "zone" not in df:
        df["zone"] = ""
    # Use consumer_type or consumer_ctype (aliased from SQL join)
    if "consumer_type" not in df and "consumer_ctype" in df:
        df["consumer_type"] = df["consumer_ctype"]
    if "consumer_type" not in df:
        df["consumer_type"] = ""
    for zone in ZONES:
        df[f"zone_{zone}"] = (df["zone"] == zone).astype(int)
    for ctype in ["Residential", "Commercial", "Industrial"]:
        df[f"consumer_type_{ctype}"] = (df["consumer_type"] == ctype).astype(int)
    return df


FEATURE_COLS_DISAGG = [
    "active_power_kw",
    "reactive_power_kvar",
    "apparent_power_kva",
    "power_factor",
    "temperature",
    "hour", "day_of_week", "weekend_flag",
] + ZONE_FEATURES + TYPE_FEATURES

TARGET_COLS_DISAGG = [
    f"target_{name}" for name in CONSUMER_FRIENDLY_APPLIANCES
]


def build_training_frame_temporal(sample_n: int = None) -> pd.DataFrame:
    """Interval-level frame sorted by time, for rolling window features."""
    limit = f"LIMIT {int(sample_n)}" if sample_n else ""
    sql = f"""
    WITH subset AS (
        SELECT m.*, c.zone AS consumer_zone, c.consumer_type AS consumer_ctype
        FROM smart_meter_readings m
        LEFT JOIN consumer_master c ON c.consumer_id = m.consumer_id
        ORDER BY m.consumer_id, m.timestamp
        {limit}
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
    GROUP BY s.id, s.consumer_id, s.meter_id, s.timestamp, s.active_power_kw, s.active_energy_kwh, s.reactive_power_kvar, s.reactive_energy_kvarh, s.apparent_power_kva, s.power_factor, s.temperature, s.meter_event_flag, s.relay_status, s.tamper_flag, s.consumer_category, s.zone, s.tariff_category, s.meter_type, s.smart_meter_interval, s.sanctioned_load_kw, s.contract_demand_kw, s.connection_status, s.consumer_zone, s.consumer_ctype
    ORDER BY s.consumer_id, s.timestamp
    """
    df = query_df(sql)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = add_categorical_features(df)

    app_sum = (
        df["ac_kw"] + df["refrigerator_kw"] + df["lighting_kw"] + df["television_kw"]
        + df["washing_machine_kw"] + df["water_heater_kw"] + df["fan_kw"] + df["miscellaneous_kw"]
    ).replace(0, np.nan)

    valid_mask = app_sum > 0
    print(f"Removing {(~valid_mask).sum()} zero-appliance rows")
    df = df[valid_mask].copy()
    app_sum = app_sum[valid_mask]

    df["target_Air Conditioner (AC)"] = (df["ac_kw"] / app_sum * 100).fillna(0)
    df["target_Refrigerator"] = (df["refrigerator_kw"] / app_sum * 100).fillna(0)
    df["target_Lighting"] = (df["lighting_kw"] / app_sum * 100).fillna(0)
    df["target_Television & Entertainment"] = (df["television_kw"] / app_sum * 100).fillna(0)
    df["target_Washing Machine"] = (df["washing_machine_kw"] / app_sum * 100).fillna(0)
    df["target_Water Heater / Geyser"] = (df["water_heater_kw"] / app_sum * 100).fillna(0)
    df["target_Fans"] = (df["fan_kw"] / app_sum * 100).fillna(0)
    df["target_Miscellaneous Appliances"] = (df["miscellaneous_kw"] / app_sum * 100).fillna(0)

    return df
