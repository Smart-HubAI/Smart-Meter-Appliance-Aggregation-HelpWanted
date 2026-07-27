from ml.feature_engineering import build_training_frame_anomaly
import numpy as np

df = build_training_frame_anomaly()
print("Total records:", len(df))
if not df.empty:
    labels = df["label_anomaly"].values
    counts = np.unique(labels, return_counts=True)
    print("Label counts:", dict(zip(counts[0], counts[1])))
    
    from database.dal import query_df
    gt = query_df("SELECT * FROM anomaly_detection WHERE is_ground_truth = true")
    print("GT anomalies in DB:", len(gt))
    if len(gt) > 0:
        print("Sample GT dates:", gt["detected_at"].head().tolist())
        print("Sample feat dates:", df["date"].head().tolist())
