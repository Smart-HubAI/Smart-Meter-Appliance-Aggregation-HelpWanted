import pandas as pd
from database.dal import query_df
from ml.feature_engineering import build_training_frame_disaggregation

print("Building dataframe...")
df = build_training_frame_disaggregation()
print(f"Total rows: {len(df)}")
