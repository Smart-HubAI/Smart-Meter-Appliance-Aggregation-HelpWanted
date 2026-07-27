"""
Appliance simulation engine: 100 consumers, 90 days, mixed 15/30-minute AMI.
Generates interval ground-truth appliance loads that sum to meter consumption.
Upgraded to use strict realistic profiles and temperatures.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import math

DAYS = 90
NUM_CONSUMERS = 100

APPLIANCE_COLS = [
    "ac_kw",
    "refrigerator_kw",
    "lighting_kw",
    "television_kw",
    "washing_machine_kw",
    "water_heater_kw",
    "fan_kw",
    "miscellaneous_kw",
]

CONSUMER_FRIENDLY_APPLIANCES = {
    "Air Conditioner (AC)": "ac_kw",
    "Refrigerator": "refrigerator_kw",
    "Lighting": "lighting_kw",
    "Television & Entertainment": "television_kw",
    "Washing Machine": "washing_machine_kw",
    "Water Heater / Geyser": "water_heater_kw",
    "Fans": "fan_kw",
    "Miscellaneous Appliances": "miscellaneous_kw",
}

SCENARIOS = [
    "normal", "peak_hour_overconsumption", "sudden_spike", "continuous_high_load",
    "poor_power_factor", "voltage_fluctuation", "sudden_drop", "meter_tampering",
    "abnormal_night_usage", "phantom_load",
]

# Per-appliance Power Factor ranges (lagging, inductive loads)
APPLIANCE_PF_PROFILES = {
    "ac_kw":              (0.80, 0.90),
    "refrigerator_kw":    (0.85, 0.95),
    "fan_kw":             (0.70, 0.85),
    "lighting_kw":        (0.90, 0.98),
    "television_kw":      (0.95, 0.99),
    "washing_machine_kw": (0.75, 0.90),
    "water_heater_kw":    (0.98, 1.00),
    "miscellaneous_kw":   (0.85, 0.97),
}

ZONES = ["Metro Zone", "Industrial Hub", "Suburban", "Commercial District"]

SCENARIO_EVENT_MAP = {
    "normal":                     ("Normal",          "Closed",  "None"),
    "peak_hour_overconsumption":  ("Current Overload", "Closed",  "None"),
    "sudden_spike":               ("Voltage Event",    "Closed",  "None"),
    "continuous_high_load":       ("Current Overload", "Closed",  "None"),
    "poor_power_factor":          ("Power Failure",    "Closed",  "None"),
    "voltage_fluctuation":        ("Voltage Event",    "Closed",  "None"),
    "sudden_drop":                ("Power Failure",    "Trip",    "None"),
    "meter_tampering":            ("Tamper Detected",  "Closed",  "Tamper"),
    "abnormal_night_usage":       ("Normal",           "Closed",  "None"),
    "phantom_load":               ("Reverse Current",  "Closed",  "None"),
}

FIRST_NAMES = [
    "Rajesh", "Priya", "Amit", "Sneha", "Vikram", "Anita", "Rahul", "Suresh",
    "Kavita", "Meera", "Arjun", "Deepa", "Sanjay", "Lakshmi", "Rohan", "Pooja",
    "Manish", "Neha", "Kiran", "Divya", "Ashok", "Sunita", "Gaurav", "Anjali",
]
LAST_NAMES = [
    "Kumar", "Sharma", "Patel", "Reddy", "Singh", "Desai", "Mehta", "Iyer",
    "Nair", "Joshi", "Gupta", "Verma", "Rao", "Pillai", "Chopra", "Malhotra",
]
CITIES = [
    "Mumbai, MH", "Delhi, DL", "Ahmedabad, GJ", "Hyderabad, TS", "Jaipur, RJ",
    "Pune, MH", "Surat, GJ", "Chennai, TN", "Kochi, KL", "Bangalore, KA",
]

@dataclass
class ConsumerSimProfile:
    consumer_id: str
    name: str
    address: str
    profile_type: str
    consumer_category: str
    base_load: float
    scenario: str
    meter_interval: int
    outstanding_amount: float = 0.0
    days_overdue: int = 0
    payment_status: str = "Current"
    risk_category: str = "Normal"
    monthly_kwh_target: Tuple[float, float] = (100.0, 300.0)
    zone: str = ""
    segment: str = ""
    consumer_type: str = "Residential"
    pf_bias: float = 0.0
    
    # Ownership Flags
    has_ac: bool = False
    has_hvac: bool = False
    has_refrigerator: bool = False
    has_com_refrigeration: bool = False
    has_washing_machine: bool = False
    has_water_heater: bool = False
    has_tv: bool = False
    has_microwave: bool = False
    has_induction: bool = False
    has_kettle: bool = False
    has_purifier: bool = False
    has_wifi: bool = False
    has_pc_laptop: bool = False
    has_iron: bool = False
    has_mixer: bool = False
    has_air_fryer: bool = False
    has_dishwasher: bool = False
    has_ev_charger: bool = False
    has_pos: bool = False
    has_printers: bool = False
    has_ups: bool = False

def _build_profiles() -> List[ConsumerSimProfile]:
    profiles = []
    # Mix of profiles based on User requirement: Primarily residential, some commercial.
    # We have 100 consumers. Let's do 85 Residential, 15 Commercial.
    
    residential_types = [
        ("Small Apartment", 30),
        ("Middle Income Apartment", 35),
        ("Premium Apartment", 15),
        ("Independent House", 5)
    ]
    
    commercial_types = [
        ("Office", 5),
        ("Retail Shop", 4),
        ("Restaurant", 3),
        ("School", 1),
        ("Hospital", 1),
        ("Bank", 1)
    ]
    
    profile_distribution = []
    for pt, count in residential_types:
        profile_distribution.extend([(pt, "Residential")] * count)
    for pt, count in commercial_types:
        profile_distribution.extend([(pt, "Commercial")] * count)
        
    for i in range(NUM_CONSUMERS):
        rng = np.random.default_rng(i + 42)
        cid = f"CON{i + 1:03d}"
        fname = FIRST_NAMES[i % len(FIRST_NAMES)]
        lname = LAST_NAMES[(i * 3) % len(LAST_NAMES)]
        city = CITIES[i % len(CITIES)]
        meter_interval = 15 if i < 50 else 30
        
        ptype, cat = profile_distribution[i]
        
        # Base attributes
        zone = ZONES[i % len(ZONES)]
        ctype = "Residential" if cat == "Residential" else "Commercial"
        seg = "premium" if ptype in ("Premium Apartment", "Independent House", "Hospital", "Office") else ("standard" if ptype in ("Middle Income Apartment", "Retail Shop", "Restaurant", "Bank", "School") else "basic")
        p = ConsumerSimProfile(
            consumer_id=cid,
            name=f"{fname} {lname}" if cat == "Residential" else f"{lname} {ptype}",
            address=f"{city}",
            profile_type=ptype,
            consumer_category=cat,
            consumer_type=ctype,
            base_load=1.0,
            scenario="normal",
            meter_interval=meter_interval,
            zone=zone,
            segment=seg,
            pf_bias=rng.uniform(-0.03, 0.03),
        )
        
        # Assign Ownership based on Profile
        if ptype == "Small Apartment":
            p.monthly_kwh_target = (70, 150)
            p.has_refrigerator = True
            p.has_tv = True
            p.has_wifi = rng.random() > 0.2
            p.has_mixer = True
            p.has_iron = True
            # No AC, No Wash
        elif ptype == "Middle Income Apartment":
            p.monthly_kwh_target = (180, 350)
            p.has_refrigerator = True
            p.has_tv = True
            p.has_wifi = True
            p.has_mixer = True
            p.has_iron = True
            p.has_washing_machine = True
            p.has_ac = rng.random() > 0.3 # 70% chance
            p.has_water_heater = True
            p.has_pc_laptop = True
            p.has_microwave = rng.random() > 0.5
            p.has_purifier = True
        elif ptype in ("Premium Apartment", "Independent House"):
            p.monthly_kwh_target = (400, 1200)
            p.has_refrigerator = True
            p.has_tv = True
            p.has_wifi = True
            p.has_mixer = True
            p.has_iron = True
            p.has_washing_machine = True
            p.has_ac = True
            p.has_water_heater = True
            p.has_pc_laptop = True
            p.has_microwave = True
            p.has_purifier = True
            p.has_induction = rng.random() > 0.5
            p.has_kettle = True
            p.has_air_fryer = rng.random() > 0.3
            p.has_dishwasher = rng.random() > 0.4
            p.has_ev_charger = rng.random() > 0.8
        elif ptype == "Office":
            p.monthly_kwh_target = (800, 2500)
            p.has_hvac = True
            p.has_pc_laptop = True
            p.has_printers = True
            p.has_ups = True
            p.has_wifi = True
            p.has_kettle = True
            p.has_microwave = True
            p.has_refrigerator = True
        elif ptype == "Retail Shop":
            p.monthly_kwh_target = (300, 900)
            p.has_ac = True
            p.has_pos = True
            p.has_wifi = True
            p.has_tv = rng.random() > 0.5
        elif ptype == "Restaurant":
            p.monthly_kwh_target = (1500, 4500)
            p.has_hvac = True
            p.has_com_refrigeration = True
            p.has_pos = True
            p.has_wifi = True
            p.has_microwave = True
            p.has_induction = True
        elif ptype in ("School", "Hospital", "Bank"):
            p.monthly_kwh_target = (2000, 8000)
            p.has_hvac = True
            p.has_pc_laptop = True
            p.has_printers = True
            p.has_ups = True
            p.has_com_refrigeration = ptype == "Hospital"
            p.has_water_heater = ptype == "Hospital"

        # Apply basic scenarios to 5%
        if rng.random() < 0.05:
            p.scenario = rng.choice(SCENARIOS[1:])
            
        p.base_load = np.mean(p.monthly_kwh_target) / 720.0 # roughly kW mean
        profiles.append(p)
    return profiles

CONSUMER_PROFILES: List[ConsumerSimProfile] = _build_profiles()

def _simulate_temperature(ts: datetime) -> float:
    # Smooth temperature curve between 15C (winter) to 42C (summer peak)
    # Plus diurnal variation
    day_of_year = ts.timetuple().tm_yday
    hour = ts.hour + ts.minute / 60.0
    
    # Seasonal base (peak in May ~ day 135)
    season_base = 25 + 10 * math.sin((day_of_year - 45) * 2 * math.pi / 365)
    
    # Diurnal (peak at 14:00)
    diurnal = 5 * math.sin((hour - 8) * 2 * math.pi / 24)
    
    return season_base + diurnal

def _generate_interval_appliances(
    profile: ConsumerSimProfile,
    ts: datetime,
    rng: np.random.Generator,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Returns (apps_kw, apps_pf) where apps_pf has per-appliance power factor."""
    hour = ts.hour + ts.minute / 60.0
    temp_c = _simulate_temperature(ts)
    weekend = ts.weekday() >= 5
    
    apps = {
        "ac_kw": 0.0, "refrigerator_kw": 0.0, "lighting_kw": 0.0,
        "television_kw": 0.0, "washing_machine_kw": 0.0, "water_heater_kw": 0.0,
        "fan_kw": 0.0, "miscellaneous_kw": 0.0,
    }
    apps_pf = {}
    
    # --- RESIDENTIAL LOGIC ---
    if profile.consumer_category == "Residential":
        # Lighting (Morning 6-8, Evening 18-23)
        if 6 <= hour < 8 or 18 <= hour < 23.5:
            apps["lighting_kw"] += rng.uniform(0.04, 0.12) if profile.profile_type == "Small Apartment" else rng.uniform(0.1, 0.4)
            
        # Fans (Increase with temp, mostly at night/evening)
        if temp_c > 22:
            fan_usage = rng.uniform(0.05, 0.15) if profile.profile_type == "Small Apartment" else rng.uniform(0.15, 0.4)
            apps["fan_kw"] += fan_usage
            
        # Refrigerator (Duty Cycle)
        if profile.has_refrigerator:
            # Simple compressor duty cycle: ON 40% of the time, more if hot
            duty = 0.3 + 0.01 * (temp_c - 20)
            if rng.random() < duty:
                apps["refrigerator_kw"] += rng.uniform(0.1, 0.25)
                
        # AC (Temp dependent, mostly evening/night)
        if profile.has_ac and temp_c > 28:
            if 14 <= hour < 17 or 20 <= hour < 24 or 0 <= hour < 6:
                # AC cycles ON
                if rng.random() < 0.7:
                    ac_power = 1.0 + 0.05 * (temp_c - 28)
                    apps["ac_kw"] += rng.uniform(ac_power*0.8, ac_power*1.2)
                    
        # TV (Evening, Weekend)
        if profile.has_tv:
            tv_prob = 0.8 if (19 <= hour < 23) else (0.4 if weekend and 10 <= hour < 23 else 0.05)
            if rng.random() < tv_prob:
                apps["television_kw"] += rng.uniform(0.05, 0.15)
                
        # Washing Machine (Discrete cycles: morning or weekend)
        if profile.has_washing_machine:
            wash_prob = 0.02 if not weekend else 0.05
            if (7 <= hour < 10) and rng.random() < wash_prob:
                apps["washing_machine_kw"] += rng.uniform(0.4, 1.2)
                
        # Water Heater (Morning/Evening, Temp dependent)
        if profile.has_water_heater and temp_c < 30:
            heater_prob = 0.1 if (6 <= hour < 9 or 18 <= hour < 20) else 0.01
            if rng.random() < heater_prob:
                apps["water_heater_kw"] += rng.uniform(1.5, 3.0)
                
        # Miscellaneous (Router, PC, Cooking etc)
        base_misc = 0.02
        if profile.has_wifi: base_misc += 0.01
        if profile.has_pc_laptop and (18 <= hour < 23): base_misc += rng.uniform(0.05, 0.1)
        if profile.has_microwave and (7 <= hour < 9 or 19 <= hour < 21) and rng.random() < 0.1: base_misc += rng.uniform(0.8, 1.5)
        if profile.has_induction and (7 <= hour < 9 or 19 <= hour < 21) and rng.random() < 0.2: base_misc += rng.uniform(1.0, 2.0)
        apps["miscellaneous_kw"] += base_misc
        # Water Heater (Cold weather, morning/evening)
        if profile.has_water_heater and temp_c < 25:
            if (6 <= hour < 9 or 18 <= hour < 20) and rng.random() < 0.3:
                apps["water_heater_kw"] += rng.uniform(1.5, 3.0)

        # Misc loads
        misc = 0.0
        if profile.has_wifi: misc += rng.uniform(0.005, 0.015)
        # Chargers (Night)
        if 0 <= hour < 7: misc += rng.uniform(0.01, 0.03)
        
        if profile.has_pc_laptop:
            if (9 <= hour < 18 and weekend) or (19 <= hour < 23):
                if rng.random() < 0.4: misc += rng.uniform(0.04, 0.08)
                
        # Kitchen Appliances (Microwave, Kettle, Induction, Mixer) - Spikes during meal times
        meal_time = (7 <= hour < 9) or (12 <= hour < 14) or (19 <= hour < 21)
        if meal_time and rng.random() < 0.15:
            if profile.has_microwave: misc += rng.uniform(0.8, 1.2)
            if profile.has_kettle: misc += rng.uniform(1.0, 1.5)
            if profile.has_induction: misc += rng.uniform(1.2, 2.0)
            if profile.has_mixer: misc += rng.uniform(0.3, 0.6)
            
        apps["miscellaneous_kw"] += misc
        
    # --- COMMERCIAL LOGIC ---
    elif profile.consumer_category == "Commercial":
        is_open = False
        if profile.profile_type in ("Office", "Bank", "School"):
            is_open = (8 <= hour < 18) and not weekend
        elif profile.profile_type == "Retail Shop":
            is_open = (10 <= hour < 21)
        elif profile.profile_type == "Restaurant":
            is_open = (11 <= hour < 23)
            
        if is_open:
            apps["lighting_kw"] += rng.uniform(0.5, 2.5)
            if profile.has_hvac and temp_c > 24:
                apps["ac_kw"] += rng.uniform(2.0, 8.0)
            if profile.has_ac and temp_c > 26:
                apps["ac_kw"] += rng.uniform(1.0, 3.0)
                
            misc = 0.0
            if profile.has_pc_laptop: apps["television_kw"] += rng.uniform(0.2, 1.0) # Map PCs to TV/Electronics
            if profile.has_pos: apps["television_kw"] += rng.uniform(0.05, 0.15)
            if profile.has_printers and rng.random() < 0.2: misc += rng.uniform(0.3, 0.8)
            if profile.has_ups: misc += rng.uniform(0.05, 0.2)
            if profile.has_wifi: misc += rng.uniform(0.01, 0.05)
            
            if profile.profile_type == "Restaurant" and profile.has_induction:
                misc += rng.uniform(2.0, 5.0)
                
            apps["miscellaneous_kw"] += misc
            
        # Continuous commercial loads
        if profile.has_com_refrigeration:
            duty = 0.6 + 0.01 * (temp_c - 20)
            if rng.random() < min(1.0, duty):
                apps["refrigerator_kw"] += rng.uniform(1.0, 3.5)
        elif profile.has_refrigerator:
            if rng.random() < 0.4:
                apps["refrigerator_kw"] += rng.uniform(0.1, 0.25)
                
        # Standby
        if not is_open:
            apps["miscellaneous_kw"] += rng.uniform(0.05, 0.2)

    # Ensure no negative values
    for k in apps:
        apps[k] = max(0.0, round(apps[k], 4))

    # Compute per-appliance power factor (only for active appliances)
    for app_col in APPLIANCE_COLS:
        if apps[app_col] > 0.001:
            pf_lo, pf_hi = APPLIANCE_PF_PROFILES[app_col]
            base_pf = (pf_lo + pf_hi) / 2.0 + profile.pf_bias
            jitter = rng.normal(0, (pf_hi - pf_lo) / 6.0)
            pf_val = float(np.clip(base_pf + jitter, pf_lo - 0.02, pf_hi + 0.02))
            pf_val = float(np.clip(pf_val, 0.60, 1.00))
            apps_pf[app_col] = round(pf_val, 4)

    return apps, apps_pf

def _apply_scenario(profile, apps, ts, day_index, rng):
    hour = ts.hour + ts.minute / 60.0
    meta = {"is_anomaly": 0, "anomaly_type": None, "severity": "low"}
    scenario = profile.scenario

    if scenario == "normal":
        return apps, meta
    if scenario == "peak_hour_overconsumption" and 18 <= hour < 21:
        apps["ac_kw"] *= 1.9
        apps["lighting_kw"] *= 1.5
        meta = {"is_anomaly": 1, "anomaly_type": "peak_hour_overconsumption", "severity": "medium"}
    elif scenario == "sudden_spike" and day_index >= 62:
        apps["ac_kw"] *= 2.5
        apps["television_kw"] *= 1.8
        meta = {"is_anomaly": 1, "anomaly_type": "consumption_spike", "severity": "high"}
    elif scenario == "continuous_high_load":
        for key in apps: apps[key] *= 1.4
        if day_index % 2 == 0: meta = {"is_anomaly": 1, "anomaly_type": "continuous_high_load", "severity": "medium"}
    elif scenario == "phantom_load":
        apps["miscellaneous_kw"] += 0.3 + 0.1 * rng.random()
        if rng.random() < 0.12: meta = {"is_anomaly": 1, "anomaly_type": "phantom_load", "severity": "low"}
    elif scenario == "poor_power_factor":
        # PF scenario - events generated via meter_events, not load modification
        if rng.random() < 0.15: meta = {"is_anomaly": 1, "anomaly_type": "poor_power_factor", "severity": "medium"}
    elif scenario == "voltage_fluctuation":
        if rng.random() < 0.10: meta = {"is_anomaly": 1, "anomaly_type": "voltage_fluctuation", "severity": "medium"}
    elif scenario == "sudden_drop":
        if day_index >= 30 and rng.random() < 0.08:
            for key in apps: apps[key] *= 0.3
            meta = {"is_anomaly": 1, "anomaly_type": "sudden_drop", "severity": "high"}
    elif scenario == "meter_tampering":
        if rng.random() < 0.10: meta = {"is_anomaly": 1, "anomaly_type": "meter_tampering", "severity": "high"}
    elif scenario == "abnormal_night_usage":
        if 0 <= hour < 6 and rng.random() < 0.15:
            apps["miscellaneous_kw"] += 0.5
            meta = {"is_anomaly": 1, "anomaly_type": "abnormal_night_usage", "severity": "low"}
    return apps, meta

def _meter_electrical(power_kw, rng, scenario):
    pf = min(0.99, max(0.82, 0.92 + rng.normal(0, 0.02)))
    
    # Return dummy values for voltage and current since they are removed from analytics
    # but still expected by the data loader signatures for now.
    return 0.0, 0.0, round(pf, 2)


def _compute_aggregate_electrical(
    apps: Dict[str, float], apps_pf: Dict[str, float],
) -> Tuple[float, float, float]:
    """Compute aggregate Q, S, PF from per-appliance P and PF.
    Returns (reactive_kvar, apparent_kva, agg_pf).
    """
    total_p, total_q = 0.0, 0.0
    for col, p_kw in apps.items():
        total_p += p_kw
        if p_kw > 0.001 and col in apps_pf:
            theta = math.acos(min(1.0, max(0.0, apps_pf[col])))
            total_q += p_kw * math.tan(theta)
    s_kva = math.sqrt(total_p ** 2 + total_q ** 2)
    agg_pf = total_p / s_kva if s_kva > 1e-9 else 1.0
    return round(total_q, 4), round(s_kva, 4), round(agg_pf, 4)


def _generate_meter_events(scenario: str, rng: np.random.Generator, is_anomaly: bool) -> Tuple[str, str, str]:
    """Generate (meter_event_flag, relay_status, tamper_flag) from scenario."""
    if not is_anomaly or scenario == "normal":
        return "Normal", "Closed", "None"
    event, relay, tamper = SCENARIO_EVENT_MAP.get(scenario, ("Normal", "Closed", "None"))
    if rng.random() < 0.3:
        event, relay, tamper = "Normal", "Closed", "None"
    return event, relay, tamper

def _scale_to_target(meter_rows, appliance_rows, target_monthly):
    total_90_day = sum(r["energy_kwh"] for r in meter_rows)
    if total_90_day <= 0: return
    target_90_day = ((target_monthly[0] + target_monthly[1]) / 2) * (DAYS / 30)
    factor = target_90_day / total_90_day
    for row in meter_rows:
        row["power_kw"] = round(row["power_kw"] * factor, 3)
        row["energy_kwh"] = round(row["energy_kwh"] * factor, 4)
        row["current"] = round(row["current"] * factor, 2)
        row["reactive_power_kvar"] = round(row["reactive_power_kvar"] * factor, 4)
        row["reactive_energy_kvarh"] = round(row["reactive_energy_kvarh"] * factor, 4)
        row["apparent_power_kva"] = round(row["apparent_power_kva"] * factor, 4)
        s = row["apparent_power_kva"]
        p = row["power_kw"]
        row["power_factor"] = min(1.0, round(p / s, 4)) if s > 1e-9 else 1.0
    for row in appliance_rows:
        for col in APPLIANCE_COLS:
            row[col] = round(row[col] * factor, 4)

def generate_consumer_dataset(profile: ConsumerSimProfile, start_date: Optional[datetime] = None):
    start_date = start_date or (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS))
    rng = np.random.default_rng(abs(hash(profile.consumer_id)) % (2**32))
    meter_rows, appliance_rows, anomaly_days = [], [], {}
    ts = start_date
    interval_h = profile.meter_interval / 60
    intervals_per_day = int(24 * 60 / profile.meter_interval)

    for day in range(DAYS):
        for _ in range(intervals_per_day):
            apps, apps_pf = _generate_interval_appliances(profile, ts, rng)
            apps, meta = _apply_scenario(profile, apps, ts, day, rng)
            power_kw = sum(apps.values())
            voltage, current, _old_pf = _meter_electrical(power_kw, rng, profile.scenario)
            reactive_kvar, apparent_kva, agg_pf = _compute_aggregate_electrical(apps, apps_pf)
            temp_c = _simulate_temperature(ts)
            event_flag, relay, tamper = _generate_meter_events(
                profile.scenario, rng, bool(meta.get("is_anomaly"))
            )
            reactive_kvarh = round(reactive_kvar * interval_h, 4)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

            meter_rows.append({
                "consumer_id": profile.consumer_id,
                "timestamp": ts_str,
                "meter_interval": profile.meter_interval,
                "power_kw": round(power_kw, 3),
                "voltage": voltage,
                "current": current,
                "power_factor": agg_pf,
                "energy_kwh": round(power_kw * interval_h, 4),
                "reactive_power_kvar": reactive_kvar,
                "reactive_energy_kvarh": reactive_kvarh,
                "apparent_power_kva": apparent_kva,
                "temperature": round(temp_c, 1),
                "meter_event_flag": event_flag,
                "relay_status": relay,
                "tamper_flag": tamper,
            })
            appliance_rows.append({
                "consumer_id": profile.consumer_id,
                "timestamp": ts_str,
                **{key: round(apps[key], 4) for key in APPLIANCE_COLS},
            })

            if meta.get("is_anomaly"):
                anomaly_days[ts.strftime("%Y-%m-%d")] = meta

            ts += timedelta(minutes=profile.meter_interval)

    _scale_to_target(meter_rows, appliance_rows, profile.monthly_kwh_target)
    
    anomaly_gt = [
        {"consumer_id": profile.consumer_id, "date": date, "anomaly_type": meta["anomaly_type"],
         "severity": meta["severity"], "is_anomaly": 1, "description": f"{profile.scenario} anomaly"}
        for date, meta in anomaly_days.items()
    ]
    return meter_rows, appliance_rows, anomaly_gt

def categories_from_appliances(apps: Dict[str, float]) -> Dict[str, float]:
    total = sum(apps.values()) or 1e-6
    return {label: round(apps.get(col, 0) / total * 100, 1) for label, col in CONSUMER_FRIENDLY_APPLIANCES.items()}

def generate_full_simulation():
    all_meter, all_apps, all_anom = [], [], []
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS)
    for profile in CONSUMER_PROFILES:
        meter, apps, anomalies = generate_consumer_dataset(profile, start)
        all_meter.extend(meter)
        all_apps.extend(apps)
        all_anom.extend(anomalies)
    return all_meter, all_apps, all_anom
