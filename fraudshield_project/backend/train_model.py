"""
FraudShield - Model Training
Generates a synthetic (but realistic-shaped) transaction dataset and trains a
scikit-learn RandomForest classifier to score fraud risk.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import joblib
import json
import os

RNG = np.random.default_rng(42)
N = 20000
FRAUD_RATE = 0.03  # realistic class imbalance

def generate_dataset(n=N, fraud_rate=FRAUD_RATE):
    n_fraud = int(n * fraud_rate)
    n_legit = n - n_fraud

    def make_rows(n_rows, fraud):
        if fraud:
            amount = RNG.gamma(shape=2.0, scale=1800, size=n_rows) + 200
            distance_km = RNG.gamma(shape=2.0, scale=350, size=n_rows)
            new_device = RNG.choice([0, 1], size=n_rows, p=[0.35, 0.65])
            new_payee = RNG.choice([0, 1], size=n_rows, p=[0.4, 0.6])
            velocity_5min = RNG.poisson(3.2, size=n_rows)
            hour = RNG.choice(range(24), size=n_rows,
                               p=_night_weighted_hours())
            account_age_days = RNG.exponential(180, size=n_rows)
        else:
            amount = RNG.gamma(shape=2.0, scale=110, size=n_rows) + 10
            distance_km = RNG.gamma(shape=1.2, scale=8, size=n_rows)
            new_device = RNG.choice([0, 1], size=n_rows, p=[0.92, 0.08])
            new_payee = RNG.choice([0, 1], size=n_rows, p=[0.85, 0.15])
            velocity_5min = RNG.poisson(0.3, size=n_rows)
            hour = RNG.integers(0, 24, size=n_rows)
            account_age_days = RNG.exponential(700, size=n_rows) + 30

        return pd.DataFrame({
            "amount": amount,
            "distance_km": distance_km,
            "new_device": new_device,
            "new_payee": new_payee,
            "velocity_5min": velocity_5min,
            "hour": hour,
            "account_age_days": account_age_days,
            "is_fraud": 1 if fraud else 0,
        })

    def _night_weighted_hours():
        p = np.ones(24)
        p[0:6] *= 3.0   # fraud more likely at night
        p[22:24] *= 2.0
        return p / p.sum()

    df = pd.concat([make_rows(n_legit, False), make_rows(n_fraud, True)], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Add realistic noise / overlap so the problem isn't trivially separable
    noise_idx = RNG.choice(len(df), size=int(len(df) * 0.015), replace=False)
    df.loc[noise_idx, "is_fraud"] = 1 - df.loc[noise_idx, "is_fraud"]
    df["amount"] *= RNG.normal(1.0, 0.08, size=len(df))
    df["distance_km"] *= RNG.normal(1.0, 0.15, size=len(df))
    df["velocity_5min"] = np.clip(
        df["velocity_5min"] + RNG.integers(-1, 2, size=len(df)), 0, None
    )

    return df


FEATURES = ["amount", "distance_km", "new_device", "new_payee",
            "velocity_5min", "hour", "account_age_days"]


def train_model():
    df = generate_dataset()
    X = df[FEATURES]
    y = df["is_fraud"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42
    )

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    metrics = {
        "precision": round(float(precision_score(y_test, y_pred)), 3),
        "recall": round(float(recall_score(y_test, y_pred)), 3),
        "f1_score": round(float(f1_score(y_test, y_pred)), 3),
        "auc_roc": round(float(roc_auc_score(y_test, y_proba)), 3),
    }

    os.makedirs("models", exist_ok=True)
    joblib.dump(clf, "models/fraud_model.joblib")
    with open("models/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Save a sample of the test set for the live-feed / seed data
    sample = X_test.copy()
    sample["is_fraud"] = y_test.values
    sample["risk_score"] = (y_proba * 100).round(1)
    sample.to_csv("models/seed_transactions.csv", index=False)

    print("Training complete.")
    print(json.dumps(metrics, indent=2))
    return clf, metrics


if __name__ == "__main__":
    train_model()
