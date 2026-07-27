# Volume 04: Energy Disaggregation (Random Forest)

## 1. Non-Intrusive Load Monitoring (NILM)

Energy Disaggregation (NILM) is the computational process of deducing the energy consumption of individual appliances from a single, aggregated smart meter reading.

**Goal**: Convert `Total kWh (15-min)` $\rightarrow$ `[AC_kWh, Refrigerator_kWh, TV_kWh, ...]`.

Because installing smart plugs on every appliance in a house is intrusive, expensive, and difficult to maintain, NILM relies exclusively on Machine Learning to detect the "signatures" of these appliances in the aggregate load.

---

## 2. Model Selection: Random Forest Regressor

### 2.1 Why Random Forest over Deep Learning or XGBoost?
- **Random Forest**: An ensemble of Decision Trees trained via Bagging (Bootstrap Aggregating). It is inherently robust against overfitting (a major issue with noisy smart meter data). It operates excellently without extensive hyperparameter tuning.
- **Deep Learning (LSTMs, CNNs)**: While sequence-to-sequence networks excel in academic NILM settings (like the UK-DALE dataset), they are computationally prohibitive for inferencing millions of rows daily on standard commodity hardware.
- **XGBoost**: Gradient Boosting builds trees sequentially to correct prior errors. While XGBoost is included in the codebase (`models/train_disaggregation_model.py`) and can yield slightly lower Mean Absolute Error (MAE), Random Forest trains significantly faster due to absolute parallelization (`n_jobs=-1`), making it the primary production model.

### 2.2 Mathematical Foundations of the Random Forest
Random Forest utilizes the concept of **Decision Trees**. At each node, the tree splits the data to minimize the variance (for regression) of the target variable.

**Variance Reduction (Splitting Criterion)**:
For a node $N$ and a split $S$ that creates subsets $N_1$ and $N_2$:
```math
\text{Gain} = \text{Var}(N) - \left( \frac{|N_1|}{|N|} \text{Var}(N_1) + \frac{|N_2|}{|N|} \text{Var}(N_2) \right)
```
Where $\text{Var}(N)$ is the Mean Squared Error (MSE) within the node.

### 2.3 Multi-Output Regression
Standard Random Forest predicts a single scalar value. Because NILM requires predicting 8 simultaneous appliance values, the model is wrapped in `sklearn.multioutput.MultiOutputRegressor`. This essentially trains 8 separate Random Forests (one for each appliance) behind a unified interface.

---

## 3. Implementation Details (`models/train_disaggregation_model.py`)

### 3.1 Feature Engineering (`ml/feature_engineering.py`)
The aggregate smart meter reading is passed through `build_training_frame_disaggregation()` to extract highly correlated features:
1. `hour_sin` and `hour_cos`: Captures the cyclical nature of human activity (e.g., TVs are primarily used at night).
2. `voltage` and `power_factor`: AC units depress the power factor significantly due to their inductive compressor motors.
3. `active_power_kw` and `reactive_power_kvar`: Allows the model to differentiate between resistive loads (Water Heater) and inductive loads (Fans, AC).

### 3.2 Training Pipeline Workflow

```mermaid
flowchart TD
    A[(PostgreSQL Database)] -->|Fetch smart_meter_data & appliance_ground_truth| B[Data Alignment (JOIN on timestamp)]
    B --> C[Feature Engineering (Cyclic Time, Rolling Means)]
    C --> D[Data Splitting 80/20]
    D --> E[MultiOutputRegressor(RandomForest)]
    E --> F[Hyperparameter Tuning (max_depth=12, n_estimators=80)]
    F --> G[Model Evaluation (MAE, RMSE)]
    G --> H[Serialization (.pkl via joblib)]
```

### 3.3 Evaluation Metrics
The system logs the following metrics to `database/dal.py` `save_model_metrics`:

- **MAE (Mean Absolute Error)**: Average absolute difference between predicted and actual appliance kWh. Highly resilient to outliers.
  ```math
  MAE = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|
  ```
- **RMSE (Root Mean Squared Error)**: Penalizes large errors heavily (e.g., misclassifying a sudden 3kW AC spike).
  ```math
  RMSE = \sqrt{ \frac{1}{n} \sum_{i=1}^{n} (y_i - \hat{y}_i)^2 }
  ```
- **R² Score**: The proportion of variance explained by the model. (e.g., an $R^2$ of 0.85 means the model explains 85% of appliance usage).

---

## 4. Confidence Score Calculation
Because NILM is a statistical guess, the model outputs a `confidence` metric alongside the predictions. 

**Logic in `app.py`**:
When aggregating appliance estimates to build the Consumer Dashboard:
```python
ai_confidence = float(app_df["confidence"].mean())
if ai_confidence < 0.7:
    ai_confidence = 0.85 + (ai_confidence * 0.1)
```
*Note: Due to high uncertainty in simulated low-tier loads, the backend heuristically boosts the mean confidence if it drops below 70%, preventing dashboard users from losing trust in the AI estimates during noisy periods.* 
The frontend normalizes any resulting unrealistic 100% scores down to realistic bands (`Very High Confidence`, `Moderate Confidence`).


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
