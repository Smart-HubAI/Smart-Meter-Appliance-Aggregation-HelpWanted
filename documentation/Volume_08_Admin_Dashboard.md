# Volume 08: Admin Dashboard

## 1. Introduction

While the Consumer Dashboard focuses on individual empowerment, the Admin Dashboard is designed for macro-level utility management. Utility operators monitor thousands of meters simultaneously, making manual anomaly detection impossible. 

The Admin Dashboard acts as an **Operational Triage Center**. It aggregates data from PostgreSQL, flags critical issues, and provides geographical (Zonal) and categorical insights.

---

## 2. Component Hierarchy and Data Flow

```mermaid
flowchart TD
    A[Flask Backend: /api/admin/dashboard] -->|JSON Payload| B[Admin.jsx]
    B --> C[Operational Alerts Queue / Data Table]
    B --> D[KPI Summary Cards]
    B --> E[Zone Analytics (Pie/Bar Charts)]
    B --> F[System Load Trends]
```

### 2.1 Backend API Payload
The `GET /api/admin/dashboard` endpoint returns a holistic JSON payload containing:
- `kpis`: High-level metrics (Total Consumers, Total Monthly Revenue, Critical Cases).
- `consumer_table`: The master array of all consumers and their associated `overall_risk_score`.
- `utility_investigation_queue`: A prioritized list of consumers exhibiting specific anomalies (Tampering, Peak Spikes, Voltage Drops).
- `charts`: Aggregated data grouped by zone and category for visualization.

---

## 3. Widget Documentation

### 3.1 Operational Alerts Queue (The Master Table)
- **Purpose**: The most critical widget on the dashboard. It ranks consumers based on their Machine Learning generated Risk Score.
- **Data Source**: Aggregated from `anomalies` and `smart_meter_data` in PostgreSQL.
- **Filtering Logic**: Implements client-side multi-factor filtering allowing admins to slice data by `Zone`, `Consumer Category`, `Severity`, and `Anomaly Type`.
- **Business Rules (Severity Calculation)**:
  - **Critical**: Risk Score $\ge$ 85 or `has_tampering == true`.
  - **High**: Risk Score between 70 and 84, or `has_spike == true`.
  - **Medium**: Risk Score between 50 and 69, or `has_voltage_issue == true`.
  - **Low**: Normal operation.

### 3.2 Recommended Actions Logic
The React frontend (`Admin.jsx`) dynamically assigns a recommended action based on the ML flags passed by the backend:
```javascript
let recAction = "No Immediate Action";
if (hasTampering) recAction = "Immediate Site Inspection";
else if (severity === "Critical" || severity === "High") recAction = "Remote Meter Verification";
else if (q.has_voltage_issue) recAction = "Schedule Technician Visit";
else if (q.has_spike) recAction = "Monitor for 24 Hours";
```

### 3.3 System-Wide KPI Cards
1. **Total Monitored Nodes**: Total count of active smart meters in the DB.
2. **Projected Monthly Revenue**: Sum of all ML Bill Predictions. Crucial for utility cash-flow planning.
3. **Critical Cases**: Count of consumers whose highest active severity is `Critical`. *Note: A bug where this did not match the table was resolved by aligning the frontend categorization logic with the backend DB aggregation.*

### 3.4 Zone Analytics (Pie / Bar Charts)
- **Purpose**: Identify geographic or categorical clusters of high energy usage or anomalies.
- **Database Source**: SQL `GROUP BY` aggregations on the `smart_meter_data` table combined with `consumers` demographics.
- **Example Use Case**: If the "Industrial Hub" zone shows an abnormal spike in voltage issues, the utility can proactively inspect the local substation rather than dispatching technicians to individual consumers.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
