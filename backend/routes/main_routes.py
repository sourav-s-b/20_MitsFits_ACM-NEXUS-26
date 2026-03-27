from fastapi import APIRouter
import requests
import os
from dotenv import load_dotenv

from state import shipment

router = APIRouter()

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

if not TOMTOM_API_KEY:
    raise ValueError("❌ TOMTOM_API_KEY not found in .env file")

# =========================
# ROUTE FETCHING FUNCTION
# =========================
def get_route(origin, destination):
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute"
        f"/{origin}:{destination}/json"
        f"?key={TOMTOM_API_KEY}&travelMode=truck"
    )

    try:
        res = requests.get(url, timeout=10)

        if res.status_code != 200:
            print("❌ API Error:", res.text)
            return []

        data   = res.json()
        points = data["routes"][0]["legs"][0]["points"]
        route  = [{"lat": p["latitude"], "lon": p["longitude"]} for p in points]
        return route

    except Exception as e:
        print("❌ Exception in get_route:", e)
        return []


# =========================
# START SHIPMENT
# =========================
@router.post("/start")
def start_shipment():
    origin      = "9.9312,76.2673"
    destination = "12.9716,77.5946"

    route = get_route(origin, destination)

    if not route:
        return {"error": "Route not found. Check API key or coordinates."}

    shipment["route"]            = route
    shipment["route_index"]      = 0
    shipment["current_location"] = route[0]
    shipment["status"]           = "SAFE"
    shipment["risk_score"]       = 0.0
    shipment["alerts"]           = []
    shipment["reroute_options"]  = []

    return {
        "message":      "✅ Shipment started",
        "total_points": len(route)
    }


# =========================
# SIMULATE TRAFFIC SPIKE (simple helper)
# =========================
@router.post("/traffic")
def traffic_spike():
    """Quick signal-only nudge — use POST /event for the full demo trigger."""
    shipment["signals"]["traffic_delay"] = 60
    return {"message": "Traffic spike signal set"}