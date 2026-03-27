"""
intel_routes.py
===============
Exposes the Intelligence Engine via REST endpoints.
Frontend can poll /shipments/{id}/intel for a full contextual snapshot.
"""

from fastapi import APIRouter, HTTPException
from live_store import get_shipment
from intel_engine import gather_intel

router = APIRouter()


@router.get("/shipments/{shipment_id}/intel")
async def get_intel_report(shipment_id: str):
    """
    Returns a full multi-source intelligence snapshot for the current
    location of a shipment. Includes weather, traffic, news, and
    social media signals along with a composite risk score.
    """
    shipment = get_shipment(shipment_id)
    loc  = shipment.get("current_location")
    dest = shipment.get("destination")

    if not loc:
        raise HTTPException(status_code=404, detail="Shipment has no current location")

    report = await gather_intel(
        lat      = loc.get("lat") or loc.get("latitude"),
        lon      = loc.get("lon") or loc.get("longitude"),
        dest_lat = dest.get("lat") if dest else None,
        dest_lon = dest.get("lon") if dest else None,
    )

    # Persist the latest intel report inside the shipment state
    shipment["intel_report"] = report
    from live_store import set_shipment
    set_shipment(shipment_id, shipment)

    return report


@router.get("/intel/location")
async def get_intel_for_location(lat: float, lon: float, dest_lat: float = None, dest_lon: float = None):
    """
    Returns an intelligence snapshot for an arbitrary lat/lon.
    Useful for a map-click-to-inspect interaction on the frontend.
    """
    return await gather_intel(lat=lat, lon=lon, dest_lat=dest_lat, dest_lon=dest_lon)
