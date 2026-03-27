from fastapi import APIRouter
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import requests
import time

from live_store import get_shipment, set_shipment
from database import save_shipment, log_audit_event

router = APIRouter()

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY")

if not TOMTOM_KEY:
    print("⚠️  TOMTOM_API_KEY not loaded — check your .env file")


# ── Models ──
class Event(BaseModel):
    type: str  # "traffic_spike" | "weather_alert" | "parade"

class RouteSelection(BaseModel):
    route_id: str  # "route_A" | "route_B"


# ── Helpers ──
def evaluate_risk(signals: dict) -> float:
    risk = 0.0
    if signals.get("traffic_delay", 0) > 20:
        risk += 0.5
    if signals.get("weather_score", 0) > 0.6:
        risk += 0.4
    return min(risk, 1.0)


def classify_status(risk: float) -> str:
    if risk < 0.4:
        return "SAFE"
    if risk < 0.6:
        return "WARNING"
    return "HIGH RISK"


def get_traffic_incidents(lat: float, lon: float):
    """Try to fetch a live TomTom incident description near the truck."""
    try:
        url = (
            f"https://api.tomtom.com/traffic/services/5/incidentDetails"
            f"?key={TOMTOM_KEY}"
            f"&bbox={lon-0.1},{lat-0.1},{lon+0.1},{lat+0.1}"
            f"&fields={{incidents{{type,geometry{{type}},properties{{iconCategory,magnitudeOfDelay,"
            f"events{{description,code}},startTime,endTime}}}}}}"
        )
        resp = requests.get(url, timeout=5).json()
        incidents = resp.get("incidents", [])
        if incidents:
            return incidents[0]["properties"]["events"][0]["description"]
    except Exception as e:
        print(f"⚠️  Traffic incidents fetch failed: {e}")
    return None


def build_alert(shipment_id: str, event_type: str, risk: float, shipment: dict) -> dict:
    loc = shipment["current_location"]
    incident_desc = get_traffic_incidents(loc["lat"], loc["lon"])

    reasons = {
        "traffic_spike": incident_desc or "Heavy traffic detected on current route",
        "weather_alert": "Severe weather warning along corridor — hydroplaning risk",
        "parade":        "Public event blocking route — city restriction active",
    }
    reason = reasons.get(event_type, "Unknown disruption")

    # Audit log
    log_audit_event(shipment_id, time.strftime("%H:%M"), event_type, risk, reason)

    return {
        "timestamp": time.strftime("%H:%M"),
        "reason":    reason,
        "risk_score": round(risk, 2),
        "severity":  classify_status(risk),
        "event_type": event_type,
    }


# ══════════════════════════════════════════
# POST /event  —  Inject a demo risk event
# ══════════════════════════════════════════
@router.post("/shipments/{shipment_id}/event")
def trigger_event(shipment_id: str, event: Event):
    """
    Inject a named disruption event.
    Mutates shipment signals, recomputes risk, and appends an alert.
    """
    shipment = get_shipment(shipment_id)
    etype = event.type

    # 1. Mutate signals based on event type
    if etype == "traffic_spike":
        shipment["signals"]["traffic_delay"] = 55
        shipment["signals"]["weather_score"] = 0.2

    elif etype == "weather_alert":
        shipment["signals"]["traffic_delay"] = 10
        shipment["signals"]["weather_score"] = 0.95

    elif etype == "parade":
        shipment["signals"]["traffic_delay"] = 45
        shipment["signals"]["weather_score"] = 0.1

    else:
        # Generic high-risk fallback
        shipment["signals"]["traffic_delay"] = 50
        shipment["signals"]["weather_score"] = 0.85

    # 2. Recompute risk
    risk = evaluate_risk(shipment["signals"])
    shipment["risk_score"] = risk
    shipment["status"] = classify_status(risk)

    # 3. Build and store alert
    alert = build_alert(shipment_id, etype, risk, shipment)
    shipment["alerts"].append(alert)

    set_shipment(shipment_id, shipment)
    save_shipment(shipment)

    return {
        "ok": True,
        "event_type": etype,
        "risk_score": risk,
        "status": shipment["status"],
        "alert": alert,
    }


# ══════════════════════════════════════════
# GET /reroute  —  Fetch alternate routes
# ══════════════════════════════════════════
@router.get("/shipments/{shipment_id}/reroute")
def get_reroute(shipment_id: str):
    """
    Call TomTom Routing API and return up to 2 alternative route options.
    Gracefully returns empty list if TomTom finds nothing.
    """
    shipment = get_shipment(shipment_id)
    loc = shipment["current_location"]
    dst = shipment["destination"]
    origin = f"{loc['lat']},{loc['lon']}"
    dest   = f"{dst['lat']},{dst['lon']}"

    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute"
            f"/{origin}:{dest}/json"
            f"?key={TOMTOM_KEY}&traffic=true&maxAlternatives=2&travelMode=truck"
        )
        resp   = requests.get(url, timeout=10).json()
        routes = resp.get("routes", [])
        print(f"DEBUG TomTom /reroute — got {len(routes)} route(s)")
    except Exception as e:
        print(f"⚠️  TomTom routing call failed: {e}")
        return {"options": [], "recommended": None, "error": str(e)}

    # ── SAFE build: check empty BEFORE indexing ──
    if len(routes) == 0:
        return {"options": [], "recommended": None}

    options = []
    for i, r in enumerate(routes[:2]):
        s = r["summary"]
        options.append({
            "id":              f"route_{chr(65 + i)}",   # route_A, route_B
            "travel_time_min": round(s["travelTimeInSeconds"] / 60),
            "distance_km":     round(s["lengthInMeters"] / 1000, 1),
            "polyline":        [{"lat": p["latitude"], "lon": p["longitude"]} for p in r["legs"][0]["points"]],
        })

    # Recommend the faster option
    recommended = min(options, key=lambda x: x["travel_time_min"])
    recommended["recommended"] = True

    if len(options) >= 2:
        other      = [o for o in options if o["id"] != recommended["id"]][0]
        time_saved = other["travel_time_min"] - recommended["travel_time_min"]
        recommended["reason"] = f"Saves {time_saved} min vs current route"

    # Persist for confirm-reroute lookup
    shipment["reroute_options"] = options
    set_shipment(shipment_id, shipment)

    return {"options": options, "recommended": recommended["id"]}


# ══════════════════════════════════════════
# POST /confirm-reroute  —  Accept a route
# ══════════════════════════════════════════
@router.post("/shipments/{shipment_id}/confirm-reroute")
def confirm_reroute(shipment_id: str, selection: RouteSelection):
    """
    Apply the chosen alternate route, update route polyline, lower risk.
    """
    shipment = get_shipment(shipment_id)

    shipment["active_route"] = selection.route_id
    shipment["status"]       = "REROUTED"
    shipment["risk_score"]   = 0.2

    # Update active route polyline so the map redraws
    new_route_found = False
    for option in shipment.get("reroute_options", []):
        if option["id"] == selection.route_id:
            print(f"Applying new route {option['id']} with {len(option['polyline'])} pts from current pos")
            shipment["route"]       = option["polyline"]
            shipment["route_index"]  = 0
            new_route_found = True
            break

    reason = (
        f"✅ Rerouted to {selection.route_id} — risk reduced"
        if new_route_found
        else "Rerouted (using default path)"
    )
    shipment["alerts"].append({
        "timestamp":  time.strftime("%H:%M"),
        "reason":     reason,
        "risk_score": 0.2,
        "severity":   "SAFE",
        "event_type": "reroute_confirmed",
    })

    shipment["reroute_options"] = []
    shipment["shadow_route_ready"] = False

    set_shipment(shipment_id, shipment)
    save_shipment(shipment)
    log_audit_event(shipment_id, time.strftime("%H:%M"), "confirm_reroute", 0.2, reason)

    return {"ok": True, "active_route": selection.route_id, "route_updated": new_route_found}


# ══════════════════════════════════════════
# POST /reset  —  Full state reset
# ══════════════════════════════════════════
@router.post("/shipments/{shipment_id}/reset")
def reset_shipment(shipment_id: str):
    """Reset shipment to clean initial state for next demo run."""
    from live_store import reset_shipment as r_shipment
    r_shipment(shipment_id)
    return {"ok": True, "message": "Shipment reset to initial state"}


# ══════════════════════════════════════════
# GET /state  —  Full shipment snapshot
# ══════════════════════════════════════════
@router.get("/shipments/{shipment_id}/state")
def get_state(shipment_id: str):
    return get_shipment(shipment_id)
