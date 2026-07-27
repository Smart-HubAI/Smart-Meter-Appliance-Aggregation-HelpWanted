"""
Load simulation directly into PostgreSQL database. Uses appliance_engine for ground truth.
"""

import logging
import os
from typing import Dict, List, Tuple

import pandas as pd

from simulation.appliance_engine import CONSUMER_PROFILES, NUM_CONSUMERS, generate_full_simulation
from database.dal import (
    clear_simulation_data,
    get_all_consumers,
    init_schema,
    insert_appliance_ground_truth,
    insert_consumers,
    insert_ground_truth_anomalies,
    insert_meter_readings,
    is_database_empty,
)



def _bulk_load(meter_rows: List[dict], app_rows: List[dict], anom_rows: List[dict]) -> int:
    consumers = [
        {
            "consumer_id": p.consumer_id,
            "name": p.name,
            "address": p.address,
            "scenario": p.scenario,
            "zone": p.zone,
            "consumer_type": p.consumer_type,
            "meter_interval": p.meter_interval,
            "outstanding_amount": p.outstanding_amount,
            "days_overdue": p.days_overdue,
            "payment_status": p.payment_status,
            "risk_category": p.risk_category,
            "segment": p.segment,
        }
        for p in CONSUMER_PROFILES
    ]
    insert_consumers(consumers)

    meter_tuples = [
        (r["consumer_id"], r["timestamp"], r["meter_interval"], r["power_kw"], r["voltage"],
         r["current"], r["power_factor"], r["energy_kwh"],
         r["reactive_power_kvar"], r["reactive_energy_kvarh"], r["apparent_power_kva"],
         r["temperature"], r["meter_event_flag"], r["relay_status"], r["tamper_flag"])
        for r in meter_rows
    ]
    chunk = 5000
    for i in range(0, len(meter_tuples), chunk):
        insert_meter_readings(meter_tuples[i : i + chunk])

    app_tuples = [
        (
            r["consumer_id"], r["timestamp"], r["ac_kw"], r["refrigerator_kw"],
            r["lighting_kw"], r["television_kw"], r["washing_machine_kw"],
            r["water_heater_kw"], r["fan_kw"], r["miscellaneous_kw"],
            r["refrigerator_kw"], r["television_kw"], r["miscellaneous_kw"],
        )
        for r in app_rows
    ]
    for i in range(0, len(app_tuples), chunk):
        insert_appliance_ground_truth(app_tuples[i : i + chunk])

    anom_tuples = [
        (r["consumer_id"], r["date"], r["anomaly_type"], r["severity"],
         r.get("is_anomaly", 1), r.get("description", ""))
        for r in anom_rows
    ]
    if anom_tuples:
        insert_ground_truth_anomalies(anom_tuples)

    return len(meter_tuples)




def get_user_by_username(username: str) -> dict | None:
    from database.dal import query_df
    df = query_df("SELECT * FROM users WHERE username = :uname", params={"uname": username})
    if not df.empty:
        return df.iloc[0].to_dict()
    return None


def _needs_upgrade() -> bool:
    from database.dal import get_all_consumers, query_df
    if is_database_empty():
        return True
    if len(get_all_consumers()) < NUM_CONSUMERS:
        return True
    cnt = query_df("SELECT COUNT(*) AS n FROM smart_meter_readings").iloc[0]["n"]
    expected = (50 * 90 * 96) + (50 * 90 * 48)
    return cnt < expected * 0.9


def load_simulation_to_database(force: bool = False) -> Dict[str, str]:
    init_schema()
    if not force and not _needs_upgrade():
        logging.info("[Smart Meter Platform] PostgreSQL database already initialized.")
        logging.info("[Smart Meter Platform] Existing consumer and meter data detected. Skipping data generation.")
        return {"status": "populated"}

    if force:
        clear_simulation_data()

    logging.info("[Smart Meter Platform] Initializing PostgreSQL database...")
    logging.info("[Smart Meter Platform] Generating simulated smart meter data...")
    meter, apps, anom = generate_full_simulation()
    
    logging.info("[Smart Meter Platform] Loading data into PostgreSQL...")
    count = _bulk_load(meter, apps, anom)

    from ml.feature_engineering import build_feature_store
    build_feature_store()

    logging.info("[Smart Meter Platform] Database initialization completed successfully.")
    return {"status": "initialized"}


def initialize_data(force: bool = False) -> Dict[str, str]:
    return load_simulation_to_database(force=force)


def get_readings_dataframe(consumer_id: str | None = None) -> pd.DataFrame:
    from database.dal import query_df
    if consumer_id:
        sql = "SELECT * FROM smart_meter_readings WHERE consumer_id = :cid ORDER BY timestamp"
        df = query_df(sql, params={"cid": consumer_id})
    else:
        sql = "SELECT * FROM smart_meter_readings ORDER BY consumer_id, timestamp"
        df = query_df(sql)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # Backward-compatible aliases for code that uses old SQLite column names
        if "active_energy_kwh" in df.columns and "energy_kwh" not in df.columns:
            df["energy_kwh"] = df["active_energy_kwh"]
        if "active_power_kw" in df.columns and "power_kw" not in df.columns:
            df["power_kw"] = df["active_power_kw"]
        if "smart_meter_interval" in df.columns and "meter_interval" not in df.columns:
            df["meter_interval"] = df["smart_meter_interval"]
    return df


def get_appliance_ground_truth(consumer_id: str | None = None) -> pd.DataFrame:
    from database.dal import query_df
    if consumer_id:
        sql = "SELECT * FROM appliance_predictions WHERE consumer_id = :cid ORDER BY timestamp"
        df = query_df(sql, params={"cid": consumer_id})
    else:
        sql = "SELECT * FROM appliance_predictions ORDER BY consumer_id, timestamp"
        df = query_df(sql)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # Pivot the normalized table back to wide format for ML training
        df = df.pivot_table(index=["consumer_id", "timestamp"], 
                            columns="appliance_name", 
                            values="predicted_energy_kwh", 
                            fill_value=0.0).reset_index()
        # Rename to match expected ML columns
        cols = {
            "Air Conditioner (AC)": "ac_kw", 
            "Refrigerator": "refrigerator_kw", 
            "Lighting": "lighting_kw", 
            "Television & Entertainment": "television_kw", 
            "Washing Machine": "washing_machine_kw", 
            "Water Heater / Geyser": "water_heater_kw", 
            "Fans": "fan_kw", 
            "Miscellaneous Appliances": "miscellaneous_kw"
        }
        df.rename(columns=cols, inplace=True)
        # Ensure all required columns exist
        for col in cols.values():
            if col not in df.columns:
                df[col] = 0.0
    return df


def get_features_dataframe(consumer_id: str | None = None) -> pd.DataFrame:
    from database.dal import query_df
    if consumer_id:
        sql = "SELECT * FROM feature_engineering WHERE consumer_id = :cid ORDER BY date"
        return query_df(sql, params={"cid": consumer_id})
    return query_df("SELECT * FROM feature_engineering ORDER BY consumer_id, date")
