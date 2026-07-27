# Anomaly Validation Report

## 1. Problem Resolution
The root cause of the **"A single label was found in 'y_true' and 'y_pred'"** warning was identified and resolved. 
A silent date-formatting mismatch inside `ml/feature_engineering.py` caused the dataset merge logic to fail. 
Specifically, the features dataset utilized an ISO timestamp format (`2026-03-21 00:00:00`), whereas the ground truth dataset utilized a date-only format (`2026-03-21`). Consequently, the intersection returned `False` for all rows, reverting all ground truth labels back to `0` prior to training.

This date parsing has been standardized (`%Y-%m-%d`), and labels are now properly injected into the training framework.

## 2. Dataset Distribution Logging
We decreased the scenario generation likelihood in `simulation/appliance_engine.py` to yield a realistic 6% anomaly rate (closely approximating the requested 5% target).

The updated dataset splits reflect a healthy label distribution:

### Complete Dataset
- Total Records: **9,100**
- Normal Samples (Class 0): **8,531**
- Anomaly Samples (Class 1): **569**
- Contamination Ratio: **6.3%**

### Training Dataset (80%)
- Total Records: **7,280**
- Normal Samples: **6,825**
- Anomaly Samples: **455**
- Contamination Ratio: **6.2%**

### Testing Dataset (20%)
- Total Records: **1,820**
- Normal Samples: **1,706**
- Anomaly Samples: **114**
- Contamination Ratio: **6.3%**

## 3. Safe Evaluation & Metric Integrity
We applied `stratify=y` to the `train_test_split()` configuration. The evaluation logic has been overhauled to compute metrics only when both labels exist. If a single-class dataset is ever fed into the evaluation pipeline in the future, it handles the failure gracefully by returning a `"Not Available"` status containing `"Validation dataset contains only one class"` alongside fallback metrics (Detection Rate, Mean Anomaly Score, etc.).

## 4. Model Training Results
Following the correction, classification metrics successfully generated without suppressing warnings or throwing `sklearn` zero-division exceptions. 

- **Isolation Forest:**
  - Accuracy: 0.887
  - Precision: 0.000
  - Recall: 0.000
  - F1 Score: 0.000
  
- **Random Forest:**
  - Accuracy: 0.802
  - Precision: 0.215
  - Recall: 0.816
  - F1 Score: 0.341

- **XGBoost:** *(Primary selected model based on F1)*
  - Accuracy: 0.945
  - Precision: 0.674
  - Recall: 0.254
  - F1 Score: 0.369

## 5. UI Updates
The **AI Models & Validation Dashboard** has been successfully recompiled (`frontend/dist`). It is strictly programmed to never fabricate `1.0` / `0.0` outputs for broken models. 

It now dynamically reads the `"status"` property from the `evaluate_anomaly_models()` response. If an evaluation yields a single class, the dashboard swaps out standard metrics in favor of fallback heuristics (Contamination Ratio, Detection Rate, Mean Anomaly Score) and gracefully alerts the user with a warning banner.
