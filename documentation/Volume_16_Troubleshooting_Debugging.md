# Volume 16: Troubleshooting & Debugging

## 1. Introduction
During the development and integration phases of the project, several critical issues were encountered across the Frontend, Backend, and Machine Learning layers. This volume documents the root cause analysis and resolution for major bugs, serving as a knowledge base for future maintenance.

---

## 2. Major Issues and Resolutions

### 2.1 React Build Changes Not Rendering
- **Problem**: Edits made to `Consumer.jsx` and `Admin.jsx` were not visible in the browser, even after hard-refreshing (`Ctrl+F5`).
- **Root Cause**: The Flask backend was configured to serve the statically compiled assets from `frontend/dist/`. Simply saving the React source code (`src/`) did not automatically recompile the bundle for Flask.
- **Resolution**: Diagnosed the routing flow (`app.py` serving `index.html`). Established a rule that developers must either run `npm run build` to update the Flask production view, or use the Vite dev server (`npm run dev` at `:5173`) for live Hot Module Replacement during active UI development.

### 2.2 Chatbot Backend Exception (`'str' object has no attribute 'get'`)
- **Problem**: Querying the AI Assistant to "Show critical consumers" resulted in a 500 Internal Server Error in the Flask logs.
- **Root Cause**: The Intent Engine (`services/ai_assistant.py`) queried the PostgreSQL `anomalies` table. It attempted to parse the returned row as a dictionary `row.get('severity')`, but due to how `pandas` serialized the SQL response natively, the row was returning a raw string representation of a tuple/dict.
- **Resolution**: Implemented strict type checking and cast the SQLAlchemy `Row` proxy to a native Python dictionary (`dict(row)`) before attempting to access its keys, ensuring the RAG context could be built without crashing.

### 2.3 UI Layout Collapse (Chart Overlap)
- **Problem**: The Pie and Line charts on the Admin and Consumer dashboards stretched infinitely or overlapped KPI cards when the browser was resized.
- **Root Cause**: `react-chartjs-2` canvas elements attempt to fill their parent container. If the parent container is a flexbox without explicit constraints, the canvas enters an infinite resize loop.
- **Resolution**: Wrapped all `<Pie>` and `<Line>` elements in a `div` with `position: relative` and `height: 300px`, and set `maintainAspectRatio={false}` on the Chart.js options object.

### 2.4 AI Confidence Score Unrealistic (Always 100%)
- **Problem**: The Consumer Dashboard consistently displayed "AI Confidence: 100%".
- **Root Cause**: The backend Random Forest prediction pipeline returned confidence scores as decimals (e.g., `0.95`). The frontend `fmtPct()` utility was indiscriminately multiplying by 100, and in some mock data cases, the raw data was `95.0`, resulting in `9500%` which hit a UI `Math.min(100)` cap.
- **Resolution**: Introduced a dedicated `fmtConfidence()` formatter in `utils/format.js` that checks if the value is $>1$. If it is (e.g. `95`), it uses it directly. If it is $<1$ (e.g., `0.95`), it multiplies by 100. Furthermore, added dynamic qualitative labels (`Very High Confidence`, `Moderate Confidence`) based on the normalized percentage.

### 2.5 Data Source Inconsistency (KPI vs Table)
- **Problem**: The Admin Dashboard "Critical Cases" KPI displayed `0`, but the Operational Alerts table clearly contained 3 consumers marked as "Critical".
- **Root Cause**: The KPI card was aggregating data based on `overall_risk_score > 90`, while the table classified consumers as Critical if their risk score was $> 85$ *or* they had a `has_tampering` flag.
- **Resolution**: Centralized the severity classification logic. The backend now calculates the `severity` string, and both the KPI card and the Table use this identical field to determine "Critical" status, ensuring absolute synchronization.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
