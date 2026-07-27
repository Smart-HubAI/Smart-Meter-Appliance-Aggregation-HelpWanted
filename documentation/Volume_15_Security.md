# Volume 15: Security Architecture

## 1. Introduction
Because smart meter data contains highly sensitive personal information (which can reveal when a house is empty, consumer sleeping habits, and specific appliance usage), security is a paramount concern at the Database, API, and Frontend levels.

---

## 2. API & Network Security

### 2.1 Cross-Origin Resource Sharing (CORS)
The Flask backend strictly limits which domains can access the API endpoints. By explicitly defining allowed origins (e.g., `http://localhost:5173` or a production domain), the system prevents malicious websites from executing cross-site requests to steal consumer data.

### 2.2 JWT Authentication & Authorization (Role-Based Access Control)
The platform uses JSON Web Tokens (JWT) via `contexts/AuthContext.jsx` and backend validation.
- **Consumers** (`role: "consumer"`) are strictly locked to querying their own `consumer_id`. If `CON001` attempts to fetch data for `CON002`, the Flask API intercepts the request and returns a `403 Forbidden`.
- **Administrators** (`role: "admin"`) are granted global read access to view aggregated Zone Analytics and the Operational Alerts queue.

---

## 3. Database Security (PostgreSQL)

### 3.1 SQL Injection Prevention
Directly concatenating strings to form SQL queries is the most common vulnerability in database-driven applications.
**Vulnerable Example:**
```python
query = f"SELECT * FROM smart_meter_data WHERE consumer_id = '{user_input}'"
```
**Secure Implementation (`dal.py`)**:
The application exclusively uses parameterized queries provided by `psycopg2` / `SQLAlchemy`:
```python
query = "SELECT * FROM smart_meter_data WHERE consumer_id = %s"
cursor.execute(query, (user_input,))
```
This ensures that even if a malicious user inputs `' OR '1'='1`, the database engine treats it strictly as a literal string parameter, neutralizing the injection attack.

### 3.2 Least Privilege Execution
The Flask backend connects to PostgreSQL using a dedicated application database user. This user has `SELECT`, `INSERT`, and `UPDATE` privileges but lacks `DROP`, `GRANT`, or schema modification privileges.

---

## 4. Large Language Model (LLM) Security

Integrating generative AI introduces the risk of "Prompt Injection" (where a user tries to trick the AI into ignoring its instructions and executing malicious commands).

### 4.1 Strict System Prompts
The `SYSTEM_PROMPT_TEMPLATE` in `ai_assistant.py` is hardcoded on the backend. The user cannot override the system instructions.
```text
You are the Tata Power AI Energy Assistant. 
Answer using ONLY the provided context. If the answer is not in the context, say you do not know.
```

### 4.2 Data Sanitization
The user's chat message is never evaluated as code or passed directly into a SQL query. It is simply appended as a natural language string to the Groq API payload. The LLM has zero execution privileges on the backend server.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
