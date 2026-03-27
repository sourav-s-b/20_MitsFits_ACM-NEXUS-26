import requests
from datetime import datetime
from dotenv import load_dotenv
import os
import joblib
import pandas as pd
from pathlib import Path

load_dotenv()

OWM_KEY = os.getenv("OWM_KEY")
TOMTOM_KEY = os.getenv("TOMTOM_KEY")

# --- Model Loading ---
MODEL_PATH = Path(__file__).parent / "risk_model.pkl"
try:
    risk_model = joblib.load(MODEL_PATH)
except Exception as e:
    print(f"[Model] Could not load model from {MODEL_PATH}: {e}")
    risk_model = None

# ── Weather ────────────────────────────────────────────────

WEATHER_RISK_MAP = {
    "Clear": 0.0,
    "Clouds": 0.1,
    "Drizzle": 0.3,
    "Rain": 0.5,
    "Thunderstorm": 0.9,
    "Snow": 0.7,
    "Fog": 0.5,
    "Mist": 0.3,
}


def get_weather_score(lat: float, lon: float) -> float:
    if not OWM_KEY:
        print("[Weather] OWM_KEY not set, using default.")
        return 0.2
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OWM_KEY},
            timeout=5,
        )
        r.raise_for_status()
        condition = r.json().get("weather", [{}])[0].get("main", "Clear")
        return WEATHER_RISK_MAP.get(condition, 0.2)
    except Exception as e:
        print(f"[Weather] API failed: {e}")
        return 0.2  # safe fallback


# ── Traffic ────────────────────────────────────────────────


def get_traffic_delay(lat: float, lon: float) -> float:
    if not TOMTOM_KEY:
        print("[Traffic] TOMTOM_KEY not set, using default.")
        return 10.0
    try:
        r = requests.get(
            "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json",
            params={"point": f"{lat},{lon}", "key": TOMTOM_KEY},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()["flowSegmentData"]
        free_flow = data["freeFlowSpeed"]
        current = data["currentSpeed"]
        if free_flow <= 0:
            return 0.0
        if current <= 0:
            return 30.0
        # Assume 10km stretch for delay calculation
        delay = ((10 / current) - (10 / free_flow)) * 60
        return max(0.0, round(delay, 2))
    except Exception as e:
        print(f"[Traffic] API failed: {e}")
        return 10.0  # safe fallback


# ── Time Risk ──────────────────────────────────────────────


def get_time_risk() -> float:
    hour = datetime.now().hour
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        return 0.3  # peak hours
    if 0 <= hour <= 5:
        return 0.2  # night driving
    return 0.0


# ── Master Scorer ──────────────────────────────────────────


def compute_risk(lat: float, lon: float, override: dict = None) -> dict:
    override = override or {}

    traffic = override.get("traffic_delay", get_traffic_delay(lat, lon))
    weather = override.get("weather_score", get_weather_score(lat, lon))
    time_risk = get_time_risk()
    hour = datetime.now().hour

    # Try using ML model if available
    if risk_model:
        try:
            # Features: traffic (0-1), weather (0-1), hour (0-23)
            # Normalize traffic delay (0-60 min -> 0-1)
            norm_traffic = min(traffic / 60, 1.0)
            X_test = pd.DataFrame(
                [[norm_traffic, weather, hour]],
                columns=["traffic", "weather", "hour"]
            )
            prediction = risk_model.predict(X_test)
            risk = round(float(prediction[0]), 3)
        except Exception as e:
            print(f"[Model] Prediction failed: {e}")
            # Fallback to manual formula
            risk = norm_traffic * 0.50 + weather * 0.35 + time_risk * 0.15
    else:
        # Weighted formula fallback
        risk = min(traffic / 60, 1.0) * 0.50 + weather * 0.35 + time_risk * 0.15

    risk = round(min(risk, 1.0), 3)

    if risk < 0.35:
        status = "SAFE"
    elif risk < 0.65:
        status = "MODERATE"
    else:
        status = "HIGH RISK"

    return {
        "traffic_delay": traffic,
        "weather_score": weather,
        "time_risk": time_risk,
        "risk_score": risk,
        "status": status,
    }
