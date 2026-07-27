# Volume 14: Testing & Validation

## 1. Introduction
To ensure the reliability of the Machine Learning models, database integrity, and UI accuracy, the platform incorporates a robust testing and validation strategy.

---

## 2. Machine Learning Model Validation

Unlike traditional software where `assert 2 + 2 == 4`, ML models are probabilistic. They are evaluated using statistical metrics.

### 2.1 Energy Disaggregation (Random Forest Regressor)
The `train_disaggregation_model.py` script automatically splits the simulated smart meter data into an 80% training set and a 20% validation set using `train_test_split(test_size=0.2)`.

**Metrics Evaluated:**
- **MAE (Mean Absolute Error)**: Validates the average error in kW for each appliance.
- **R² (R-Squared)**: Validates how well the Random Forest captures the variance in the data. An $R^2 > 0.85$ indicates highly successful disaggregation.
- **Cross-Validation**: Because the simulation engine generates deterministic scenarios, ensuring the model generalizes rather than memorizing the training data is crucial.

### 2.2 Anomaly Detection (Isolation Forest & RF Classifier)
The anomaly models are validated against the `ground_truth_anomalies` table.
- **Precision**: Validates that when the model flags a "Critical Anomaly", it is actually an anomaly (minimizing False Positives so admins don't waste time).
- **Recall**: Validates that the model successfully catches all injected anomalies (minimizing False Negatives).

---

## 3. API & Backend Testing

The Flask REST APIs are validated via manual and automated endpoint testing.
- **JSON Serialization Tests**: Because Pandas DataFrames often contain `NaN` values, validation ensures that `replace_nan_with_none()` successfully executes before Flask crashes with a JSON encoding error.
- **Database Consistency**: Validates that the API correctly joins `smart_meter_data` with `consumers` to build the required payloads.

---

## 4. Frontend & UI Validation

- **Component Rendering**: Ensuring `Chart.js` components properly unmount and remount when the `consumerId` changes, preventing memory leaks or "ghost" data overlapping.
- **Responsive Design**: Testing the Bootstrap grid layout on simulated mobile devices to ensure the UI remains usable when utility administrators access it via tablets in the field.
- **State Integrity**: Verifying that filtering the Operational Alerts table by "Critical" severity successfully removes all Low/Medium alerts without modifying the underlying cached array.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
