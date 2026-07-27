"""
Tata Power FY2026-27 Tariff Configuration
==========================================
Source: Tata Power Mumbai Distribution FY27 Tariff Schedule
All rates in INR per kWh. Fixed charges in INR per month.

This file is the single source of truth for all tariff parameters.
Future tariff revisions only require updating this file.

Consumer Categories:
  - Residential (LT-I / LT-II)
  - Commercial (LT-III)
  - Industrial (LT-IV / HT)
  - Public Services (LT-V / Street Lighting)
  - EV Charging (LT-VII)

Progressive Slab Billing:
  - Each slab rate applies ONLY to units within that slab range.
  - Example: 450 units = 100×rate1 + 200×rate2 + 150×rate3

Time-of-Day (ToD) Multipliers (Smart Meter AMI consumers):
  - Night     00:00–06:00: 15% rebate  (×0.85)
  - Morning   06:00–09:00: Normal      (×1.00)
  - Solar     09:00–17:00: 15–25% rebate depending on season
  - Peak      17:00–24:00: 20% surcharge (×1.20)

PPCA (Power Purchase Cost Adjustment):
  - Placeholder — currently 0. Apply when MERC approves revision.
"""

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Residential Tariff (LT-I / LT-II — Domestic)
# (Units = kWh consumed in billing month)
# ---------------------------------------------------------------------------
RESIDENTIAL_SLABS: List[Tuple[float, float, float]] = [
    # (lower_limit, upper_limit, rate_per_unit_INR)
    (0,    100,  3.50),   # Slab 1: 0–100 units  @ ₹3.50
    (100,  300,  7.00),   # Slab 2: 101–300 units @ ₹7.00
    (300,  500,  9.00),   # Slab 3: 301–500 units @ ₹9.00
    (500,  999999.0, 11.00),  # Slab 4: >500 units @ ₹11.00
]
RESIDENTIAL_FIXED_CHARGE: float = 125.0    # INR/month (single-phase meter)
RESIDENTIAL_FIXED_CHARGE_3PH: float = 200.0  # INR/month (three-phase)

# ---------------------------------------------------------------------------
# Commercial Tariff (LT-III — Non-domestic / shops / offices)
# No slabs — flat rate with fixed charge
# ---------------------------------------------------------------------------
COMMERCIAL_RATE: float = 12.50             # INR/kWh
COMMERCIAL_FIXED_CHARGE: float = 350.0    # INR/month

# ---------------------------------------------------------------------------
# Industrial Tariff (LT-IV / HT — Industrial / Factories)
# No slabs — flat rate with higher fixed charge
# ---------------------------------------------------------------------------
INDUSTRIAL_RATE: float = 10.00            # INR/kWh (bulk metering discount)
INDUSTRIAL_FIXED_CHARGE: float = 750.0   # INR/month
INDUSTRIAL_DEMAND_CHARGE: float = 180.0  # INR/kVA per month (max demand)

# ---------------------------------------------------------------------------
# Public Services Tariff (LT-V — Govt, hospitals, schools, street lighting)
# ---------------------------------------------------------------------------
PUBLIC_SERVICES_SLABS: List[Tuple[float, float, float]] = [
    (0,   500, 6.00),    # 0–500 units @ ₹6.00
    (500, 999999.0, 8.50),  # >500 units @ ₹8.50
]
PUBLIC_SERVICES_FIXED_CHARGE: float = 250.0   # INR/month

# ---------------------------------------------------------------------------
# EV Charging Tariff (LT-VII — EV Charging Stations)
# Incentive tariff to promote EV adoption
# ---------------------------------------------------------------------------
EV_CHARGING_RATE: float = 7.50            # INR/kWh (incentive rate)
EV_CHARGING_FIXED_CHARGE: float = 200.0  # INR/month

# ---------------------------------------------------------------------------
# Time-of-Day (ToD) Multipliers
# Applied at interval level using timestamp from smart meter reading
# ---------------------------------------------------------------------------
TOD_SLOTS: Dict[str, Dict] = {
    "night": {
        "label": "Night Hours",
        "hours_start": 0,
        "hours_end": 6,
        "multiplier_default": 0.85,   # 15% rebate
        "description": "00:00–06:00: 15% Night Rebate",
    },
    "morning": {
        "label": "Morning Hours",
        "hours_start": 6,
        "hours_end": 9,
        "multiplier_default": 1.00,   # Normal tariff
        "description": "06:00–09:00: Normal Tariff",
    },
    "solar_summer": {
        "label": "Solar Hours (Apr–Sep)",
        "hours_start": 9,
        "hours_end": 17,
        "multiplier_default": 0.85,   # 15% rebate (summer)
        "description": "09:00–17:00 Apr–Sep: 15% Solar Rebate",
    },
    "solar_winter": {
        "label": "Solar Hours (Oct–Mar)",
        "hours_start": 9,
        "hours_end": 17,
        "multiplier_default": 0.75,   # 25% rebate (winter — more sun incentive)
        "description": "09:00–17:00 Oct–Mar: 25% Solar Rebate",
    },
    "peak": {
        "label": "Peak Hours",
        "hours_start": 17,
        "hours_end": 24,
        "multiplier_default": 1.20,   # 20% surcharge
        "description": "17:00–24:00: 20% Peak Surcharge",
    },
}

# Months classified as summer (Apr–Sep = months 4–9)
SUMMER_MONTHS: set = {4, 5, 6, 7, 8, 9}

# ---------------------------------------------------------------------------
# Taxes & Levies
# ---------------------------------------------------------------------------
ELECTRICITY_DUTY_PCT: float = 0.16        # 16% ED on energy charges (Maharashtra)
PPCA_PER_UNIT: float = 0.00               # PPCA placeholder — update when notified
WHEELING_CHARGE_RESIDENTIAL: float = 0.45  # INR/kWh (open access wheeling, residential)

# ---------------------------------------------------------------------------
# Fuel Adjustment Charge (FAC)
# ---------------------------------------------------------------------------
FAC_PER_UNIT: float = 0.30                # ₹0.30/kWh (Q1 FY27 avg, subject to quarterly revision)

# ---------------------------------------------------------------------------
# Consumer Category Mapping
# Maps consumer_type strings (from DB) → tariff category
# ---------------------------------------------------------------------------
CONSUMER_TYPE_TO_TARIFF: Dict[str, str] = {
    "Residential": "residential",
    "residential": "residential",
    "Commercial": "commercial",
    "commercial": "commercial",
    "Industrial": "industrial",
    "industrial": "industrial",
    "Public Services": "public_services",
    "public_services": "public_services",
    "Street Lighting": "public_services",
    "EV Charging": "ev_charging",
    "ev_charging": "ev_charging",
}

# ---------------------------------------------------------------------------
# Tariff registry — single entry point for all category configs
# ---------------------------------------------------------------------------
TARIFF_REGISTRY: Dict[str, Dict] = {
    "residential": {
        "category": "Residential",
        "billing_type": "slab",
        "slabs": RESIDENTIAL_SLABS,
        "fixed_charge": RESIDENTIAL_FIXED_CHARGE,
        "tod_enabled": True,
    },
    "commercial": {
        "category": "Commercial",
        "billing_type": "flat",
        "rate": COMMERCIAL_RATE,
        "fixed_charge": COMMERCIAL_FIXED_CHARGE,
        "tod_enabled": True,
    },
    "industrial": {
        "category": "Industrial",
        "billing_type": "flat",
        "rate": INDUSTRIAL_RATE,
        "fixed_charge": INDUSTRIAL_FIXED_CHARGE,
        "tod_enabled": True,
    },
    "public_services": {
        "category": "Public Services",
        "billing_type": "slab",
        "slabs": PUBLIC_SERVICES_SLABS,
        "fixed_charge": PUBLIC_SERVICES_FIXED_CHARGE,
        "tod_enabled": False,  # No ToD for public services
    },
    "ev_charging": {
        "category": "EV Charging",
        "billing_type": "flat",
        "rate": EV_CHARGING_RATE,
        "fixed_charge": EV_CHARGING_FIXED_CHARGE,
        "tod_enabled": False,  # Flat incentive rate
    },
}


def get_tariff_config(consumer_type: str) -> Dict:
    """Return tariff config dict for a given consumer_type string."""
    category_key = CONSUMER_TYPE_TO_TARIFF.get(consumer_type, "residential")
    return TARIFF_REGISTRY.get(category_key, TARIFF_REGISTRY["residential"])


def compute_slab_charge(units: float, slabs: List[Tuple[float, float, float]]) -> Tuple[float, List[dict]]:
    """
    Progressive slab billing. Each slab rate applies only to units within that band.

    Returns:
        (total_energy_charge, slab_breakdown_list)

    Example:
        450 units → 100×3.50 + 200×7.00 + 150×9.00 = 350 + 1400 + 1350 = ₹3100
    """
    remaining = units
    total_charge = 0.0
    breakdown = []

    for lower, upper, rate in slabs:
        if remaining <= 0:
            break
        slab_size = upper - lower  # units this slab covers
        units_in_slab = min(remaining, slab_size)
        charge = units_in_slab * rate
        total_charge += charge
        breakdown.append({
            "slab": f"{int(lower)}–{int(upper) if upper != float('inf') else '∞'} units",
            "units": round(units_in_slab, 2),
            "rate": rate,
            "charge": round(charge, 2),
        })
        remaining -= units_in_slab

    return round(total_charge, 2), breakdown


def get_tod_multiplier(hour: int, month: int) -> Tuple[float, str]:
    """
    Return (multiplier, slot_label) for a given hour (0–23) and calendar month (1–12).

    Night    00–06: ×0.85 (15% rebate)
    Morning  06–09: ×1.00 (normal)
    Solar    09–17: ×0.85 summer / ×0.75 winter
    Peak     17–24: ×1.20 (20% surcharge)
    """
    if 0 <= hour < 6:
        return TOD_SLOTS["night"]["multiplier_default"], "night"
    elif 6 <= hour < 9:
        return TOD_SLOTS["morning"]["multiplier_default"], "morning"
    elif 9 <= hour < 17:
        slot_key = "solar_summer" if month in SUMMER_MONTHS else "solar_winter"
        return TOD_SLOTS[slot_key]["multiplier_default"], "solar"
    else:
        return TOD_SLOTS["peak"]["multiplier_default"], "peak"
