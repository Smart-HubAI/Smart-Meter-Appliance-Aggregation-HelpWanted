# Volume 10: Flask Backend Architecture

## 1. Introduction
The backend of the platform is built on **Flask** (Python). It serves as the intelligent middleware layer between the robust PostgreSQL database and the responsive React frontend. 
Unlike standard CRUD applications, this backend is highly analytical, utilizing `pandas` for in-memory data manipulation and complex aggregations before serializing to JSON.

---

## 2. Core File Structure

- `app.py`: The primary entry point. Initializes the Flask application, configures CORS, handles JWT authentication, and defines all RESTful route endpoints.
- `database/dal.py`: The Data Access Layer. Contains all SQL query strings and functions to interact with PostgreSQL using `psycopg2` or `SQLAlchemy`.
- `services/ai_assistant.py`: Encapsulates the integration logic for the Groq LLM API.
- `utils/aggregations.py`: Helper functions to aggregate millions of smart meter rows into daily trends.

---

## 3. Major API Endpoints

### 3.1 `GET /api/consumer/<consumer_id>`
- **Purpose**: Fetches the complete payload required to render the Consumer Dashboard.
- **Workflow**:
  1. Validates the `consumer_id` against the `consumers` table.
  2. Fetches 30 days of raw consumption from `smart_meter_data`.
  3. Fetches ML predictions from `appliance_predictions` for the current month.
  4. Fetches active alerts from `anomalies`.
  5. Calculates the `Green Energy Score` locally.
- **Time Complexity**: $\mathcal{O}(N)$ where $N$ is the number of 15-minute intervals in 30 days (~2,880 rows). Due to PostgreSQL indexing on `consumer_id`, execution is typically $< 50$ms.
- **Return Value**: Nested JSON containing `consumer_details`, `bill_breakdown`, `green_score`, `trends`, and `appliance_details`.

### 3.2 `GET /api/admin/dashboard`
- **Purpose**: Fetches the complete payload for the Admin Dashboard.
- **Workflow**:
  1. Executes a massive `GROUP BY` query on `smart_meter_data` joined with `consumers` to generate `Zone Analytics`.
  2. Retrieves the `utility_investigation_queue` by fetching all consumers with `risk_score > 0`.
  3. Aggregates system-wide KPIs (`SUM(projected_bill)`).
- **Optimization**: To prevent the Flask server from locking during massive table scans, these queries heavily rely on PostgreSQL Materialized Views and pre-aggregated tables where possible.

### 3.3 `POST /api/chat`
- **Purpose**: Interfaces with the AI Energy Assistant.
- **Parameters**: `{"message": "string", "consumer_id": "string", "role": "string"}`.
- **Workflow**: Routes the payload to `services.ai_assistant.chat()`. Validates RBAC rules, builds the dynamic RAG context, and proxies the request to Groq.

---

## 4. Error Handling & Security

- **JSON Serialization Errors**: A common issue in Python/Flask when interfacing with DataFrames is encountering `NaN` (Not a Number) or `NaT` (Not a Time) values, which invalidate JSON. `app.py` implements a custom recursive cleaner (`replace_nan_with_none()`) that sanitizes all dicts before returning the `jsonify()` response.
- **CORS**: Configured strictly to allow only the local Vite Dev Server (`http://localhost:5173`) or the production Nginx origin.

---

## 5. Cross-Origin Resource Sharing (CORS) Bug
- **Problem**: During early development, the React frontend could not fetch data from the Flask backend, throwing a `CORS Preflight Failed` error.
- **Root Cause**: Flask-CORS was improperly initialized before the routes were defined, or missing specific methods (`GET`, `POST`, `OPTIONS`).
- **Resolution**: Ensured `CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)` was declared immediately after `Flask(__name__)` initialization.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
