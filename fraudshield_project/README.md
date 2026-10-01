# FraudShield — Unified Fraud Detection & Risk Scoring Platform

A working prototype of the FraudShield dashboard: a real-time-styled fraud
risk scoring platform with a trained ML model, a REST API backend, and a
dashboard UI matching the "Fraud Risk Command Center" design.

**Team:** D. Rohini Tanmayi (2520030349) · S. Manvi Vaishnavi (2520030326) · Varshith (2520030598)

## Tech Stack (matches project software requirements)

| Layer          | Tech                                            |
|----------------|--------------------------------------------------|
| Frontend       | HTML, CSS, JavaScript + Chart.js                  |
| Backend        | Python, Flask (REST API)                          |
| Machine Learning | Python, scikit-learn (RandomForest), pandas, NumPy |
| Database       | SQLite (swap in MySQL/MongoDB with minimal changes) |
| Visualization  | Chart.js                                          |
| Tools          | VS Code, GitHub, Postman (for API testing)        |

> The model uses a synthetic but realistically-shaped transaction dataset
> (generated in `train_model.py`) since no real fraud dataset was provided.
> Swap in a real dataset by replacing `generate_dataset()`.

## Project Structure

```
fraudshield_project/
├── backend/
│   ├── app.py            # Flask REST API (all endpoints)
│   ├── db.py              # SQLite schema + seeding
│   ├── train_model.py     # Synthetic data generator + RandomForest training
│   └── requirements.txt
└── frontend/
    ├── index.html         # Dashboard UI (all views/tabs)
    ├── style.css          # Dark theme matching the reference design
    ├── app.js             # API calls + Chart.js rendering
    └── vendor/
        └── chart.umd.min.js   # Chart.js, bundled locally (no CDN needed)
```

## How to Run

### 1. Backend (Flask API + ML model)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The first run will:
- Train the RandomForest fraud model on a synthetic dataset (~5 seconds)
- Save it to `backend/models/fraud_model.joblib`
- Create `backend/fraudshield.db` (SQLite) and seed it with ~150 sample
  transactions and cases

The API will be live at **http://localhost:5000**.

### 2. Frontend (Dashboard)

In a second terminal:

```bash
cd frontend
python3 -m http.server 8080
```

Then open **http://localhost:8080** in your browser.

(The frontend is plain HTML/CSS/JS, so you can also just open
`frontend/index.html` directly in a browser — but serving it over
`http.server` avoids any local-file CORS quirks.)

## Features

- **Dashboard** — live KPIs, risk score distribution, fraud trend, top risk
  factors, live transaction feed, alerts overview, alerts by channel, model
  performance.
- **Transactions** — full transaction table, click any row for detail.
- **Live Monitoring (Transaction Detail)** — risk gauge, "why was this
  flagged?" panel, score breakdown table, and a feature-contribution chart
  (a SHAP-style explanation computed from the model's feature importances).
- **Alerts** — high/medium/low risk alert counts and a flagged-transactions
  table.
- **Cases** — case summary counts and a case management table with editable
  status (Open / In Review / Escalated / Closed).
- **Score Transaction** — submit a new transaction's details and get a
  real-time risk score + explanation from the live model (this is exactly
  how new transactions would be scored in production).
- **Models** — model performance metrics and feature importances, plus a
  "Reset Demo Data" button to reseed the database before a presentation.

## API Endpoints (for Postman testing)

| Method | Endpoint                     | Description                          |
|--------|-------------------------------|---------------------------------------|
| GET    | `/api/summary`                | Dashboard KPI totals                  |
| GET    | `/api/risk-distribution`      | Low/Medium/High risk counts           |
| GET    | `/api/fraud-trend`            | Time-series of risky/fraud counts     |
| GET    | `/api/top-risk-factors`       | Global feature importances            |
| GET    | `/api/alerts-overview`        | Alert counts by risk level            |
| GET    | `/api/alerts-by-channel`      | Alert % by channel (Web/Mobile/API/POS)|
| GET    | `/api/model-performance`      | Precision/Recall/F1/AUC-ROC           |
| GET    | `/api/live-feed`               | Most recent 10 transactions           |
| GET    | `/api/transactions?limit=N`   | List transactions                     |
| GET    | `/api/transactions/<txn_id>`  | Full detail + score breakdown         |
| POST   | `/api/score`                   | Score a new transaction in real time  |
| GET    | `/api/cases?status=`          | List cases (optional status filter)   |
| GET    | `/api/cases/summary`          | Case counts by status                 |
| PATCH  | `/api/cases/<case_id>`        | Update a case's status                |
| POST   | `/api/reset-demo`             | Wipe & reseed demo data               |

Example `POST /api/score` body:
```json
{
  "amount": 8950,
  "distance_km": 1200,
  "new_device": 1,
  "new_payee": 1,
  "velocity_5min": 5,
  "hour": 0,
  "account_age_days": 20,
  "channel": "Mobile",
  "location": "New York, USA"
}
```

## Notes on the ML Model

- Model: `RandomForestClassifier` (scikit-learn), 300 trees, class-balanced.
- Features: transaction amount, distance from home, new-device flag,
  new-payee flag, 5-minute transaction velocity, hour of day, account age.
- Reported metrics (on held-out test data): Precision 0.965, Recall 0.638,
  F1 0.768, AUC-ROC 0.827 — realistic numbers for an imbalanced fraud
  problem (your exact numbers will vary slightly each time you retrain,
  since the synthetic dataset uses randomised noise).
- Explainability: rather than a full SHAP dependency, `app.py` computes a
  lightweight, SHAP-style directional breakdown from the model's feature
  importances and how far a transaction's values deviate from typical
  values. This keeps the dependency list matching your declared software
  requirements (scikit-learn only) while still giving analysts a "why was
  this flagged" explanation per transaction. If you want true SHAP values,
  `pip install shap` and swap in `shap.TreeExplainer(MODEL)`.

## Extending to MySQL / MongoDB

The app currently uses SQLite for zero-setup local development. To switch:
- **MySQL**: replace `db.py`'s `sqlite3` calls with `mysql-connector-python`
  or `SQLAlchemy` + a MySQL URI; the schema (`SCHEMA` string) translates
  almost directly.
- **MongoDB**: replace the SQL schema with two collections
  (`transactions`, `cases`) and swap the SQL queries in `app.py` for
  `pymongo` filter/aggregation calls.
