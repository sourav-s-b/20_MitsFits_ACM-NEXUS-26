"""
live_store.py
=============
Mocked Redis in-memory key-value store.
Stores the high-frequency telemetry (truck lat/lon, risk scores)
for active shipments seamlessly without crushing a database.
"""
from typing import Dict, Any

# Our "Redis" DB
LIVE_STORE: Dict[str, Any] = {}

def get_shipment(shipment_id: str) -> dict:
    if shipment_id not in LIVE_STORE:
        # Auto-initialize an empty structure if it doesn't exist
        LIVE_STORE[shipment_id] = _default_shipment(shipment_id)
    return LIVE_STORE[shipment_id]

def set_shipment(shipment_id: str, data: dict):
    LIVE_STORE[shipment_id] = data

def get_all_active_shipments() -> list:
    return list(LIVE_STORE.values())

def reset_shipment(shipment_id: str):
    LIVE_STORE[shipment_id] = _default_shipment(shipment_id)

def _default_shipment(shipment_id: str) -> dict:
    return {
        "shipment_id": shipment_id,
        "current_location": {"lat": 9.9312, "lon": 76.2673},
        "destination":      {"lat": 12.9716, "lon": 77.5946},
        "route":            [],
        "route_index":      0,
        "eta":              180,
        "checkpoints":      [],
        "signals": {
            "traffic_delay":  0,
            "weather_score":  0.0,
        },
        "weather": {
            "description":    "clear sky",
            "temp_c":         28.0,
            "humidity":       60,
            "visibility_km":  10.0,
            "wind_kph":       12.0,
            "score":          0.0,
        },
        "critical_since": None,
        "speed_kmh": 85,
        "junction_dist_m": 500,
        "auto_pilot": False,
        "auto_reroute_armed": False,
        "auto_reroute_deadline": None,
        "last_auto_reroute_time": 0,
        "risk_score":   0.0,
        "status":       "SAFE",
        "active_route": "A",
        "alerts":       [],
        "reroute_options": [],
        "ai_reason":  None,
        "ai_level":   None,
        "pipeline_last_run": None,
        "shadow_route_ready": False,
    }
import time
from database import log_audit_event

def apply_reroute_logic(shipment_id: str, route_id: str, reason_prefix: str = "Rerouted"):
    """
    Unified logic for applying a reroute to a shipment.
    Resets risk, clears signals, updates polyline, and logs the event.
    Used by both manual (UI) and autonomous (Autopilot) systems.
    """
    shipment = get_shipment(shipment_id)
    
    # 1. Update State
    shipment["active_route"] = route_id
    shipment["status"]       = "REROUTED"
    shipment["risk_score"]   = 0.2
    
    # 2. Reset Sensors
    shipment["signals"] = {"traffic_delay": 0, "weather_score": 0.0}
    if "weather" in shipment:
        shipment["weather"]["score"] = 0.0
        
    # 3. Update Polyline
    new_route_found = False
    for option in shipment.get("reroute_options", []):
        if option["id"] == route_id:
            shipment["route"]       = option["polyline"]
            shipment["route_index"]  = 0
            new_route_found = True
            break
            
    # 4. Clean up state
    shipment["shadow_route_ready"] = False
    shipment["reroute_options"] = []
    shipment["auto_reroute_armed"] = False
    shipment["auto_reroute_deadline"] = None
    shipment["last_auto_reroute_time"] = time.time()
    shipment["critical_since"] = None
    
    # 5. Log & Audit
    reason = f"✅ {reason_prefix} to {route_id} $ risk reduced to SAFE"
    alert = {
        "timestamp":  time.strftime("%H:%M"),
        "reason":     reason,
        "risk_score": 0.2,
        "severity":   "REROUTED",
        "event_type": "reroute"
    }
    shipment["alerts"].append(alert)
    
    # Persist the state update
    set_shipment(shipment_id, shipment)
    
    # Database persistence
    log_audit_event(shipment_id, time.strftime("%H:%M"), "reroute", 0.2, reason)
    
    return shipment, reason
