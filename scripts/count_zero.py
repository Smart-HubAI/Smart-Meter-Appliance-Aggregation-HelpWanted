import pandas as pd
from database.dal import query_df

sql = """
SELECT 
    SUM(CASE WHEN (
        COALESCE(ac.predicted_energy_kwh, 0) +
        COALESCE(ref.predicted_energy_kwh, 0) +
        COALESCE(lig.predicted_energy_kwh, 0) +
        COALESCE(tv.predicted_energy_kwh, 0) +
        COALESCE(wm.predicted_energy_kwh, 0) +
        COALESCE(wh.predicted_energy_kwh, 0) +
        COALESCE(fan.predicted_energy_kwh, 0) +
        COALESCE(misc.predicted_energy_kwh, 0)
    ) <= 0 THEN 1 ELSE 0 END) AS zero_rows,
    COUNT(*) AS total_rows
FROM smart_meter_readings s
LEFT JOIN appliance_predictions ac ON s.consumer_id = ac.consumer_id AND s.timestamp = ac.timestamp AND ac.appliance_name = 'Air Conditioner (AC)'
LEFT JOIN appliance_predictions ref ON s.consumer_id = ref.consumer_id AND s.timestamp = ref.timestamp AND ref.appliance_name = 'Refrigerator'
LEFT JOIN appliance_predictions lig ON s.consumer_id = lig.consumer_id AND s.timestamp = lig.timestamp AND lig.appliance_name = 'Lighting'
LEFT JOIN appliance_predictions tv ON s.consumer_id = tv.consumer_id AND s.timestamp = tv.timestamp AND tv.appliance_name = 'Television & Entertainment'
LEFT JOIN appliance_predictions wm ON s.consumer_id = wm.consumer_id AND s.timestamp = wm.timestamp AND wm.appliance_name = 'Washing Machine'
LEFT JOIN appliance_predictions wh ON s.consumer_id = wh.consumer_id AND s.timestamp = wh.timestamp AND wh.appliance_name = 'Water Heater / Geyser'
LEFT JOIN appliance_predictions fan ON s.consumer_id = fan.consumer_id AND s.timestamp = fan.timestamp AND fan.appliance_name = 'Fans'
LEFT JOIN appliance_predictions misc ON s.consumer_id = misc.consumer_id AND s.timestamp = misc.timestamp AND misc.appliance_name = 'Miscellaneous Appliances'
"""

df = query_df(sql)
print(df)
