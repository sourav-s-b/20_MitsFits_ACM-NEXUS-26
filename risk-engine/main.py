from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from model.predictor import compute_risk
import json


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared override state — Person 1/3 injects events here
event_override = {}


@app.get("/risk")
def get_risk(lat: float, lon: float):
    return compute_risk(lat, lon, override=event_override)


@app.post("/event")
def inject_event(payload: dict):
    """Person 3 (controller.js) calls this to simulate crisis for demo."""
    global event_override
    if payload.get("type") == "traffic_spike":
        event_override = {"traffic_delay": 45}
    elif payload.get("type") == "storm":
        event_override = {"weather_score": 0.9}
    elif payload.get("type") == "clear":
        event_override = {}  # reset
    return {"status": "ok", "active_override": event_override}


@app.get("/risk/mock")
def mock_risk():
    """Person 4 uses this while real engine is being built."""
    return {
        "traffic_delay": 12.4,
        "weather_score": 0.1,
        "time_risk": 0.0,
        "risk_score": 0.22,
        "status": "SAFE",
    }


@app.get("/health")
def health():
    return {"status": "running"}


@app.get("/sop")
def get_sop(status: str):
    with open("data/knowledge.json") as f:
        sops = json.load(f)["sops"]
    matches = [s for s in sops if s["trigger"] == status]
    return {"recommendations": matches}
