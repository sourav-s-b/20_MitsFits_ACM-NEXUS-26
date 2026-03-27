from fastapi import APIRouter
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import requests, time

from state import shipment

router = APIRouter()

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY")

if not TOMTOM_KEY:
    print("Key not loaded")

# ── 1. Inject a demo event (for the live demo trigger) ──
class Event(BaseModel):
    type: str  # "traffic_spike" | "weather_alert" | "parade"


# ── 2. Get alternative route from TomTom ──
@router.get("/reroute")
def get_reroute():
    loc = shipment["current_location"]
    dst = shipment["destination"]
    origin = f"{loc['lat']},{loc['lon']}"
    dest = f"{dst['lat']},{dst['lon']}"

    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute"
        f"/{origin}:{dest}/json"
        f"?key={TOMTOM_KEY}&traffic=true&maxAlternatives=2&travelMode=truck"
    )
    resp = requests.get(url).json()
    routes = resp.get("routes", [])
    print(f"DEBUG TOMTOM RESPONSE: {resp}")

    options = []
    for i, r in enumerate(routes[:2]):
        s = r["summary"]
        options.append({
            "id": f"route_{chr(65+i)}",
            "travel_time_min": round(s["travelTimeInSeconds"] / 60),
            "distance_km": round(s["lengthInMeters"] / 1000, 1),
            "polyline": r["legs"][0]["points"]
        })


    # recommend the faster one
    recommended = options[0]

    if len(options) >= 2:
        recommended = min(options, key=lambda x: x["travel_time_min"])
        recommended["recommended"] = True
        other = [o for o in options if o["id"] != recommended["id"]][0]
        time_saved = other["travel_time_min"] - recommended["travel_time_min"]
        recommended["reason"] = f"Saves {time_saved} min vs current route"

    if len(options) == 0:
        return {"options": [], "recommended": "No recommendation"}
    shipment["reroute_options"] = options
    return {"options": options, "recommended": recommended["id"]}


# ── helpers ──
def evaluate_risk(signals):
    risk = 0.0
    if signals["traffic_delay"] > 20: risk += 0.5
    if signals["weather_score"] > 0.6: risk += 0.4
    return min(risk, 1.0)

def classify_status(risk):
    if risk < 0.4: return "SAFE"
    if risk < 0.6: return "WARNING"
    return "HIGH RISK"


def get_traffic_incidents(lat, lon):
    url = (
        f"https://api.tomtom.com/traffic/services/5/incidentDetails"
        f"?key={TOMTOM_KEY}"
        f"&bbox={lon-0.1},{lat-0.1},{lon+0.1},{lat+0.1}"
        f"&fields={{incidents{{type,geometry{{type}},properties{{iconCategory,magnitudeOfDelay,events{{description,code}},startTime,endTime}}}}}}"
    )
    resp = requests.get(url).json()
    incidents = resp.get("incidents", [])
    if incidents:
        return incidents[0]["properties"]["events"][0]["description"]
    return None

def build_alert(event_type, risk):
    # try to get real incident description
    loc = shipment["current_location"]
    incident_desc = get_traffic_incidents(loc["lat"], loc["lon"])

    reasons = {
        "traffic_spike": incident_desc or "Heavy traffic detected on current route",
        "weather_alert": "Severe weather warning along corridor",
        "parade": "Public event blocking route — city restriction active"
    }
    return {
        "timestamp": time.strftime("%H:%M"),
        "reason": reasons.get(event_type, "Unknown disruption"),
        "risk_score": round(risk, 2),
        "severity": classify_status(risk)
    }

class RouteSelection(BaseModel):
    route_id: str  # "route_A" or "route_B"

@router.post("/confirm-reroute")
def confirm_reroute(selection: RouteSelection):
    shipment["active_route"] = selection.route_id
    shipment["status"] = "REROUTED"
    shipment["risk_score"] = 0.2  # risk drops after reroute
    shipment["alerts"].append({
        "timestamp": time.strftime("%H:%M"),
        "reason": f"Rerouted to {selection.route_id} successfully",
        "risk_score": 0.2,
        "severity": "SAFE"
    })
    return {"ok": True, "active_route": selection.route_id}

@router.post("/reset")
def reset_shipment():
    shipment["signals"] = {"traffic_delay": 5, "weather_score": 0.1}
    shipment["risk_score"] = 0.0
    shipment["status"] = "SAFE"
    shipment["active_route"] = "A"
    shipment["alerts"] = []
    shipment.pop("reroute_options", None)
    return {"ok": True, "message": "Shipment reset to initial state"}

@router.get("/state")
def get_state():
    return shipment