import pandas as pd
import os
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib


def generate_mock_data(samples=5000):
    np.random.seed(42)

    # 1. Features
    traffic = np.random.uniform(0, 1, samples)  # 0 (Clear) to 1 (Jam)
    weather = np.random.uniform(0, 1, samples)  # 0 (Clear) to 1 (Storm)
    hour = np.random.randint(0, 24, samples)  # 0 to 23

    # 2. Logic for the Label (Risk Score)
    # Risk increases with traffic and weather, and spikes during rush hours (8-10, 17-19)
    base_risk = (traffic * 0.5) + (weather * 0.4)
    rush_hour_effect = np.where(
        ((hour >= 8) & (hour <= 10)) | ((hour >= 17) & (hour <= 19)), 0.15, 0
    )

    risk_score = base_risk + rush_hour_effect + np.random.normal(0, 0.05, samples)
    risk_score = np.clip(risk_score, 0, 1)  # Keep between 0 and 1

    df = pd.DataFrame(
        {"traffic": traffic, "weather": weather, "hour": hour, "risk_score": risk_score}
    )
    return df


# 3. Training Script
def train():
    print("Generating synthetic training data...")
    data = generate_mock_data()

    X = data[["traffic", "weather", "hour"]]
    y = data["risk_score"]

    print("Training Random Forest Regressor...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    # --- FIXED PATH LOGIC ---
    # Get the directory where train.py actually lives
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, "risk_model.pkl")

    joblib.dump(model, model_path)
    print(f"Model saved successfully to: {model_path}")

    # Quick Test

    test_model = joblib.load(model_path)
    prediction = test_model.predict(
        [[0.9, 0.8, 18]]
    )  # High traffic, High weather, Rush hour
    print(f"Test Prediction (Should be high): {prediction[0]:.2f}")


if __name__ == "__main__":
    train()
