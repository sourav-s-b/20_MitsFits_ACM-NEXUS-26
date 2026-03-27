import asyncio
import random
import requests
from live_store import get_all_active_shipments, set_shipment
from websocket import manager

RISK_ENGINE_URL = "http://127.0.0.1:8001/risk"

async def move_truck(shipment: dict):
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 1

async def update_signals(shipment: dict):
    # Don't overwrite signals if they were manually overridden (e.g. for demo)
    # But for simulation, we can nudge them slightly
    if random.random() > 0.8:
        shipment["signals"]["traffic_delay"] = random.randint(0, 40)
        shipment["signals"]["weather_score"] = round(random.uniform(0, 1), 2)

async def compute_risk(shipment: dict):
    """
    Delegate to the Risk-Engine Microservice (Port 8001).
    Ensures consistency between manual checks and background simulation.
    """
    loc = shipment["current_location"]
    try:
        # Pass current signals as an override if they are already higher (event driven)
        params = {
            "lat": loc["lat"],
            "lon": loc["lon"]
        }
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
        
        await asyncio.sleep(2) # Faster polling for real-time feel
