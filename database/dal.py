import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, cast, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from database.postgres_config import engine, SessionLocal, Base
from database.postgres_models import (
    Consumer_Master, Smart_Meter_Readings, Feature_Engineering,
    Appliance_Predictions, Anomaly_Detection, Model_Validation,
    User, Audit_Log, Analytics, Investigation, Investigation_History
)

def init_schema() -> None:
    """Create all PostgreSQL tables if they don't exist."""
    Base.metadata.create_all(bind=engine)

def clear_simulation_data() -> None:
    """Clear simulation data for regeneration (FK-safe order)."""
    with SessionLocal() as db:
        # Clear child tables first
        for table in [Smart_Meter_Readings, Appliance_Predictions, Anomaly_Detection,
                      Feature_Engineering, Analytics, Model_Validation]:
            db.query(table).delete()
        # Clear billing/carbon before consumer_master (FK deps)
        db.execute(text("DELETE FROM billing"))
        db.execute(text("DELETE FROM carbon_emission"))
        db.query(Consumer_Master).delete()
        db.commit()

def is_database_empty() -> bool:
    with SessionLocal() as db:
        count = db.query(Smart_Meter_Readings).count()
        return count == 0

def insert_consumers(consumers: List[Dict[str, Any]]) -> None:
    with SessionLocal() as db:
        for row in consumers:
            stmt = insert(Consumer_Master).values(
                consumer_id=row["consumer_id"],
                consumer_name=row.get("consumer_name", row["name"]),
                name=row["name"],
                address=row.get("address", ""),
                meter_number=row.get("meter_number", f"MTR-{row['consumer_id'][-3:]}"),
                tariff_category=row.get("tariff_category", "domestic"),
                scenario=row.get("scenario", "normal"),
                zone=row.get("zone", ""),
                consumer_type=row.get("consumer_type", "Residential"),
                meter_interval=int(row.get("meter_interval", 15)),
                outstanding_amount=float(row.get("outstanding_amount", 0)),
                days_overdue=int(row.get("days_overdue", 0)),
                payment_status=row.get("payment_status", "Current"),
                risk_category=row.get("risk_category", "Normal"),
                segment=row.get("segment", ""),
            )
            # PostgreSQL UPSERT
            stmt = stmt.on_conflict_do_update(
                index_elements=['consumer_id'],
                set_={
                    "consumer_name": stmt.excluded.consumer_name,
                    "name": stmt.excluded.name,
                    "address": stmt.excluded.address,
                    "meter_number": stmt.excluded.meter_number,
                    "tariff_category": stmt.excluded.tariff_category,
                    "scenario": stmt.excluded.scenario,
                    "zone": stmt.excluded.zone,
                    "consumer_type": stmt.excluded.consumer_type,
                    "meter_interval": stmt.excluded.meter_interval,
                    "outstanding_amount": stmt.excluded.outstanding_amount,
                    "days_overdue": stmt.excluded.days_overdue,
                    "payment_status": stmt.excluded.payment_status,
                    "risk_category": stmt.excluded.risk_category,
                    "segment": stmt.excluded.segment,
                }
            )
            db.execute(stmt)
        db.commit()

def insert_meter_readings(readings: List[Tuple]) -> None:
    # Tuple: 0:consumer_id 1:timestamp 2:meter_interval 3:power_kw 4:voltage
    #   5:current 6:power_factor 7:energy_kwh 8:reactive_power_kvar
    #   9:reactive_energy_kvarh 10:apparent_power_kva 11:temperature
    #   12:meter_event_flag 13:relay_status 14:tamper_flag
    mappings = []
    for r in readings:
        mappings.append({
            "consumer_id": r[0],
            "timestamp": r[1],
            "smart_meter_interval": int(r[2]),
            "active_power_kw": float(r[3]),
            "active_energy_kwh": float(r[7]),
            "reactive_power_kvar": float(r[8]),
            "reactive_energy_kvarh": float(r[9]),
            "apparent_power_kva": float(r[10]),
            "power_factor": float(r[6]),
            "temperature": float(r[11]),
            "meter_event_flag": str(r[12]),
            "relay_status": str(r[13]),
            "tamper_flag": str(r[14]),
            "consumer_category": "Domestic",
            "zone": "North",
            "tariff_category": "residential",
            "meter_type": "Smart",
            "sanctioned_load_kw": 5.0,
            "contract_demand_kw": 5.0,
            "connection_status": "Active",
            "meter_id": f"MTR-{r[0]}"
        })
    with SessionLocal() as db:
        db.bulk_insert_mappings(Smart_Meter_Readings, mappings)
        db.commit()

def insert_appliance_ground_truth(rows: List[Tuple]) -> None:
    # Tuple mapping: consumer_id, timestamp, ac_kw, refrigerator_kw, lighting_kw, television_kw,
    # washing_machine_kw, water_heater_kw, fan_kw, miscellaneous_kw, fridge_kw, tv_kw, others_kw
    mappings = []
    appliance_names = [
        "Air Conditioner (AC)", "Refrigerator", "Lighting", "Television & Entertainment",
        "Washing Machine", "Water Heater / Geyser", "Fans", "Miscellaneous Appliances"
    ]
    for r in rows:
        consumer_id = r[0]
        timestamp = r[1]
        kws = [float(x) for x in r[2:10]]
        total_kw = sum(kws)
        
        for i, app_name in enumerate(appliance_names):
            kw = kws[i]
            if kw > 0.001:  # Only store if there is usage to save space
                mappings.append({
                    "consumer_id": consumer_id,
                    "timestamp": timestamp,
                    "appliance_name": app_name,
                    "predicted_energy_kwh": kw, # kw over 15 mins is kw/4 kwh, but let's keep kw as energy for now as old schema used kw
                    "percentage_contribution": (kw / total_kw * 100) if total_kw > 0 else 0,
                    "confidence": 1.0,
                    "probability": 1.0,
                    "model_used": "Ground Truth",
                    "estimated_monthly_cost": 0.0,
                    "reasoning_summary": "Ground truth from simulation",
                    "important_features": {},
                    "status": "Verified",
                    "last_updated": datetime.now(timezone.utc)
                })
    
    with SessionLocal() as db:
        chunk = 10000
        for i in range(0, len(mappings), chunk):
            db.bulk_insert_mappings(Appliance_Predictions, mappings[i:i+chunk])
        db.commit()

def insert_ground_truth_anomalies(rows: List[Tuple]) -> None:
    # consumer_id, date, anomaly_type, severity, is_anomaly, description
    mappings = []
    for r in rows:
        mappings.append({
            "consumer_id": r[0],
            "detected_at": r[1],
            "anomaly_type": r[2],
            "severity": r[3],
            "is_ground_truth": bool(r[4]),
            "reason": r[5],
        })
    with SessionLocal() as db:
        db.bulk_insert_mappings(Anomaly_Detection, mappings)
        db.commit()

def insert_features(rows: List[Tuple]) -> None:
    # consumer_id, date, daily_kwh, average_load, peak_load, load_factor,
    # night_usage_ratio, power_factor_average, voltage_variance, consumption_deviation
    with SessionLocal() as db:
        for r in rows:
            stmt = insert(Feature_Engineering).values(
                consumer_id=r[0],
                date=r[1],
                daily_kwh=float(r[2]),
                average_load=float(r[3]),
                peak_load=float(r[4]),
                load_factor=float(r[5]),
                night_usage_ratio=float(r[6]),
                power_factor_average=float(r[7]),
                voltage_variance=float(r[8]),
                consumption_deviation=float(r[9])
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['consumer_id', 'date'],
                set_={
                    "daily_kwh": stmt.excluded.daily_kwh,
                    "average_load": stmt.excluded.average_load,
                    "peak_load": stmt.excluded.peak_load,
                    "load_factor": stmt.excluded.load_factor,
                    "night_usage_ratio": stmt.excluded.night_usage_ratio,
                    "power_factor_average": stmt.excluded.power_factor_average,
                    "voltage_variance": stmt.excluded.voltage_variance,
                    "consumption_deviation": stmt.excluded.consumption_deviation,
                }
            )
            db.execute(stmt)
        db.commit()

def save_model_metrics(model_name: str, task: str, metrics: Dict[str, float],
                       samples: int, details: str = "") -> None:
    with SessionLocal() as db:
        for metric_name, value in metrics.items():
            db.add(Model_Validation(
                model_name=model_name,
                task=task,
                metric_name=metric_name,
                metric_value=float(value),
                samples=samples,
                details_json=json.loads(details) if details else None
            ))
        db.commit()

def get_model_metrics(task: str | None = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM model_validation"
    params = {}
    if task:
        sql += " WHERE task = :task"
        params["task"] = task
    sql += " ORDER BY trained_at DESC"
    
    df = query_df(sql, params)
    return cast(List[Dict[str, Any]], df.to_dict("records"))

def query_df(sql: str, params=None, tuple_params: tuple | None = None) -> pd.DataFrame:
    """Execute raw SQL safely, supporting dict params, tuple params, and legacy ? placeholders."""
    with engine.connect() as conn:
        # Handle tuple passed as second positional arg (backward compat with SQLite calls)
        if isinstance(params, tuple):
            tuple_params = params
            params = None

        if tuple_params is not None:
            # Convert SQLite ? placeholders to PostgreSQL %s
            sql = sql.replace("?", "%s")
            return pd.read_sql_query(text(sql), conn, params=tuple_params)
        elif params is not None:
            return pd.read_sql_query(text(sql), conn, params=params)
        else:
            # Always wrap in text() for SQLAlchemy 2.0 compat
            return pd.read_sql_query(text(sql), conn)

def get_all_consumers() -> List[Dict[str, Any]]:
    sql = "SELECT * FROM consumer_master ORDER BY consumer_id"
    df = query_df(sql)
    return cast(List[Dict[str, Any]], df.to_dict("records"))

def get_recent_anomalies(limit: int = 50) -> List[Dict[str, Any]]:
    sql = """
        SELECT a.*, c.name AS consumer_name 
        FROM anomaly_detection a
        LEFT JOIN consumer_master c ON a.consumer_id = c.consumer_id
        WHERE a.resolved = false 
        ORDER BY a.detected_at DESC LIMIT :limit
    """
    df = query_df(sql, {"limit": limit})
    return cast(List[Dict[str, Any]], df.to_dict("records"))

def clear_anomalies() -> None:
    """Clear only ML-detected anomalies (preserve ground truth)."""
    with SessionLocal() as db:
        db.query(Anomaly_Detection).filter(Anomaly_Detection.is_ground_truth == False).delete()
        db.commit()

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "password_hash": user.password_hash,
                "role": user.role,
                "consumer_id": user.consumer_id,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }
        return None

def update_last_login(username: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.last_login = datetime.now(timezone.utc)  # type: ignore
            db.commit()

def insert_audit_log(username: str, role: str, action: str, page_accessed: str = "") -> None:
    with SessionLocal() as db:
        db.add(Audit_Log(
            username=username,
            role=role,
            action=action,
            page_accessed=page_accessed
        ))
        db.commit()

def insert_user(username: str, password_hash: str, role: str, consumer_id: str | None = None) -> None:
    with SessionLocal() as db:
        # Ignore if exists
        user = db.query(User).filter(User.username == username).first()
        if not user:
            db.add(User(
                username=username,
                password_hash=password_hash,
                role=role,
                consumer_id=consumer_id
            ))
            db.commit()

def user_count() -> int:
    with SessionLocal() as db:
        return db.query(User).count()

def save_anomaly(consumer_id: str, anomaly_type: str, reason: str,
                 severity: str, details_json: str = "") -> None:
    with SessionLocal() as db:
        db.add(Anomaly_Detection(
            consumer_id=consumer_id,
            detected_at=datetime.now(timezone.utc),
            anomaly_type=anomaly_type,
            reason=reason,
            severity=severity,
            details_json=json.loads(details_json) if details_json else None,
            is_ground_truth=False
        ))
        db.commit()

def get_all_investigations() -> Dict[str, Dict[str, Any]]:
    """Return a mapping of consumer_id -> Investigation details"""
    with SessionLocal() as db:
        invs = db.query(Investigation).all()
        return {
            str(inv.consumer_id): {
                "status": str(inv.status),
                "assigned_to": str(inv.assigned_to) if inv.assigned_to else None,
                "last_updated": inv.last_updated.isoformat() if inv.last_updated else None,
                "remarks": str(inv.remarks) if inv.remarks else None
            }
            for inv in invs
        }

def update_investigation(consumer_id: str, new_status: str, changed_by: str, assigned_to: str | None = None, remarks: str | None = None) -> bool:
    """Update investigation and append history. Returns True if successful."""
    with SessionLocal() as db:
        inv = db.query(Investigation).filter(Investigation.consumer_id == consumer_id).first()
        prev_status = inv.status if inv else "Open"
        
        if not inv:
            inv = Investigation(
                consumer_id=consumer_id,
                status=new_status,
                assigned_to=assigned_to,
                remarks=remarks,
                last_updated=datetime.now(timezone.utc)
            )
            db.add(inv)
        else:
            inv.status = new_status  # type: ignore
            inv.assigned_to = assigned_to or inv.assigned_to  # type: ignore
            inv.remarks = remarks or inv.remarks  # type: ignore
            inv.last_updated = datetime.now(timezone.utc)  # type: ignore
            
        history = Investigation_History(
            consumer_id=consumer_id,
            timestamp=datetime.now(timezone.utc),
            previous_status=prev_status,
            new_status=new_status,
            changed_by=changed_by,
            remarks=remarks
        )
        db.add(history)
        db.commit()
        return True

def get_investigation_history(consumer_id: str) -> List[Dict[str, Any]]:
    """Get history log for a specific consumer's investigations"""
    with SessionLocal() as db:
        history = db.query(Investigation_History).filter(Investigation_History.consumer_id == consumer_id).order_by(Investigation_History.timestamp.desc()).all()
        return [{
            "timestamp": h.timestamp.isoformat() if h.timestamp else None,
            "previous_status": h.previous_status,
            "new_status": h.new_status,
            "changed_by": h.changed_by,
            "remarks": h.remarks
        } for h in history]

