"""
Anomaly detection for smart meter consumption patterns.
Tata Power–style severity from % deviation vs usual daily consumption.

Severity (|deviation| from baseline):
  >= 20% and < 50%  -> Low
  >= 50% and < 100% -> Medium
  >= 100%           -> High
  2+ consecutive anomaly days -> Critical
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyDetector:
    """
    Detects daily usage deviations from the consumer's usual (median) consumption.
  ML-ready: replace baseline/severity with model scores later.
    """

    # Minimum |deviation %| to flag a day as anomalous
    ANOMALY_THRESHOLD_PCT = 20.0

    def __init__(self, readings_df: pd.DataFrame, recent_days: int = 14):
        self.df = readings_df.copy()
        self.recent_days = recent_days
        if not self.df.empty and "timestamp" in self.df.columns:
            self.df["timestamp"] = pd.to_datetime(self.df["timestamp"])

    def detect(self) -> Dict[str, Any]:
        """Run detection on daily consumption vs usual baseline."""
        if self.df.empty:
            return self._no_anomaly_response()

        daily = self._aggregate_daily()
        if len(daily) < 3:
            return self._no_anomaly_response()

        # Usual consumption: median daily kWh (robust "typical" day)
        baseline_kwh = float(daily["energy_kwh"].median())
        if baseline_kwh <= 0:
            baseline_kwh = float(daily["energy_kwh"].mean()) or 1.0

        anomalies = self._evaluate_days(daily, baseline_kwh)
        anomalies = self._apply_consecutive_critical(anomalies, daily)

        interval_anomaly = self._detect_interval_spike(baseline_kwh / 96)

        recent_anomalies = [a for a in anomalies if a.get("in_recent_window")]

        if not recent_anomalies:
            if interval_anomaly.get("is_anomalous"):
                return {
                    "anomaly_status": "anomaly_detected",
                    "anomaly_reason": interval_anomaly["reason"],
                    "severity": interval_anomaly["severity"],
                    "baseline_daily_kwh": round(baseline_kwh, 2),
                    "anomalies": [],
                    "interval_anomaly": interval_anomaly,
                    "is_anomalous": True,
                }
            return self._no_anomaly_response(baseline_kwh)

        # Highest severity among recent days
        severity_order = {
            AnomalySeverity.LOW.value: 1,
            AnomalySeverity.MEDIUM.value: 2,
            AnomalySeverity.HIGH.value: 3,
            AnomalySeverity.CRITICAL.value: 4,
        }
        worst = max(
            recent_anomalies,
            key=lambda a: severity_order.get(a["severity"], 0),
        )
        status = "anomaly_detected"
        critical_count = sum(
            1 for a in recent_anomalies if a["severity"] == AnomalySeverity.CRITICAL.value
        )
        if critical_count >= 1 or len(recent_anomalies) >= 3:
            status = "suspicious_behavior"

        return {
            "anomaly_status": status,
            "anomaly_reason": worst["reason"],
            "severity": worst["severity"],
            "baseline_daily_kwh": round(baseline_kwh, 2),
            "anomalies": anomalies,
            "recent_anomalies": recent_anomalies,
            "interval_anomaly": interval_anomaly,
            "is_anomalous": True,
            "latest_day": worst,
        }

    def _evaluate_days(
        self, daily: pd.DataFrame, baseline_kwh: float
    ) -> List[Dict[str, Any]]:
        """Flag each day with deviation >= 20% and assign severity."""
        from datetime import timedelta

        max_date = daily["date"].max()
        min_date = max_date - timedelta(days=self.recent_days) if hasattr(max_date, "toordinal") else None

        anomalies: List[Dict[str, Any]] = []

        for _, row in daily.iterrows():
            day_kwh = float(row["energy_kwh"])
            row_date = row["date"]
            date_str = (
                row_date.strftime("%Y-%m-%d")
                if hasattr(row_date, "strftime")
                else str(row_date)
            )

            deviation_pct, direction = self._deviation_percent(day_kwh, baseline_kwh)

            if abs(deviation_pct) < self.ANOMALY_THRESHOLD_PCT:
                continue

            severity = self._severity_from_deviation(abs(deviation_pct))
            in_recent = min_date is None or row_date >= min_date

            if direction == "increase":
                atype = "sudden_increase"
                reason = (
                    f"Usually {baseline_kwh:.1f} kWh/day; on {date_str} usage was "
                    f"{day_kwh:.1f} kWh/day — increase of {deviation_pct:.0f}% "
                    f"(above typical by {day_kwh - baseline_kwh:.1f} kWh)"
                )
            else:
                atype = "sudden_decrease"
                reason = (
                    f"Usually {baseline_kwh:.1f} kWh/day; on {date_str} usage was "
                    f"{day_kwh:.1f} kWh/day — decrease of {abs(deviation_pct):.0f}% "
                    f"(below typical by {baseline_kwh - day_kwh:.1f} kWh)"
                )

            anomalies.append({
                "date": date_str,
                "type": atype,
                "reason": reason,
                "severity": severity.value,
                "consumption_kwh": round(day_kwh, 2),
                "baseline_kwh": round(baseline_kwh, 2),
                "deviation_pct": round(deviation_pct, 1),
                "direction": direction,
                "in_recent_window": in_recent,
                "consecutive_streak": 1,
            })

        return anomalies

    def _apply_consecutive_critical(
        self, anomalies: List[Dict[str, Any]], daily: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Escalate to Critical when 2+ anomaly days occur in a row."""
        if not anomalies:
            return anomalies

        anomaly_dates = {a["date"] for a in anomalies}
        sorted_dates = sorted(daily["date"].unique())

        date_to_streak: Dict[str, int] = {}
        streak = 0
        for d in sorted_dates:
            d_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            if d_str in anomaly_dates:
                streak += 1
            else:
                streak = 0
            if d_str in anomaly_dates:
                date_to_streak[d_str] = streak

        for a in anomalies:
            streak_len = date_to_streak.get(a["date"], 1)
            a["consecutive_streak"] = streak_len
            if streak_len >= 2:
                a["severity"] = AnomalySeverity.CRITICAL.value
                a["reason"] += (
                    f" — CRITICAL: {streak_len} consecutive anomaly days detected"
                )

        return anomalies

    @staticmethod
    def _deviation_percent(day_kwh: float, baseline_kwh: float) -> Tuple[float, str]:
        """
        Percent change vs usual. Positive = increase, negative = decrease.
        Example: usual 15, today 35 -> +133.3%
        """
        if baseline_kwh <= 0:
            return 0.0, "increase"
        pct = ((day_kwh - baseline_kwh) / baseline_kwh) * 100.0
        direction = "increase" if pct >= 0 else "decrease"
        return pct, direction

    @staticmethod
    def _severity_from_deviation(abs_deviation_pct: float) -> AnomalySeverity:
        """Map |deviation %| to Tata Power severity bands."""
        if abs_deviation_pct >= 100:
            return AnomalySeverity.HIGH
        if abs_deviation_pct >= 50:
            return AnomalySeverity.MEDIUM
        if abs_deviation_pct >= 20:
            return AnomalySeverity.LOW
        return AnomalySeverity.LOW

    def _aggregate_daily(self) -> pd.DataFrame:
        self.df["date"] = self.df["timestamp"].dt.date
        return (
            self.df.groupby("date", as_index=False)["energy_kwh"]
            .sum()
        )

    def _detect_interval_spike(self, avg_interval_kwh: float) -> Dict[str, Any]:
        if self.df.empty or avg_interval_kwh <= 0:
            return {"is_anomalous": False}

        recent = self.df.tail(96)
        max_interval = recent["energy_kwh"].max()
        if max_interval > avg_interval_kwh * 3:
            return {
                "is_anomalous": True,
                "reason": "Abnormally high 15-minute demand spike in last 24 hours",
                "severity": AnomalySeverity.HIGH.value,
            }
        return {"is_anomalous": False}

    def _no_anomaly_response(self, baseline_kwh: float = 0) -> Dict[str, Any]:
        return {
            "anomaly_status": "normal",
            "anomaly_reason": "Consumption within ±20% of usual daily pattern",
            "severity": AnomalySeverity.LOW.value,
            "baseline_daily_kwh": round(baseline_kwh, 2),
            "anomalies": [],
            "is_anomalous": False,
        }


def detect_anomalies(readings_df: pd.DataFrame) -> Dict[str, Any]:
    return AnomalyDetector(readings_df).detect()


def scan_all_consumers(readings_df: pd.DataFrame) -> List[Dict[str, Any]]:
    flagged = []
    if readings_df.empty:
        return flagged

    for consumer_id, group in readings_df.groupby("consumer_id"):
        result = AnomalyDetector(group).detect()
        if result.get("is_anomalous"):
            latest = result.get("latest_day") or {}
            flagged.append({
                "consumer_id": consumer_id,
                "anomaly_status": result["anomaly_status"],
                "anomaly_reason": result["anomaly_reason"],
                "severity": result["severity"],
                "baseline_daily_kwh": result.get("baseline_daily_kwh"),
                "deviation_pct": latest.get("deviation_pct"),
                "anomaly_count": len(result.get("recent_anomalies", [])),
            })
    return flagged
