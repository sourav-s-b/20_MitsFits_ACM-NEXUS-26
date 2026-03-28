import asyncio
import time
import os
import httpx
from dotenv import load_dotenv

from live_store import get_all_active_shipments, set_shipment
from websocket import manager
from routes.orchestration_routes import (
    fetch_weather, fetch_tomtom_traffic, get_reroute_options_tomtom, call_person2
)

load_dotenv()
RISK_ENGINE_URL = os.getenv("PERSON2_URL", "http://127.0.0.1:8001") + "/risk"



async def move_truck(shipment: dict):
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        # Move to next point
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 1
        
        # Validation Log: occasional position reporting
        if shipment["route_index"] % 20 == 0:
            print(f"[Simulator] {shipment['shipment_id']} at point {shipment['route_index']}/{len(shipment['route'])} (Status: {shipment['status']})")


import random

async def update_signals(shipment: dict):
    # Mock dynamic telemetry for Gate 3 (Driver Context)
    shipment["speed_kmh"] = random.randint(70, 95)
    shipment["junction_dist_m"] = random.randint(150, 400)

    if shipment["status"] in ("HIGH RISK", "WARNING", "REROUTED"):
        return

    now = time.time()
    last_fetch = shipment.get("last_api_fetch", 0)

    # Throttled live API fetch (every 30s per shipment)
    if now - last_fetch > 30:
        loc = shipment.get("current_location")
        dest = shipment.get("destination")

        if loc and dest:
            weather_data = await fetch_weather(loc["lat"], loc["lon"])
            shipment["weather"] = weather_data
            shipment["signals"]["weather_score"] = weather_data.get("score", 0.0)

            delay = await fetch_tomtom_traffic(
                loc["lat"], loc["lon"], dest["lat"], dest["lon"]
            )
            shipment["signals"]["traffic_delay"] = delay

        shipment["last_api_fetch"] = now


async def compute_risk(shipment: dict):
    # REMOVED: Early return on HIGH RISK/REROUTED to allow recovery
    
    loc = shipment["current_location"]
    
    # --- Intelligence Layer: Call Risk-Engine (ML) ---
    try:
        params = {"lat": loc["lat"], "lon": loc["lon"]}
        async with httpx.AsyncClient() as client:
            resp = await client.get(RISK_ENGINE_URL, params=params, timeout=1.0)
            data = resp.json()
        
        shipment["risk_score"] = data["risk_score"]
        shipment["ai_reason"] = data.get("ai_reason", "Real-time analysis active.")
        shipment["ai_level"] = data.get("status")
    except Exception:
        # Fallback to local elite rule engine (Onyx-Brain)
        p2_result = call_person2(shipment["shipment_id"], loc["lat"], loc["lon"])
        shipment["risk_score"] = p2_result["risk"]
        shipment["ai_reason"] = p2_result["reason"]
        shipment["ai_level"] = p2_result["level"]
        shipment["is_compound"] = p2_result.get("is_compound", False)
        shipment["is_night"] = p2_result.get("is_night", False)

    # Gate 2 Timer Tracking
    if shipment["risk_score"] >= 0.85:
        if not shipment.get("critical_since"):
            shipment["critical_since"] = time.time()
    else:
        shipment["critical_since"] = None

    # --- Decision Layer: Autonomous Action ---
    if shipment["risk_score"] >= 0.4:
        # Only trigger new reroute if not already rerouted or if risk is still high
        if shipment["status"] != "REROUTED":
            shipment["status"] = "HIGH RISK"
            
            # Fetch options unconditionally so dispatcher can see them manually
            if not shipment.get("reroute_options"):
                options = await get_reroute_options_tomtom(shipment["shipment_id"])
                shipment["reroute_options"] = options
                shipment["shadow_route_ready"] = True
                print(f"[Simulator] Reroute options generated for {shipment['shipment_id']}.")

            # GATES 2 & 3: Stable Window and Context
            stable_passed = shipment.get("critical_since") and (time.time() - shipment["critical_since"] >= 15)
            velocity_passed = shipment.get("speed_kmh", 0) <= 80 and shipment.get("junction_dist_m", 0) >= 200

            # GATE 1: Validated Auto-Reroute (Risk Delta > 0.3)
            # If the new route is only slightly better, don't trigger the blind countdown at all.
            # It just waits for the driver's manual choice.
            new_risk = 0.45 # Mocked alternative route risk
            risk_delta_passed = (shipment["risk_score"] - new_risk) > 0.3

            if shipment.get("reroute_options") and stable_passed and velocity_passed and risk_delta_passed:
                if not shipment.get("auto_reroute_armed"):
                    if time.time() - shipment.get("last_auto_reroute_time", 0) > 300:
                        shipment["auto_reroute_armed"] = True
                        shipment["auto_reroute_deadline"] = time.time() + 5
                        print(f"🚨 [Simulator] Gates 1-3 Passed for {shipment['shipment_id']}. Armed 5s auto-reroute countdown.")

            if shipment.get("auto_reroute_armed") and shipment.get("auto_reroute_deadline"):
                if time.time() >= shipment["auto_reroute_deadline"]:
                    options = shipment["reroute_options"]
                    if options:
                        best_option = next((o for o in options if o.get("recommended")), options[0])
                        print(f"[Simulator] Auto-confirming reroute for {shipment['shipment_id']} -> {best_option['id']} at T-0.")
                        
                        shipment["active_route"] = best_option["id"]
                        shipment["route"] = best_option["polyline"]
                        shipment["route_index"] = 0
                        shipment["status"] = "REROUTED"
                        shipment["shadow_route_ready"] = False
                        shipment["reroute_options"] = []
                        shipment["auto_reroute_armed"] = False
                        shipment["auto_reroute_deadline"] = None
                        shipment["last_auto_reroute_time"] = time.time()
                        shipment["critical_since"] = None
                        
                        reason = f"🤖 Autonomous intervention: Switched to {best_option['id']} (Gates 1-3 Passed)"
                        shipment["alerts"].append({
                            "timestamp": time.strftime("%H:%M"),
                            "reason": reason,
                            "risk_score": 0.2,
                            "severity": "REROUTED",
                            "event_type": "auto_reroute"
                        })
                        from database import log_audit_event
                        log_audit_event(shipment["shipment_id"], time.strftime("%H:%M"), "auto_reroute", 0.2, reason)

    elif shipment["risk_score"] > 0.2:
        shipment["status"] = "WARNING"
    else:
        # Recovery to SAFE: allow even REROUTED to go back to SAFE if risk is very low
        if shipment["risk_score"] < 0.2:
             shipment["status"] = "SAFE"
        # If they were rerouted but risk is now safe, we keep "REROUTED" 
        # as a status badge but the intelligence is nominal.
        if shipment["status"] == "REROUTED" and shipment["risk_score"] < 0.2:
             # Potentially add a "REROUTE SUCCESSFUL" indicator
             pass


async def process_shipment(shipment: dict):
    await move_truck(shipment)
    await update_signals(shipment)
    await compute_risk(shipment)
    set_shipment(shipment["shipment_id"], shipment)

    # Broadcast state via WebSockets
    await manager.broadcast(shipment["shipment_id"], shipment)


async def run_simulation():
    while True:
        shipments = get_all_active_shipments()
        # Concurrently process all shipments for ultra-low latency
        if shipments:
            await asyncio.gather(*(process_shipment(s) for s in shipments))
        
        await asyncio.sleep(2)  # Faster polling for real-time feel
