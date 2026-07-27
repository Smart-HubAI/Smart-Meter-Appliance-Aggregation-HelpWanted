# Volume 18: Interview Preparation & Viva Guide

## 1. Introduction
This volume provides a comprehensive Question & Answer guide designed to prepare you for technical defense, viva examinations, and software engineering interviews based on the technologies and architectural decisions utilized in this project.

---

## 2. Machine Learning & Algorithms

**Q1: What is NILM and why is it important?**
*Answer:* Non-Intrusive Load Monitoring (NILM) is a computational technique used to deduce appliance-level energy consumption from a single, aggregated smart meter reading. It is important because it solves the "appliance blind spot", allowing consumers to see exactly which devices are driving their bills without requiring expensive, intrusive smart plugs on every socket.

**Q2: Why did you choose Random Forest for the Disaggregation model instead of XGBoost or Deep Learning (LSTMs)?**
*Answer:* While LSTMs offer excellent accuracy for sequential time-series data, they require massive computational resources and suffer from the "black box" problem. Random Forest was chosen because it is highly interpretable (feature importance is easily extracted), extremely fast to train via parallelization (`n_jobs=-1`), and highly resistant to overfitting the noisy signals inherent in our simulated smart meter data. XGBoost was also evaluated but Random Forest offered a better balance of training speed vs. accuracy for our multi-output regression needs.

**Q3: How does an Isolation Forest detect anomalies?**
*Answer:* Isolation Forest is an unsupervised algorithm based on the concept that anomalies are "few and different." It builds random decision trees. Because anomalous data points (like a sudden voltage spike) are statistically far from the norm, they require fewer splits to be isolated in a leaf node. The algorithm flags instances with abnormally short path lengths as anomalies.

**Q4: How did you handle cyclical time features in your dataset?**
*Answer:* Machine learning models treat time linearly (e.g., 23:00 and 01:00 appear mathematically distant). I engineered sine and cosine transformations (`np.sin(2 * pi * hour / 24)`) to map the hour of the day onto a unit circle. This allows the Random Forest to understand that 11 PM and 1 AM are temporally adjacent.

---

## 3. Backend & API Design

**Q5: Why Flask instead of Django or FastAPI?**
*Answer:* The backend acts primarily as a lightweight REST API routing layer between PostgreSQL, the ML models, and the React frontend. Flask's micro-framework architecture was perfect for this. Django would have been too heavyweight (its built-in ORM wasn't necessary as we heavily utilized `pandas` for data manipulation). FastAPI is excellent for async workloads, but our ML inference is strictly synchronous and batch-processed, making Flask's `psycopg2` synchronous flow highly reliable.

**Q6: Explain the flow when the AI Chatbot is queried.**
*Answer:* When a user sends a message to `/api/chat`, the Flask backend does *not* immediately pass the text to the LLM. It first executes an Intent Detection regex to understand what the user wants. If the user asks for "Critical cases", the backend queries the PostgreSQL `anomalies` table, formats the exact Risk Scores into a strict string, and prepends it to the LLM prompt as context. This Retrieval-Augmented Generation (RAG) ensures the LLM never hallucinates fake data.

**Q7: How did you solve the CORS (Cross-Origin Resource Sharing) issue during development?**
*Answer:* Because the Vite frontend runs on port `5173` and Flask on `5000`, the browser blocked the API calls for security reasons. I resolved this by utilizing the `flask-cors` library on the backend to explicitly allow the localhost origin, and subsequently configured the Vite proxy to route `/api` calls directly to the Flask port to bypass preflight checks seamlessly.

---

## 4. Database Architecture (PostgreSQL)

**Q8: Why migrate from SQLite to PostgreSQL?**
*Answer:* SQLite locks the entire database during a write operation. Given that our simulator inserts millions of telemetry rows and the Flask API concurrently executes heavy `GROUP BY` reads for Zone Analytics, SQLite caused severe bottlenecking and "Database is locked" errors. PostgreSQL handles highly concurrent read/write operations seamlessly via Multi-Version Concurrency Control (MVCC).

**Q9: How do you prevent SQL Injection in your backend?**
*Answer:* Every single SQL query in the `dal.py` file uses parameterized queries. Instead of formatting strings (e.g., `f"SELECT * FROM tbl WHERE id = '{input}'"`), I pass parameters to `psycopg2` (e.g., `execute("SELECT * FROM tbl WHERE id = %s", (input,))`). This ensures the database engine treats all input strictly as literal values, never as executable SQL commands.

---

## 5. React Frontend

**Q10: Why didn't you use Redux for state management?**
*Answer:* The dashboards are "read-heavy" visualization layers. They fetch a massive JSON payload from the backend and render charts. There is very little complex client-side state mutation (like a shopping cart) that requires a global store. Standard React hooks (`useState`, `useEffect`) and prop-drilling were sufficient, keeping the bundle size small and the architecture simple.

**Q11: How did you solve the Chart.js overlapping issue?**
*Answer:* `react-chartjs-2` canvases inherently try to fill their flexbox parent, causing infinite resize loops on window resize. I solved this by wrapping every chart component in a relatively positioned `div` with a fixed or constrained height (`height: 300px`), and setting `maintainAspectRatio: false` in the chart options.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
