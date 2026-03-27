from fastapi import FastAPI
import requests
import threading
import os
from dotenv import load_dotenv

from state import shipment
from simulator import run_simulation

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

if not TOMTOM_API_KEY:
    raise ValueError("❌ TOMTOM_API_KEY not found in .env file")

# =========================
# INIT APP
# =========================
app = FastAPI()


# =========================
# ROUTE FETCHING FUNCTION
# =========================
def get_route(origin, destination):
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin}:{destination}/json?key={TOMTOM_API_KEY}"

    try:
        res = requests.get(url)

        if res.status_code != 200:
            print("❌ API Error:", res.text)
            return []

        data = res.json()

        points = data["routes"][0]["legs"][0]["points"]

        route = [{"lat": p["latitude"], "lon": p["longitude"]} for p in points]

        return route

    except Exception as e:
        print("❌ Exception in get_route:", e)
        return []


# =========================
# START SHIPMENT
# =========================
@app.post("/start")
def start_shipment():
    origin = "9.9312,76.2673"
    destination = "12.9716,77.5946"

    route = get_route(origin, destination)

    if not route:
        return {"error": "Route not found. Check API key or coordinates."}

    shipment["route"] = route
    shipment["route_index"] = 0
    shipment["current_location"] = route[0]
    shipment["status"] = "SAFE"

    return {
        "message": "✅ Shipment started",
        "total_points": len(route)
    }


# =========================
# GET CURRENT STATE
# =========================
@app.get("/state")
def get_state():
    return shipment


# =========================
# TRIGGER EVENT (FOR DEMO)
# =========================
@app.post("/event")
def trigger_event():
    shipment["signals"]["traffic_delay"] = 50
    shipment["signals"]["weather_score"] = 0.9
    shipment["status"] = "HIGH RISK"

    return {"message": "⚠️ High risk event triggered"}

@app.post("/traffic")
def traffic_spike():
    shipment["signals"]["traffic_delay"] = 60
    return {"message": "Traffic spike simulated"}

# =========================
# RESET (OPTIONAL BUT USEFUL)
# =========================
@app.post("/reset")
def reset():
    shipment["route"] = []
    shipment["route_index"] = 0
    shipment["signals"] = {
        "traffic_delay": 0,
        "weather_score": 0
    }
    shipment["risk_score"] = 0
    shipment["status"] = "SAFE"

    return {"message": "🔄 Reset successful"}

# =========================
# BACKGROUND SIMULATION
# =========================
def start_simulation_thread():
    thread = threading.Thread(target=run_simulation)
    thread.daemon = True
    thread.start()


start_simulation_thread()