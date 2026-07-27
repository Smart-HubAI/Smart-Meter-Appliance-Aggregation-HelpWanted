import pandas as pd
from database.dal import query_df
pd.set_option('display.max_columns', None)
df = query_df("SELECT model_name, metric_name, metric_value, trained_at FROM model_validation WHERE task='disaggregation' ORDER BY trained_at DESC LIMIT 12")
print(df)
