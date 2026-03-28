import numpy as np
import xgboost as xgb
import pickle
import requests
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

OWM_KEY = os.getenv("OWM_KEY")
TOMTOM_KEY = os.getenv("TOMTOM_KEY")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgb_model.json")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "feature_names.pkl")

if not os.path.exists(MODEL_PATH):
    print("ERROR: xgb_model.json not found in model/")
    print("Train on Kaggle and download the file first.")
    sys.exit(1)

# Load model
_model = xgb.XGBRegressor()
_model.load_model(MODEL_PATH)

with open(FEATURES_PATH, "rb") as f:
    _feature_names = pickle.load(f)

print(f"[XGBoost] Loaded. Features: {_feature_names}")

# ── SOP Mapping ────────────────────────────────────────────

SOP_MAP = {
    "CRITICAL": "SOP-Gamma-7",
    "HIGH": "SOP-Beta-3",
    "MODERATE": "SOP-Alpha-1",
    "SAFE": None,
}

# ── Weather Client ─────────────────────────────────────────

WEATHER_CONDITION_MAP = {
    "Clear": {"precipitation_mm": 0.0, "visibility_km": 10.0},
    "Clouds": {"precipitation_mm": 0.0, "visibility_km": 8.0},
    "Drizzle": {"precipitation_mm": 2.0, "visibility_km": 7.0},
    "Rain": {"precipitation_mm": 8.0, "visibility_km": 4.0},
    "Thunderstorm": {"precipitation_mm": 20.0, "visibility_km": 1.0},
    "Snow": {"precipitation_mm": 5.0, "visibility_km": 2.0},
    "Fog": {"precipitation_mm": 0.0, "visibility_km": 0.5},
    "Mist": {"precipitation_mm": 0.0, "visibility_km": 3.0},
}


def get_weather_signals(lat: float, lon: float) -> dict:
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OWM_KEY},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        condition = data["weather"][0]["main"]
        signals = WEATHER_CONDITION_MAP.get(
            condition, {"precipitation_mm": 2.0, "visibility_km": 5.0}
        )
        if condition in ["Snow"]:
            road_condition = 2
        elif condition in ["Rain", "Thunderstorm", "Drizzle"]:
            road_condition = 1
        else:
            road_condition = 0
        return {**signals, "road_condition": road_condition}
    except Exception as e:
        print(f"[Weather] Failed: {e}")
        return {"precipitation_mm": 2.0, "visibility_km": 5.0, "road_condition": 0}


# ── Traffic Client ─────────────────────────────────────────


def get_traffic_signals(lat: float, lon: float) -> dict:
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
        confidence = data.get("confidence", 0.5)

        speed_delta = max(0, free_flow - current)
        delay_seconds = ((10 / max(current, 1)) - (10 / max(free_flow, 1))) * 3600
        density = max(0, (1 - current / max(free_flow, 1)) * 100)

        return {
            "traffic_density": round(density, 2),
            "delay_seconds": round(max(0, delay_seconds), 2),
            "speed_delta": round(speed_delta, 2),
            "sensor_confidence": confidence,
        }
    except Exception as e:
        print(f"[Traffic] Failed: {e}")
        return {
            "traffic_density": 20.0,
            "delay_seconds": 120.0,
            "speed_delta": 10.0,
            "sensor_confidence": 0.5,
        }


# ── Time of Day ────────────────────────────────────────────


def get_time_of_day() -> int:
    return datetime.now().hour


# ── News Sentiment ─────────────────────────────────────────

KEYWORD_SCORES = {
    "blockade": 1.0,
    "protest": 0.9,
    "accident": 0.8,
    "flood": 0.85,
    "strike": 0.75,
    "closed": 0.7,
    "delay": 0.4,
    "slow": 0.3,
    "congestion": 0.5,
}


def score_news_text(text: str) -> float:
    if not text:
        return 0.0
    text_lower = text.lower()
    scores = [v for k, v in KEYWORD_SCORES.items() if k in text_lower]
    return round(min(max(scores, default=0.0), 1.0), 2)


# ── Confidence via Prediction Interval ─────────────────────
# XGBoost doesn't expose trees like RandomForest.
# Strategy: perturb input slightly, measure output stability.
# Stable output = high confidence. Volatile = low confidence.


def compute_confidence(feature_vector: np.ndarray, sensor_conf: float) -> float:
    noise_scale = 0.05  # 5% perturbation
    n_samples = 20

    perturbed_preds = []
    for _ in range(n_samples):
        noise = np.random.normal(0, noise_scale, feature_vector.shape)
        perturbed = np.clip(feature_vector + noise, 0, None)
        pred = float(_model.predict(perturbed)[0])
        perturbed_preds.append(pred)

    std = np.std(perturbed_preds)
    # std of ~0.1 or more = model is sensitive = lower confidence
    model_confidence = float(np.clip(1.0 - (std / 0.10), 0.0, 1.0))
    blended = (model_confidence * 0.7) + (sensor_conf * 0.3)
    return round(blended, 3)


# ── Master Compute ─────────────────────────────────────────


def compute_risk(lat: float, lon: float, override: dict = None) -> dict:
    override = override or {}

    weather = get_weather_signals(lat, lon)
    traffic = get_traffic_signals(lat, lon)
    hour = get_time_of_day()

    news_raw = override.get("news_text", "")
    news_sentiment = override.get("news_sentiment", score_news_text(news_raw))

    # Apply overrides
    traffic["traffic_density"] = override.get(
        "traffic_density", traffic["traffic_density"]
    )
    traffic["delay_seconds"] = override.get("delay_seconds", traffic["delay_seconds"])
    traffic["speed_delta"] = override.get("speed_delta", traffic["speed_delta"])
    weather["precipitation_mm"] = override.get(
        "precipitation_mm", weather["precipitation_mm"]
    )
    weather["visibility_km"] = override.get("visibility_km", weather["visibility_km"])
    weather["road_condition"] = override.get(
        "road_condition", weather["road_condition"]
    )

    sensor_conf = traffic.pop("sensor_confidence", 0.7)

    # Interaction terms — must match Kaggle notebook exactly
    traffic_x_weather = traffic["traffic_density"] * weather["precipitation_mm"]
    delay_x_road = traffic["delay_seconds"] * (weather["road_condition"] + 1)

    feature_vector = np.array(
        [
            [
                traffic["traffic_density"],
                traffic["delay_seconds"],
                traffic["speed_delta"],
                weather["precipitation_mm"],
                weather["visibility_km"],
                weather["road_condition"],
                hour,
                news_sentiment,
                traffic_x_weather,
                delay_x_road,
            ]
        ]
    )

    risk_score = float(np.clip(_model.predict(feature_vector)[0], 0.0, 1.0))

    # Black Swan override
    if news_sentiment >= 0.85:
        risk_score = max(risk_score, 0.95)
        print(f"[BlackSwan] Triggered: sentiment={news_sentiment}")

    risk_score = round(risk_score, 3)
    confidence = compute_confidence(feature_vector, sensor_conf)

    # Status
    if risk_score >= 0.75:
        status = "CRITICAL"
    elif risk_score >= 0.55:
        status = "HIGH"
    elif risk_score >= 0.35:
        status = "MODERATE"
    else:
        status = "SAFE"

    sop = SOP_MAP.get(status)

    importances = dict(zip(_feature_names, _model.feature_importances_))
    top_feature = max(importances, key=importances.get)

    return {
        "risk_score": risk_score,
        "confidence": confidence,
        "status": status,
        "top_feature": top_feature,
        "reasoning_trigger": sop,
        "signals": {
            "traffic_density": traffic["traffic_density"],
            "delay_seconds": traffic["delay_seconds"],
            "precipitation_mm": weather["precipitation_mm"],
            "visibility_km": weather["visibility_km"],
            "news_sentiment": news_sentiment,
            "time_of_day": hour,
        },
    }
