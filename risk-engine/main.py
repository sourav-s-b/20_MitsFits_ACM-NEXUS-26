from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from model.predictor import compute_risk, OWM_KEY, TOMTOM_KEY
import json
from pathlib import Path


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared override state — Person 1/3 injects events here
event_override = {}

# --- Startup Checks ---
@app.on_event("startup")
def startup_event():
    if not OWM_KEY:
        print("WARNING: OWM_KEY is not set in .env. Weather data will be mock only.")
    if not TOMTOM_KEY:
        print("WARNING: TOMTOM_KEY is not set in .env. Traffic data will be mock only.")


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
def get_sop(status: str, weather_score: float = None):
    knowledge_path = Path(__file__).parent / "data" / "knowledge.json"
    try:
        with open(knowledge_path) as f:
            sops = json.load(f)["sops"]
    except Exception as e:
        return {"error": f"Could not load knowledge base: {e}"}

    matches = []
    for s in sops:
        trigger = s["trigger"]
        # Exact match for status
        if trigger == status:
            matches.append(s)
        # Check for numeric conditions (e.g., weather_score > 0.7)
        elif ">" in trigger or "<" in trigger:
            try:
                if "weather_score" in trigger and weather_score is not None:
                    # Simple safe evaluation for demo purposes
                    # In production, use a safer expression parser!
                    var, op, threshold = trigger.split()
                    if op == ">" and weather_score > float(threshold):
                        matches.append(s)
                    elif op == "<" and weather_score < float(threshold):
                        matches.append(s)
            except Exception:
                pass
                
    return {"recommendations": matches}
