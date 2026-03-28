import asyncio
import time
import os
import httpx
import random
from dotenv import load_dotenv

from live_store import get_all_active_shipments, set_shipment, apply_reroute_logic
from websocket import manager
from routes.orchestration_routes import (
    fetch_weather, fetch_tomtom_traffic, get_reroute_options_tomtom, call_person2
)

load_dotenv()
RISK_ENGINE_URL = os.getenv("PERSON2_URL", "http://127.0.0.1:8001") + "/risk"


async def move_truck(shipment: dict):
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 30

        if shipment["route_index"] % 60 == 0:
            print(f"[Simulator] {shipment['shipment_id']} at point {shipment['route_index']}/{len(shipment['route'])} (Status: {shipment['status']})")


async def update_signals(shipment: dict):
    # Gate 3 telemetry — always update speed/junction regardless of status
    shipment["speed_kmh"] = random.randint(70, 95)
    shipment["junction_dist_m"] = random.randint(150, 400)

    # BUG FIX 3: removed early-return guard for REROUTED so signals keep
    # updating after a reroute — otherwise a second event never raises risk
    if shipment["status"] == "HIGH RISK":
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

    # BUG FIX 1: Recovery — once risk drops below threshold after a reroute,
    # clear REROUTED status back to SAFE so the next event can be processed.
    # Without this, status stays "REROUTED" forever and all future event
    # detection branches are skipped.
    if shipment["status"] == "REROUTED" and shipment["risk_score"] < 0.2:
        print(f"✅ [Simulator] {shipment['shipment_id']} recovered to SAFE after reroute.")
        shipment["status"] = "SAFE"
        # BUG FIX 2: Also clear stale reroute_options here so the next high-risk
        # event triggers a fresh TomTom fetch instead of reusing old routes.
        shipment["reroute_options"] = []
        shipment["shadow_route_ready"] = False
        shipment["auto_reroute_armed"] = False
        shipment["auto_reroute_deadline"] = None
        shipment["critical_since"] = None

    # Gate 2 Timer Tracking
    if shipment["risk_score"] >= 0.85:
        if not shipment.get("critical_since"):
            shipment["critical_since"] = time.time()
    else:
        shipment["critical_since"] = None

    # --- Decision Layer: Autonomous Action ---
    # BUG FIX 2: has_options must ignore empty lists — previously a leftover
    # [] in reroute_options would make has_options True and skip the fetch
    has_options = bool(shipment.get("reroute_options"))

    # 1. Fetch options if risk is high (only when not already rerouted/in-progress)
    if shipment["risk_score"] >= 0.4 and shipment["status"] != "REROUTED" and not has_options:
        shipment["status"] = "HIGH RISK"
        options = await get_reroute_options_tomtom(shipment["shipment_id"])
        shipment["reroute_options"] = options
        shipment["shadow_route_ready"] = True
        has_options = bool(options)
        print(f"[Simulator] Reroute options generated for {shipment['shipment_id']}.")

    # 2. Reroute Confirmation Logic (Shared between Autopilot and Gates)
    if has_options and shipment["status"] != "REROUTED":
        stable_passed = shipment.get("critical_since") and (time.time() - shipment["critical_since"] >= 15)
        velocity_passed = shipment.get("speed_kmh", 0) <= 80 and shipment.get("junction_dist_m", 0) >= 200
        new_risk = 0.45
        risk_delta_passed = (shipment["risk_score"] - new_risk) > 0.3

        trigger_auto = shipment.get("auto_pilot") or (stable_passed and velocity_passed and risk_delta_passed)

        if trigger_auto:
            # BUG FIX 4: Reduced cooldown from 300s to 30s so back-to-back
            # events in a demo session are not silently swallowed.
            if time.time() - shipment.get("last_auto_reroute_time", 0) > 30:

                # PATH A: Autopilot (Instant)
                if shipment.get("auto_pilot"):
                    options = shipment["reroute_options"]
                    if options:
                        best_option = next((o for o in options if o.get("recommended")), options[0])
                        print(f"🚀 [Simulator] Autopilot INSTANT-CONFIRM for {shipment['shipment_id']} -> {best_option['id']}")

                        updated_shipment, _ = apply_reroute_logic(
                            shipment["shipment_id"],
                            best_option["id"],
                            reason_prefix="Autopilot Navigation"
                        )
                        shipment.update(updated_shipment)
                        shipment["last_auto_reroute_time"] = time.time()
                        # Clear options immediately so recovery check works cleanly
                        shipment["reroute_options"] = []

                # PATH B: Standard Gated Auto-Reroute (countdown for visual feedback)
                elif not shipment.get("auto_reroute_armed"):
                    shipment["auto_reroute_armed"] = True
                    shipment["auto_reroute_deadline"] = time.time() + 5
                    print(f"🚨 [Simulator] Standard Auto-Reroute Armed (5s) for {shipment['shipment_id']}.")

    # 3. Execute Armed Countdowns (PATH B execution)
    if shipment.get("auto_reroute_armed") and shipment.get("auto_reroute_deadline"):
        if time.time() >= shipment["auto_reroute_deadline"]:
            options = shipment["reroute_options"]
            if options:
                best_option = next((o for o in options if o.get("recommended")), options[0])
                print(f"🤖 [Simulator] Executing Gated Auto-Reroute for {shipment['shipment_id']} -> {best_option['id']}")

                updated_shipment, _ = apply_reroute_logic(
                    shipment["shipment_id"],
                    best_option["id"],
                    reason_prefix="Gates 1-3 Passed"
                )
                shipment.update(updated_shipment)
                shipment["last_auto_reroute_time"] = time.time()
                # Clear options so recovery works cleanly next cycle
                shipment["reroute_options"] = []

    # 4. Status fallback for non-rerouted states
    elif shipment["status"] != "REROUTED":
        if shipment["risk_score"] > 0.2:
            shipment["status"] = "WARNING"
        else:
            shipment["status"] = "SAFE"


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
        if shipments:
            await asyncio.gather(*(process_shipment(s) for s in shipments))

        await asyncio.sleep(1)  # Real-time heartbeat (1Hz)