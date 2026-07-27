import os
import sys

from utils.data_loader import initialize_data
from database.dal import query_df

if __name__ == "__main__":
    print("Verifying 15-minute consumer (CON001)...")
    df = query_df("SELECT timestamp FROM smart_meter_readings WHERE consumer_id='CON001' ORDER BY timestamp")
    print(f"First timestamp: {df['timestamp'].iloc[0]}")
    print(f"Last timestamp: {df['timestamp'].iloc[-1]}")
    print(f"Total readings: {len(df)}")
    print(f"Readings per day: {len(df) / 90}")
    
    print("Verifying 30-minute consumer (CON060)...")
    df2 = query_df("SELECT timestamp FROM smart_meter_readings WHERE consumer_id='CON060' ORDER BY timestamp")
    print(f"First timestamp: {df2['timestamp'].iloc[0]}")
    print(f"Last timestamp: {df2['timestamp'].iloc[-1]}")
    print(f"Total readings: {len(df2)}")
    print(f"Readings per day: {len(df2) / 90}")
