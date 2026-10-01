"""
FraudShield - Flask Backend
Unified Fraud Detection & Risk Scoring Platform

Run:
    python app.py
Then open the frontend/index.html in a browser (it calls this API at
http://localhost:5000).
"""
import os
import json
import random
import string
from datetime import datetime

import joblib
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS

import db
from train_model import FEATURES, train_model

BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "models", "fraud_model.joblib")
METRICS_PATH = os.path.join(BASE_DIR, "models", "metrics.json")
SEED_CSV_PATH = os.path.join(BASE_DIR, "models", "seed_transactions.csv")

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Startup: train the model (if missing) and seed the database (if empty)
# ---------------------------------------------------------------------------

def bootstrap():
    if not os.path.exists(MODEL_PATH):
        print("No trained model found — training now...")
        train_model()

    db.init_db(reset=False)
    conn = db.get_conn()
    count = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
    conn.close()
    if count == 0:
        print("Seeding database with sample transactions...")
        db.seed_from_csv(SEED_CSV_PATH, n_seed=150)


bootstrap()
MODEL = joblib.load(MODEL_PATH)
with open(METRICS_PATH) as f:
    METRICS = json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def score_transaction(features: dict) -> float:
    x = np.array([[features[f] for f in FEATURES]])
    proba = MODEL.predict_proba(x)[0, 1]
    return round(float(proba) * 100, 1)


def shap_like_breakdown(features: dict):
    """
    Lightweight, dependency-free approximation of a SHAP-style explanation:
    combines the model's global feature importances with how far this
    transaction's values deviate from typical "normal" values, so each
    factor gets a directional, weighted contribution to the score.
    """
    importances = MODEL.feature_importances_
    baselines = {
        "amount": 150, "distance_km": 10, "new_device": 0, "new_payee": 0,
        "velocity_5min": 0.3, "hour": 13, "account_age_days": 400,
    }
    spread = {
        "amount": 400, "distance_km": 60, "new_device": 1, "new_payee": 1,
        "velocity_5min": 2, "hour": 12, "account_age_days": 300,
    }
    labels = {
        "amount": "High Transaction Amount",
        "distance_km": "Unusual Location",
        "new_device": "New Device",
        "new_payee": "New Payee",
        "velocity_5min": "Velocity / High Frequency",
        "hour": "Odd Transaction Hour",
        "account_age_days": "New / Young Account",
    }
    reasons = {
        "amount": "Amount is significantly higher than usual",
        "distance_km": "Location is far from usual activity area",
        "new_device": "Device not seen before on this account",
        "new_payee": "Payee/recipient not in user history",
        "velocity_5min": "Multiple transactions in a short window",
        "hour": "Transaction occurred at an unusual hour",
        "account_age_days": "Account is relatively new",
    }

    rows = []
    for i, f in enumerate(FEATURES):
        z = (features[f] - baselines[f]) / spread[f]
        z = max(-2.5, min(2.5, z))
        contribution = round(float(importances[i] * z * 40), 1)
        rows.append({
            "factor": labels[f],
            "reason": reasons[f],
            "impact": "High" if abs(contribution) >= 15 else ("Medium" if abs(contribution) >= 6 else "Low"),
            "weight": round(float(importances[i]), 2),
            "score_contribution": contribution,
        })
    rows.sort(key=lambda r: abs(r["score_contribution"]), reverse=True)
    return rows


def gen_txn_id():
    return "TXN" + "".join(random.choices(string.digits, k=7))


# ---------------------------------------------------------------------------
# Dashboard endpoints
# ---------------------------------------------------------------------------

@app.route("/api/summary")
def api_summary():
    conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"]
    risky = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score >= 30").fetchone()["c"]
    high_risk = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score >= 70").fetchone()["c"]
    confirmed = conn.execute("SELECT COUNT(*) c FROM transactions WHERE status='Flagged'").fetchone()["c"]
    avg_score = conn.execute("SELECT AVG(risk_score) a FROM transactions").fetchone()["a"] or 0
    blocked = conn.execute(
        "SELECT SUM(amount) s FROM transactions WHERE status='Flagged'"
    ).fetchone()["s"] or 0
    conn.close()

    return jsonify({
        "total_transactions": total,
        "risky_transactions": risky,
        "high_risk": high_risk,
        "fraud_confirmed": confirmed,
        "avg_risk_score": round(avg_score, 1),
        "blocked_amount": round(blocked, 2),
    })


@app.route("/api/risk-distribution")
def api_risk_distribution():
    conn = db.get_conn()
    low = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score < 30").fetchone()["c"]
    med = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score >= 30 AND risk_score < 70").fetchone()["c"]
    high = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score >= 70").fetchone()["c"]
    conn.close()
    total = max(low + med + high, 1)
    return jsonify({
        "labels": ["0-30 (Low)", "31-70 (Medium)", "71-100 (High)"],
        "counts": [low, med, high],
        "percentages": [round(low/total*100,1), round(med/total*100,1), round(high/total*100,1)],
    })


@app.route("/api/fraud-trend")
def api_fraud_trend():
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT created_at, risk_score, status FROM transactions ORDER BY created_at ASC"
    ).fetchall()
    conn.close()

    buckets = {}
    for r in rows:
        minute = r["created_at"][:16]
        buckets.setdefault(minute, {"risky": 0, "fraud": 0})
        if r["risk_score"] >= 30:
            buckets[minute]["risky"] += 1
        if r["status"] == "Flagged":
            buckets[minute]["fraud"] += 1

    labels = sorted(buckets.keys())[-12:]
    return jsonify({
        "labels": [l[-5:] for l in labels],
        "risky": [buckets[l]["risky"] for l in labels],
        "fraud": [buckets[l]["fraud"] for l in labels],
    })


@app.route("/api/top-risk-factors")
def api_top_risk_factors():
    importances = MODEL.feature_importances_
    labels = {
        "amount": "High Transaction Amt", "distance_km": "Unusual Location",
        "new_device": "New Device", "new_payee": "New Payee/Account",
        "velocity_5min": "Velocity/High Frequency", "hour": "Odd Hour",
        "account_age_days": "New Account",
    }
    pairs = sorted(zip(FEATURES, importances), key=lambda p: p[1], reverse=True)[:5]
    total = sum(imp for _, imp in pairs)
    return jsonify([
        {"factor": labels[f], "percentage": round(float(imp/total*100), 0)}
        for f, imp in pairs
    ])


@app.route("/api/alerts-overview")
def api_alerts_overview():
    conn = db.get_conn()
    high = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score >= 70").fetchone()["c"]
    med = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score >= 30 AND risk_score < 70").fetchone()["c"]
    low = conn.execute("SELECT COUNT(*) c FROM transactions WHERE risk_score < 30").fetchone()["c"]
    conn.close()
    return jsonify({"high_risk_alerts": high, "medium_risk_alerts": med, "low_risk_alerts": low})


@app.route("/api/alerts-by-channel")
def api_alerts_by_channel():
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT channel, COUNT(*) c FROM transactions WHERE risk_score >= 30 GROUP BY channel"
    ).fetchall()
    conn.close()
    total = sum(r["c"] for r in rows) or 1
    return jsonify([
        {"channel": r["channel"], "percentage": round(r["c"]/total*100, 1)} for r in rows
    ])


@app.route("/api/model-performance")
def api_model_performance():
    return jsonify(METRICS)


@app.route("/api/live-feed")
def api_live_feed():
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT txn_id, user_id, amount, risk_score, created_at, status "
        "FROM transactions ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@app.route("/api/transactions")
def api_transactions():
    limit = int(request.args.get("limit", 50))
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/transactions/<txn_id>")
def api_transaction_detail(txn_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    txn = dict(row)
    breakdown = shap_like_breakdown({f: txn[f] for f in FEATURES})
    risk_label = "High Risk" if txn["risk_score"] >= 70 else ("Medium Risk" if txn["risk_score"] >= 30 else "Low Risk")
    return jsonify({
        "transaction": txn,
        "risk_label": risk_label,
        "breakdown": breakdown,
    })


@app.route("/api/score", methods=["POST"])
def api_score():
    """Real-time scoring endpoint for a new transaction."""
    payload = request.get_json(force=True)

    features = {
        "amount": float(payload.get("amount", 0)),
        "distance_km": float(payload.get("distance_km", 0)),
        "new_device": int(payload.get("new_device", 0)),
        "new_payee": int(payload.get("new_payee", 0)),
        "velocity_5min": int(payload.get("velocity_5min", 0)),
        "hour": int(payload.get("hour", datetime.utcnow().hour)),
        "account_age_days": float(payload.get("account_age_days", 365)),
    }
    risk_score = score_transaction(features)
    status = "Flagged" if risk_score >= 70 else ("Review" if risk_score >= 30 else "Cleared")

    txn_id = gen_txn_id()
    conn = db.get_conn()
    conn.execute("""
        INSERT INTO transactions
        (txn_id, user_id, amount, channel, location, device, ip_address,
         distance_km, new_device, new_payee, velocity_5min, hour,
         account_age_days, risk_score, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        txn_id, payload.get("user_id", "U" + "".join(random.choices(string.digits, k=6))),
        features["amount"], payload.get("channel", "Web"),
        payload.get("location", "Unknown"), payload.get("device", "Unknown"),
        payload.get("ip_address", "0.0.0.0"), features["distance_km"],
        features["new_device"], features["new_payee"], features["velocity_5min"],
        features["hour"], features["account_age_days"], risk_score, status,
        datetime.utcnow().isoformat()
    ))

    if risk_score >= 55:
        case_id = "CASE-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        conn.execute("""
            INSERT INTO cases (case_id, txn_id, priority, status, assigned_to, created_at)
            VALUES (?,?,?,?,?,?)
        """, (case_id, txn_id, "High" if risk_score >= 80 else "Medium", "Open",
              "Unassigned", datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

    breakdown = shap_like_breakdown(features)
    return jsonify({
        "txn_id": txn_id, "risk_score": risk_score, "status": status,
        "breakdown": breakdown,
    })


# ---------------------------------------------------------------------------
# Case management
# ---------------------------------------------------------------------------

@app.route("/api/cases")
def api_cases():
    conn = db.get_conn()
    status_filter = request.args.get("status")
    query = """
        SELECT c.case_id, c.priority, c.status, c.assigned_to, c.created_at,
               t.txn_id, t.user_id, t.amount, t.risk_score
        FROM cases c JOIN transactions t ON c.txn_id = t.txn_id
    """
    params = ()
    if status_filter and status_filter != "All":
        query += " WHERE c.status = ?"
        params = (status_filter,)
    query += " ORDER BY c.created_at DESC LIMIT 100"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/cases/summary")
def api_cases_summary():
    conn = db.get_conn()
    open_c = conn.execute("SELECT COUNT(*) c FROM cases WHERE status='Open'").fetchone()["c"]
    review_c = conn.execute("SELECT COUNT(*) c FROM cases WHERE status='In Review'").fetchone()["c"]
    escalated_c = conn.execute("SELECT COUNT(*) c FROM cases WHERE status='Escalated'").fetchone()["c"]
    closed_c = conn.execute("SELECT COUNT(*) c FROM cases WHERE status='Closed'").fetchone()["c"]
    conn.close()
    return jsonify({"open": open_c, "in_review": review_c, "escalated": escalated_c, "closed_today": closed_c})


@app.route("/api/cases/<case_id>", methods=["PATCH"])
def api_update_case(case_id):
    payload = request.get_json(force=True)
    new_status = payload.get("status")
    if new_status not in ("Open", "In Review", "Escalated", "Closed"):
        return jsonify({"error": "invalid status"}), 400
    conn = db.get_conn()
    conn.execute("UPDATE cases SET status=? WHERE case_id=?", (new_status, case_id))
    conn.commit()
    conn.close()
    return jsonify({"case_id": case_id, "status": new_status})


@app.route("/api/reset-demo", methods=["POST"])
def api_reset_demo():
    """Wipe and reseed the demo database (handy for repeated presentations)."""
    db.init_db(reset=True)
    db.seed_from_csv(SEED_CSV_PATH, n_seed=150)
    return jsonify({"status": "reset complete"})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
