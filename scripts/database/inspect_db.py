import json
from database.postgres_config import SessionLocal, engine
from database.postgres_models import *
import pandas as pd
from sqlalchemy import text

tables = [
    "consumer_master", "smart_meter_readings", "feature_engineering",
    "appliance_predictions", "anomaly_detection", "billing", "tariff",
    "carbon_emission", "model_validation", "users", "audit_logs", "analytics"
]

print("--- DATABASE INSPECTION ---")
with engine.connect() as conn:
    for t in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM {t}", conn)
            print(f"\nTable: {t}")
            print(f"Total Rows: {len(df)}")
            if len(df) > 0:
                nulls = df.isnull().sum()
                nulls = nulls[nulls > 0]
                if len(nulls) > 0:
                    print("NULL values:")
                    for col, count in nulls.items():
                        print(f"  - {col}: {count} NULLs")
                else:
                    print("NULL values: None")
            else:
                print("Status: EMPTY")
        except Exception as e:
            print(f"Error reading {t}: {e}")
