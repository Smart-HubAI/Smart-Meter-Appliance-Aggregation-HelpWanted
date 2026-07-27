# Volume 13: Deployment Architecture

## 1. Introduction
The platform is designed with a modern, decoupled architecture allowing for both localized development deployments and scalable cloud-based production environments.

---

## 2. Local Development Deployment

The current local development setup operates natively on Windows utilizing PowerShell and Python Virtual Environments.

### 2.1 Backend (Flask & ML)
1. **Virtual Environment**: Initialized via `python -m venv venv`.
2. **Dependencies**: `pip install -r requirements.txt` installs Flask, Scikit-Learn, Pandas, Psycopg2, and Groq.
3. **Environment Variables**: Managed via a `.env` file at the root.
   - `GROQ_API_KEY`: Required for the AI Assistant.
   - `DATABASE_URL`: `postgresql://user:pass@localhost:5432/energy_db`
4. **Execution**: Running `python app.py` starts the Werkzeug WSGI server on port `5000`.

### 2.2 Frontend (React & Vite)
1. **Dependencies**: `cd frontend && npm install`.
2. **Execution**: `npm run dev` starts the Vite HMR server on port `5173`.
3. **API Proxy**: The Vite config proxies all `/api` requests to `http://localhost:5000` to bypass CORS issues during development.

---

## 3. Production Deployment Strategy

For a final-year project submission or a real-world enterprise deployment, a robust, containerized approach is recommended.

### 3.1 Dockerization (Future Implementation)
- **Frontend Container**: The React app is built (`npm run build`) and served statically using an `NGINX` alpine container.
- **Backend Container**: The Flask app runs via `Gunicorn` (a production-grade WSGI HTTP Server) to handle concurrent requests natively.
- **Database Container**: A `postgres:15-alpine` container with a persistent Docker volume mapping to ensure data retention across restarts.

### 3.2 Cloud Infrastructure (AWS / Azure)
If deployed to AWS:
1. **RDS (Relational Database Service)**: Hosts the PostgreSQL instance, providing automated backups and Multi-AZ high availability.
2. **EC2 / Fargate**: Hosts the Dockerized Flask and NGINX containers.
3. **CloudWatch**: Monitors container health and captures Flask/Gunicorn logs for debugging.

---

## 4. Model Deployment & Batch Scheduling

Machine Learning inference is not triggered via API requests (which would cause massive latency). Instead, it runs as a scheduled batch process.
- **Linux/Production**: A `cron` job executes `train_all_models.py` daily at 01:00 AM.
- **Windows/Local**: Windows Task Scheduler or a dedicated background Python thread runs the inference pipeline.
- The models (`.pkl` files) are loaded from disk into memory, the previous 24 hours of data is fetched from PostgreSQL, and the resulting predictions are `UPSERT`ed back into the database.


---

## Meta Information
- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`
- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`
- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)
- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API
- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.
