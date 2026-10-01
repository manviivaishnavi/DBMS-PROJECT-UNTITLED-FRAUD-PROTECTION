"""
FraudShield - Database layer (SQLite)
"""
import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "fraudshield.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    txn_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount REAL NOT NULL,
    channel TEXT NOT NULL,
    location TEXT NOT NULL,
    device TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    distance_km REAL NOT NULL,
    new_device INTEGER NOT NULL,
    new_payee INTEGER NOT NULL,
    velocity_5min INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    account_age_days REAL NOT NULL,
    risk_score REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    txn_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    assigned_to TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (txn_id) REFERENCES transactions (txn_id)
);
"""

CITIES = ["New York, USA", "Mumbai, India", "London, UK", "Hyderabad, India",
          "Singapore", "Toronto, Canada", "Berlin, Germany", "Dubai, UAE"]
DEVICES = ["iPhone 14 Pro", "Samsung Galaxy S23", "Windows PC - Chrome",
           "MacBook Pro - Safari", "Pixel 8", "iPad Air"]
CHANNELS = ["Web", "Mobile", "API", "POS"]
ANALYSTS = ["Analyst A", "Analyst B", "Analyst C", "Analyst D", "Team Lead"]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def _random_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"


def seed_from_csv(csv_path, n_seed=150):
    """Populate the transactions/cases tables from the trained model's held-out sample."""
    import pandas as pd
    df = pd.read_csv(csv_path)
    df = df.sample(n=min(n_seed, len(df)), random_state=7).reset_index(drop=True)

    conn = get_conn()
    cur = conn.cursor()

    now = datetime.utcnow()
    for i, row in df.iterrows():
        txn_id = f"TXN{9500000 + i}"
        user_id = f"U{100000 + random.randint(0, 900)}"
        created_at = (now - timedelta(minutes=random.randint(0, 180))).isoformat()
        risk_score = float(row["risk_score"])
        status = "Flagged" if risk_score >= 70 else ("Review" if risk_score >= 30 else "Cleared")

        cur.execute("""
            INSERT OR REPLACE INTO transactions
            (txn_id, user_id, amount, channel, location, device, ip_address,
             distance_km, new_device, new_payee, velocity_5min, hour,
             account_age_days, risk_score, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            txn_id, user_id, round(float(row["amount"]), 2),
            random.choice(CHANNELS), random.choice(CITIES), random.choice(DEVICES),
            _random_ip(), round(float(row["distance_km"]), 1),
            int(row["new_device"]), int(row["new_payee"]), int(row["velocity_5min"]),
            int(row["hour"]), round(float(row["account_age_days"]), 1),
            round(risk_score, 1), status, created_at
        ))

        if risk_score >= 55:
            case_id = f"CASE-2026-{100000 + i}"
            priority = "High" if risk_score >= 80 else "Medium"
            case_status = random.choice(["Open", "In Review", "Escalated", "Closed"])
            cur.execute("""
                INSERT OR REPLACE INTO cases
                (case_id, txn_id, priority, status, assigned_to, created_at)
                VALUES (?,?,?,?,?,?)
            """, (case_id, txn_id, priority, case_status,
                  random.choice(ANALYSTS), created_at))

    conn.commit()
    conn.close()
