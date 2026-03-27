"""
orchestration_routes.py
=======================
Person 3 — Integration Orchestrator
Now supports multi-tenancy and async BackgroundTasks.
"""

from fastapi import APIRouter, BackgroundTasks
from datetime import datetime, timezone
import os
import httpx
import time
from dotenv import load_dotenv

from live_store import get_shipment, set_shipment
from database import log_audit_event

router = APIRouter()
load_dotenv()

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY")
OWM_KEY = os.getenv("OPENWEATHER_API_KEY")
PERSON2_URL = os.getenv("PERSON2_URL", "http://127.0.0.1:8001")

# ══════════════════════════════════════════════════════
# SECTION 1 — HELPERS
# ══════════════════════════════════════════════════════


async def fetch_weather(lat: float, lon: float) -> dict:
    if not OWM_KEY or OWM_KEY == "your_openweathermap_key_here":
        return _fallback_weather()
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
            data = resp.json()

        if data.get("cod") != 200:
            return _fallback_weather()

        rain_1h = data.get("rain", {}).get("1h", 0.0)
        wind_speed = data.get("wind", {}).get("speed", 0.0)
        visibility = data.get("visibility", 10000) / 1000
        description = data["weather"][0]["description"]
        temp_c = data["main"]["temp"]
        humidity = data["main"]["humidity"]

        rain_score = min(rain_1h / 20.0, 1.0)
        wind_score = min(wind_speed / 25.0, 1.0)
        vis_score = 1.0 - min(visibility / 10.0, 1.0)
        score = round((rain_score * 0.5 + wind_score * 0.3 + vis_score * 0.2), 3)

        return {
            "description": description,
            "temp_c": round(temp_c, 1),
            "humidity": humidity,
            "visibility_km": round(visibility, 1),
            "wind_kph": round(wind_speed * 3.6, 1),
            "rain_1h_mm": rain_1h,
            "score": score,
        }
    except Exception:
        return _fallback_weather()


def _fallback_weather() -> dict:
    return {
        "description": "clear sky (simulated)",
        "temp_c": 28.0,
        "humidity": 60,
        "visibility_km": 10.0,
        "wind_kph": 12.0,
        "rain_1h_mm": 0.0,
        "score": 0.05,
    }


async def fetch_tomtom_traffic(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> float:
    if not TOMTOM_KEY or TOMTOM_KEY == "your_tomtom_key_here":
        return 0.0
    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute"
            f"/{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
            f"?key={TOMTOM_KEY}&travelMode=truck&traffic=true"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
            data = resp.json()

        if "routes" not in data or not data["routes"]:
            return 0.0
        summary = data["routes"][0].get("summary", {})
        delay_seconds = summary.get("trafficDelayInSeconds", 0)
        return round(delay_seconds / 60.0, 1)
    except Exception:
        return 0.0


def normalize_traffic(delay_minutes: float) -> float:
    return round(min(delay_minutes / 60.0, 1.0), 3)


def call_person2(shipment_id: str, lat: float, lon: float) -> dict:
    shipment = get_shipment(shipment_id)
    hour = datetime.now(timezone.utc).hour
    traffic_norm = normalize_traffic(shipment["signals"]["traffic_delay"])
    weather_norm = shipment["signals"]["weather_score"]
    return _local_risk_model(traffic_norm, weather_norm, hour)


def _fetch_sop_reason(status: str, weather_score: float, shipment: dict) -> str:
    hour = datetime.now(timezone.utc).hour
    traffic_norm = normalize_traffic(shipment["signals"]["traffic_delay"])
    return _rag_lookup(status, weather_score, traffic_norm, hour)


def _local_risk_model(traffic: float, weather: float, hour: int) -> dict:
    # 1. Temporal Intelligence: Night-time multiplier (22:00 - 05:00)
    is_night = (hour >= 22 or hour <= 5)
    time_multiplier = 1.3 if is_night else 1.0
    
    # 2. Multimodal Risk Fusion (Compound Hazards)
    # 80% traffic + 80% rain is ~4x more dangerous than either alone
    base_risk = (traffic * 0.5) + (weather * 0.5)
    compound_factor = 2.0 if (traffic > 0.7 and weather > 0.7) else 1.0
    
    risk = round(min(base_risk * compound_factor * time_multiplier, 1.0), 3)

    if risk >= 0.7:
        level = "CRITICAL"
    elif risk >= 0.4:
        level = "HIGH"
    elif risk >= 0.2:
        level = "MODERATE"
    else:
        level = "SAFE"

    reason = _rag_lookup(level, weather, traffic, hour)
    return {
        "risk": risk,
        "level": level,
        "reason": reason,
        "source": "Nexus-Brain Core",
        "is_compound": (compound_factor > 1.0),
        "is_night": is_night
    }


def _rag_lookup(level: str, weather: float, traffic: float, hour: int, event_type: str = None) -> str:
    # Event-specific SOPs
    if event_type == "accident":
        return "SOP-ACCIDENT: Major collision reported ahead. Multiple lanes blocked. Immediate diversion required."
    elif event_type == "parade":
        return "SOP-PARADE: Local festival crowd causing massive congestion. Rerouting to bypass."
    elif event_type == "roadblock":
        return "SOP-ROADBLOCK: Local roadblock/checkpoint detected. Standstill traffic. Alternative route activated."
    elif event_type == "construction":
        return "SOP-CONSTRUCT: Unplanned heavy roadwork ahead. Lanes closed. Proceed via alternate route."

    # Night-time / Storm (SOP-Alpha)
    if weather > 0.7 and (hour >= 22 or hour <= 5):
        return "SOP-ALPHA: Night-time storm protocol active. Extreme hydroplaning risk + reduced visibility. Mandatory reroute suggested to maintain shipment integrity."
    if weather > 0.7:
        return "SOP-07: Severe precipitation on corridor. Reduce speed 40 km/h, hazard lights on, seek shelter if vis < 100m."
    if traffic > 0.7 and weather > 0.7:
        return "SOP-BRAVO: Compound hazard (High Traffic + Storm). Estimated 4x safety impact. Immediate course correction required."
    if traffic > 0.7:
        return "SOP-001: Heavy congestion on primary route. Switch to Route B via NH-66 to avoid 40+ min delay."
    if level == "CRITICAL":
        return "SOP-DELTA: Risk threshold exceeded. Execute emergency avoidance maneuver and alert delivery hub."
    return "SOP-001: All corridor conditions nominal. Continuous AI monitoring active."

async def get_reroute_options_tomtom(shipment_id: str) -> list:
    shipment = get_shipment(shipment_id)
    loc = shipment["current_location"]
    dst = shipment["destination"]
    origin = f"{loc['lat']},{loc['lon']}"
    dest = f"{dst['lat']},{dst['lon']}"
    if not loc or not dest:
        return []
    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute"
            f"/{origin}:{dest}/json"
            f"?key={TOMTOM_KEY}"
            f"&traffic=true&maxAlternatives=3&travelMode=truck"
            f"&alternativeType=anyRoute&minDeviationDistance=1000"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            data = resp.json()

        routes = data.get("routes", [])
        if not routes:
            fallback_url = (
                f"https://api.tomtom.com/routing/1/calculateRoute"
                f"/{origin}:{dest}/json"
                f"?key={TOMTOM_KEY}&traffic=true&travelMode=truck"
            )
            async with httpx.AsyncClient() as client:
                resp = await client.get(fallback_url, timeout=10.0)
                data = resp.json()
            routes = data.get("routes", [])

        if not routes:
            return []

        options = []
        for i, r in enumerate(routes[:3]):
            s = r["summary"]
            options.append(
                {
                    "id": f"route_{chr(65 + i)}",
                    "travel_time_min": round(s["travelTimeInSeconds"] / 60),
                    "distance_km": round(s["lengthInMeters"] / 1000, 1),
                    "polyline": [
                        {"lat": p["latitude"], "lon": p["longitude"]}
                        for p in r["legs"][0]["points"]
                    ],
                    "recommended": (i == 1) if len(routes) > 1 else True,
                    "reason": "AI-recommended reroute"
                    if i == 1
                    else "Current traffic loaded route",
                }
            )
        return options
    except Exception:
        return []


# ══════════════════════════════════════════════════════
# SECTION 2 — PIPELINE CORE
# ══════════════════════════════════════════════════════


async def run_pipeline(shipment_id: str, override_weather_score: float = None, event_type: str = None):
    shipment = get_shipment(shipment_id)
    loc = shipment["current_location"]

    weather_data = await fetch_weather(loc["lat"], loc["lon"])
    if override_weather_score is not None:
        weather_data["score"] = override_weather_score
        weather_data["description"] = "storm (simulated)"

    shipment["weather"] = weather_data
    if override_weather_score is not None:
        shipment["signals"]["weather_score"] = override_weather_score
    else:
        shipment["signals"]["weather_score"] = weather_data["score"]


    set_shipment(shipment_id, shipment)

    p2_result = call_person2(shipment_id, loc["lat"], loc["lon"])
    shipment = get_shipment(shipment_id)  # reload if modified

    risk = p2_result["risk"]
    level = p2_result["level"]
    reason = p2_result["reason"]

    if event_type:
        risk = max(risk, 0.85)
        level = "CRITICAL"
        reason = _rag_lookup(
            level=level, 
            weather=shipment["signals"]["weather_score"], 
            traffic=0.9, 
            hour=12, 
            event_type=event_type
        )

    shipment["risk_score"] = risk
    shipment["ai_reason"] = reason
    shipment["ai_level"] = level
    STATUS_MAP = {
        "CRITICAL": "HIGH RISK",
        "HIGH": "HIGH RISK",
        "MODERATE": "WARNING",
        "SAFE": "SAFE",
    }
    shipment["status"] = STATUS_MAP.get(level, "SAFE")

    shadow_route_options = []
    if risk > 0.7:
        shadow_route_options = await get_reroute_options_tomtom(shipment_id)
        if shadow_route_options:
            shipment["reroute_options"] = shadow_route_options
            shipment["shadow_route_ready"] = True

    alert = {
        "timestamp": time.strftime("%H:%M"),
        "reason": reason,
        "risk_score": round(risk, 2),
        "severity": shipment["status"],
        "event_type": "pipeline",
        "ai_level": level,
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


def _trigger_event(shipment_id: str, event_type: str, background_tasks: BackgroundTasks):
    shipment = get_shipment(shipment_id)
    shipment["signals"]["traffic_delay"] = 120  # Force severe delay
    set_shipment(shipment_id, shipment)
    background_tasks.add_task(run_pipeline, shipment_id, None, event_type)
    return {"status": "processing", "message": f"{event_type.title()} simulation started"}


@router.post("/shipments/{shipment_id}/simulate-accident")
def simulate_accident(shipment_id: str, background_tasks: BackgroundTasks):
    return _trigger_event(shipment_id, "accident", background_tasks)

@router.post("/shipments/{shipment_id}/simulate-parade")
def simulate_parade(shipment_id: str, background_tasks: BackgroundTasks):
    return _trigger_event(shipment_id, "parade", background_tasks)

@router.post("/shipments/{shipment_id}/simulate-roadblock")
def simulate_roadblock(shipment_id: str, background_tasks: BackgroundTasks):
    return _trigger_event(shipment_id, "roadblock", background_tasks)

@router.post("/shipments/{shipment_id}/simulate-construction")
def simulate_construction(shipment_id: str, background_tasks: BackgroundTasks):
    return _trigger_event(shipment_id, "construction", background_tasks)


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
        "ai_reason": shipment.get("ai_reason"),
        "ai_level": shipment.get("ai_level"),
        "risk_score": shipment.get("risk_score"),
        "status": shipment.get("status"),
        "last_run": shipment.get("pipeline_last_run"),
    }
