"""
Utility Priority Score engine — composite risk scoring for consumer prioritization.
Fraud 40% | Revenue 30% | Technical 20% | Behavioral 10%

Only uses the 5 utility-grade anomaly types:
  meter_tampering, consumption_spike, consumption_drop,
  voltage_issue, continuous_high_load

Anomaly-specific risk weights (separate from utility priority):
  meter_tampering      = 40
  consumption_spike    = 25
  consumption_drop     = 20
  voltage_issue        = 15
  continuous_high_load = 10
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from database.dal import get_all_consumers, query_df
from anomaly_config import ANOMALY_WEIGHTS, VALID_ANOMALY_TYPES, compute_anomaly_risk_score, risk_band

# --- Type groupings (only 5 valid types) ---
FRAUD_TYPES = {"meter_tampering", "consumption_drop"}
REVENUE_STATUSES = {"Overdue", "Partial"}
TECHNICAL_TYPES = {"voltage_issue", "continuous_high_load"}
BEHAVIORAL_TYPES = {"consumption_spike"}

PRIORITY_BANDS = [
    (90, 100, "Immediate Action"),
    (75, 89, "High Priority"),
    (50, 74, "Medium Priority"),
    (25, 49, "Low Priority"),
    (0, 24, "Normal"),
]


def priority_label(score: float) -> str:
    s = max(0, min(100, score))
    for lo, hi, label in PRIORITY_BANDS:
        if lo <= s <= hi:
            return label
    return "Normal"


def _fraud_risk(consumer: dict, anomalies: List[dict]) -> tuple:
    score = 0.0
    reasons = []
    scenario = (consumer.get("scenario") or "").lower()

    if "tampering" in scenario or scenario == "meter_tampering":
        score = max(score, 95)
        reasons.append("Possible Meter Tampering")

    for a in anomalies:
        atype = (a.get("anomaly_type") or "").lower()
        if atype == "meter_tampering" or "tamper" in atype:
            score = max(score, 90 if a.get("severity") == "critical" else 75)
            reasons.append(a.get("reason") or "Meter Tampering")
        elif atype == "consumption_drop":
            score = max(score, 70)
            reasons.append(a.get("reason") or "Suspicious Consumption Drop")

    if scenario in ("sudden_drop", "meter_tampering"):
        score = max(score, 88 if scenario == "meter_tampering" else 70)
        if not reasons:
            reasons.append(
                "Possible Meter Tampering" if scenario == "meter_tampering"
                else "Suspicious Consumption Drop"
            )

    return min(100, score), reasons


def _revenue_risk(consumer: dict) -> tuple:
    score = 0.0
    reasons = []
    outstanding = float(consumer.get("outstanding_amount") or 0)
    days_od = int(consumer.get("days_overdue") or 0)
    status = consumer.get("payment_status") or "Current"

    if outstanding > 10000:
        score = max(score, 90)
        reasons.append(f"Outstanding ₹{outstanding:,.0f}")
    elif outstanding > 5000:
        score = max(score, 70)
        reasons.append(f"Outstanding ₹{outstanding:,.0f}")
    elif outstanding > 1000:
        score = max(score, 45)
        reasons.append(f"Outstanding ₹{outstanding:,.0f}")

    if days_od > 90:
        score = max(score, 85)
        if not any("Outstanding" in r for r in reasons):
            reasons.append(f"{days_od} days overdue")
    elif days_od > 60:
        score = max(score, 65)
    elif days_od > 30:
        score = max(score, 40)

    if status in REVENUE_STATUSES:
        score = max(score, 55 if status == "Partial" else 75)
        if status == "Overdue" and not reasons:
            reasons.append("Payment Overdue")

    if consumer.get("risk_category") == "High" and outstanding > 0:
        score = max(score, 80)

    return min(100, score), reasons


def _technical_risk(consumer: dict, anomalies: List[dict], feat_row: Optional[pd.Series]) -> tuple:
    score = 0.0
    reasons = []
    scenario = (consumer.get("scenario") or "").lower()

    if scenario in ("voltage_fluctuation", "continuous_high_load"):
        score = max(score, {"voltage_fluctuation": 70, "continuous_high_load": 60}[scenario])
        reasons.append(scenario.replace("_", " ").title())

    for a in anomalies:
        atype = (a.get("anomaly_type") or "").lower()
        if atype in TECHNICAL_TYPES or "voltage" in atype:
            sev = a.get("severity", "low")
            score = max(score, {"critical": 85, "high": 70, "medium": 55, "low": 35}.get(sev, 40))
            reasons.append(a.get("reason") or atype.replace("_", " ").title())

    if feat_row is not None and not (hasattr(feat_row, "empty") and feat_row.empty):
        vv = float(feat_row.get("voltage_variance", 0) or 0)
        if vv > 50:
            score = max(score, 65)
            reasons.append("Voltage Fluctuation")

    return min(100, score), reasons


def _behavioral_risk(consumer: dict, anomalies: List[dict], feat_row: Optional[pd.Series]) -> tuple:
    score = 0.0
    reasons = []

    for a in anomalies:
        atype = (a.get("anomaly_type") or "").lower()
        if atype == "consumption_spike" or "spike" in atype:
            sev = a.get("severity", "low")
            score = max(score, {"critical": 75, "high": 60, "medium": 45, "low": 25}.get(sev, 30))
            reasons.append(a.get("reason") or "Consumption Spike")

    if feat_row is not None and not (hasattr(feat_row, "empty") and feat_row.empty):
        dev = abs(float(feat_row.get("consumption_deviation", 0) or 0))
        if dev > 80:
            score = max(score, 55)
            reasons.append("Consumption Spike")

    return min(100, score), reasons


def _anomaly_details(anomalies: List[dict]) -> List[dict]:
    """Extract structured anomaly details for the anomaly table."""
    details = []
    for a in anomalies:
        atype = a.get("anomaly_type", "")
        if atype not in VALID_ANOMALY_TYPES:
            continue
        details.append({
            "anomaly_type": atype,
            "severity": a.get("severity", "low"),
            "reason": a.get("reason", ""),
            "risk_weight": ANOMALY_WEIGHTS.get(atype, 0),
        })
    return details


def compute_consumer_risk(
    consumer: dict,
    anomalies: Optional[List[dict]] = None,
    feat_row: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    anomalies = anomalies or []
    fraud, fraud_r = _fraud_risk(consumer, anomalies)
    revenue, rev_r = _revenue_risk(consumer)
    technical, tech_r = _technical_risk(consumer, anomalies, feat_row)
    behavioral, beh_r = _behavioral_risk(consumer, anomalies, feat_row)

    base_score = (
        fraud * 0.40 + revenue * 0.30 + technical * 0.20 + behavioral * 0.10
    )
    utility_score = base_score
    if fraud >= 90:
        utility_score = max(utility_score, fraud * 0.92 + revenue * 0.08)
    if revenue >= 85 and fraud >= 70:
        utility_score = max(utility_score, 90 + min(8, revenue / 15))
    if technical >= 65 and fraud < 50:
        utility_score = max(utility_score, 75 + technical * 0.12)
    utility_score = round(min(100, utility_score), 1)

    all_reasons = fraud_r + rev_r + tech_r + beh_r
    if fraud_r:
        primary = fraud_r[0]
    elif rev_r:
        primary = rev_r[0]
    elif tech_r:
        primary = tech_r[0]
    elif beh_r:
        primary = beh_r[0]
    else:
        primary = "Routine monitoring"

    # Anomaly-specific risk scoring (separate from utility priority)
    anomaly_types_present = list(set(
        a.get("anomaly_type") for a in anomalies if a.get("anomaly_type") in VALID_ANOMALY_TYPES
    ))
    anomaly_risk_score = compute_anomaly_risk_score(anomaly_types_present)
    anomaly_risk_band = risk_band(anomaly_risk_score)

    return {
        "consumer_id": consumer["consumer_id"],
        "name": consumer.get("name", consumer["consumer_id"]),
        "risk_score": utility_score,
        "priority": priority_label(utility_score),
        "primary_reason": primary,
        "fraud_risk": round(fraud, 1),
        "revenue_risk": round(revenue, 1),
        "technical_risk": round(technical, 1),
        "behavioral_risk": round(behavioral, 1),
        "reasons": all_reasons[:5],
        "zone": consumer.get("zone", ""),
        "outstanding_amount": consumer.get("outstanding_amount", 0),
        "payment_status": consumer.get("payment_status", "Current"),
        # Anomaly-specific fields
        "anomaly_risk_score": anomaly_risk_score,
        "anomaly_risk_band": anomaly_risk_band,
        "anomaly_types": anomaly_types_present,
        "anomaly_count": len(anomaly_types_present),
        "has_tampering": "meter_tampering" in anomaly_types_present,
        "anomaly_details": _anomaly_details(anomalies),
    }


def build_priority_queue(limit: int = 100) -> List[Dict[str, Any]]:
    consumers = get_all_consumers()
    feat_df = query_df("SELECT * FROM feature_engineering")
    anomaly_df = query_df(
        "SELECT consumer_id, anomaly_type, reason, severity FROM anomaly_detection WHERE resolved = false AND is_ground_truth = false"
    )

    queue = []
    for c in consumers:
        cid = c["consumer_id"]
        c_anoms = anomaly_df[anomaly_df["consumer_id"] == cid].to_dict("records") if not anomaly_df.empty else []
        c_feat = feat_df[feat_df["consumer_id"] == cid]
        feat_row = c_feat.iloc[-1] if not c_feat.empty else None
        risk = compute_consumer_risk(c, c_anoms, feat_row)
        queue.append(risk)

    queue.sort(key=lambda x: (-x["risk_score"], x["consumer_id"]))
    for rank, item in enumerate(queue[:limit], start=1):
        item["rank"] = rank
    return queue


# Anomaly type → priority label (based on highest weight anomaly)
ANOMALY_PRIORITY = {
    "meter_tampering": "Critical",
    "consumption_spike": "High",
    "consumption_drop": "High",
    "voltage_issue": "Medium",
    "continuous_high_load": "Medium",
}

_PRIORITY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _highest_priority(types: List[str]) -> str:
    """Return the highest priority among anomaly types."""
    best = "Low"
    for t in types:
        p = ANOMALY_PRIORITY.get(t, "Low")
        if _PRIORITY_RANK.get(p, 3) < _PRIORITY_RANK.get(best, 3):
            best = p
    return best


def build_anomaly_summary_table(limit: int = 200) -> List[Dict[str, Any]]:
    """
    Build a consumer-grouped anomaly summary table.
    ONE ROW per consumer with all their anomalies nested inside.
    Sorted by anomaly risk score descending, then priority.
    """
    from anomaly_config import ANOMALY_META
    consumers = {c["consumer_id"]: c for c in get_all_consumers()}

    # Query ground_truth_anomalies (valid types only)
    gt_df = query_df(
        "SELECT consumer_id, anomaly_type, severity, detected_at AS date, reason AS description "
        "FROM anomaly_detection "
        "WHERE is_ground_truth = true AND anomaly_type IN ({})".format(
            ",".join(f"'{t}'" for t in VALID_ANOMALY_TYPES)
        )
    )
    if gt_df.empty:
        return []

    # Group by consumer_id
    grouped: Dict[str, List[dict]] = {}
    for _, row in gt_df.iterrows():
        cid = row["consumer_id"]
        if cid not in grouped:
            grouped[cid] = []
        grouped[cid].append(dict(row))

    rows = []
    seen_consumers = set()
    for cid, anomaly_rows in grouped.items():
        if cid in seen_consumers:
            continue
        seen_consumers.add(cid)

        consumer = consumers.get(cid, {"consumer_id": cid, "name": cid, "zone": ""})

        # Deduplicate anomaly types (take first occurrence per type)
        type_seen: set = set()
        anomalies = []
        for a in anomaly_rows:
            atype = a.get("anomaly_type", "")
            if atype in type_seen:
                continue
            type_seen.add(atype)
            meta = ANOMALY_META.get(atype, {})
            anomalies.append({
                "anomaly_type": atype,
                "anomaly_label": meta.get("label", atype.replace("_", " ").title()),
                "severity": a.get("severity", "low"),
                "risk_weight": ANOMALY_WEIGHTS.get(atype, 0),
                "priority": ANOMALY_PRIORITY.get(atype, "Low"),
                "detection_reason": a.get("description", "") or a.get("reason", ""),
                "detected_at": a.get("date", ""),
                "what_it_means": meta.get("what_it_means", ""),
                "how_detected": meta.get("how_detected", ""),
                "risk_impact": meta.get("risk_impact", {}),
                "recommended_action": meta.get("recommended_action", []),
                "icon": meta.get("icon", "bi-exclamation-circle"),
                "color": meta.get("color", "#455a64"),
            })

        # Sort anomalies by risk weight desc
        anomalies.sort(key=lambda x: -x["risk_weight"])

        # Unique types for scoring
        unique_types = list(type_seen)
        risk_score = compute_anomaly_risk_score(unique_types)
        priority = _highest_priority(unique_types)
        primary = anomalies[0] if anomalies else {}

        rows.append({
            "consumer_id": cid,
            "consumer_name": consumer.get("name", cid),
            "zone": consumer.get("zone", ""),
            "risk_score": risk_score,
            "risk_band": risk_band(risk_score),
            "priority": priority,
            "anomaly_count": len(unique_types),
            "primary_anomaly": primary.get("anomaly_label", ""),
            "primary_anomaly_type": primary.get("anomaly_type", ""),
            "has_tampering": "meter_tampering" in type_seen,
            "anomalies": anomalies,
        })

    # Sort: risk_score desc, then priority rank, then consumer_id
    rows.sort(key=lambda r: (
        -r["risk_score"],
        _PRIORITY_RANK.get(r["priority"], 3),
        r["consumer_id"],
    ))
    return rows[:limit]


def overall_risk_band(score: float) -> str:
    """Unified risk band label from 0–100 overall score."""
    s = max(0, min(100, score))
    if s >= 75:
        return "Critical"
    elif s >= 50:
        return "High"
    elif s >= 25:
        return "Medium"
    return "Low"


def compute_overall_risk_score(gt_rows: list, feat_row: Optional[pd.Series]) -> float:
    """
    Unified overall risk score (0–100) calculated dynamically.
    Uses anomaly weight as base, then adds contributions.
    """
    if not gt_rows:
        return 0.0

    from anomaly_config import ANOMALY_WEIGHTS
    
    types = [a.get("anomaly_type", "") for a in gt_rows if a.get("anomaly_type")]
    if not types:
        return 0.0
        
    primary_type = max(types, key=lambda t: ANOMALY_WEIGHTS.get(t, 0))
    base_weight = ANOMALY_WEIGHTS.get(primary_type, 0)
    
    if base_weight == 0:
        return 0.0
        
    score = float(base_weight)
    
    # Load Contribution
    if feat_row is not None and not (hasattr(feat_row, "empty") and feat_row.empty):
        peak = float(feat_row.get("peak_load", 0) or 0)
        if peak > 15:
            score += 5
        elif peak > 10:
            score += 2
            
        # Power Factor Contribution
        pf = float(feat_row.get("power_factor_average", 1.0) or 1.0)
        if pf < 0.85:
            score += 5
            
        # Consumption Deviation Contribution
        dev = abs(float(feat_row.get("consumption_deviation", 0) or 0))
        if dev > 50:
            score += 5
            
    # Frequency/Repeat Offender Contribution
    if len(gt_rows) > 1:
        score += min(15.0, (len(gt_rows) - 1) * 3.0)
        
    return round(max(0.0, min(100.0, score)), 1)


def build_utility_investigation_queue(limit: int = 200) -> List[Dict[str, Any]]:
    """
    Build the unified Utility Investigation Queue.
    Merges Consumer Priority Queue + Anomaly Investigation Dashboard
    into a single table with ONE ROW per consumer.

    Columns: Rank, Consumer ID, Name, Zone, Risk Score, Priority,
             Primary Issue, Revenue Impact, Fraud Risk,
             Anomaly Count, Status.

    Each row includes expandable anomaly details.
    Sorted by: Risk Score desc, Fraud Risk desc, Revenue Impact desc.
    """
    from database.dal import get_all_consumers, query_df, get_all_investigations
    from anomaly_config import ANOMALY_META

    consumers_list = get_all_consumers()
    consumers_map = {c["consumer_id"]: c for c in consumers_list}
    feat_df = query_df("SELECT * FROM feature_engineering")
    
    # Fetch all investigation statuses from DB
    investigations_db = get_all_investigations()

    # ML anomalies (from anomalies table)
    anomaly_df = query_df(
        "SELECT consumer_id, anomaly_type, reason, severity FROM anomaly_detection WHERE resolved = false AND is_ground_truth = false"
    )

    # Ground-truth anomalies (valid types only)
    gt_df = query_df(
        "SELECT consumer_id, anomaly_type, severity, detected_at AS date, reason AS description "
        "FROM anomaly_detection "
        "WHERE is_ground_truth = true AND anomaly_type IN ({})".format(
            ",".join(f"'{t}'" for t in VALID_ANOMALY_TYPES)
        )
    )

    # Build per-consumer anomaly details from ground truth
    consumer_anomaly_map: Dict[str, List[dict]] = {}
    if not gt_df.empty:
        for _, row in gt_df.iterrows():
            cid = row["consumer_id"]
            if cid not in consumer_anomaly_map:
                consumer_anomaly_map[cid] = []
            consumer_anomaly_map[cid].append(dict(row))

    rows = []
    for c in consumers_list:
        cid = c["consumer_id"]

        # ML anomalies for risk computation
        ml_anoms = (
            anomaly_df[anomaly_df["consumer_id"] == cid].to_dict("records")
            if not anomaly_df.empty else []
        )
        c_feat = feat_df[feat_df["consumer_id"] == cid]
        feat_row = c_feat.iloc[-1] if not c_feat.empty else None
        risk = compute_consumer_risk(c, ml_anoms, feat_row)

        # Build detailed anomaly cards from ground truth
        gt_rows = consumer_anomaly_map.get(cid, [])
        type_seen: set = set()
        anomalies = []
        for a in gt_rows:
            atype = a.get("anomaly_type", "")
            if atype in type_seen:
                continue
            type_seen.add(atype)
            meta = ANOMALY_META.get(atype, {})
            anomalies.append({
                "anomaly_type": atype,
                "anomaly_label": meta.get("label", atype.replace("_", " ").title()),
                "severity": a.get("severity", "low"),
                "risk_weight": ANOMALY_WEIGHTS.get(atype, 0),
                "priority": ANOMALY_PRIORITY.get(atype, "Low"),
                "detection_reason": a.get("description", "") or a.get("reason", ""),
                "detected_at": a.get("date", ""),
                "what_it_means": meta.get("what_it_means", ""),
                "how_detected": meta.get("how_detected", ""),
                "risk_impact": meta.get("risk_impact", {}),
                "recommended_action": meta.get("recommended_action", []),
                "icon": meta.get("icon", "bi-exclamation-circle"),
                "color": meta.get("color", "#455a64"),
            })
        anomalies.sort(key=lambda x: -x["risk_weight"])

        # Status based on utility priority score
        score = risk["risk_score"]
        if score >= 90:
            status = "Critical"
        elif score >= 75:
            status = "High"
        elif score >= 50:
            status = "Medium"
        elif score >= 25:
            status = "Low"
        else:
            status = "Normal"

        outstanding = float(c.get("outstanding_amount") or 0)

        # Investigation status from database (default to Open)
        has_tampering_flag = "meter_tampering" in type_seen
        has_voltage = "voltage_issue" in type_seen
        
        db_inv = investigations_db.get(cid)
        if db_inv:
            inv_status = db_inv["status"]
            assigned_to = db_inv.get("assigned_to", "")
            inv_remarks = db_inv.get("remarks", "")
            inv_last_updated = db_inv.get("last_updated", "")
        else:
            # For anomalies that haven't been touched yet
            if len(type_seen) == 0:
                inv_status = "Closed" if score < 25 else "Resolved" if score < 40 else "Open"
            else:
                inv_status = "Open"
            assigned_to = ""
            inv_remarks = ""
            inv_last_updated = ""
        # Latest detection date from anomalies
        detection_dates = [a.get("detected_at", "") for a in anomalies if a.get("detected_at")]
        latest_detection = max(detection_dates) if detection_dates else ""

        # Unified overall risk score (0–100) dynamically calculated
        overall_score = compute_overall_risk_score(gt_rows, feat_row)

        # -------------------------------------------------------------
        # Single Source of Truth for Severity and Recommended Action
        # -------------------------------------------------------------
        from anomaly_config import ANOMALY_WEIGHTS
        primary_type = "None"
        if type_seen:
            sorted_types = sorted(list(type_seen), key=lambda t: ANOMALY_WEIGHTS.get(t, 0), reverse=True)
            primary_type = sorted_types[0]

        # Validation Rule 1
        if primary_type == "None" or overall_score == 0:
            primary_type = "None"
            overall_score = min(24.0, overall_score)
            severity = "Low"
            rec_action = "No Immediate Action"
        else:
            # Step 3: Severity derived ONLY from final Risk Score
            if overall_score >= 75:
                severity = "Critical"
            elif overall_score >= 50:
                severity = "High"
            elif overall_score >= 25:
                severity = "Medium"
            else:
                severity = "Low"
            
            # Step 4: Recommended Action from anomaly type
            if primary_type in ("meter_tampering", "power_theft"):
                rec_action = "Immediate Site Inspection" if primary_type == "meter_tampering" else "Immediate Investigation"
            elif primary_type == "continuous_high_load":
                rec_action = "Remote Meter Verification"
            elif primary_type == "low_power_factor":
                rec_action = "Inspect Inductive Loads"
            elif primary_type == "peak_hour_overload":
                rec_action = "Consumer Awareness"
            elif primary_type == "minor_consumption_variation":
                rec_action = "Monitor"
            elif primary_type == "voltage_issue":
                rec_action = "Schedule Technician Visit"
            elif primary_type in ("consumption_spike", "consumption_drop"):
                rec_action = "Remote Meter Verification"
            else:
                rec_action = "Monitor"
                
        # Final validation fallback
        expected_severity = "Low"
        if overall_score >= 75: expected_severity = "Critical"
        elif overall_score >= 50: expected_severity = "High"
        elif overall_score >= 25: expected_severity = "Medium"
        if severity != expected_severity:
            import logging
            logging.warning(f"Validation failed for {cid} (Severity mismatch). Score {overall_score}, got {severity}. Correcting.")
            severity = expected_severity

        rows.append({
            "consumer_id": cid,
            "consumer_name": risk["name"],
            "zone": risk["zone"],
            "risk_score": risk["risk_score"],
            "overall_risk_score": overall_score,
            "risk_band": overall_risk_band(overall_score),
            "priority": risk["priority"],
            "primary_issue": risk["primary_reason"],
            "revenue_impact": round(outstanding, 0),
            "revenue_risk": risk["revenue_risk"],
            "fraud_risk": risk["fraud_risk"],
            "technical_risk": risk["technical_risk"],
            "behavioral_risk": risk["behavioral_risk"],
            "anomaly_count": len(type_seen),
            "status": status,
            "investigation_status": inv_status,
            "assigned_to": assigned_to,
            "inv_remarks": inv_remarks,
            "inv_last_updated": inv_last_updated,
            "has_tampering": has_tampering_flag,
            "has_voltage_issue": has_voltage,
            "has_high_load": "continuous_high_load" in type_seen,
            "has_spike": "consumption_spike" in type_seen,
            "has_drop": "consumption_drop" in type_seen,
            "latest_detection_date": latest_detection,
            "payment_status": risk["payment_status"],
            "anomalies": anomalies,
            "severity": severity,
            "rec_action": rec_action,
            "primary_anomaly": primary_type,
            "current_load": float(feat_row.get("average_load", 0)) if feat_row is not None and not (hasattr(feat_row, "empty") and feat_row.empty) else 0.0,
        })

    # Sort: overall_risk_score desc, fraud_risk desc, revenue_impact desc
    rows.sort(key=lambda r: (-r["overall_risk_score"], -r["fraud_risk"], -r["revenue_impact"]))
    for rank, item in enumerate(rows[:limit], start=1):
        item["rank"] = rank
    return rows[:limit]
