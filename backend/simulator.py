import asyncio
import random
import time
import requests
import os
from dotenv import load_dotenv

from live_store import get_all_active_shipments, set_shipment
from websocket import manager
from routes.orchestration_routes import fetch_weather, fetch_tomtom_traffic

load_dotenv()
RISK_ENGINE_URL = os.getenv("PERSON2_URL", "http://127.0.0.1:8001") + "/risk"



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
    if shipment["status"] in ("HIGH RISK", "REROUTED"):
        return

    t = shipment["signals"].get("traffic_delay", 0)
    w = shipment["signals"].get("weather_score", 0.0)

    risk = 0.0
    if t > 20: risk += 0.5
    if w > 0.6: risk += 0.4

    shipment["risk_score"] = min(risk, 1.0)
    if shipment["risk_score"] >= 0.4:
        shipment["status"] = "HIGH RISK"
        if not shipment.get("reroute_options"):
            shipment["shadow_route_ready"] = True
    elif shipment["risk_score"] > 0.2:
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

        await asyncio.sleep(2)  # Faster polling for real-time feel
