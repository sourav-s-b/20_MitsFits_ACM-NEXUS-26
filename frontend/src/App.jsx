import { useState, useEffect, useRef } from "react";
import {
  MapContainer, TileLayer, Marker, Polyline, useMap, Tooltip
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const API = "http://127.0.0.1:8000";

// ── Fix the default Leaflet icon path (Vite asset issue) ──
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Custom truck icon
const truckIcon = new L.DivIcon({
  html: `<div style="
    width:28px;height:28px;border-radius:50%;
    background:linear-gradient(135deg,#6366f1,#22d3ee);
    border:2px solid rgba(255,255,255,0.3);
    display:flex;align-items:center;justify-content:center;
    font-size:14px;box-shadow:0 0 12px rgba(99,102,241,0.7);
  ">🚛</div>`,
  className: "",
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

// Destination icon
const destIcon = new L.DivIcon({
  html: `<div style="
    width:24px;height:24px;border-radius:50%;
    background:rgba(16,185,129,0.2);
    border:2px solid #10b981;
    display:flex;align-items:center;justify-content:center;
    font-size:12px;box-shadow:0 0 10px rgba(16,185,129,0.5);
  ">📍</div>`,
  className: "",
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

// Auto-recentre helper
function RecenterMap({ coords }) {
  const map = useMap();
  const firstRun = useRef(true);
  useEffect(() => {
    if (!coords) return;
    if (firstRun.current) {
      map.setView([coords.lat, coords.lon], 7);
      firstRun.current = false;
    }
  }, [coords]);
  return null;
}

// ── Risk colour helper ──
function riskColor(score) {
  if (score > 0.6) return "#ef4444";
  if (score > 0.4) return "#f59e0b";
  return "#10b981";
}

function statusBadgeClass(status) {
  if (status === "HIGH RISK")  return "badge-high";
  if (status === "WARNING")    return "badge-warning";
  if (status === "REROUTED")   return "badge-rerouted";
  return "badge-safe";
}

function alertClass(severity) {
  if (severity === "HIGH RISK") return "alert-high";
  if (severity === "WARNING")   return "alert-warning";
  if (severity === "SAFE")      return "alert-safe";
  return "alert-reroute";
}

// ── Animated SVG risk ring ──
function RiskRing({ score }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - score);
  const color = riskColor(score);
  return (
    <div className="risk-ring">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={r} className="risk-ring-track" />
        <circle
          cx="36" cy="36" r={r}
          className="risk-ring-fill"
          stroke={color}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="risk-ring-label" style={{ color }}>
        {Math.round(score * 100)}%
      </div>
    </div>
  );
}

// ═══════════════════════════════════
// Main App
// ═══════════════════════════════════
export default function App() {
  const [shipment, setShipment]       = useState(null);
  const [reroutes, setReroutes]       = useState([]);
  const [recommended, setRecommended] = useState(null);
  const [selected, setSelected]       = useState(null);
  const [loading, setLoading]         = useState(true);
  const [rerouteLoading, setRerouteLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);

  // ── Poll /state every 3 s ──
  useEffect(() => {
    const fetchState = async () => {
      try {
        const res  = await fetch(`${API}/state`);
        const data = await res.json();
        setShipment(data);
        setLoading(false);
      } catch (e) {
        console.error("State fetch error:", e);
      }
    };
    fetchState();
    const id = setInterval(fetchState, 3000);
    return () => clearInterval(id);
  }, []);

  // ── POST /event (Inject Risk) ──
  const handleInjectRisk = async () => {
    await fetch(`${API}/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "traffic_spike" }),
    });
  };

  // ── GET /reroute ──
  const handleGetReroute = async () => {
    setRerouteLoading(true);
    try {
      const res  = await fetch(`${API}/reroute`);
      const data = await res.json();
      setReroutes(data.options || []);
      setRecommended(data.recommended || null);
      setSelected(data.recommended || null);
    } catch (e) {
      console.error("Reroute fetch error:", e);
    } finally {
      setRerouteLoading(false);
    }
  };

  // ── POST /confirm-reroute ──
  const handleConfirmReroute = async () => {
    if (!selected) return;
    setConfirmLoading(true);
    try {
      await fetch(`${API}/confirm-reroute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ route_id: selected }),
      });
      setReroutes([]);
      setSelected(null);
      setRecommended(null);
    } catch (e) {
      console.error("Confirm reroute error:", e);
    } finally {
      setConfirmLoading(false);
    }
  };

  // ── POST /reset ──
  const handleReset = async () => {
    await fetch(`${API}/reset`, { method: "POST" });
    setReroutes([]);
    setSelected(null);
    setRecommended(null);
  };

  if (loading || !shipment) {
    return (
      <div className="nexus-loading">
        <div className="nexus-spinner" />
        <p>Connecting to NexusPath live feed…</p>
      </div>
    );
  }

  // Polylines
  const mainRoutePoints = (shipment.route || []).map(p => [p.lat, p.lon]);
  const currentPos = [shipment.current_location.lat, shipment.current_location.lon];
  const destPos    = [shipment.destination.lat, shipment.destination.lon];

  const rColor = riskColor(shipment.risk_score);

  // Ghost alt route — the NON-selected option's polyline
  const altRoute = reroutes.find(r => r.id !== selected);
  const altPoints = altRoute ? altRoute.polyline.map(p => [p.latitude ?? p.lat, p.longitude ?? p.lon]) : [];

  // Selected route polyline
  const selRoute = reroutes.find(r => r.id === selected);
  const selPoints = selRoute ? selRoute.polyline.map(p => [p.latitude ?? p.lat, p.longitude ?? p.lon]) : [];

  return (
    <div className="nexus-shell">

      {/* ── Header ── */}
      <header className="nexus-header">
        <div className="nexus-logo">
          <div className="nexus-logo-dot" />
          NexusPath
        </div>
        <div className="nexus-header-meta">
          <span>SHP: <span>{shipment.shipment_id}</span></span>
          <span>ROUTE IDX: <span>{shipment.route_index ?? "—"}</span></span>
          <span>ETA: <span>{shipment.eta ?? "—"} min</span></span>
        </div>
      </header>

      <div className="nexus-main">

        {/* ══ MAP ══ */}
        <div className="nexus-map-pane">
          <MapContainer center={currentPos} zoom={7} style={{ height: "100%", width: "100%" }} zoomControl={false}>
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            />

            {/* Main route — colour by risk */}
            {mainRoutePoints.length > 0 && (
              <Polyline
                positions={mainRoutePoints}
                color={rColor}
                weight={4}
                opacity={0.75}
              />
            )}

            {/* Ghost alternate route (dashed cyan) */}
            {altPoints.length > 0 && (
              <Polyline
                positions={altPoints}
                color="#22d3ee"
                weight={3}
                opacity={0.5}
                dashArray="8 6"
              />
            )}

            {/* Selected reroute (solid cyan) */}
            {selPoints.length > 0 && (
              <Polyline
                positions={selPoints}
                color="#22d3ee"
                weight={4}
                opacity={0.9}
              />
            )}

            {/* Truck marker */}
            <Marker position={currentPos} icon={truckIcon}>
              <Tooltip permanent direction="top" offset={[0, -16]}>
                <span style={{ fontSize: "11px" }}>🚛 {shipment.status}</span>
              </Tooltip>
            </Marker>

            {/* Destination marker */}
            <Marker position={destPos} icon={destIcon} />

            <RecenterMap coords={shipment.current_location} />
          </MapContainer>

          {/* Map overlay legend */}
          <div className="map-overlay">
            <div className="map-tag map-tag-live">
              <div className="map-tag-dot" /> Live Route
            </div>
            {altPoints.length > 0 && (
              <div className="map-tag map-tag-alt">
                <div className="map-tag-dot" /> Alt Route
              </div>
            )}
          </div>
        </div>

        {/* ══ SIDE PANEL ══ */}
        <aside className="nexus-panel">

          {/* Risk gauge */}
          <div className="nexus-card">
            <div className="nexus-card-title">Risk Monitor</div>
            <div className="risk-gauge-wrap">
              <RiskRing score={shipment.risk_score} />
              <div className="risk-info">
                <div className={`risk-status-badge ${statusBadgeClass(shipment.status)}`}>
                  {shipment.status}
                </div>
                <div className="risk-shipment-id">{shipment.shipment_id}</div>
              </div>
            </div>
          </div>

          {/* Signals */}
          <div className="nexus-card">
            <div className="nexus-card-title">Signal Feed</div>

            <div className="signal-row">
              <span className="signal-label">Traffic Delay</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{
                  width: `${Math.min(shipment.signals.traffic_delay / 60 * 100, 100)}%`,
                  background: shipment.signals.traffic_delay > 30 ? "#ef4444" : "#6366f1"
                }} />
              </div>
              <span className="signal-value">{shipment.signals.traffic_delay}m</span>
            </div>

            <div className="signal-row">
              <span className="signal-label">Weather Score</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{
                  width: `${shipment.signals.weather_score * 100}%`,
                  background: shipment.signals.weather_score > 0.6 ? "#f59e0b" : "#10b981"
                }} />
              </div>
              <span className="signal-value">{shipment.signals.weather_score.toFixed(2)}</span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="nexus-card">
            <div className="nexus-card-title">Actions</div>
            <div className="nexus-btn-row" style={{ marginBottom: 8 }}>
              <button id="btn-inject-risk" className="nexus-btn btn-danger" onClick={handleInjectRisk}>
                ⚡ Inject Risk
              </button>
              <button
                id="btn-get-reroute"
                className={`nexus-btn btn-cyan ${rerouteLoading ? "btn-loading" : ""}`}
                onClick={handleGetReroute}
                disabled={rerouteLoading}
              >
                {rerouteLoading ? "…" : "🛰 Get Reroute"}
              </button>
            </div>
            <div className="nexus-btn-row">
              <button id="btn-reset" className="nexus-btn btn-ghost" onClick={handleReset}>
                ↺ Reset
              </button>
            </div>
          </div>

          {/* Reroute options */}
          {reroutes.length > 0 && (
            <div className="nexus-card">
              <div className="nexus-card-title">Route Options</div>
              <div className="route-options-grid">
                {reroutes.map(r => (
                  <div
                    key={r.id}
                    id={`route-option-${r.id}`}
                    className={`route-card 
                      ${selected === r.id ? "selected" : ""}
                      ${r.id === recommended ? "recommended-badge" : ""}
                    `}
                    onClick={() => setSelected(r.id)}
                  >
                    <div className="route-card-id">{r.id.toUpperCase()}</div>
                    <div className="route-card-stats">
                      <div>
                        <span className="route-stat">{r.travel_time_min}</span>
                        <span className="route-stat-unit">min</span>
                      </div>
                      <div>
                        <span className="route-stat">{r.distance_km}</span>
                        <span className="route-stat-unit">km</span>
                      </div>
                    </div>
                    {r.reason && <div className="route-reason">↳ {r.reason}</div>}
                  </div>
                ))}
              </div>
              <button
                id="btn-confirm-reroute"
                className={`nexus-btn btn-green ${confirmLoading ? "btn-loading" : ""}`}
                style={{ width: "100%" }}
                onClick={handleConfirmReroute}
                disabled={!selected || confirmLoading}
              >
                {confirmLoading ? "Confirming…" : `✓ Accept ${selected ?? ""}`}
              </button>
            </div>
          )}

          {/* Alert feed */}
          <div className="nexus-card" style={{ flex: 1 }}>
            <div className="nexus-card-title">Alert Feed</div>
            {(!shipment.alerts || shipment.alerts.length === 0) ? (
              <div className="empty-state">No active alerts</div>
            ) : (
              <div className="alert-feed">
                {[...shipment.alerts].reverse().map((alert, i) => (
                  <div key={i} className={`alert-item ${alertClass(alert.severity)}`}>
                    <div className="alert-header">
                      <span className="alert-severity" style={{ color: riskColor(alert.risk_score) }}>
                        {alert.severity}
                      </span>
                      <span className="alert-time">{alert.timestamp}</span>
                    </div>
                    <div className="alert-reason">{alert.reason}</div>
                    <div className="alert-score">Risk: {Math.round(alert.risk_score * 100)}%</div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </aside>
      </div>
    </div>
  );
}