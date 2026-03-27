"""
database.py
===========
Mocked PostgreSQL database using SQLite.
Stores persistent entities like Shipments, Routes, and Audit Logs.
"""
import sqlite3
import json

DB_FILE = "nexuspath.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Shipments Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS shipments (
            shipment_id TEXT PRIMARY KEY,
            origin_lat REAL,
            origin_lon REAL,
            dest_lat REAL,
            dest_lon REAL,
            status TEXT,
            route_json TEXT
        )
    ''')
    # Audit Log Table (Decisions/Alerts)
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id TEXT,
            timestamp TEXT,
            event_type TEXT,
            risk_score REAL,
            reason TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_shipment(shipment_data: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO shipments 
        (shipment_id, origin_lat, origin_lon, dest_lat, dest_lon, status, route_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        shipment_data["shipment_id"],
        shipment_data["current_location"]["lat"],
        shipment_data["current_location"]["lon"],
        shipment_data["destination"]["lat"],
        shipment_data["destination"]["lon"],
        shipment_data["status"],
        json.dumps(shipment_data.get("route", []))
    ))
    conn.commit()
    conn.close()

def log_audit_event(shipment_id: str, timestamp: str, event_type: str, risk_score: float, reason: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO audit_logs (shipment_id, timestamp, event_type, risk_score, reason)
        VALUES (?, ?, ?, ?, ?)
    ''', (shipment_id, timestamp, event_type, risk_score, reason))
    conn.commit()
    conn.close()

# Initialize DB on load
init_db()
