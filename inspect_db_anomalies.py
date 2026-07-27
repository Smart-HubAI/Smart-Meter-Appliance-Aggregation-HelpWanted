from database.dal import query_df

gt = query_df("SELECT * FROM anomaly_detection WHERE is_ground_truth = true LIMIT 5")
print("GT Data types:")
print(gt.dtypes)
print("GT rows:")
print(gt)

feat = query_df("SELECT * FROM feature_engineering LIMIT 5")
print("Feat Data types:")
print(feat.dtypes)
print("Feat rows:")
print(feat)
