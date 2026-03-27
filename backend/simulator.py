import time
import random
from state import shipment


def move_truck():
    """Advance truck one step along the active route."""
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 1


def update_signals():
    """
    Randomly update signals ONLY when no active high-risk event is in progress.
    This prevents the simulator from overwriting a demo-injected event.
    """
    # Freeze randomisation if an event was deliberately injected
    if shipment["status"] in ("HIGH RISK", "WARNING", "REROUTED"):
        return

    shipment["signals"]["traffic_delay"] = random.randint(0, 40)
    shipment["signals"]["weather_score"] = round(random.uniform(0, 1), 2)


def compute_risk():
    """
    Recompute risk_score and status from current signals.
    Skip if status was manually set (HIGH RISK / REROUTED).
    """
    if shipment["status"] in ("HIGH RISK", "REROUTED"):
        return  # Preserve the injected / confirmed state

    t = shipment["signals"]["traffic_delay"]
    w = shipment["signals"]["weather_score"]

    risk = 0.0
    if t > 20:
        risk += 0.5
    if w > 0.6:
        risk += 0.4

    shipment["risk_score"] = min(risk, 1.0)

    if shipment["risk_score"] > 0.6:
        shipment["status"] = "HIGH RISK"
    elif shipment["risk_score"] > 0.4:
        shipment["status"] = "WARNING"
    else:
        shipment["status"] = "SAFE"


def run_simulation():
    """Background loop: moves truck and updates ambient signals every 5 s."""
    while True:
        move_truck()
        update_signals()
        compute_risk()
        time.sleep(5)