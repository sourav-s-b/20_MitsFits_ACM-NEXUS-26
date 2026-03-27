shipment = {
    "shipment_id": "SHP001",
    "current_location": {"lat": 9.9312, "lon": 76.2673},
    "destination":      {"lat": 12.9716, "lon": 77.5946},
    "route":            [],
    "route_index":      0,
    "eta":              180,
    "checkpoints":      [],

    # ── Raw signals ──
    "signals": {
        "traffic_delay":  0,
        "weather_score":  0.0,
    },

    # ── Live weather telemetry (from OpenWeatherMap) ──
    "weather": {
        "description":    "clear sky",
        "temp_c":         28.0,
        "humidity":       60,
        "visibility_km":  10.0,
        "wind_kph":       12.0,
        "score":          0.0,       # normalised 0-1
    },

    # ── Risk state ──
    "risk_score":   0.0,
    "status":       "SAFE",
    "active_route": "A",
    "alerts":       [],
    "reroute_options": [],

    # ── AI / Person 2 output ──
    "ai_reason":  None,
    "ai_level":   None,          # "SAFE" | "MODERATE" | "HIGH" | "CRITICAL"

    # ── Pipeline metadata ──
    "pipeline_last_run": None,
    "shadow_route_ready": False,
}