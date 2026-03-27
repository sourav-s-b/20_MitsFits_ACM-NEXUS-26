import time
import random
from state import shipment


def move_truck():
    if shipment["route"] and shipment["route_index"] < len(shipment["route"]):
        shipment["current_location"] = shipment["route"][shipment["route_index"]]
        shipment["route_index"] += 1


def update_signals():
    shipment["signals"]["traffic_delay"] = random.randint(0, 40)
    shipment["signals"]["weather_score"] = round(random.uniform(0, 1), 2)


def compute_risk():
    t = shipment["signals"]["traffic_delay"]
    w = shipment["signals"]["weather_score"]

    risk = 0

    if t > 20:
        risk += 0.5
    if w > 0.6:
        risk += 0.4

    shipment["risk_score"] = min(risk, 1.0)

    if shipment["risk_score"] > 0.6:
        shipment["status"] = "HIGH RISK"
    else:
        shipment["status"] = "SAFE"


def run_simulation():
    while True:
        move_truck()
        update_signals()
        compute_risk()
        time.sleep(5)