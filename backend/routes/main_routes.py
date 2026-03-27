from fastapi import APIRouter
import requests
import os
from dotenv import load_dotenv

from live_store import get_shipment, set_shipment
from database import save_shipment

router = APIRouter()

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

if not TOMTOM_API_KEY:
    raise ValueError("❌ TOMTOM_API_KEY not found in .env file")

def get_route(origin: str, destination: str):
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
        return [{"lat": p["latitude"], "lon": p["longitude"]} for p in points]
    except Exception as e:
        print("❌ Exception in get_route:", e)
        return []

from pydantic import BaseModel
from typing import Optional

class StartRequest(BaseModel):
    origin: Optional[str] = "9.9312,76.2673"
    destination: Optional[str] = "12.9716,77.5946"

@router.post("/shipments/{shipment_id}/start")
def start_shipment(shipment_id: str, req: StartRequest = None):
    origin      = req.origin if req else "9.9312,76.2673"
    destination = req.destination if req else "12.9716,77.5946"

    route = get_route(origin, destination)
    if not route:
        return {"error": "Route not found. Check API key or coordinates."}

    shipment = get_shipment(shipment_id)
    shipment["route"] = route
    shipment["route_index"] = 0
    shipment["current_location"] = route[0]
    shipment["destination"] = {
        "lat": float(destination.split(",")[0]),
        "lon": float(destination.split(",")[1])
    }
    shipment["status"] = "SAFE"
    shipment["risk_score"] = 0.0
    shipment["alerts"] = []
    shipment["reroute_options"] = []
    
    set_shipment(shipment_id, shipment)
    
    # Save to SQLite
    try:
        save_shipment(shipment)
    except Exception as e:
        print(f"DB Save Error: {e}")

    return {
        "message":      f"✅ Shipment {shipment_id} started",
        "total_points": len(route)
    }

@router.post("/shipments/{shipment_id}/traffic")
def traffic_spike(shipment_id: str):
    shipment = get_shipment(shipment_id)
    shipment["signals"]["traffic_delay"] = 60
    set_shipment(shipment_id, shipment)
    return {"message": "Traffic spike signal set"}

# =========================
# PERSON 3 EXTENSION APIS
# =========================
@router.get("/shipments")
def get_all_shipments():
    """Return all active shipments for the Fleet Dashboard."""
    from live_store import get_all_active_shipments
    shipments = get_all_active_shipments()
    return [
        {
            "shipment_id": s["shipment_id"],
            "current_location": s["current_location"],
            "status": s["status"],
            "risk_score": s["risk_score"],
            "eta": s["eta"]
        } for s in shipments
    ]

@router.get("/shipments/{shipment_id}/history")
def get_shipment_history(shipment_id: str):
    """Return the audit log history for a specific shipment."""
    from database import get_audit_history
    history = get_audit_history(shipment_id)
    return {"shipment_id": shipment_id, "history": history}

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def mock_login(req: LoginRequest):
    """Mock authentication endpoint for Person 4's auth screen."""
    # Extremely basic mock since this is a hackathon
    if req.password == "password":
        return {
            "token": "mock-jwt-token-12345",
            "role": "Global Dispatcher",
            "name": "Nexus Admin"
        }
    return {"error": "Invalid credentials", "status": 401}