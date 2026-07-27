# Disaggregation Model Audit Report

## Part 1 – Dataset Audit

**Total dataset source:** 
PostgreSQL tables `smart_meter_readings` and `consumer_master`, joined with `appliance_predictions`.

**Function used to load data:**
- In `train_disaggregation_model.py`: `build_training_frame_disaggregation()` and `build_training_frame_temporal(sample_n=20000)`
- In `test_disagg_r2.py`: `build_training_frame_disaggregation(sample_n=50000)`

**Exact call signature:**
```python
def build_training_frame_disaggregation() -> pd.DataFrame:
```

**Determinations:**
- **Is the dataset limited?** No, the SQL query in `build_training_frame_disaggregation` has no `LIMIT` clause. However, `build_training_frame_temporal` does use a `LIMIT` clause.
- **Is sample_n being used?** It is passed in `test_disagg_r2.py` as `sample_n=50000`, but since the function `build_training_frame_disaggregation` takes no arguments, this will result in a `TypeError` and crash the test script.
- **Is LIMIT being applied indirectly?** No, except for the temporal ensemble training.
- **Is the full PostgreSQL dataset used?** Yes, for the classic models (Random Forest, Gradient Boosting, XGBoost).
- **Number of rows actually reaching model training:** 80% of the total fetched dataset (`test_size=0.2`).
- **Number of rows actually reaching evaluation:** 20% of the total fetched dataset.

---

## Part 2 – Train/Test Split Audit

**Train/Test Split Implementation:**
```python
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
```

**Report:**
- **test_size:** `0.2` (20%)
- **random_state:** `42`
- **stratify usage:** Not used (`None`).
- **training sample count:** `len(df) * 0.8` (80% of the data)
- **testing sample count:** `len(df) * 0.2` (20% of the data)

**Determinations:**
- **Actual training rows:** ~80% of the query results.
- **Actual testing rows:** ~20% of the query results.

---

## Part 3 – Feature Audit

**Report on `FEATURE_COLS_DISAGG`:**
Total **15** features used:
1. `active_power_kw`
2. `reactive_power_kvar`
3. `apparent_power_kva`
4. `power_factor`
5. `temperature`
6. `hour`
7. `day_of_week`
8. `weekend_flag`
9. `zone_Metro Zone`
10. `zone_Industrial Hub`
11. `zone_Suburban`
12. `zone_Commercial District`
13. `consumer_type_Residential`
14. `consumer_type_Commercial`
15. `consumer_type_Industrial`

**Check for:**
- **Missing columns:** Handled gracefully via `df[FEATURE_COLS_DISAGG].fillna(0).values`.
- **Duplicated columns:** None found.
- **Leakage risk:** Low. The features strictly contain meter readings and categorical data (zones, consumer types, time info), while targets are generated from appliance predictions. 

---

## Part 4 – Target Audit

**Report on `TARGET_COLS_DISAGG`:**
Total **8** targets used:
1. `target_Air Conditioner (AC)`
2. `target_Refrigerator`
3. `target_Lighting`
4. `target_Television & Entertainment`
5. `target_Washing Machine`
6. `target_Water Heater / Geyser`
7. `target_Fans`
8. `target_Miscellaneous Appliances`

**Determinations:**
- **Are targets percentages?** Yes.
- **Are targets kWh values?** No, they are derived as percentage distributions of total predicted kWh.
- **Are targets normalized?** Yes.
- **Do target rows sum to 100?** Yes, unless `app_sum` is zero, in which case the rows are filled with zeros and sum to 0.

**Code evidence:**
```python
app_sum = (df["ac_kw"] + ... + df["miscellaneous_kw"]).replace(0, np.nan)
df["target_Air Conditioner (AC)"] = (df["ac_kw"] / app_sum * 100).fillna(0)
# Repeated for all appliances
```

---

## Part 5 – Prediction Pipeline Audit

**Exact sequence post-prediction:**
```python
pred = model.predict(X_test)
pred = np.clip(pred, 0, None)
row_sum = pred.sum(axis=1, keepdims=True)
row_sum[row_sum == 0] = 1
pred = pred / row_sum * 100
```

**Determinations:**
- **Is prediction normalization occurring?** Yes (`pred / row_sum * 100`).
- **Is clipping occurring?** Yes (`np.clip(pred, 0, None)`).
- **Is scaling occurring?** No (except for normalization).

**Explain why:** 
Because the targets represent a percentage distribution that sums to exactly 100%, the model's raw multi-output regression predictions might include negative values and will naturally not sum to exactly 100. The script clips negatives to 0 and normalizes the outputs so the predicted distribution strictly sums to 100 across all 8 appliance categories.

---

## Part 6 – Metric Audit

**Report on Metric Calculations:**
- **Raw metric calculation:** Exists only in `test_disagg_r2.py`: `r2_score(y_test, raw_pred)`.
- **Normalized metric calculation:** Calculated in both `evaluate_model` (`train_disaggregation_model.py`) and `test_disagg_r2.py` as `r2_score(y_test, pred)`.
- **Database metric calculation:** Passed directly from the normalized predictions to `save_model_metrics()`.

**Determinations:**
- **Which metric is shown in dashboard:** The **Normalized metric** (as fetched from the `model_metrics` PostgreSQL table).
- **Which metric is saved to PostgreSQL:** The **Normalized metric**.

---

## Part 7 – R² Investigation

**Why negative R² values occur:**
**Primary Cause: Prediction Normalization on zero-target rows.** 
If `app_sum` is zero for a given interval, all 8 targets are set to exactly 0 (row sum = 0). When the model outputs small, non-zero raw predictions for these rows, the normalization pipeline artificially scales these predictions to sum to 100. Evaluating a prediction vector that sums to 100 against a true label vector that sums to 0 creates an astronomically high Mean Squared Error relative to the dataset variance, resulting in highly negative R² values.

**Probability Ranking:**
1. **Prediction normalization** (Forcing small errors on 0-sum rows to scale to 100) - *Highest Probability*
2. **Target issue** (Many rows have `app_sum = 0`, resulting in entirely 0 labels) - *High Probability*
3. **Dataset sampling bias** (Failing `sample_n` argument limits dataset flexibility for testing) - *Moderate Probability*
4. **Feature issue** - *Low Probability*

---

## Part 8 – Training Artifact Audit

**Files generated:**
- `disaggregation_random_forest.pkl`
- `disaggregation_gradient_boosting.pkl`
- `disaggregation_xgboost.pkl` (Conditional on library availability)
- `disaggregation_model.pkl`

**Determinations:**
- **Which model becomes `disaggregation_model.pkl`:** The model that achieves the highest R² score during the loop.
- **Selection criteria:** `metrics["r2"] > best_r2`
- **Best-model logic:** The script evaluates all initialized classic models based on their normalized R² score. The top-performing algorithm's weights are saved a second time under the generic `disaggregation_model.pkl` name.

---

## Part 9 – Dashboard Consistency Audit

**Dashboard Mapping Source:**
Values are NOT freshly inferred dynamically. They are fetched from cached records in the PostgreSQL `appliance_predictions` table.

**Exact code path in `app.py`:**
```python
# Read appliance predictions from DB instead of dynamic ML inference
app_df = query_df("SELECT appliance_name, predicted_energy_kwh, confidence, model_used, reasoning_summary, important_features, estimated_monthly_cost FROM appliance_predictions WHERE consumer_id = :cid", params={"cid": consumer_id})
```

---

## Part 10 – Final Conclusion

### Current Training Dataset
**Rows:** Full PostgreSQL extraction (No LIMIT for classic models).
**Consumers:** All available via `consumer_master`.
**Features:** 15.
**Targets:** 8 (Percentage distribution).

### Current Evaluation Dataset
**Rows:** 20% of query frame.
**Train:** 80%.
**Test:** 20%.

### Root Cause of Negative R²
**Primary Cause:** Aggressive prediction normalization. A raw prediction of `0.01` when the true labels are all `0.0` is normalized to `100.0`. This generates exponential error distortion specifically for periods where the target appliance sum is 0.
**Secondary Cause:** Many target intervals have `app_sum = 0` (due to missing predictions or no activity), which inherently conflicts with a pipeline that expects percentage distributions to sum to 100. Furthermore, `test_disagg_r2.py` crashes due to a buggy `sample_n` argument being passed to `build_training_frame_disaggregation()`.

### Recommended Fixes
**Fix #1:** Implement row-sum thresholds. Skip normalization if the raw prediction sum is extremely small, or if the true label row sum is exactly 0.
**Fix #2:** Filter out periods where `app_sum == 0` from the training frame to ensure the model only trains on valid percentage distributions.
**Fix #3:** Update `test_disagg_r2.py` to remove `sample_n=50000` from `build_training_frame_disaggregation()`, or modify the underlying function in `feature_engineering.py` to accept and execute SQL `LIMIT` parameters.
