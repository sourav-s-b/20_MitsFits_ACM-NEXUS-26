"""
orchestration_routes.py
=======================
Person 3 — Integration Orchestrator
Now supports multi-tenancy and async BackgroundTasks.
"""

from fastapi import APIRouter, BackgroundTasks
from datetime import datetime, timezone
import os, time, requests
from dotenv import load_dotenv

from live_store import get_shipment, set_shipment
from database import log_audit_event

router = APIRouter()
load_dotenv()

TOMTOM_KEY      = os.getenv("TOMTOM_API_KEY")
OWM_KEY         = os.getenv("OPENWEATHER_API_KEY")
PERSON2_URL     = os.getenv("PERSON2_URL", "http://127.0.0.1:8001")

# ══════════════════════════════════════════════════════
# SECTION 1 — HELPERS
# ══════════════════════════════════════════════════════

def fetch_weather(lat: float, lon: float) -> dict:
    if not OWM_KEY or OWM_KEY == "your_openweathermap_key_here":
        return _fallback_weather()
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric"
        )
        data = requests.get(url, timeout=6).json()
        if data.get("cod") != 200:
            return _fallback_weather()

        rain_1h     = data.get("rain", {}).get("1h", 0.0)
        wind_speed  = data.get("wind", {}).get("speed", 0.0)
        visibility  = data.get("visibility", 10000) / 1000
        description = data["weather"][0]["description"]
        temp_c      = data["main"]["temp"]
        humidity    = data["main"]["humidity"]

        rain_score  = min(rain_1h / 20.0, 1.0)
        wind_score  = min(wind_speed / 25.0, 1.0)
        vis_score   = 1.0 - min(visibility / 10.0, 1.0)
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
        return _fallback_weather()

def _fallback_weather() -> dict:
    return {
        "description":   "clear sky (simulated)",
        "temp_c":        28.0,
        "humidity":      60,
        "visibility_km": 10.0,
        "wind_kph":      12.0,
        "rain_1h_mm":    0.0,
        "score":         0.05,
    }

def fetch_tomtom_traffic(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> float:
    if not TOMTOM_KEY or TOMTOM_KEY == "your_tomtom_key_here":
        return 0.0
    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute"
            f"/{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
            f"?key={TOMTOM_KEY}&travelMode=truck&traffic=true"
        )
        data = requests.get(url, timeout=6).json()
        if "routes" not in data or not data["routes"]:
            return 0.0
        summary = data["routes"][0].get("summary", {})
        delay_seconds = summary.get("trafficDelayInSeconds", 0)
        return round(delay_seconds / 60.0, 1)
    except Exception as e:
        return 0.0

def normalize_traffic(delay_minutes: float) -> float:
    return round(min(delay_minutes / 60.0, 1.0), 3)

def call_person2(shipment_id: str, lat: float, lon: float) -> dict:
    shipment = get_shipment(shipment_id)
    try:
        risk_resp = requests.get(
            f"{PERSON2_URL}/risk",
            params={"lat": lat, "lon": lon},
            timeout=5,
        )
        if risk_resp.status_code != 200:
            raise ValueError(f"Person 2 /risk returned {risk_resp.status_code}")

        p2 = risk_resp.json()
        risk   = p2["risk_score"]
        status = p2["status"]

        shipment["signals"]["traffic_delay"] = p2.get("traffic_delay", shipment["signals"]["traffic_delay"])
        shipment["signals"]["weather_score"]  = p2.get("weather_score",  shipment["signals"]["weather_score"])
        set_shipment(shipment_id, shipment)

        reason = _fetch_sop_reason(status, p2.get("weather_score", 0), shipment)
        level = {"HIGH RISK": "CRITICAL", "MODERATE": "MODERATE", "SAFE": "SAFE"}.get(status, "SAFE")

        return {"risk": risk, "level": level, "reason": reason, "source": "person2"}
    except Exception as e:
        hour = datetime.now(timezone.utc).hour
        traffic_norm = normalize_traffic(shipment["signals"]["traffic_delay"])
        weather_norm = shipment["signals"]["weather_score"]
        return _local_risk_model(traffic_norm, weather_norm, hour)

def _fetch_sop_reason(status: str, weather_score: float, shipment: dict) -> str:
    try:
        resp = requests.get(
            f"{PERSON2_URL}/sop",
            params={"status": status},
            timeout=3,
        )
        if resp.status_code == 200:
            recs = resp.json().get("recommendations", [])
            if recs:
                sop = recs[0]
                return f"{sop['id']}: {sop['action']} [{sop['source']}]"
    except Exception as e:
        pass
    hour = datetime.now(timezone.utc).hour
    traffic_norm = normalize_traffic(shipment["signals"]["traffic_delay"])
    return _rag_lookup(status, weather_score, traffic_norm, hour)

def _local_risk_model(traffic: float, weather: float, hour: int) -> dict:
    time_risk = 0.15 if (hour >= 22 or hour <= 5) else (0.3 if (8 <= hour <= 10 or 17 <= hour <= 20) else 0.0)
    risk = round(min((traffic * 0.5) + (weather * 0.35) + (time_risk * 0.15), 1.0), 3)

    if risk >= 0.65:   level = "CRITICAL"
    elif risk >= 0.35: level = "MODERATE"
    else:              level = "SAFE"

    reason = _rag_lookup(level, weather, traffic, hour)
    return {"risk": risk, "level": level, "reason": reason, "source": "local_fallback"}

def _rag_lookup(level: str, weather: float, traffic: float, hour: int) -> str:
    if weather > 0.7 and (hour >= 22 or hour <= 5):
        return "SOP-09: Night-time storm protocol active. Extreme hydroplaning risk. Mandatory reroute via NH-48 bypass."
    if weather > 0.7:
        return "SOP-07: Severe weather on corridor. Reduce speed 40 km/h, hazard lights on, seek shelter if vis < 100m."
    if traffic > 0.7:
        return "SOP-001: Switch to Route B via NH-66. Notify warehouse coordinator. [Logistics SOP v2.3]"
    if level in ("MODERATE", "CRITICAL"):
        return "SOP-002: Monitor for next 10 min. Pre-alert destination hub. [Logistics SOP v2.3]"
    return "SOP-001: All corridor conditions nominal. Monitoring active."

def get_shadow_route_tomtom(shipment_id: str) -> list:
    shipment = get_shipment(shipment_id)
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
        points = routes[0]["legs"][0]["points"]
        return [{"lat": p["latitude"], "lon": p["longitude"]} for p in points]
    except Exception as e:
        return []

# ══════════════════════════════════════════════════════
# SECTION 2 — PIPELINE CORE
# ══════════════════════════════════════════════════════

def run_pipeline(shipment_id: str, override_weather_score: float = None):
    shipment = get_shipment(shipment_id)
    loc  = shipment["current_location"]
    hour = datetime.now(timezone.utc).hour

    weather_data = fetch_weather(loc["lat"], loc["lon"])
    if override_weather_score is not None:
        weather_data["score"] = override_weather_score
        weather_data["description"] = "storm (simulated)"

    shipment["weather"] = weather_data
    if override_weather_score is not None:
        shipment["signals"]["weather_score"] = override_weather_score
    else:
        shipment["signals"]["weather_score"] = weather_data["score"]

    traffic_norm  = normalize_traffic(shipment["signals"]["traffic_delay"])
    weather_norm  = shipment["signals"]["weather_score"]

    set_shipment(shipment_id, shipment)

    p2_result = call_person2(shipment_id, loc["lat"], loc["lon"])
    shipment = get_shipment(shipment_id) # reload if modified
    
    risk      = p2_result["risk"]
    level     = p2_result["level"]
    reason    = p2_result["reason"]

    shipment["risk_score"] = risk
    shipment["ai_reason"]  = reason
    shipment["ai_level"]   = level
    STATUS_MAP = {"CRITICAL": "HIGH RISK", "HIGH": "HIGH RISK", "MODERATE": "WARNING", "SAFE": "SAFE"}
    shipment["status"] = STATUS_MAP.get(level, "SAFE")

    shadow_route = []
    if risk > 0.7:
        shadow_route = get_shadow_route_tomtom(shipment_id)
        if shadow_route:
            shadow_option = {
                "id":              "route_shadow",
                "travel_time_min": None,
                "distance_km":     None,
                "polyline":        shadow_route,
                "reason":          f"AI-recommended safe corridor — {reason[:60]}…",
                "recommended":     True,
            }
            shipment["reroute_options"] = [shadow_option]
            shipment["shadow_route_ready"] = True

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

    set_shipment(shipment_id, shipment)
    log_audit_event(shipment_id, time.strftime("%H:%M"), "pipeline_run", risk, reason)


# ══════════════════════════════════════════════════════
# SECTION 3 — ENDPOINTS
# ══════════════════════════════════════════════════════

@router.post("/shipments/{shipment_id}/simulate-storm")
def simulate_storm(shipment_id: str, background_tasks: BackgroundTasks):
    shipment = get_shipment(shipment_id)
    shipment["signals"]["traffic_delay"] = 52
    set_shipment(shipment_id, shipment)

    # Offload the heavy pipeline processing to a background task
    background_tasks.add_task(run_pipeline, shipment_id, 1.0)
    
    return {
        "status": "processing",
        "triggered_by": "simulate-storm",
        "message": "🌩 Storm simulation started in background",
    }

@router.get("/shipments/{shipment_id}/pipeline")
def get_pipeline(shipment_id: str, background_tasks: BackgroundTasks):
    # Offload standard polling run to background task
    background_tasks.add_task(run_pipeline, shipment_id)
    return {
        "status": "processing",
        "message": "Pipeline queued in background",
    }

@router.get("/shipments/{shipment_id}/weather")
def get_weather(shipment_id: str):
    return get_shipment(shipment_id).get("weather", {})

@router.get("/shipments/{shipment_id}/ai-status")
def get_ai_status(shipment_id: str):
    shipment = get_shipment(shipment_id)
    return {
        "ai_reason":  shipment.get("ai_reason"),
        "ai_level":   shipment.get("ai_level"),
        "risk_score": shipment.get("risk_score"),
        "status":     shipment.get("status"),
        "last_run":   shipment.get("pipeline_last_run"),
    }
