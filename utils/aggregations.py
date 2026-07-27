"""
Fast SQL aggregations — avoid loading 288k rows per API request.
All admin dashboard KPIs are computed here from a single source of truth.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from database.dal import query_df

CATEGORY_COLS = {
    "Air Conditioner (AC)": "ac_kw",
    "Refrigerator": "refrigerator_kw",
    "Lighting": "lighting_kw",
    "Television & Entertainment": "television_kw",
    "Washing Machine": "washing_machine_kw",
    "Water Heater / Geyser": "water_heater_kw",
    "Fans": "fan_kw",
    "Miscellaneous Appliances": "miscellaneous_kw",
}


def _top_appliance_from_row(row: pd.Series) -> Tuple[str, float]:
    totals = {}
    for cat, cols in CATEGORY_COLS.items():
        if isinstance(cols, tuple):
            totals[cat] = sum(float(row.get(c, 0) or 0) for c in cols)
        else:
            totals[cat] = float(row.get(cols, 0) or 0)
    total = sum(totals.values()) or 1
    top = max(totals.keys(), key=lambda k: totals[k])
    return top, round(totals[top] / total * 100, 1)


def fleet_consumption_stats() -> pd.DataFrame:
    return query_df("""
        SELECT consumer_id,
               SUM(active_energy_kwh) AS total_kwh,
               COUNT(DISTINCT CAST(timestamp AS DATE)) AS days
        FROM smart_meter_readings
        GROUP BY consumer_id
        ORDER BY consumer_id
    """)


def fleet_appliance_totals() -> pd.DataFrame:
    return query_df("""
        SELECT consumer_id,
               SUM(CASE WHEN appliance_name = 'Air Conditioner (AC)' THEN predicted_energy_kwh ELSE 0 END) AS ac_kw,
               SUM(CASE WHEN appliance_name = 'Refrigerator' THEN predicted_energy_kwh ELSE 0 END) AS refrigerator_kw,
               SUM(CASE WHEN appliance_name = 'Lighting' THEN predicted_energy_kwh ELSE 0 END) AS lighting_kw,
               SUM(CASE WHEN appliance_name = 'Television & Entertainment' THEN predicted_energy_kwh ELSE 0 END) AS television_kw,
               SUM(CASE WHEN appliance_name = 'Fans' THEN predicted_energy_kwh ELSE 0 END) AS fan_kw,
               SUM(CASE WHEN appliance_name = 'Washing Machine' THEN predicted_energy_kwh ELSE 0 END) AS washing_machine_kw,
               SUM(CASE WHEN appliance_name = 'Water Heater / Geyser' THEN predicted_energy_kwh ELSE 0 END) AS water_heater_kw,
               SUM(CASE WHEN appliance_name = 'Miscellaneous Appliances' THEN predicted_energy_kwh ELSE 0 END) AS miscellaneous_kw
        FROM appliance_predictions
        GROUP BY consumer_id
    """)


def fleet_baseline_daily() -> Dict[str, float]:
    df = query_df("""
        SELECT consumer_id, AVG(daily_kwh) AS baseline
        FROM feature_engineering
        GROUP BY consumer_id
    """)
    if df.empty:
        return {}
    return {str(r.consumer_id): round(float(r.baseline), 2) for r in df.itertuples()}


def build_fleet_summary_fast(tariff_rate: float = 8.5) -> List[dict]:
    consumers = query_df("SELECT consumer_id, name FROM consumer_master ORDER BY consumer_id")
    stats = fleet_consumption_stats()
    apps = fleet_appliance_totals()
    baselines = fleet_baseline_daily()

    app_map = apps.set_index("consumer_id") if not apps.empty else pd.DataFrame()
    stat_map = stats.set_index("consumer_id") if not stats.empty else pd.DataFrame()

    rows = []
    for r in consumers.itertuples():
        cid = r.consumer_id
        st = stat_map.loc[cid] if cid in stat_map.index else None
        if st is None:
            continue
        days = max(1, int(st["days"]))
        total_kwh = float(st["total_kwh"])
        avg_daily = total_kwh / days

        top_app, top_pct = "—", 0.0
        if cid in app_map.index:
            top_app, top_pct = _top_appliance_from_row(app_map.loc[cid])

        monthly_bill = round(avg_daily * 30 * tariff_rate, 0)
        rows.append({
            "consumer_id": cid,
            "name": r.name,
            "total_kwh": round(total_kwh, 1),
            "avg_daily_kwh": round(avg_daily, 1),
            "monthly_bill_inr": monthly_bill,
            "top_appliance": top_app,
            "top_appliance_pct": top_pct,
            "baseline_daily_kwh": baselines.get(cid, round(avg_daily, 1)),
        })
    return rows




def zone_analytics(tariff_rate: float = 8.5) -> List[dict]:
    # Aggregate meter_readings per consumer first to avoid row-multiplication
    # when joining to anomalies or consumers (prevents counting readings instead
    # of consumers and duplicate sums).
    # Aggregate anomalies per consumer first to avoid multiplying meter aggregations
    df = query_df("""
        SELECT c.zone,
               COUNT(DISTINCT c.consumer_id) AS consumers,
               COALESCE(SUM(m.total_kwh), 0) AS total_kwh,
               COALESCE(MAX(m.peak_kw), 0) AS peak_kw,
               SUM(COALESCE(c.outstanding_amount, 0)) AS outstanding_inr,
               SUM(CASE WHEN c.risk_category = 'High' THEN 1 ELSE 0 END) AS high_risk_consumers,
               SUM(CASE WHEN ga_agg.anomaly_count > 0 THEN 1 ELSE 0 END) AS anomalies,
               SUM(CASE WHEN ga_agg.tamper_count > 0 THEN 1 ELSE 0 END) AS tampering_cases
        FROM consumer_master c
        LEFT JOIN (
            SELECT consumer_id,
                   SUM(active_energy_kwh) AS total_kwh,
                   MAX(active_power_kw) AS peak_kw
            FROM smart_meter_readings
            GROUP BY consumer_id
        ) m ON m.consumer_id = c.consumer_id
        LEFT JOIN (
            SELECT consumer_id,
                   COUNT(*) AS anomaly_count,
                   SUM(CASE WHEN anomaly_type LIKE '%tamper%' THEN 1 ELSE 0 END) AS tamper_count
            FROM anomaly_detection
            GROUP BY consumer_id
        ) ga_agg ON ga_agg.consumer_id = c.consumer_id
        GROUP BY c.zone
        ORDER BY c.zone
    """)
    if df.empty:
        return []
    rows = []
    for r in df.itertuples():
        rows.append({
            "zone": r.zone,
            "consumers": int(r.consumers or 0),
            "total_consumption_kwh": round(float(r.total_kwh or 0), 2),
            "peak_demand_kw": round(float(r.peak_kw or 0), 2),
            "predicted_revenue_inr": round(float(r.total_kwh or 0) * tariff_rate, 0),
            "outstanding_revenue_inr": round(float(r.outstanding_inr or 0), 0),
            "average_energy_score": 0,
            # these are consumer counts (distinct) after corrected aggregation
            "high_risk_consumers": int(r.high_risk_consumers or 0),
            "tampering_cases": int(r.tampering_cases or 0),
            "anomalies": int(r.anomalies or 0),
        })
    return rows


def peer_avg_daily_kwh() -> float:
    df = query_df("""
        SELECT AVG(total_kwh * 1.0 / GREATEST(days, 1)) AS peer_avg
        FROM (
            SELECT consumer_id,
                   SUM(active_energy_kwh) AS total_kwh,
                   COUNT(DISTINCT CAST(timestamp AS DATE)) AS days
            FROM smart_meter_readings
            GROUP BY consumer_id
        ) sub
    """)
    if df.empty or pd.isna(df.iloc[0]["peer_avg"]):
        df = query_df("SELECT AVG(daily_kwh) AS peer_avg FROM feature_engineering")
    return float(df.iloc[0]["peer_avg"] or 0) if not df.empty else 0.0


# ---------------------------------------------------------------------------
# Admin Dashboard — consistent KPI helpers (single source of truth)
# ---------------------------------------------------------------------------

def admin_monthly_energy() -> dict:
    """
    Current-month total energy sent:
    SUM(active_energy_kwh) from 1st of current month to latest available timestamp.
    Returns {monthly_energy_kwh, start_date, end_date, month_name}.
    """
    df = query_df("""
        SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts
        FROM smart_meter_readings
    """)
    if df.empty or pd.isna(df.iloc[0]["max_ts"]):
        return {"monthly_energy_kwh": 0, "start_date": "", "end_date": "", "month_name": ""}

    max_ts = pd.Timestamp(df.iloc[0]["max_ts"])
    month_start = max_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    energy_df = query_df("""
        SELECT COALESCE(SUM(active_energy_kwh), 0) AS total_kwh
        FROM smart_meter_readings
        WHERE timestamp >= :start
    """, params={"start": month_start.to_pydatetime()})

    total_kwh = float(energy_df.iloc[0]["total_kwh"]) if not energy_df.empty else 0.0

    return {
        "monthly_energy_kwh": round(total_kwh, 2),
        "start_date": month_start.strftime("%d %b %Y"),
        "end_date": max_ts.strftime("%d %b %Y"),
        "month_name": max_ts.strftime("%B %Y"),
    }


def admin_consumer_counts() -> dict:
    """Consumer counts from consumer_master: total, connected, disconnected, inactive."""
    df = query_df("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN r.consumer_id IS NOT NULL THEN 1 ELSE 0 END) AS connected,
            SUM(CASE WHEN c.scenario = 'meter_tampering' THEN 1 ELSE 0 END) AS tampered,
            SUM(CASE WHEN r.consumer_id IS NULL THEN 1 ELSE 0 END) AS inactive
        FROM consumer_master c
        LEFT JOIN (
            SELECT DISTINCT consumer_id FROM smart_meter_readings
        ) r ON r.consumer_id = c.consumer_id
    """)
    if df.empty:
        return {"total": 0, "connected": 0, "disconnected": 0, "inactive": 0}
    row = df.iloc[0]
    total = int(row["total"] or 0)
    connected = int(row["connected"] or 0)
    tampered = int(row["tampered"] or 0)
    inactive = int(row["inactive"] or 0)
    # disconnected = those with tamper scenario (service may be disconnected)
    return {"total": total, "connected": connected - tampered, "disconnected": tampered, "inactive": inactive}





def admin_avg_pf() -> float:
    """Average power factor across current-month readings."""
    df = query_df("""
        SELECT AVG(power_factor) AS avg_pf
        FROM smart_meter_readings
        WHERE power_factor IS NOT NULL AND power_factor > 0
    """)
    if df.empty or pd.isna(df.iloc[0]["avg_pf"]):
        return 0.0
    return round(float(df.iloc[0]["avg_pf"]), 4)


def admin_avg_load_factor() -> float:
    """Average load factor from feature_engineering."""
    df = query_df("""
        SELECT AVG(load_factor) AS avg_lf
        FROM feature_engineering
        WHERE load_factor IS NOT NULL AND load_factor > 0
    """)
    if df.empty or pd.isna(df.iloc[0]["avg_lf"]):
        return 0.0
    return round(float(df.iloc[0]["avg_lf"]), 4)





def admin_monthly_revenue() -> dict:
    """
    Monthly revenue from billing table (current month).
    Falls back to tariff × monthly energy if billing table is empty.
    """
    # Determine current month key (YYYY-MM)
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    df = query_df("""
        SELECT COALESCE(SUM(final_bill), 0) AS total_revenue,
               COUNT(DISTINCT consumer_id) AS billed_consumers
        FROM billing
        WHERE billing_month = :month
    """, params={"month": month_key})

    total_revenue = float(df.iloc[0]["total_revenue"] or 0) if not df.empty else 0.0
    billed = int(df.iloc[0]["billed_consumers"] or 0) if not df.empty else 0

    if total_revenue > 0:
        return {
            "monthly_revenue_inr": round(total_revenue, 2),
            "source": "billing_table",
            "billed_consumers": billed,
            "billing_month": month_key,
        }

    # Fallback: use tariff × monthly energy
    me = admin_monthly_energy()
    from tariff_config import RESIDENTIAL_FIXED_CHARGE, compute_slab_charge, RESIDENTIAL_SLABS, FAC_PER_UNIT, ELECTRICITY_DUTY_PCT
    monthly_kwh = me["monthly_energy_kwh"]
    # Approximate: use residential slab as average
    ec, _ = compute_slab_charge(monthly_kwh, RESIDENTIAL_SLABS)
    fixed = RESIDENTIAL_FIXED_CHARGE * 100  # assume 100 consumers
    fac = monthly_kwh * FAC_PER_UNIT
    subtotal = ec + fixed + fac
    ed = subtotal * ELECTRICITY_DUTY_PCT
    fallback_revenue = subtotal + ed
    return {
        "monthly_revenue_inr": round(fallback_revenue, 2),
        "source": "tariff_calculation",
        "billed_consumers": 0,
        "billing_month": month_key,
    }


# ---------------------------------------------------------------------------
# Chart data helpers for Admin Dashboard
# ---------------------------------------------------------------------------

def admin_monthly_energy_trend() -> dict:
    """Monthly energy trend across all months in DB."""
    df = query_df("""
        SELECT TO_CHAR(DATE_TRUNC('month', timestamp), 'YYYY-MM') AS month_label,
               SUM(active_energy_kwh) AS total_kwh
        FROM smart_meter_readings
        GROUP BY month_label
        ORDER BY month_label
    """)
    if df.empty:
        return {"labels": [], "values": []}
    return {
        "labels": df["month_label"].tolist(),
        "values": df["total_kwh"].round(2).tolist(),
    }


def admin_daily_load_curve() -> dict:
    """Daily load curve for the current month."""
    me = admin_monthly_energy()
    if not me["start_date"]:
        return {"labels": [], "values": []}

    # Parse start date
    start_str = me["start_date"]  # e.g. "01 Jun 2026"
    try:
        start_dt = datetime.strptime(start_str, "%d %b %Y")
    except Exception:
        return {"labels": [], "values": []}

    df = query_df("""
        SELECT CAST(timestamp AS DATE) AS day,
               SUM(active_energy_kwh) AS total_kwh,
               AVG(active_power_kw) AS avg_kw
        FROM smart_meter_readings
        WHERE timestamp >= :start
        GROUP BY day
        ORDER BY day
    """, params={"start": start_dt})

    if df.empty:
        return {"labels": [], "values": []}
    return {
        "labels": [d.strftime("%d %b") for d in df["day"]],
        "values": df["total_kwh"].round(2).tolist(),
    }


def admin_zone_consumption_chart() -> list:
    """Zone-wise consumption for pie/bar chart."""
    df = query_df("""
        SELECT c.zone,
               SUM(m.active_energy_kwh) AS total_kwh
        FROM consumer_master c
        JOIN smart_meter_readings m ON m.consumer_id = c.consumer_id
        GROUP BY c.zone
        ORDER BY total_kwh DESC
    """)
    if df.empty:
        return []
    return [{"zone": r["zone"], "total_kwh": round(float(r["total_kwh"]), 2)} for _, r in df.iterrows()]


def admin_category_distribution() -> list:
    """Consumer category distribution for pie chart."""
    df = query_df("""
        SELECT consumer_type, COUNT(*) AS count
        FROM consumer_master
        GROUP BY consumer_type
        ORDER BY count DESC
    """)
    if df.empty:
        return []
    return [{"category": r["consumer_type"] or "Residential", "count": int(r["count"])} for _, r in df.iterrows()]




def admin_consumer_table_data(risk_scores: list, tariff_rate: float = 8.5) -> list:
    """
    Consumer table data with today's consumption, monthly consumption,
    predicted bill, unified risk score, status, last update.
    """
    from tariff_config import compute_slab_charge, get_tariff_config, FAC_PER_UNIT, ELECTRICITY_DUTY_PCT

    # Per-consumer monthly and today's consumption
    me = admin_monthly_energy()
    start_dt = None
    if me["start_date"]:
        try:
            start_dt = datetime.strptime(me["start_date"], "%d %b %Y")
        except Exception:
            pass

    # Current month consumption per consumer
    if start_dt:
        monthly_df = query_df("""
            SELECT consumer_id,
                   SUM(active_energy_kwh) AS monthly_kwh,
                   MAX(timestamp) AS last_update
            FROM smart_meter_readings
            WHERE timestamp >= :start
            GROUP BY consumer_id
        """, params={"start": start_dt})
    else:
        monthly_df = query_df("""
            SELECT consumer_id,
                   SUM(active_energy_kwh) AS monthly_kwh,
                   MAX(timestamp) AS last_update
            FROM smart_meter_readings
            GROUP BY consumer_id
        """)

    # Today's consumption
    today_df = query_df("""
        SELECT consumer_id, SUM(active_energy_kwh) AS today_kwh
        FROM smart_meter_readings
        WHERE CAST(timestamp AS DATE) = (
            SELECT CAST(MAX(timestamp) AS DATE) FROM smart_meter_readings
        )
        GROUP BY consumer_id
    """)

    # Get billing data for current month
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    billing_df = query_df("""
        SELECT consumer_id, final_bill
        FROM billing
        WHERE billing_month = :month
    """, params={"month": month_key})

    # Build maps
    monthly_map = {}
    last_update_map = {}
    if not monthly_df.empty:
        for _, r in monthly_df.iterrows():
            cid = r["consumer_id"]
            monthly_map[cid] = float(r["monthly_kwh"] or 0)
            last_update_map[cid] = r["last_update"].isoformat() if r["last_update"] else ""

    today_map = {}
    if not today_df.empty:
        for _, r in today_df.iterrows():
            today_map[r["consumer_id"]] = float(r["today_kwh"] or 0)

    bill_map = {}
    if not billing_df.empty:
        for _, r in billing_df.iterrows():
            bill_map[r["consumer_id"]] = float(r["final_bill"] or 0)

    # Risk score map
    risk_map = {r["consumer_id"]: r for r in risk_scores}

    # Consumer master for name, zone, category, status
    consumers_df = query_df("""
        SELECT consumer_id, name, zone, consumer_type, scenario, payment_status
        FROM consumer_master
        ORDER BY consumer_id
    """)

    rows = []
    for _, c in consumers_df.iterrows():
        cid = c["consumer_id"]
        risk_row = risk_map.get(cid, {})
        monthly_kwh = monthly_map.get(cid, 0.0)
        today_kwh = today_map.get(cid, 0.0)

        # Derive status from scenario and readings
        scenario = (c["scenario"] or "").lower()
        if scenario == "meter_tampering":
            status = "Disconnected"
        elif cid in monthly_map:
            status = "Active"
        else:
            status = "Inactive"

        # Predicted bill: from billing table if available, else calculate from monthly kWh
        if cid in bill_map:
            predicted_bill = bill_map[cid]
        elif monthly_kwh > 0:
            ctype = c["consumer_type"] or "Residential"
            tariff_cfg = get_tariff_config(ctype)
            if tariff_cfg.get("billing_type") == "slab":
                ec, _ = compute_slab_charge(monthly_kwh, tariff_cfg["slabs"])
            else:
                ec = monthly_kwh * tariff_cfg.get("rate", tariff_rate)
            fixed = tariff_cfg.get("fixed_charge", 125.0)
            fac = monthly_kwh * FAC_PER_UNIT
            subtotal = ec + fixed + fac
            ed = subtotal * ELECTRICITY_DUTY_PCT
            predicted_bill = subtotal + ed
        else:
            predicted_bill = 0

        rows.append({
            "consumer_id": cid,
            "name": c["name"] or cid,
            "zone": c["zone"] or "",
            "consumer_category": c["consumer_type"] or "Residential",
            "today_kwh": round(today_kwh, 2),
            "monthly_kwh": round(monthly_kwh, 2),
            "predicted_bill_inr": round(predicted_bill, 2),
            "overall_risk_score": risk_row.get("overall_risk_score", 0),
            "risk_band": risk_row.get("risk_band", "Low"),
            "status": status,
            "payment_status": c["payment_status"] or "Current",
            "last_update": last_update_map.get(cid, ""),
        })

    return rows

def admin_active_alerts() -> int:
    """Returns the total number of active (unresolved) anomalies."""
    df = query_df("""
        SELECT COUNT(*) as active_count 
        FROM anomaly_detection 
        WHERE resolved = FALSE OR resolved IS NULL
    """)
    if df.empty:
        return 0
    return int(df.iloc[0]["active_count"] or 0)

def admin_tamper_stats() -> dict:
    """Returns total tampering events and number of affected consumers."""
    df = query_df("""
        SELECT 
            COUNT(*) as tamper_events,
            COUNT(DISTINCT consumer_id) as tampered_consumers
        FROM anomaly_detection
        WHERE LOWER(anomaly_type) LIKE '%tamper%' OR LOWER(reason) LIKE '%tamper%'
    """)
    if df.empty:
        return {"tamper_events": 0, "tampered_consumers": 0}
    return {
        "tamper_events": int(df.iloc[0]["tamper_events"] or 0),
        "tampered_consumers": int(df.iloc[0]["tampered_consumers"] or 0)
    }

