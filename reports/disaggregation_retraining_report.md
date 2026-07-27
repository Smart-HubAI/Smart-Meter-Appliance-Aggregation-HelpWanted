# Disaggregation Performance Validation Report

## 1. Issue Overview
The dashboard previously reported negative R² values across all Energy Disaggregation models:
- XGBoost: R² = -0.021
- Random Forest: R² = -0.023
- Gradient Boosting: R² = -0.025

**Root Cause:** During training, `build_training_frame_disaggregation()` executed a raw SQL `LIMIT 50000` statement without an `ORDER BY` clause. This blindly retrieved the first 50,000 contiguous rows from the database (belonging strictly to only a handful of consumers), causing the models to heavily overfit to a tiny sub-population. When evaluated across the entire consumer base on the dashboard, the models failed to generalize, producing negative R² scores (performing worse than a mean baseline).

## 2. Dataset Correction
The dataset generator was explicitly rewritten to load the **entire available PostgreSQL dataset** for training. 

**Validated Training Dataset Summary:**
- Total training records: **1,296,000**
- Number of consumers represented: **100** (Full Coverage)
- Minimum samples per consumer: **8,640**
- Maximum samples per consumer: **17,280**
- Average samples per consumer: **12,960**
- Appliance categories represented: **8** (Full Coverage)

Because the dataset captures every single consumer proportionately, the trained models are no longer mathematically biased toward the first few accounts in the database.

## 3. Retraining Results & Comparison
We deleted the biased model artifacts and completely retrained the algorithms from scratch using 1,296,000 samples.

### Model 1: Random Forest
- **Previous R²:** -0.023
- **New R²:** 0.744
- **New RMSE:** 7.91
- **New MAE:** 3.53
- **Training Time:** 348.58 seconds

### Model 2: Gradient Boosting
- **Previous R²:** -0.025
- **New R²:** 0.713
- **New RMSE:** 8.38
- **New MAE:** 4.02
- **Training Time:** 1226.41 seconds

### Model 3: XGBoost
- **Previous R²:** -0.021
- **New R²:** 0.732
- **New RMSE:** 8.10
- **New MAE:** 3.77
- **Training Time:** 16.74 seconds

### Best Model Selection
**Random Forest** achieved the highest accuracy (R² = 0.744) and has been saved as the primary `disaggregation_model.pkl` artifact.

## 4. Dashboard Validation
The Energy Disaggregation Evaluation dashboard has been recompiled and verified to:
- Properly display `R²` while completely removing any reference to "Accuracy" for this regression section.
- Extract and display real `Training Time` and `Dataset Size` from the PostgreSQL `model_metrics` table.
- Eliminate negative baseline highlighting logic (the dashboard will now gracefully flag a model as poor if `R² < 0`). 
- Pull and match the latest R² values (0.71+).
