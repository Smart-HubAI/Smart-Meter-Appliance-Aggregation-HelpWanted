"""
Energy disaggregation using time-window energy attribution (NILM-ready).
Estimates kWh per appliance from 15-minute load signatures.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd


# Typical domestic share benchmarks (India urban household reference)
APPLIANCE_BENCHMARKS = {
    "AC": {"typical_pct": 38, "high_pct": 45},
    "Refrigerator": {"typical_pct": 17, "high_pct": 22},
    "Lighting": {"typical_pct": 12, "high_pct": 18},
    "TV": {"typical_pct": 5, "high_pct": 8},
    "Fan": {"typical_pct": 6, "high_pct": 10},
    "Washing Machine": {"typical_pct": 8, "high_pct": 12},
    "Water Heater": {"typical_pct": 12, "high_pct": 18},
    "Others": {"typical_pct": 5, "high_pct": 10},
}

REDUCTION_TIPS = {
    "AC": (
        "Set AC to 24°C, clean filters monthly, use fan + AC combo, seal doors/windows. "
        "Each 1°C lower can add ~6% to AC energy."
    ),
    "Refrigerator": (
        "Keep fridge 3/4 full, avoid frequent door opening, ensure 10cm wall clearance, "
        "defrost if not frost-free. Old units use 2× modern BEE 5-star models."
    ),
    "Lighting": (
        "Replace incandescent/CFL with LED, use motion sensors outdoors, "
        "switch off daytime lights. LEDs use ~80% less than conventional bulbs."
    ),
    "TV": (
        "Enable TV/set-top box auto power-off, unplug chargers when idle, "
        "avoid gaming consoles on standby overnight."
    ),
    "Fan": (
        "Ensure fans are cleaned regularly and use electronic regulators for better efficiency."
    ),
    "Washing Machine": (
        "Run full loads and use cold water settings where possible to reduce heater usage."
    ),
    "Water Heater": (
        "Set thermostat to 45-50°C and switch off immediately after use. Use insulated pipes."
    ),
    "Others": (
        "Identify standby loads (geyser, washing machine, iron). "
        "Use timer switches and run heavy appliances in off-peak hours if on TOU tariff."
    ),
}


class EnergyDisaggregator:
    """Attribute interval energy to appliance categories from load shape."""

    APPLIANCE_KEYS = ["AC", "Refrigerator", "Lighting", "TV", "Fan", "Washing Machine", "Water Heater", "Others"]

    def __init__(self, readings_df: pd.DataFrame):
        self.df = readings_df.copy()
        self.total_kwh = 0.0
        if not self.df.empty:
            if "timestamp" in self.df.columns:
                self.df["timestamp"] = pd.to_datetime(self.df["timestamp"])
                self.df["hour"] = self.df["timestamp"].dt.hour  # type: ignore
            if "energy_kwh" in self.df.columns:
                self.total_kwh = float(self.df["energy_kwh"].sum())

    def disaggregate(self) -> Dict[str, float]:
        """Percentage breakdown summing to 100."""
        kwh_map = self._attribute_energy_kwh()
        if self.total_kwh <= 0:
            return self._default_breakdown()
        return {
            k: round((v / self.total_kwh) * 100, 1)
            for k, v in kwh_map.items()
        }

    def get_energy_by_appliance_kwh(self, total_kwh: float | None = None) -> Dict[str, float]:
        total = total_kwh if total_kwh is not None else self.total_kwh
        pcts = self.disaggregate()
        return {k: round(total * (p / 100.0), 2) for k, p in pcts.items()}

    def get_detailed_breakdown(self) -> List[Dict[str, Any]]:
        """
        Per-appliance kWh, %, benchmark comparison, and reduction guidance.
        """
        kwh_map = self._attribute_energy_kwh()
        if self.total_kwh <= 0:
            kwh_map = {k: 0.0 for k in self.APPLIANCE_KEYS}

        details = []
        for key in self.APPLIANCE_KEYS:
            kwh = round(kwh_map.get(key, 0), 2)
            pct = round((kwh / self.total_kwh) * 100, 1) if self.total_kwh > 0 else 0
            bench = APPLIANCE_BENCHMARKS[key]
            is_high = pct >= bench["high_pct"]
            is_elevated = pct >= bench["typical_pct"] * 1.15

            monthly_cost = round(kwh * (30 / max(1, self._days_in_data())) * 8.5, 0)

            item = {
                "appliance": key,
                "kwh": kwh,
                "pct": pct,
                "typical_pct": bench["typical_pct"],
                "high_threshold_pct": bench["high_pct"],
                "status": "high" if is_high else ("elevated" if is_elevated else "normal"),
                "is_high": is_high,
                "reduction_tip": REDUCTION_TIPS[key],
                "est_monthly_cost_inr": monthly_cost,
            }
            if is_high:
                excess_pct = pct - bench["typical_pct"]
                item["alert"] = (
                    f"{key} is {excess_pct:.0f}% above typical household share "
                    f"(yours {pct}% vs typical ~{bench['typical_pct']}%)"
                )
                item["potential_saving_inr"] = round(monthly_cost * 0.15, 0)
            details.append(item)

        return details

    def _days_in_data(self) -> int:
        if self.df.empty or "timestamp" not in self.df.columns:
            return 30
        return max(
            1,
            (self.df["timestamp"].max() - self.df["timestamp"].min()).days + 1,
        )

    def _attribute_energy_kwh(self) -> Dict[str, float]:
        """
        Assign measured interval energy to categories using physical heuristics.
        Residual always flows to Others last.
        """
        if self.df.empty or self.total_kwh <= 0:
            return {k: 0.0 for k in self.APPLIANCE_KEYS}

        df = self.df
        baseline_kw = df["power_kw"].quantile(0.15) if "power_kw" in df.columns else 0.2

        # AC: incremental energy when load exceeds baseline during cooling hours
        ac_mask = df["hour"].between(10, 23) & (df["power_kw"] > baseline_kw + 0.35)
        ac_kwh = self._incremental_energy(df, ac_mask, baseline_kw)

        # Refrigerator: 24h baseline draw (compressor) — low stable overnight + day min
        overnight = df[df["hour"].between(0, 6)]
        if len(overnight) > 0:
            fridge_kw = min(float(overnight["power_kw"].median()), baseline_kw + 0.25)
        else:
            fridge_kw = baseline_kw
        # Fridge runs ~24h at compressor duty cycle (~40% of nameplate draw)
        interval_h = 0.25
        fridge_kwh = fridge_kw * interval_h * len(df) * 0.42
        fridge_kwh = min(fridge_kwh, self.total_kwh * 0.22)

        # Lighting: evening uplift (17–23) above morning reference (7–9)
        evening = df[df["hour"].between(17, 23)]
        morning = df[df["hour"].between(7, 9)]
        ev_avg = float(evening["power_kw"].mean()) if len(evening) else 0
        am_avg = float(morning["power_kw"].mean()) if len(morning) else baseline_kw
        light_delta = max(0, ev_avg - am_avg)
        light_kwh = sum(
            max(0, row.energy_kwh - (am_avg * 0.25))
            for row in evening.itertuples()
            if light_delta > 0.05
        )
        light_kwh = min(light_kwh, self.total_kwh * 0.25)

        # High Power Appliances (Washing Machine / Water Heater)
        # Signature: Sudden high spikes (> 1.2kW) usually in morning/evening
        high_power_mask = (df["power_kw"] > baseline_kw + 1.2)
        wash_wh_kwh = self._incremental_energy(df, high_power_mask, baseline_kw)
        
        # Split Wash/WH based on time (Simplified heuristic)
        water_heater_kwh = wash_wh_kwh * 0.7 if any(df["hour"].between(6, 9)) else wash_wh_kwh * 0.3
        washing_machine_kwh = wash_wh_kwh - water_heater_kwh

        # TV and Fans
        tv_kwh = self.total_kwh * 0.05 if any(df["hour"].between(18, 23)) else 0.01
        fan_kwh = self.total_kwh * 0.07 # Fans are often a steady baseline in many regions

        attributed = ac_kwh + fridge_kwh + light_kwh + water_heater_kwh + washing_machine_kwh + tv_kwh + fan_kwh
        others_kwh = max(0, self.total_kwh - attributed)

        raw = {
            "AC": ac_kwh,
            "Refrigerator": fridge_kwh,
            "Lighting": light_kwh,
            "TV": tv_kwh,
            "Fan": fan_kwh,
            "Washing Machine": washing_machine_kwh,
            "Water Heater": water_heater_kwh,
            "Others": others_kwh,
        }

        # Normalize if attribution exceeded total due to overlap
        total_attr = sum(raw.values()) or 1.0
        if total_attr > self.total_kwh * 1.05:
            scale = self.total_kwh / total_attr
            raw = {k: v * scale for k, v in raw.items()}

        return {k: round(raw[k], 2) for k in self.APPLIANCE_KEYS}

    def _incremental_energy(
        self, df: pd.DataFrame, mask: pd.Series, baseline_kw: float
    ) -> float:
        """Sum (power - baseline) * 0.25h for masked intervals."""
        if mask.sum() == 0:
            return 0.0
        subset = df.loc[mask]
        incremental = (subset["power_kw"] - baseline_kw).clip(lower=0) * 0.25
        return float(incremental.sum())

    def _default_breakdown(self) -> Dict[str, float]:
        return {
            "AC": 35.0,
            "Refrigerator": 18.0,
            "Lighting": 15.0,
            "TV": 5.0,
            "Fan": 7.0,
            "Washing Machine": 8.0,
            "Water Heater": 7.0,
            "Others": 5.0,
        }


def disaggregate_consumer(readings_df: pd.DataFrame) -> Dict[str, float]:
    return EnergyDisaggregator(readings_df).disaggregate()
