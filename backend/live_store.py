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
