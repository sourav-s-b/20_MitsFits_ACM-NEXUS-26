"""
collision_routes.py  —  Predictive Collision Avoidance Network
==============================================================
PURELY ADDITIVE: This file is a new FastAPI router.
To wire it in, add these 2 lines to server.py (no other changes):

    from routes.collision_routes import router as collision_router
    app.include_router(collision_router, prefix="", tags=["collision"])

No existing files are modified.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import math
import time

router = APIRouter()


# ── Models ─────────────────────────────────────────────────────────────────

class TruckPosition(BaseModel):
    shipment_id: str
    lat: float
    lon: float
    speed_kmh: float = 60.0          # default speed assumption
    heading_deg: Optional[float] = None   # optional heading (0 = North)


class CollisionRequest(BaseModel):
    trucks: List[TruckPosition]
    lookahead_minutes: float = 3.0   # how far ahead to predict
    safe_distance_km: float = 1.0    # min safe separation distance


# ── Helpers ─────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def predict_position(truck: TruckPosition, minutes: float):
    """
    Dead-reckoning: move the truck along its heading for `minutes` at its speed.
    If heading is unknown we keep position fixed (conservative — no phantom alerts).
    Returns (lat, lon).
    """
    if truck.heading_deg is None:
        return truck.lat, truck.lon

    distance_km = (truck.speed_kmh / 60.0) * minutes
    # Convert heading to bearing
    bearing = math.radians(truck.heading_deg)
    R = 6371.0
    lat1 = math.radians(truck.lat)
    lon1 = math.radians(truck.lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_km / R) +
        math.cos(lat1) * math.sin(distance_km / R) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(distance_km / R) * math.cos(lat1),
        math.cos(distance_km / R) - math.sin(lat1) * math.sin(lat2)
    )
    return math.degrees(lat2), math.degrees(lon2)


def collision_probability(current_dist: float, predicted_dist: float, safe_dist: float) -> float:
    """
    Simple heuristic: probability increases as predicted distance shrinks below safe_dist.
    Returns 0.0 – 1.0.
    """
    if predicted_dist >= safe_dist:
        return 0.0
    # How deep into the danger zone are they?
    danger_fraction = 1.0 - (predicted_dist / safe_dist)
    # Amplify if they were already approaching each other
    approach_factor = 1.2 if predicted_dist < current_dist else 0.8
    return min(round(danger_fraction * approach_factor, 2), 1.0)


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/collision/predict")
def predict_collisions(req: CollisionRequest):
    """
    Accept current positions of all trucks, return predicted collision pairs.

    Request body:
        {
          "trucks": [
            {"shipment_id": "SHP001", "lat": 9.931, "lon": 76.267,
             "speed_kmh": 60, "heading_deg": 45},
            {"shipment_id": "SHP002", "lat": 9.940, "lon": 76.275,
             "speed_kmh": 55, "heading_deg": 200}
          ],
          "lookahead_minutes": 3,
          "safe_distance_km": 1.0
        }

    Response:
        {
          "timestamp": "14:03",
          "lookahead_minutes": 3,
          "safe_distance_km": 1.0,
          "collision_pairs": [...],
          "all_clear": true/false
        }
    """
    trucks = req.trucks
    lookahead = req.lookahead_minutes
    safe_dist = req.safe_distance_km

    collision_pairs = []

    for i in range(len(trucks)):
        for j in range(i + 1, len(trucks)):
            a, b = trucks[i], trucks[j]

            # Current separation
            current_dist = haversine_km(a.lat, a.lon, b.lat, b.lon)

            # Predicted positions
            a_lat, a_lon = predict_position(a, lookahead)
            b_lat, b_lon = predict_position(b, lookahead)
            predicted_dist = haversine_km(a_lat, a_lon, b_lat, b_lon)

            prob = collision_probability(current_dist, predicted_dist, safe_dist)

            if prob > 0.0:
                # Mid-point of the predicted collision zone
                conflict_lat = (a_lat + b_lat) / 2
                conflict_lon = (a_lon + b_lon) / 2

                severity = "HIGH" if prob >= 0.7 else "MODERATE" if prob >= 0.4 else "LOW"

                collision_pairs.append({
                    "truck_a": a.shipment_id,
                    "truck_b": b.shipment_id,
                    "current_distance_km": round(current_dist, 2),
                    "predicted_distance_km": round(predicted_dist, 2),
                    "collision_probability": prob,
                    "severity": severity,
                    "conflict_zone": {"lat": round(conflict_lat, 5), "lon": round(conflict_lon, 5)},
                    "predicted_positions": {
                        a.shipment_id: {"lat": round(a_lat, 5), "lon": round(a_lon, 5)},
                        b.shipment_id: {"lat": round(b_lat, 5), "lon": round(b_lon, 5)},
                    },
                    "suggested_action": (
                        f"Reroute {a.shipment_id} — delay by ~2 min to create safe gap"
                        if prob >= 0.5 else
                        f"Monitor {a.shipment_id} & {b.shipment_id} — approaching safe boundary"
                    ),
                    "time_to_conflict_min": round(lookahead * (predicted_dist / max(current_dist, 0.001)), 1),
                })

    # Sort by probability descending
    collision_pairs.sort(key=lambda x: x["collision_probability"], reverse=True)

    return {
        "timestamp": time.strftime("%H:%M"),
        "lookahead_minutes": lookahead,
        "safe_distance_km": safe_dist,
        "collision_pairs": collision_pairs,
        "all_clear": len(collision_pairs) == 0,
        "total_trucks_analyzed": len(trucks),
    }


# ══════════════════════════════════════════
# GET /collision/status  —  Quick health check
# ══════════════════════════════════════════
@router.get("/collision/status")
def collision_status():
    return {"module": "Predictive Collision Avoidance Network", "status": "online"}
