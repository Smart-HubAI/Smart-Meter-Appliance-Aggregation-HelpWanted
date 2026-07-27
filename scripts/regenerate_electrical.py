#!/usr/bin/env python -u
"""
Regenerate synthetic dataset with full electrical parameters and validate.
Uses -u flag for unbuffered output.
"""
import sys, io, math, time
# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("=" * 60)
print("REGENERATING SYNTHETIC DATASET WITH ELECTRICAL PARAMETERS")
print("=" * 60)

# Step 1: Recreate schema
print("\n[1/6] Recreating schema with new columns...")
from database.postgres_config import engine, Base
from database.postgres_models import Smart_Meter_Readings
Smart_Meter_Readings.__table__.drop(bind=engine, checkfirst=True)
Base.metadata.create_all(bind=engine)
print("  OK - schema recreated")

# Step 2: Generate data
print("\n[2/6] Generating synthetic data...")
from simulation.appliance_engine import generate_full_simulation, CONSUMER_PROFILES, APPLIANCE_COLS
t0 = time.time()
meter, apps, anom = generate_full_simulation()
print(f"  Generated {len(meter)} meter rows in {time.time()-t0:.1f}s")

# Step 3: Validate electrical relationships
print("\n[3/6] Validating electrical relationships...")
import numpy as np
violations_s2 = 0
violations_pf = 0
pf_values, q_values, s_values, p_values = [], [], [], []
event_counts, relay_counts, tamper_counts = {}, {}, {}
sample_rows = []

for row in meter:
    p, q, s, pf = row["power_kw"], row["reactive_power_kvar"], row["apparent_power_kva"], row["power_factor"]
    p_values.append(p); q_values.append(q); s_values.append(s); pf_values.append(pf)
    # S^2 = P^2 + Q^2
    if s > 0.01 and abs(s*s - (p*p + q*q)) > 0.05 * max(1, p*p + q*q):
        violations_s2 += 1
    # PF = P/S
    if s > 0.01 and abs(pf - p/s) > 0.02:
        violations_pf += 1
    event_counts[row["meter_event_flag"]] = event_counts.get(row["meter_event_flag"], 0) + 1
    relay_counts[row["relay_status"]] = relay_counts.get(row["relay_status"], 0) + 1
    tamper_counts[row["tamper_flag"]] = tamper_counts.get(row["tamper_flag"], 0) + 1
    if len(sample_rows) < 5 and p > 0.5:
        sample_rows.append(row)

n = len(meter)
print(f"  S^2=P^2+Q^2 violations: {violations_s2}/{n} ({violations_s2/n*100:.2f}%)")
print(f"  PF=P/S violations: {violations_pf}/{n} ({violations_pf/n*100:.2f}%)")

# Step 4: Load into PostgreSQL
print("\n[4/6] Loading into PostgreSQL...")
from database.dal import (clear_simulation_data, insert_consumers, insert_meter_readings,
    insert_appliance_ground_truth, insert_ground_truth_anomalies, init_schema)

init_schema()
clear_simulation_data()
print("  Cleared old data")

consumers = [{"consumer_id": p.consumer_id, "name": p.name, "address": p.address,
    "scenario": p.scenario, "zone": p.zone, "consumer_type": p.consumer_type,
    "meter_interval": p.meter_interval, "outstanding_amount": p.outstanding_amount,
    "days_overdue": p.days_overdue, "payment_status": p.payment_status,
    "risk_category": p.risk_category, "segment": p.segment} for p in CONSUMER_PROFILES]
insert_consumers(consumers)
print(f"  Inserted {len(consumers)} consumers")

meter_tuples = [(r["consumer_id"], r["timestamp"], r["meter_interval"], r["power_kw"],
    r["voltage"], r["current"], r["power_factor"], r["energy_kwh"],
    r["reactive_power_kvar"], r["reactive_energy_kvarh"], r["apparent_power_kva"],
    r["temperature"], r["meter_event_flag"], r["relay_status"], r["tamper_flag"]) for r in meter]
chunk = 5000
for i in range(0, len(meter_tuples), chunk):
    insert_meter_readings(meter_tuples[i:i+chunk])
    if (i // chunk) % 30 == 0:
        print(f"    Meter: {i}/{len(meter_tuples)}")
print(f"  Inserted {len(meter_tuples)} meter readings")

app_tuples = [(r["consumer_id"], r["timestamp"], r["ac_kw"], r["refrigerator_kw"],
    r["lighting_kw"], r["television_kw"], r["washing_machine_kw"], r["water_heater_kw"],
    r["fan_kw"], r["miscellaneous_kw"], r["refrigerator_kw"], r["television_kw"],
    r["miscellaneous_kw"]) for r in apps]
for i in range(0, len(app_tuples), chunk):
    insert_appliance_ground_truth(app_tuples[i:i+chunk])
print(f"  Inserted appliance ground truth")

anom_tuples = [(r["consumer_id"], r["date"], r["anomaly_type"], r["severity"],
    r.get("is_anomaly", 1), r.get("description", "")) for r in anom]
if anom_tuples:
    insert_ground_truth_anomalies(anom_tuples)
print(f"  Inserted {len(anom_tuples)} anomalies")

print("  Building feature store...")
from ml.feature_engineering import build_feature_store
feat_count = build_feature_store()
print(f"  Built {feat_count} feature rows")

# Step 5: DB Validation
print("\n[5/6] Database validation...")
from database.dal import query_df
db_check = query_df("""
    SELECT COUNT(*) as total,
        SUM(CASE WHEN active_power_kw IS NULL THEN 1 ELSE 0 END) as null_p,
        SUM(CASE WHEN active_energy_kwh IS NULL THEN 1 ELSE 0 END) as null_e,
        SUM(CASE WHEN reactive_power_kvar IS NULL THEN 1 ELSE 0 END) as null_q,
        SUM(CASE WHEN reactive_energy_kvarh IS NULL THEN 1 ELSE 0 END) as null_qe,
        SUM(CASE WHEN apparent_power_kva IS NULL THEN 1 ELSE 0 END) as null_s,
        SUM(CASE WHEN power_factor IS NULL THEN 1 ELSE 0 END) as null_pf,
        SUM(CASE WHEN temperature IS NULL THEN 1 ELSE 0 END) as null_temp,
        SUM(CASE WHEN meter_event_flag IS NULL THEN 1 ELSE 0 END) as null_event,
        SUM(CASE WHEN relay_status IS NULL THEN 1 ELSE 0 END) as null_relay,
        SUM(CASE WHEN tamper_flag IS NULL THEN 1 ELSE 0 END) as null_tamper,
        AVG(active_power_kw) as avg_p,
        AVG(reactive_power_kvar) as avg_q,
        AVG(apparent_power_kva) as avg_s,
        AVG(power_factor) as avg_pf
    FROM smart_meter_readings
""").iloc[0]
print(f"  Total rows: {int(db_check['total'])}")
print(f"  NULLs: P={int(db_check['null_p'])}, E={int(db_check['null_e'])}, Q={int(db_check['null_q'])}, "
      f"QE={int(db_check['null_qe'])}, S={int(db_check['null_s'])}, PF={int(db_check['null_pf'])}, "
      f"Temp={int(db_check['null_temp'])}, Event={int(db_check['null_event'])}, "
      f"Relay={int(db_check['null_relay'])}, Tamper={int(db_check['null_tamper'])}")
print(f"  Averages: P={db_check['avg_p']:.4f} kW, Q={db_check['avg_q']:.4f} kvar, "
      f"S={db_check['avg_s']:.4f} kVA, PF={db_check['avg_pf']:.4f}")

# Step 6: Final report
print("\n" + "=" * 60)
print("VALIDATION REPORT")
print("=" * 60)
p_arr, q_arr, s_arr, pf_arr = np.array(p_values), np.array(q_values), np.array(s_values), np.array(pf_values)
print(f"\nTotal records: {n}")
print(f"\n--- Averages ---")
print(f"  Active Power (P):    {p_arr.mean():.4f} kW")
print(f"  Reactive Power (Q):  {q_arr.mean():.4f} kvar")
print(f"  Apparent Power (S):  {s_arr.mean():.4f} kVA")
print(f"  Power Factor (PF):   {pf_arr.mean():.4f}")
print(f"\n--- PF Distribution ---")
for pct in [5, 25, 50, 75, 95]:
    print(f"  P{pct}: {np.percentile(pf_arr, pct):.4f}")
print(f"  Min: {pf_arr.min():.4f}  Max: {pf_arr.max():.4f}")
print(f"\n--- Meter Events ---")
for ev, cnt in sorted(event_counts.items(), key=lambda x: -x[1]):
    print(f"  {ev}: {cnt} ({cnt/n*100:.1f}%)")
print(f"\n--- Relay Status ---")
for s, cnt in sorted(relay_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {cnt} ({cnt/n*100:.1f}%)")
print(f"\n--- Tamper Flags ---")
for f, cnt in sorted(tamper_counts.items(), key=lambda x: -x[1]):
    print(f"  {f}: {cnt} ({cnt/n*100:.1f}%)")
print(f"\n--- Sample Rows ---")
print(f"  {'P (kW)':>10} {'Q (kvar)':>10} {'S (kVA)':>10} {'PF':>8}")
for row in sample_rows:
    print(f"  {row['power_kw']:10.4f} {row['reactive_power_kvar']:10.4f} "
          f"{row['apparent_power_kva']:10.4f} {row['power_factor']:8.4f}")
print(f"\n{'='*60}")
print("REGENERATION COMPLETE")
print(f"{'='*60}")
