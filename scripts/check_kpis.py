import json
import os
import sys

# Ensure project root is on sys.path when run from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.aggregations import fleet_kpis, zone_analytics

print('FLEET_KPIS:')
print(json.dumps(fleet_kpis(), indent=2))
print('\nZONE_ANALYTICS:')
print(json.dumps(zone_analytics(), indent=2))

# Additional DB sanity checks
from database.dal import query_df
print('\nRAW_SUMS:')
print(query_df("SELECT SUM(active_energy_kwh) AS total FROM smart_meter_readings").to_dict('records'))
print(query_df("SELECT consumer_id, SUM(active_energy_kwh) AS total_kwh FROM smart_meter_readings GROUP BY consumer_id ORDER BY consumer_id").head(6).to_dict('records'))
