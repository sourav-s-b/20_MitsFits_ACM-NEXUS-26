import asyncio
import random
import time
from live_store import get_all_active_shipments, set_shipment
from websocket import manager
from routes.orchestration_routes import fetch_weather, fetch_tomtom_traffic


async def move_truck(shipment: dict):
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 1


async def update_signals(shipment: dict):
    if shipment["status"] in ("HIGH RISK", "WARNING", "REROUTED"):
        return

    now = time.time()
    last_fetch = shipment.get("last_api_fetch", 0)

    # Throttled live API fetch (every 30s per shipment)
    if now - last_fetch > 30:
        loc = shipment.get("current_location")
        dest = shipment.get("destination")

        if loc and dest:
            weather_data = fetch_weather(loc["lat"], loc["lon"])
            shipment["signals"]["weather_score"] = weather_data.get("score", 0.0)

            delay = fetch_tomtom_traffic(
                loc["lat"], loc["lon"], dest["lat"], dest["lon"]
            )
            shipment["signals"]["traffic_delay"] = delay

        shipment["last_api_fetch"] = now


async def compute_risk(shipment: dict):
    """
    Delegate to the Risk-Engine Microservice (Port 8001).
    Ensures consistency between manual checks and background simulation.
    """
    loc = shipment["current_location"]
    try:
        # Pass current signals as an override if they are already higher (event driven)
        params = {"lat": loc["lat"], "lon": loc["lon"]}
        # In this multi-tenant simulator, we can also pass the existing signals
        # but the risk-engine's /risk endpoint uses internal state (event_override)
        # For this simulation, we'll just let the engine fetch or use overrides.
        resp = requests.get(RISK_ENGINE_URL, params=params, timeout=2).json()

        shipment["risk_score"] = resp["risk_score"]
        shipment["status"] = resp["status"]
        shipment["ai_reason"] = resp.get("ai_reason")
        shipment["ai_level"] = resp.get("ai_level")

        # If risk is very high, offer reroute options if not already there
        if shipment["status"] == "HIGH RISK" and not shipment.get("reroute_options"):
            shipment["shadow_route_ready"] = True

    except Exception as e:
        print(f"Simulator Risk-Engine Call Error: {e}")


async def run_simulation():
    while True:
        shipments = get_all_active_shipments()
        for shipment in shipments:
            await move_truck(shipment)
            await update_signals(shipment)
            await compute_risk(shipment)
            set_shipment(shipment["shipment_id"], shipment)

            # Broadcast state via WebSockets
            await manager.broadcast(shipment["shipment_id"], shipment)

        await asyncio.sleep(2)  # Faster polling for real-time feel
