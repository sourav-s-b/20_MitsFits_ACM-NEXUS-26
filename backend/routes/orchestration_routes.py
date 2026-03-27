"""
orchestration_routes.py
=======================
Person 3 — Integration Orchestrator

Responsibilities:
  1. Fetch live weather from OpenWeatherMap
  2. Combine with traffic signals (from state / Person 1)
  3. Normalise everything to 0.0–1.0 features
  4. Call Person 2's /predict endpoint (with local fallback)
  5. If risk > 0.7, auto-fetch TomTom shadow route
  6. Update shared state with the full "Strategic Payload"
  7. Expose /pipeline and /simulate-storm for Person 4's UI

Endpoint contract for Person 4:
  POST /simulate-storm   → triggers full pipeline with weather=1.0
  GET  /pipeline         → runs full pipeline on current state
  GET  /weather          → current weather telemetry block
"""

from fastapi import APIRouter
from datetime import datetime, timezone
import os, time, requests
from dotenv import load_dotenv

from state import shipment

router = APIRouter()
load_dotenv()

TOMTOM_KEY      = os.getenv("TOMTOM_API_KEY")
OWM_KEY         = os.getenv("OPENWEATHER_API_KEY")
PERSON2_URL     = os.getenv("PERSON2_URL", "http://127.0.0.1:8001")

# ══════════════════════════════════════════════════════
# SECTION 1 — HELPERS
# ══════════════════════════════════════════════════════

def fetch_weather(lat: float, lon: float) -> dict:
    """
    Call OpenWeatherMap current-weather API.
    Returns a normalised weather dict.
    Falls back gracefully if key is missing or call fails.
    """
    if not OWM_KEY or OWM_KEY == "your_openweathermap_key_here":
        print("⚠️  No OWM key — using fallback weather")
        return _fallback_weather()

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric"
        )
        data = requests.get(url, timeout=6).json()

        if data.get("cod") != 200:
            print(f"⚠️  OWM error: {data.get('message')}")
            return _fallback_weather()

        rain_1h     = data.get("rain", {}).get("1h", 0.0)
        wind_speed  = data.get("wind", {}).get("speed", 0.0)   # m/s
        visibility  = data.get("visibility", 10000) / 1000      # convert m → km
        description = data["weather"][0]["description"]
        temp_c      = data["main"]["temp"]
        humidity    = data["main"]["humidity"]

        # Compute normalised weather risk score (0–1)
        rain_score  = min(rain_1h / 20.0, 1.0)                 # heavy rain ≥ 20mm/h
        wind_score  = min(wind_speed / 25.0, 1.0)              # severe ≥ 25 m/s
        vis_score   = 1.0 - min(visibility / 10.0, 1.0)        # low visibility = high risk
        score       = round((rain_score * 0.5 + wind_score * 0.3 + vis_score * 0.2), 3)

        return {
            "description":  description,
            "temp_c":       round(temp_c, 1),
            "humidity":     humidity,
            "visibility_km": round(visibility, 1),
            "wind_kph":     round(wind_speed * 3.6, 1),
            "rain_1h_mm":   rain_1h,
            "score":        score,
        }

    except Exception as e:
        print(f"⚠️  Weather fetch failed: {e}")
        return _fallback_weather()


def _fallback_weather() -> dict:
    """Synthetic clear-sky weather used when OWM is unavailable."""
    return {
        "description":   "clear sky (simulated)",
        "temp_c":        28.0,
        "humidity":      60,
        "visibility_km": 10.0,
        "wind_kph":      12.0,
        "rain_1h_mm":    0.0,
        "score":         0.05,
    }


def normalize_traffic(delay_minutes: float) -> float:
    """Map traffic_delay (0–60 min) → 0.0–1.0."""
    return round(min(delay_minutes / 60.0, 1.0), 3)


def call_person2_predict(traffic_norm: float, weather_norm: float, hour: int) -> dict:
    """
    POST to Person 2's FastAPI /predict endpoint.
    Returns {risk, level, reason}.
    Falls back to local rule-based model if Person 2 is not running.
    """
    payload = {
        "traffic": traffic_norm,
        "weather": weather_norm,
        "hour":    hour,
    }
    try:
        resp = requests.post(
            f"{PERSON2_URL}/predict",
            json=payload,
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Person 2 responded: risk={data.get('risk')}")
            return data
        else:
            print(f"⚠️  Person 2 returned {resp.status_code} — using local fallback")
    except Exception as e:
        print(f"⚠️  Person 2 unreachable ({e}) — using local risk model")

    return _local_risk_model(traffic_norm, weather_norm, hour)


def _local_risk_model(traffic: float, weather: float, hour: int) -> dict:
    """
    Rule-based fallback risk model (mirrors what Person 2 will implement).
    Used when Person 2's service is not yet running.
    """
    # Night-time penalty (22:00–05:00)
    night_penalty = 0.15 if (hour >= 22 or hour <= 5) else 0.0

    risk = (traffic * 0.5) + (weather * 0.4) + night_penalty
    risk = round(min(risk, 1.0), 3)

    if risk >= 0.75:
        level  = "CRITICAL"
        reason = _rag_lookup("CRITICAL", weather, traffic, hour)
    elif risk >= 0.5:
        level  = "HIGH"
        reason = _rag_lookup("HIGH", weather, traffic, hour)
    elif risk >= 0.3:
        level  = "MODERATE"
        reason = _rag_lookup("MODERATE", weather, traffic, hour)
    else:
        level  = "SAFE"
        reason = "All corridor conditions nominal. No action required."

    return {"risk": risk, "level": level, "reason": reason}


def _rag_lookup(level: str, weather: float, traffic: float, hour: int) -> str:
    """
    Lightweight RAG-style knowledge base.
    Returns an SOP string matching the current risk scenario.
    Mirrors the knowledge.json lookup Person 2 will implement.
    """
    knowledge = [
        {
            "condition": lambda w, t, h: w > 0.7 and (h >= 22 or h <= 5),
            "sop": "SOP-09: Night-time storm protocol active. Extreme hydroplaning risk. Mandatory reroute via NH-48 bypass.",
        },
        {
            "condition": lambda w, t, h: w > 0.7,
            "sop": "SOP-07: Severe weather on corridor. Reduce speed to 40 km/h, activate hazard lights, seek shelter if visibility < 100m.",
        },
        {
            "condition": lambda w, t, h: t > 0.7 and w < 0.4,
            "sop": "SOP-03: Heavy traffic congestion detected. Suggest alternate route via Ring Road to avoid 55-min delay.",
        },
        {
            "condition": lambda w, t, h: t > 0.5 and w > 0.5,
            "sop": "SOP-11: Combined traffic-weather risk. Driver advisory: increase following distance, reduce convoy speed.",
        },
        {
            "condition": lambda w, t, h: h >= 22 or h <= 5,
            "sop": "SOP-02: Night driving protocol. Headlight check required. Fatigue monitoring active.",
        },
        {
            "condition": lambda w, t, h: True,  # default
            "sop": f"SOP-01: Elevated {level} risk detected. Monitor corridor conditions. Standby for reroute.",
        },
    ]

    for entry in knowledge:
        if entry["condition"](weather, traffic, hour):
            return entry["sop"]

    return f"{level} risk on current route. Suggest caution."


def get_shadow_route_tomtom() -> list:
    """
    Ask TomTom for an alternative route with traffic avoidance.
    Returns a list of {lat, lon} points, or [] on failure.
    """
    loc = shipment["current_location"]
    dst = shipment["destination"]
    origin = f"{loc['lat']},{loc['lon']}"
    dest   = f"{dst['lat']},{dst['lon']}"

    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute"
            f"/{origin}:{dest}/json"
            f"?key={TOMTOM_KEY}"
            f"&traffic=true&maxAlternatives=1&travelMode=truck"
            f"&avoid=unpavedRoads"
        )
        data   = requests.get(url, timeout=10).json()
        routes = data.get("routes", [])
        if not routes:
            return []

        # Pick the first (TomTom already picked the best with avoid params)
        points = routes[0]["legs"][0]["points"]
        return [{"lat": p["latitude"], "lon": p["longitude"]} for p in points]

    except Exception as e:
        print(f"⚠️  Shadow route fetch failed: {e}")
        return []


# ══════════════════════════════════════════════════════
# SECTION 2 — PIPELINE CORE
# ══════════════════════════════════════════════════════

def run_pipeline(override_weather_score: float = None) -> dict:
    """
    The full Person 3 orchestration pipeline:
      1. Fetch live weather
      2. Normalize signals
      3. Call Person 2 /predict
      4. If CRITICAL/HIGH → fetch shadow route
      5. Update shipment state
      6. Return strategic payload for Person 4

    override_weather_score: force weather to this value (for simulate-storm)
    """
    loc  = shipment["current_location"]
    hour = datetime.now(timezone.utc).hour

    # Step 1 — Weather
    weather_data = fetch_weather(loc["lat"], loc["lon"])
    if override_weather_score is not None:
        weather_data["score"] = override_weather_score
        weather_data["description"] = "storm (simulated)"

    shipment["weather"] = weather_data

    # Also update the signals dict so the existing risk logic sees it
    if override_weather_score is not None:
        shipment["signals"]["weather_score"] = override_weather_score
    else:
        shipment["signals"]["weather_score"] = weather_data["score"]

    # Step 2 — Normalise traffic
    traffic_norm  = normalize_traffic(shipment["signals"]["traffic_delay"])
    weather_norm  = shipment["signals"]["weather_score"]

    # Step 3 — Call Person 2
    p2_result = call_person2_predict(traffic_norm, weather_norm, hour)
    risk      = p2_result["risk"]
    level     = p2_result["level"]
    reason    = p2_result["reason"]

    # Step 4 — Update shipment state
    shipment["risk_score"] = risk
    shipment["ai_reason"]  = reason
    shipment["ai_level"]   = level
    shipment["status"]     = level if level in ("CRITICAL", "HIGH") else (
        "WARNING" if level == "MODERATE" else "SAFE"
    )
    # Map level to status strings the UI already understands
    STATUS_MAP = {
        "CRITICAL": "HIGH RISK",
        "HIGH":     "HIGH RISK",
        "MODERATE": "WARNING",
        "SAFE":     "SAFE",
    }
    shipment["status"] = STATUS_MAP.get(level, "SAFE")

    # Step 5 — Shadow route if dangerous
    shadow_route = []
    if risk > 0.7:
        shadow_route = get_shadow_route_tomtom()
        if shadow_route:
            # Store as a reroute option for Person 4 to accept
            shadow_option = {
                "id":              "route_shadow",
                "travel_time_min": None,   # TomTom didn't return summary here
                "distance_km":     None,
                "polyline":        shadow_route,
                "reason":          f"AI-recommended safe corridor — {reason[:60]}…",
                "recommended":     True,
            }
            shipment["reroute_options"] = [shadow_option]
            shipment["shadow_route_ready"] = True

    # Step 6 — Append alert
    alert = {
        "timestamp":  time.strftime("%H:%M"),
        "reason":     reason,
        "risk_score": round(risk, 2),
        "severity":   shipment["status"],
        "event_type": "pipeline",
        "ai_level":   level,
    }
    shipment["alerts"].append(alert)
    shipment["pipeline_last_run"] = time.strftime("%H:%M:%S")

    # Strategic payload (what Person 4 needs)
    return {
        "ok":              True,
        "risk":            risk,
        "level":           level,
        "reason":          reason,
        "status":          shipment["status"],
        "weather":         weather_data,
        "traffic_norm":    traffic_norm,
        "weather_norm":    weather_norm,
        "shadow_route":    shadow_route,
        "shadow_ready":    bool(shadow_route),
        "pipeline_ran_at": shipment["pipeline_last_run"],
    }


# ══════════════════════════════════════════════════════
# SECTION 3 — ENDPOINTS
# ══════════════════════════════════════════════════════

@router.post("/simulate-storm")
def simulate_storm():
    """
    Demo trigger — simulates weather=1.0 and high traffic,
    runs the full pipeline.
    Person 4 should call this from the 'Simulate Storm' button.
    """
    # Force high traffic signal first
    shipment["signals"]["traffic_delay"] = 52

    result = run_pipeline(override_weather_score=1.0)
    return {
        **result,
        "triggered_by": "simulate-storm",
        "message":       "🌩 Storm simulation complete — full pipeline executed",
    }


@router.get("/pipeline")
def get_pipeline():
    """
    Run the full orchestration pipeline on current shipment state.
    Uses live weather data from OpenWeatherMap.
    Returns the complete Strategic Payload for Person 4.
    """
    return run_pipeline()


@router.get("/weather")
def get_weather():
    """
    Return current weather telemetry block.
    Useful for Person 4 to display a weather widget.
    """
    return shipment.get("weather", {})


@router.get("/ai-status")
def get_ai_status():
    """
    Return the latest Person 2 AI inference result stored in state.
    For Person 4 to display the AI Reason sidebar.
    """
    return {
        "ai_reason":  shipment.get("ai_reason"),
        "ai_level":   shipment.get("ai_level"),
        "risk_score": shipment.get("risk_score"),
        "status":     shipment.get("status"),
        "last_run":   shipment.get("pipeline_last_run"),
    }
