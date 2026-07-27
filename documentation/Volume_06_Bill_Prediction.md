# Volume 06: Bill Prediction

## 1. Introduction

One of the primary causes of consumer dissatisfaction (and delayed utility payments) is "bill shock"—receiving an unexpectedly high electricity bill at the end of the billing cycle.

The platform solves this by continuously projecting the consumer's monthly energy bill. Because actual billing involves complex, non-linear pricing logic (slabs, time-of-day multipliers, fixed charges), a simple `Total kWh * Rate` calculation is entirely insufficient.

This module combines **Machine Learning Time-Series Forecasting** (to predict future consumption) with **Deterministic Tariff Logic** (to calculate the exact cost of that consumption).

---

## 2. Tariff Configuration (`tariff_config.py`)

All billing logic is centralized in `tariff_config.py`. This acts as the single source of truth for the platform, ensuring that tariff revisions only require updating a single file.

### 2.1 Progressive Slab Billing (Residential)
Residential consumers (LT-I / LT-II) are billed progressively.
For example, if a consumer uses 450 kWh:
- The first 100 kWh are billed at Slab 1 (₹3.50/kWh).
- The next 200 kWh (101 to 300) are billed at Slab 2 (₹7.00/kWh).
- The remaining 150 kWh (301 to 450) are billed at Slab 3 (₹9.00/kWh).

```python
RESIDENTIAL_SLABS = [
    (0,    100,  3.50),
    (100,  300,  7.00),
    (300,  500,  9.00),
    (500,  999999.0, 11.00),
]
```

### 2.2 Time-of-Day (ToD) Multipliers
Because smart meters transmit data at 15-minute intervals, the platform applies ToD rebates and surcharges dynamically:
- **Night (00:00 - 06:00)**: 15% Rebate (Multiplier: 0.85)
- **Morning (06:00 - 09:00)**: Normal Tariff (Multiplier: 1.00)
- **Solar (09:00 - 17:00)**: Variable Rebate based on season.
- **Peak (17:00 - 24:00)**: 20% Surcharge (Multiplier: 1.20)

### 2.3 Other Consumer Categories
- **Commercial (LT-III)**: Flat rate of ₹12.50/kWh + ₹350 Fixed Charge.
- **Industrial (LT-IV)**: Flat rate of ₹10.00/kWh + ₹180/kVA Demand Charge.
- **EV Charging (LT-VII)**: Subsidized flat rate of ₹7.50/kWh.

---

## 3. Machine Learning Forecasting (`models/train_bill_model.py`)

To predict the end-of-month bill midway through the month, the platform must first forecast what the total consumption will be on day 30.

### 3.1 Training the Regressor
The module extracts the daily aggregated kWh from the `smart_meter_data` PostgreSQL table and builds a feature set (similar to the anomaly detection framework, utilizing rolling means and date features).

Three models are trained and evaluated:
1. `LinearRegression()`
2. `RandomForestRegressor()`
3. `XGBRegressor()` (If XGBoost is installed)

The `RandomForestRegressor(n_estimators=80, random_state=42)` is serialized as the primary model.

### 3.2 Evaluation Metrics
The model logs standard regression metrics:
- **MAE** (Mean Absolute Error)
- **RMSE** (Root Mean Squared Error)
- **R²** (Coefficient of Determination)

---

## 4. Prediction Workflow (`app.py` & Database Layer)

When the Consumer Dashboard requests the billing data (`GET /api/consumer/<id>`), the following sequence occurs:

1. **Calculate Actual Consumed (To Date)**:
   The backend queries the exact kWh consumed from Day 1 to the current day of the billing cycle from the PostgreSQL database.
   
2. **Forecast Remaining Days**:
   The `RandomForestRegressor` takes the consumer's rolling 7-day average and predicts the daily consumption for the remaining days in the month.

3. **Apply Deterministic Slab Logic**:
   The predicted Total kWh (Actual + Forecasted) is passed through the progressive slab calculator in `tariff_config.py`.

4. **Add Fixed Charges & Taxes**:
   Based on the `consumer_category` (e.g., Residential), the specific fixed charge is added.

### 4.1 Example Mathematical Calculation
If a Residential consumer is projected to use **350 kWh** by month-end:
```math
\text{Cost}_{Slab1} = 100 \times 3.50 = \text{,1350}
```
```math
\text{Cost}_{Slab2} = 200 \times 7.00 = \text{,11400}
```
```math
\text{Cost}_{Slab3} = 50 \times 9.00 = \text{,1450}
```
```math
\text{Total Energy Charge} = 350 + 1400 + 450 = \text{,12200}
```
```math
\text{Final Predicted Bill} = \text{Energy Charge} + \text{Fixed Charge (125)} = \text{,12325}
```

This resulting figure (₹2325) is injected directly into the `Predicted Bill` widget on the Consumer React frontend, preventing bill shock and encouraging the consumer to reduce usage if the prediction exceeds their budget.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
