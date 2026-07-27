import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, ".")

from models.bill_predictor import compute_monthly_bill_projection
from utils.data_loader import get_readings_dataframe
from database.dal import get_all_consumers
from database.postgres_config import engine
from sqlalchemy import text

def generate_report():
    print("Starting billing forecast generation for all consumers...")
    
    consumers_list = get_all_consumers()
    consumer_dict = {c["consumer_id"]: c for c in consumers_list}
    
    results = []
    
    # Process CON001 to CON100
    for i in range(1, 101):
        consumer_id = f"CON{i:03d}"
        
        consumer_info = consumer_dict.get(consumer_id, {"consumer_type": "Residential"})
        consumer_type = consumer_info.get("consumer_type", "Residential")
        
        df = get_readings_dataframe(consumer_id)
        if df.empty:
            print(f"Skipping {consumer_id} - no data")
            continue
            
        bill_info = compute_monthly_bill_projection(df, consumer_type)
        
        # Calculate exactly as backend/frontend integration
        current_kwh = df[df["timestamp"] >= df["timestamp"].max().replace(day=1)]["energy_kwh"].sum()
        current_charges = bill_info.get("final_bill", 0)
        est_final = bill_info.get("projected_monthly_bill", 0)
        pred_remaining_kwh = bill_info.get("predicted_remaining_kwh", 0)
        pred_remaining_charges = bill_info.get("predicted_remaining_charges", 0)
        days_elapsed = bill_info.get("days_elapsed", 0)
        days_remaining = bill_info.get("days_remaining", 0)
        forecast_method = bill_info.get("forecast_method", "None")
        
        # Validation checks
        assert est_final >= current_charges, f"{consumer_id}: Final {est_final} < Current {current_charges}"
        assert abs((current_charges + pred_remaining_charges) - est_final) <= 1.0, f"{consumer_id}: Math mismatch: {current_charges} + {pred_remaining_charges} != {est_final}"
        
        increase_pct = (pred_remaining_charges / current_charges * 100) if current_charges > 0 else 0
        
        results.append({
            "Consumer ID": consumer_id,
            "Category": consumer_type,
            "Current Month kWh": round(current_kwh, 2),
            "Current Charges": current_charges,
            "Predicted Remaining kWh": pred_remaining_kwh,
            "Predicted Remaining Charges": pred_remaining_charges,
            "Estimated Final Bill": est_final,
            "Expected Increase Pct": round(increase_pct, 1),
            "Days Elapsed": days_elapsed,
            "Days Remaining": days_remaining,
            "Forecast Method": forecast_method
        })
        
    df_results = pd.DataFrame(results)
    
    os.makedirs("reports", exist_ok=True)
    
    # Save CSV
    csv_path = "reports/billing_forecast_validation.csv"
    df_results.to_csv(csv_path, index=False)
    print(f"Saved CSV to {csv_path}")
    
    # Insert to DB
    now = datetime.now()
    with engine.begin() as conn:
        for r in results:
            conn.execute(
                text("INSERT INTO billing_forecasts (consumer_id, forecast_generated_date, predicted_final_bill) VALUES (:cid, :dt, :pb)"),
                {"cid": r["Consumer ID"], "dt": now, "pb": r["Estimated Final Bill"]}
            )
    print("Saved forecasts to DB table `billing_forecasts`")
    
    # Generate MD Report
    md_path = "reports/billing_forecast_validation_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Billing Forecast Validation Report\n\n")
        
        f.write("## Overview\n")
        f.write(f"- Total Consumers Evaluated: {len(df_results)}\n")
        f.write(f"- Average Estimated Final Bill: ₹{df_results['Estimated Final Bill'].mean():.2f}\n")
        
        f.write("\\n## Averages by Consumer Category\\n")
        cat_avg = df_results.groupby('Category')[['Estimated Final Bill', 'Expected Increase Pct']].mean().reset_index()
        f.write(cat_avg.to_markdown(index=False))
        f.write("\\n\\n")
        
        f.write("## Top 10 Highest Estimated Final Bills\n")
        f.write(df_results.sort_values(by="Estimated Final Bill", ascending=False).head(10).drop(columns=['Category']).to_markdown(index=False))
        f.write("\n\n")
        
        f.write("## Top 10 Lowest Estimated Final Bills\n")
        f.write(df_results.sort_values(by="Estimated Final Bill", ascending=True).head(10).drop(columns=['Category']).to_markdown(index=False))
        f.write("\n\n")
        
        f.write("## Top 10 Highest Predicted Increases (%)\n")
        f.write(df_results.sort_values(by="Expected Increase Pct", ascending=False).head(10).drop(columns=['Category']).to_markdown(index=False))
        f.write("\n\n")
        
        f.write("## Top 10 Lowest Predicted Increases (%)\n")
        f.write(df_results.sort_values(by="Expected Increase Pct", ascending=True).head(10).drop(columns=['Category']).to_markdown(index=False))
        f.write("\n\n")

    print(f"Saved MD Report to {md_path}")
    print("Done!")

if __name__ == "__main__":
    generate_report()
