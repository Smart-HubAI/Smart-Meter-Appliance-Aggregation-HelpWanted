import pandas as pd
from database.dal import query_df

def _to_native(obj):
    import numpy as np
    import math
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if pd.isna(obj) or (isinstance(obj, float) and math.isnan(obj)):
        return None
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    return obj

def classify_power_factor(pf: float) -> dict:
    """Single Source of Truth for Power Factor classification."""
    if pf >= 0.90:
        return {
            "status": "Excellent",
            "severity": "Good",
            "color": "#4CAF50",
            "description": "No action required."
        }
    elif pf >= 0.80:
        return {
            "status": "Warning",
            "severity": "Medium",
            "color": "#FFC107",
            "description": "Power Factor is below the recommended level. Consider inspecting inductive loads."
        }
    else:
        return {
            "status": "Critical",
            "severity": "High",
            "color": "#F44336",
            "description": "Critical Power Factor detected. Immediate inspection of inductive loads and installation of Power Factor Correction equipment is recommended."
        }

def get_admin_power_factor_analytics():
    """
    Fetch aggregated power factor analytics for all consumers.
    Computes all stats and island/gap analysis (longest low PF duration) directly in PostgreSQL.
    """
    query = """
    WITH base_readings AS (
        SELECT consumer_id, timestamp, 
               COALESCE(power_factor, active_power_kw / NULLIF(apparent_power_kva, 0), 1.0) AS pf
        FROM smart_meter_readings
    ),
    flagged AS (
        SELECT consumer_id, timestamp, pf,
               CASE WHEN pf < 0.90 THEN 1 ELSE 0 END as is_low,
               ROW_NUMBER() OVER(PARTITION BY consumer_id ORDER BY timestamp) as rn1,
               ROW_NUMBER() OVER(PARTITION BY consumer_id, CASE WHEN pf < 0.90 THEN 1 ELSE 0 END ORDER BY timestamp) as rn2
        FROM base_readings
    ),
    islands AS (
        SELECT consumer_id, 
               (rn1 - rn2) as island_id,
               COUNT(*) as duration_readings
        FROM flagged
        WHERE is_low = 1
        GROUP BY consumer_id, (rn1 - rn2)
    ),
    max_durations AS (
        SELECT consumer_id, MAX(duration_readings) as max_low_pf_duration
        FROM islands
        GROUP BY consumer_id
    ),
    consumer_stats AS (
        SELECT consumer_id,
               AVG(pf) as avg_pf,
               MIN(pf) as min_pf,
               MAX(pf) as max_pf,
               SUM(is_low) as low_pf_events,
               MAX(timestamp) as last_updated
        FROM flagged
        GROUP BY consumer_id
    )
    SELECT s.consumer_id, c.name as consumer_name, c.zone, COALESCE(c.consumer_type, 'Residential') as category,
           ROUND(CAST(s.avg_pf AS NUMERIC), 4) as avg_pf, 
           ROUND(CAST(s.min_pf AS NUMERIC), 4) as min_pf, 
           ROUND(CAST(s.max_pf AS NUMERIC), 4) as max_pf, 
           s.low_pf_events,
           COALESCE(m.max_low_pf_duration, 0) as longest_low_pf_duration,
           s.last_updated,
           CASE WHEN s.avg_pf >= 0.90 THEN 'Excellent'
                WHEN s.avg_pf >= 0.80 THEN 'Warning'
                ELSE 'Critical' END as status
    FROM consumer_stats s
    LEFT JOIN max_durations m ON s.consumer_id = m.consumer_id
    LEFT JOIN consumer_master c ON s.consumer_id = c.consumer_id
    ORDER BY s.avg_pf ASC
    """
    df = query_df(query)
    if df.empty:
        return []
    
    rows = []
    for _, row in df.iterrows():
        pf_class = classify_power_factor(float(row["avg_pf"]))
        rows.append({
            "consumer_id": row["consumer_id"],
            "consumer_name": row["consumer_name"] or row["consumer_id"],
            "zone": row["zone"] or "Unknown",
            "category": row["category"],
            "average_pf": float(row["avg_pf"]),
            "minimum_pf": float(row["min_pf"]),
            "maximum_pf": float(row["max_pf"]),
            "low_pf_events": int(row["low_pf_events"]),
            "longest_low_pf_duration": int(row["longest_low_pf_duration"]),
            "status": pf_class["status"],
            "severity": pf_class["severity"],
            "color": pf_class["color"],
            "description": pf_class["description"],
            "last_updated": row["last_updated"].isoformat() if pd.notnull(row["last_updated"]) else None
        })
    return _to_native(rows)


def get_consumer_power_factor(consumer_id: str):
    """
    Fetch daily power factor trend and stats for a specific consumer.
    """
    query = """
    WITH max_date AS (
        SELECT CAST(MAX(timestamp) AS DATE) as latest_date
        FROM smart_meter_readings
        WHERE consumer_id = :cid
    )
    SELECT timestamp, 
           COALESCE(power_factor, active_power_kw / NULLIF(apparent_power_kva, 0), 1.0) AS pf
    FROM smart_meter_readings
    WHERE consumer_id = :cid 
      AND CAST(timestamp AS DATE) = (SELECT latest_date FROM max_date)
    ORDER BY timestamp
    """
    df = query_df(query, params={"cid": consumer_id})
    if df.empty:
        return {"error": "No data available"}
    
    # Determine interval (15-min or 30-min)
    if len(df) > 1:
        diffs = df['timestamp'].diff().dt.total_seconds().dropna()
        interval_minutes = int(diffs.mode()[0] / 60)
    else:
        interval_minutes = 15
        
    readings = []
    for _, row in df.iterrows():
        readings.append({
            "timestamp": row["timestamp"].isoformat(),
            "time_label": row["timestamp"].strftime("%H:%M"),
            "power_factor": round(float(row["pf"]), 4)
        })
        
    # Calculate stats
    pfs = df["pf"]
    avg_pf = float(pfs.mean())
    min_pf = float(pfs.min())
    max_pf = float(pfs.max())
    
    is_low = pfs < 0.90
    low_pf_events = int(is_low.sum())
    
    # Calculate longest consecutive low pf
    # Group consecutive True values
    condition = is_low
    islands = condition != condition.shift()
    groups = islands.cumsum()
    consecutive_counts = condition.groupby(groups).sum()
    longest_low_pf_duration = int(consecutive_counts.max()) if not consecutive_counts.empty else 0
    
    pf_class = classify_power_factor(avg_pf)
        
    # Check for alert (1 continuous hour)
    alert = False
    if interval_minutes == 15 and longest_low_pf_duration >= 4:
        alert = True
    elif interval_minutes == 30 and longest_low_pf_duration >= 2:
        alert = True
    elif interval_minutes not in (15, 30) and longest_low_pf_duration * interval_minutes >= 60:
        alert = True
        
    return _to_native({
        "consumer_id": consumer_id,
        "date": df["timestamp"].max().strftime("%Y-%m-%d"),
        "interval_minutes": interval_minutes,
        "readings": readings,
        "summary": {
            "average_pf": round(avg_pf, 4),
            "minimum_pf": round(min_pf, 4),
            "maximum_pf": round(max_pf, 4),
            "low_pf_events": low_pf_events,
            "longest_low_pf_duration": longest_low_pf_duration,
            "status": pf_class["status"],
            "severity": pf_class["severity"],
            "color": pf_class["color"],
            "description": pf_class["description"]
        },
        "alert": alert,
        "alert_message": pf_class["description"] if alert else None
    })
