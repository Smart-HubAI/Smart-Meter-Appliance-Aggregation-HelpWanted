import sys
import os

# Add directory to python path
sys.path.insert(0, os.path.abspath('.'))

from app import build_consumer_home, build_consumer_dashboard
import pandas as pd

consumers_to_test = ["CON001", "CON050", "CON093", "CON100"]

print("Consumer ID | Home Page Bill | Dashboard Bill | Final Bill")
print("-" * 65)

for cid in consumers_to_test:
    home_data = build_consumer_home(cid)
    dashboard_data = build_consumer_dashboard(cid)
    
    home_bill = home_data.get("overview", {}).get("estimated_monthly_bill", 0)
    dash_bill = dashboard_data.get("overview", {}).get("estimated_monthly_bill", 0)
    final_bill = dashboard_data.get("bill_breakdown", {}).get("estimated_bill", 0)
    if final_bill == 0:
        final_bill = dashboard_data.get("bill_breakdown", {}).get("final_bill", 0)
        
    projected = dashboard_data.get("bill_breakdown", {}).get("projected_monthly_bill", 0)

    print(f"{cid:<11} | {home_bill:<14} | {dash_bill:<14} | {projected:<10}")

