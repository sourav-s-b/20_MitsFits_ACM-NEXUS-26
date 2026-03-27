"""
orchestration_routes.py
=======================
Person 3 — Integration Orchestrator

Person 2 API contract (risk-engine running on :8001):
  GET  /risk?lat=&lon=   → {traffic_delay, weather_score, time_risk, risk_score, status}
  GET  /sop?status=      → {recommendations: [{id, trigger, action, source}]}
  POST /event            → inject {type: traffic_spike|storm|clear}
  GET  /health           → {status: running}

Person 2 status values: "SAFE" | "MODERATE" | "HIGH RISK"

Endpoint contract for Person 4:
  POST /simulate-storm   → triggers full pipeline with weather=1.0
  GET  /pipeline         → runs full pipeline on current live state
  GET  /weather          → current weather telemetry block
  GET  /ai-status        → latest AI inference result
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


def call_person2(lat: float, lon: float) -> dict:
    """
    Call Person 2's risk engine at GET /risk?lat=&lon=.
    Person 2's response shape:
      {traffic_delay, weather_score, time_risk, risk_score, status}
    where status ∈ {"SAFE", "MODERATE", "HIGH RISK"}

    Also queries GET /sop?status= to get the RAG action string.
    Falls back to local model if Person 2 is not running.
    """
    try:
        # 1. Get risk score from Person 2
        risk_resp = requests.get(
            f"{PERSON2_URL}/risk",
            params={"lat": lat, "lon": lon},
            timeout=5,
        )
        if risk_resp.status_code != 200:
            raise ValueError(f"Person 2 /risk returned {risk_resp.status_code}")

        p2 = risk_resp.json()
        risk   = p2["risk_score"]
        status = p2["status"]       # "SAFE" | "MODERATE" | "HIGH RISK"
        print(f"✅ Person 2 /risk → risk={risk}, status={status}")

        # 2. Sync Person 2's traffic/weather back into our signals
        shipment["signals"]["traffic_delay"] = p2.get("traffic_delay", shipment["signals"]["traffic_delay"])
        shipment["signals"]["weather_score"]  = p2.get("weather_score",  shipment["signals"]["weather_score"])

        # 3. Fetch SOP reason from Person 2's RAG endpoint
        reason = _fetch_sop_reason(status, p2.get("weather_score", 0))

        # 4. Map Person 2 status → our level labels
        level = {"HIGH RISK": "CRITICAL", "MODERATE": "MODERATE", "SAFE": "SAFE"}.get(status, "SAFE")

        return {"risk": risk, "level": level, "reason": reason, "source": "person2"}

    except Exception as e:
        print(f"⚠️  Person 2 unreachable ({e}) — using local fallback")
        hour = datetime.now(timezone.utc).hour
        traffic_norm = normalize_traffic(shipment["signals"]["traffic_delay"])
        weather_norm = shipment["signals"]["weather_score"]
        return _local_risk_model(traffic_norm, weather_norm, hour)


def _fetch_sop_reason(status: str, weather_score: float) -> str:
    """
    Call Person 2's GET /sop?status= to get the RAG action text.
    Falls back to local knowledge base on failure.
    """
    try:
        resp = requests.get(
            f"{PERSON2_URL}/sop",
            params={"status": status},
            timeout=3,
        )
        if resp.status_code == 200:
            recs = resp.json().get("recommendations", [])
            if recs:
                # Return the most relevant SOP action
                sop = recs[0]
                return f"{sop['id']}: {sop['action']} [{sop['source']}]"
    except Exception as e:
        print(f"⚠️  /sop fetch failed: {e}")

    # Local RAG fallback using our own knowledge base
    hour = datetime.now(timezone.utc).hour
    traffic_norm = normalize_traffic(shipment["signals"]["traffic_delay"])
    return _rag_lookup(status, weather_score, traffic_norm, hour)


def _local_risk_model(traffic: float, weather: float, hour: int) -> dict:
    """
    Rule-based fallback — used when Person 2's service is not running.
    Mirrors Person 2's weighted formula: traffic*0.5 + weather*0.35 + time*0.15
    """
    time_risk = 0.15 if (hour >= 22 or hour <= 5) else (0.3 if (8 <= hour <= 10 or 17 <= hour <= 20) else 0.0)
    risk = round(min((traffic * 0.5) + (weather * 0.35) + (time_risk * 0.15), 1.0), 3)

    if risk >= 0.65:   level = "CRITICAL"
    elif risk >= 0.35: level = "MODERATE"
    else:              level = "SAFE"

    reason = _rag_lookup(level, weather, traffic, hour)
    return {"risk": risk, "level": level, "reason": reason, "source": "local_fallback"}


def _rag_lookup(level: str, weather: float, traffic: float, hour: int) -> str:
    """
    Local knowledge base — mirrors Person 2's knowledge.json.
    Returns the most relevant SOP string for the current conditions.
    """
    if weather > 0.7 and (hour >= 22 or hour <= 5):
        return "SOP-09: Night-time storm protocol active. Extreme hydroplaning risk. Mandatory reroute via NH-48 bypass."
    if weather > 0.7:
        return "SOP-07: Severe weather on corridor. Reduce speed 40 km/h, hazard lights on, seek shelter if vis < 100m."
    if traffic > 0.7:
        return "SOP-001: Switch to Route B via NH-66. Notify warehouse coordinator. [Logistics SOP v2.3]"
    if level in ("MODERATE", "CRITICAL"):
        return "SOP-002: Monitor for next 10 min. Pre-alert destination hub. [Logistics SOP v2.3]"
    return "SOP-001: All corridor conditions nominal. Monitoring active."


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

    # Step 2 — Normalise traffic (used by local fallback)
    traffic_norm  = normalize_traffic(shipment["signals"]["traffic_delay"])
    weather_norm  = shipment["signals"]["weather_score"]

    # Step 3 — Call Person 2's risk engine
    p2_result = call_person2(loc["lat"], loc["lon"])
    risk      = p2_result["risk"]
    level     = p2_result["level"]
    reason    = p2_result["reason"]
    print(f"Pipeline source: {p2_result.get('source', 'unknown')}")

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
