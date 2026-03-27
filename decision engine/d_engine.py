from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import requests, time

app = FastAPI()

load_dotenv('../.env',override=True)
TOMTOM_KEY = os.getenv("TOMTOM_API_KEY")

# ── shared state (Person 1 writes this, you read + update it) ──
shipment = {
    "shipment_id": "SHP001",
    "current_location": {"lat": 9.9312, "lon": 76.2673},
    "destination": {"lat": 12.9716, "lon": 77.5946},
    "signals": {"traffic_delay": 5, "weather_score": 0.1},
    "risk_score": 0.0,
    "status": "SAFE",
    "active_route": "A",
    "alerts": []
}

# ── 1. Inject a demo event (for the live demo trigger) ──
class Event(BaseModel):
    type: str  # "traffic_spike" | "weather_alert" | "parade"

@app.post("/event")
def inject_event(event: Event):
    if event.type == "traffic_spike":
        shipment["signals"]["traffic_delay"] = 45
    elif event.type == "weather_alert":
        shipment["signals"]["weather_score"] = 0.85
    elif event.type == "parade":
        shipment["signals"]["traffic_delay"] = 60
        shipment["signals"]["weather_score"] = 0.2

    # re-evaluate risk after injection
    risk = evaluate_risk(shipment["signals"])
    shipment["risk_score"] = risk
    shipment["status"] = classify_status(risk)

    if risk > 0.6:
        alert = build_alert(event.type, risk)
        shipment["alerts"].append(alert)

    return {"ok": True, "risk_score": risk, "status": shipment["status"]}


# ── 2. Get alternative route from TomTom ──
@app.get("/reroute")
def get_reroute():
    loc = shipment["current_location"]
    dst = shipment["destination"]
    origin = f"{loc['lat']},{loc['lon']}" # Try this first
    dest   = f"{dst['lat']},{dst['lon']}"

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
            "id": f"route_{chr(65+i)}",   # "route_A", "route_B"
            "travel_time_min": round(s["travelTimeInSeconds"] / 60),
            "distance_km": round(s["lengthInMeters"] / 1000, 1),
            "polyline": r["legs"][0]["points"]  # send to frontend for map
        })

    shipment["reroute_options"] = options
    return {"options": options}

@app.get("/state")
def get_state():
    return shipment

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

def build_alert(event_type, risk):
    reasons = {
        "traffic_spike": "Heavy traffic detected on current route",
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

@app.post("/confirm-reroute")
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