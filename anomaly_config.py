"""
Tata Power Anomaly Detection Configuration
==========================================
Defines the 5 utility-grade anomalies that Tata Power would realistically
prioritise in a smart meter monitoring platform.

Removed anomalies (peak_hour_overconsumption, phantom_load, night_usage,
poor_power_factor) are converted to AI Insights / Efficiency Recommendations
rather than flagged as anomalies.

Risk Weights:
  meter_tampering      = 40
  consumption_spike    = 25
  consumption_drop     = 20
  voltage_issue        = 15
  continuous_high_load = 10

Risk Score Bands:
  0–25   = Low
  26–50  = Medium
  51–75  = High
  76–100 = Critical
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 5 Valid Anomaly Types (ordered by priority)
# ---------------------------------------------------------------------------
VALID_ANOMALY_TYPES: List[str] = [
    "meter_tampering",
    "consumption_spike",
    "consumption_drop",
    "voltage_issue",
    "continuous_high_load",
]

# ---------------------------------------------------------------------------
# Risk Weights (contribution to overall risk score)
# ---------------------------------------------------------------------------
ANOMALY_WEIGHTS: Dict[str, int] = {
    "meter_tampering": 80,
    "power_theft": 80,
    "continuous_high_load": 55,
    "consumption_spike": 55,
    "consumption_drop": 55,
    "voltage_issue": 35,
    "low_power_factor": 35,
    "peak_hour_overload": 35,
    "abnormal_night_usage": 35,
    "minor_consumption_variation": 15,
    "None": 0,
}

# ---------------------------------------------------------------------------
# Risk Score → Band
# ---------------------------------------------------------------------------
RISK_BANDS = [
    (0, 24, "Low"),
    (25, 49, "Medium"),
    (50, 74, "High"),
    (75, 100, "Critical"),
]


def risk_band(score: int) -> str:
    s = max(0, min(100, score))
    for lo, hi, label in RISK_BANDS:
        if lo <= s <= hi:
            return label
    return "Low"


def compute_anomaly_risk_score(anomaly_types: List[str]) -> int:
    """Sum of weights for all unique anomaly types present (max 100)."""
    total = sum(ANOMALY_WEIGHTS.get(t, 0) for t in set(anomaly_types))
    return min(100, total)


# ---------------------------------------------------------------------------
# Anomaly Metadata (for Admin Dashboard accordion sections + tooltips)
# ---------------------------------------------------------------------------
ANOMALY_META: Dict[str, Dict[str, Any]] = {
    "meter_tampering": {
        "label": "Meter Tampering",
        "icon": "bi-shield-exclamation",
        "color": "#c62828",
        "severity": "Critical",
        "risk_weight": 40,
        "what_it_means": (
            "Potential bypassing or manipulation of smart meter readings "
            "resulting in revenue loss. This is the highest-priority anomaly "
            "for Tata Power as it directly impacts billing accuracy."
        ),
        "how_detected": (
            "Detection Conditions:\n"
            "• Suspicious reduction in recorded consumption compared to historical profile\n"
            "• Known tampering scenario flagged during simulation\n"
            "• Consumption pattern inconsistent with expected appliance load\n"
            "• ML ensemble vote (Random Forest + XGBoost + Isolation Forest)"
        ),
        "risk_impact": {
            "severity": "Critical",
            "risk_score_contribution": 40,
            "business_impact": "Direct revenue loss, potential legal action, field inspection required",
        },
        "recommended_action": [
            "Immediate field inspection",
            "Customer verification & meter seal check",
            "Historical consumption pattern review",
            "Legal/revenue protection team escalation",
        ],
    },
    "consumption_spike": {
        "label": "Consumption Spike",
        "icon": "bi-graph-up-arrow",
        "color": "#e65100",
        "severity": "High",
        "risk_weight": 25,
        "what_it_means": (
            "A sudden, significant increase in electricity consumption "
            "that deviates sharply from the consumer's typical usage pattern."
        ),
        "how_detected": (
            "Detection Conditions:\n"
            "• Consumption deviation > 60% compared to baseline average\n"
            "• Deviation flagged in daily features table\n"
            "• ML model classifies as anomaly based on load_factor and peak_load features"
        ),
        "risk_impact": {
            "severity": "High",
            "risk_score_contribution": 25,
            "business_impact": "Higher bill shock for consumer, potential equipment failure, grid stress",
        },
        "recommended_action": [
            "Notify consumer of unusual consumption",
            "Check for faulty appliances or wiring",
            "Review meter readings for accuracy",
            "Equipment check if sustained",
        ],
    },
    "consumption_drop": {
        "label": "Consumption Drop",
        "icon": "bi-graph-down-arrow",
        "color": "#f57f17",
        "severity": "High",
        "risk_weight": 20,
        "what_it_means": (
            "A sudden, significant decrease in electricity consumption "
            "that may indicate meter issues, disconnection, or tampering."
        ),
        "how_detected": (
            "Detection Conditions:\n"
            "• Consumption deviation < −50% compared to baseline average\n"
            "• Historical usage remains high while current drops sharply\n"
            "• ML model flags based on load_factor and daily_kwh features"
        ),
        "risk_impact": {
            "severity": "High",
            "risk_score_contribution": 20,
            "business_impact": "Possible meter bypass, billing gap, or unauthorized disconnection",
        },
        "recommended_action": [
            "Verify meter connectivity",
            "Field inspection for meter bypass",
            "Cross-check with appliance ground truth",
            "Customer contact for verification",
        ],
    },
    "voltage_issue": {
        "label": "Voltage Issue",
        "icon": "bi-lightning",
        "color": "#1565c0",
        "severity": "Medium",
        "risk_weight": 15,
        "what_it_means": (
            "Abnormal voltage fluctuations detected in the smart meter readings "
            "that exceed the configured variance threshold."
        ),
        "how_detected": (
            "Detection Conditions:\n"
            "• Voltage variance > 40 (configured threshold)\n"
            "• Voltage readings outside 230V ± 10% range\n"
            "• Pattern inconsistent with normal grid behaviour"
        ),
        "risk_impact": {
            "severity": "Medium",
            "risk_score_contribution": 15,
            "business_impact": "Equipment damage risk, appliance failure, potential grid fault",
        },
        "recommended_action": [
            "Power quality audit",
            "Voltage stabiliser check",
            "Distribution transformer inspection",
            "Grid maintenance escalation if widespread",
        ],
    },
    "continuous_high_load": {
        "label": "Continuous High Load",
        "icon": "bi-speedometer2",
        "color": "#6a1b9a",
        "severity": "Medium",
        "risk_weight": 10,
        "what_it_means": (
            "Sustained high electricity consumption over an extended period, "
            "indicating potential equipment inefficiency or unauthorized commercial usage."
        ),
        "how_detected": (
            "Detection Conditions:\n"
            "• Load factor > 0.85 (sustained high usage)\n"
            "• Daily consumption > 25 kWh threshold\n"
            "• Pattern persists for multiple consecutive days"
        ),
        "risk_impact": {
            "severity": "Medium",
            "risk_score_contribution": 10,
            "business_impact": "Higher infrastructure wear, potential overload, tariff category mismatch",
        },
        "recommended_action": [
            "Review tariff category (Residential vs Commercial)",
            "Equipment efficiency audit",
            "Load balancing recommendation",
            "Consumer advisory for usage reduction",
        ],
    },
}

# ---------------------------------------------------------------------------
# Removed Anomaly Types → AI Insights Mapping
# ---------------------------------------------------------------------------
REMOVED_ANOMALY_TO_INSIGHT: Dict[str, Dict[str, str]] = {
    "peak_hour_overconsumption": {
        "label": "Peak Usage Opportunity",
        "icon": "bi-clock-history",
        "description": (
            "Your consumption during peak hours (17:00–24:00) is above average. "
            "Shifting heavy appliance usage to solar hours (09:00–17:00) could "
            "reduce your bill by up to 15%."
        ),
        "tip": "Run washing machine, water heater, and EV charger during 09:00–17:00 to save on ToD charges.",
    },
    "phantom_load": {
        "label": "Standby Power Loss",
        "icon": "bi-plug",
        "description": (
            "Standby power from idle appliances (TVs, chargers, set-top boxes) "
            "is consuming energy 24/7 even when not in active use."
        ),
        "tip": "Use smart power strips and unplug chargers when not in use to eliminate phantom load.",
    },
    "night_usage": {
        "label": "Consumption Pattern Insight",
        "icon": "bi-moon-stars",
        "description": (
            "Unusual energy consumption detected during night hours (23:00–05:00). "
            "This may indicate inefficient night-time appliance usage."
        ),
        "tip": "Schedule EV charging and water heating during night hours (00:00–06:00) to benefit from 15% night rebate.",
    },
    "poor_power_factor": {
        "label": "Power Quality Observation",
        "icon": "bi-activity",
        "description": (
            "Your power factor is below the optimal 0.90 threshold. "
            "Low power factor means reactive power is increasing your bill "
            "without delivering useful energy."
        ),
        "tip": "Install power factor correction capacitors for motors and heavy appliances to improve efficiency.",
    },
}

# All removed types (for filtering)
REMOVED_ANOMALY_TYPES: List[str] = list(REMOVED_ANOMALY_TO_INSIGHT.keys())

# ---------------------------------------------------------------------------
# Consumer Status Logic (using only 5 valid anomalies)
# ---------------------------------------------------------------------------
def compute_consumer_anomaly_status(anomalies: List[dict]) -> Dict[str, Any]:
    """
    Compute consumer status from list of anomaly dicts.
    Only considers the 5 valid anomaly types.

    Returns:
        {
            "status": "Healthy" | "Monitoring" | "Warning" | "Critical",
            "status_detail": str,
            "anomaly_count": int,
            "critical_count": int,
            "anomaly_types_present": list,
            "risk_score": int,
            "risk_band": str,
        }
    """
    valid = [a for a in anomalies if a.get("anomaly_type") in VALID_ANOMALY_TYPES]
    types_present = list(set(a.get("anomaly_type") for a in valid))
    count = len(valid)
    critical = sum(1 for a in valid if a.get("severity") == "critical")
    tampering = any(a.get("anomaly_type") == "meter_tampering" for a in valid)

    risk_score = compute_anomaly_risk_score(types_present)
    band = risk_band(risk_score)

    if tampering or critical >= 2 or risk_score >= 76:
        status = "Critical"
        detail = "Tampering or multiple major anomalies detected."
    elif risk_score >= 51 or count >= 2:
        status = "Warning"
        detail = "One medium-severity anomaly detected."
    elif count >= 1:
        status = "Monitoring"
        detail = "Minor usage deviations observed."
    else:
        status = "Healthy"
        detail = "No significant anomalies detected."

    return {
        "status": status,
        "status_detail": detail,
        "anomaly_count": count,
        "critical_count": critical,
        "anomaly_types_present": types_present,
        "risk_score": risk_score,
        "risk_band": band,
    }


def build_energy_insights_from_removed(removed_anomalies: List[dict]) -> List[dict]:
    """
    Convert removed anomaly types into AI Energy Insights.
    These do NOT affect anomaly counts or status.
    """
    seen = set()
    insights = []
    for a in removed_anomalies:
        atype = a.get("anomaly_type")
        if atype in REMOVED_ANOMALY_TO_INSIGHT and atype not in seen:
            seen.add(atype)
            meta = REMOVED_ANOMALY_TO_INSIGHT[atype]
            insights.append({
                "type": atype,
                "label": meta["label"],
                "icon": meta["icon"],
                "description": meta["description"],
                "tip": meta["tip"],
            })
    return insights
