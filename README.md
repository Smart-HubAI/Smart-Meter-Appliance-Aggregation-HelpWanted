# AI-Powered Smart Meter Energy Disaggregation Platform

Tata Power–style utility analytics with **simulated ground truth**, **feature store**, and **ML training pipelines** for NILM, anomaly detection, and bill prediction.

## Project Architecture
This enterprise application utilizes a modern tech stack to serve smart meter analytics:
- **Backend**: Flask (Python) exposing RESTful APIs.
- **Database**: PostgreSQL storing meter readings, ground truth, metrics, and logs.
- **Frontend**: React-based Single Page Application (Vite) rendering professional Dashboards.
- **Machine Learning**: Scikit-Learn and XGBoost pipelines storing artifacts via joblib.

## Models Used
The system is powered exclusively by the following production models:
- **Energy Disaggregation**: Gradient Boosting, Random Forest, XGBoost
- **Anomaly Detection**: Isolation Forest, Random Forest, XGBoost
- **Bill Prediction**: Linear Regression, XGBoost

## Dataset Information
- Smart Meter Readings (15-min interval AMI data)
- Appliance Ground Truth (AC, Refrigerator, Lighting, TV, Washing Machine, Water Heater, Fans, Miscellaneous)
- Labelled Anomalies (Voltage fluctuations, tamper events, peak hour overconsumption, phantom loads)
- Features (Daily extracted attributes including peak load, night usage ratio, voltage variance)

## Project Structure
```
energy-dis/
├── app.py                      # Main Flask Server
├── requirements.txt
├── .env
├── config.py
├── train_disaggregation_model.py # Primary ML Entry Points
├── train_anomaly_model.py
├── train_bill_model.py
├── train_all_models.py
├── frontend/                   # React SPA
├── models/                     # Inference & Evaluation Layer
│   └── artifacts/              # Production .pkl Models
├── database/                   # PostgreSQL Configs & ORM
├── data/                       # Raw Data / Assets
├── scripts/                    # Utility Scripts
│   └── database/               # Database Inspection & Scripts
├── tests/                      # Unit Tests
├── reports/                    # Generated Analytics
└── output/                     # Generated Outputs
```

## How to Run the Project

1. **Install Dependencies**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. **Database Setup & PostgreSQL Configuration**
Ensure PostgreSQL is running locally on port 5432.
Update `.env` with your PostgreSQL credentials:
```env
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smart_meter_db
```

3. **Generate DB + Ground Truth + Features**
```bash
python -c "from utils.data_loader import load_simulation_to_database; load_simulation_to_database(force=True)"
```

4. **Start the Frontend Build**
```bash
cd frontend
npm install
npm run build
cd ..
```

5. **Start the Server**
```bash
python app.py
```
The application will be served at `http://127.0.0.1:5000/`.

## How to Retrain Models
To retrain the ML pipelines with the latest database features, simply execute the training scripts from the root directory:
```bash
python train_all_models.py
```
Alternatively, train specific components:
```bash
python train_disaggregation_model.py
python train_anomaly_model.py
python train_bill_model.py
```
Model artifacts will be seamlessly updated inside `models/artifacts/` and metrics synced to the database.

## Dashboard Overview
| Page | URL | Description |
|------|-----|-------------|
| **Home** | `http://127.0.0.1:5000/` | Consumer Overview and system aggregates. |
| **Consumer** | `http://127.0.0.1:5000/consumer` | Deep-dive into individual smart meter consumption. |
| **Admin** | `http://127.0.0.1:5000/admin` | Platform configurations and user management. |
| **AI Models & Validation** | `http://127.0.0.1:5000/ai` | MLOps Dashboard displaying actual ground truth, confusion matrices, and real-time training evaluation metrics. |
