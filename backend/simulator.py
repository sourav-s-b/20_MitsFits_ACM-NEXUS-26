import asyncio
import random
from live_store import get_all_active_shipments, set_shipment
from websocket import manager

async def move_truck(shipment: dict):
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 1

async def update_signals(shipment: dict):
    if shipment["status"] in ("HIGH RISK", "WARNING", "REROUTED"):
        return
    shipment["signals"]["traffic_delay"] = random.randint(0, 40)
    shipment["signals"]["weather_score"] = round(random.uniform(0, 1), 2)

async def compute_risk(shipment: dict):
    if shipment["status"] in ("HIGH RISK", "REROUTED"):
        return

    t = shipment["signals"]["traffic_delay"]
    w = shipment["signals"]["weather_score"]

    risk = 0.0
    if t > 20: risk += 0.5
    if w > 0.6: risk += 0.4

    shipment["risk_score"] = min(risk, 1.0)
    if shipment["risk_score"] > 0.6:
        shipment["status"] = "HIGH RISK"
    elif shipment["risk_score"] > 0.4:
        shipment["status"] = "WARNING"
    else:
        shipment["status"] = "SAFE"

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
        
        await asyncio.sleep(3) # Broadcast every 3 seconds for smooth frontend movement
