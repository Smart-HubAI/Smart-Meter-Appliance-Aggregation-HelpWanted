# Volume 03: Dataset & Feature Engineering

## 1. Introduction
Because high-resolution, labeled smart meter data is highly restricted by utility companies due to privacy concerns, this platform relies on a sophisticated simulation engine (`simulation/appliance_engine.py`) to generate highly realistic, physics-based load profiles.

This volume explains exactly how data is generated, structured, and engineered into features suitable for the Machine Learning models.

---

## 2. Smart Meter Data Simulation

### 2.1 The Need for Simulation
Public datasets like REDD or UK-DALE contain granular appliance data, but only for a handful of houses. Our platform requires hundreds of consumers across different tariff zones, exhibiting complex behavior (like power theft and sudden grid drops) to train the Anomaly Detection and Billing models accurately. 

### 2.2 Time Resolution (15-min and 30-min intervals)
The `ConsumerSimProfile` class configures the `meter_interval`. We mix 15-minute and 30-minute intervals because different Advanced Metering Infrastructure (AMI) vendors output data at different frequencies. The models must be robust enough to handle mixed granularities.
- 96 readings per day for 15-minute intervals.
- 48 readings per day for 30-minute intervals.

### 2.3 Generation Logic (`simulation/appliance_engine.py`)

1. **Base Load**: Every house is assigned a constant baseload (e.g., phantom loads from plugged-in devices).
2. **Appliance Profiles**: 
   - **Refrigerators**: Cyclical, on/off every few hours.
   - **Air Conditioners (AC)**: Highly dependent on simulated temperature and time of day (afternoon peaks).
   - **Lighting**: Peaks strictly between 18:00 and 23:00.
   - **Washing Machines**: Spiky, short-duration high-wattage loads occurring randomly on weekends.
3. **Power Factor Simulation**: 
   Different appliances have different inherent power factors (inductive vs. resistive loads):
   - `water_heater_kw`: 0.98 - 1.0 (Purely resistive)
   - `ac_kw`: 0.80 - 0.90 (Highly inductive, motor-based)
   - `fan_kw`: 0.70 - 0.85
4. **Reactive & Apparent Power Calculation**:
   Using the formula:
   ```math
   Apparent Power (kVA) = \frac{Active Power (kW)}{Power Factor}
   ```
   ```math
   Reactive Power (kVAR) = \sqrt{kVA^2 - kW^2}
   ```
   These are explicitly calculated in the simulator to generate true three-dimensional power matrices.

---

## 3. Behavioral Scenarios

The simulator injects specific scenarios across the 90-day period. These scenarios are mapped in `SCENARIO_EVENT_MAP` to specific meter event flags.

| Scenario | Behavior | Associated Flag |
| :--- | :--- | :--- |
| `normal` | Standard cyclical usage | `Normal` |
| `peak_hour_overconsumption` | Triples expected load during 18:00-22:00 | `Current Overload` |
| `poor_power_factor` | Drastically reduces total PF below 0.7 | `Power Failure` |
| `meter_tampering` | Introduces sudden drops in recorded kWh without appliance changes | `Tamper Detected` |
| `phantom_load` | High constant base load throughout the night | `Reverse Current` |

---

## 4. Feature Engineering

Raw data (`timestamp`, `energy_kwh`) is completely insufficient for Machine Learning. A model cannot understand that "02:00 AM" is close to "23:00 PM" if passed as a raw string or integer.

### 4.1 Temporal Encoding (Cyclic Features)
To help the Random Forest understand the cyclical nature of time, `train_disaggregation_model.py` extracts the hour and maps it onto a circle using sine and cosine transformations:
```python
df["hour"] = df["timestamp"].dt.hour
df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
```
*Why?* The Euclidean distance between 23:00 and 01:00 is technically 22 hours if treated linearly. On a unit circle, they are correctly mapped as being 2 hours apart.

### 4.2 Aggregated Windows
The Anomaly model (`train_anomaly_model.py`) calculates rolling features to detect sudden shifts rather than absolute values:
- `rolling_24h_mean`: The average kWh over the last 24 hours.
- `rolling_24h_std`: The standard deviation, providing a measure of volatility.
- `pf_drop_flag`: Boolean value indicating if the rolling Power Factor suddenly shifted below 0.8.

### 4.3 Data Cleaning & Normalization
- **Missing Values**: Simulates transmission drops. Filled using `ffill()` (forward fill) or `interpolate(method='linear')`.
- **Scaling**: While Random Forests do not strictly require feature scaling, scaling is performed via `StandardScaler()` for the Anomaly Detection pipeline to ensure features with large variances (like Voltage) do not overshadow small variance features (like Power Factor).

---

## 5. Storage and Export
The engineered and simulated data is stored in the PostgreSQL database in two primary tables:
1. `smart_meter_data` (The raw telemetry sent from the meter)
2. `appliance_ground_truth` (The absolute truth of what was actually running, used ONLY for training, never for inference).


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
