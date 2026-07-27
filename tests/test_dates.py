from database.dal import query_df

feat = query_df("SELECT * FROM feature_engineering LIMIT 1")
gt = query_df("SELECT consumer_id, CAST(detected_at AS DATE) AS date, true AS is_anomaly FROM anomaly_detection WHERE is_ground_truth = true LIMIT 1")

print("Feat date str:", str(feat["date"].iloc[0]))
print("GT date str:", str(gt["date"].iloc[0]))
