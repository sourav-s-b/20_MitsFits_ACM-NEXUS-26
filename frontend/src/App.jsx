import { useState, useEffect, useRef } from "react";
import {
  MapContainer, TileLayer, Marker, Polyline, Circle, useMap, Tooltip
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const BASE_URL = "http://127.0.0.1:8000";
const WS_BASE_URL = "ws://127.0.0.1:8000";

// ── Fix Leaflet icon paths for Vite ──
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Icons
const truckIcon = new L.DivIcon({
  html: `<div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#22d3ee);border:2px solid rgba(255,255,255,0.3);display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 12px rgba(99,102,241,0.7);">🚛</div>`,
  className: "", iconSize: [28, 28], iconAnchor: [14, 14],
});
const destIcon = new L.DivIcon({
  html: `<div style="width:24px;height:24px;border-radius:50%;background:rgba(16,185,129,0.2);border:2px solid #10b981;display:flex;align-items:center;justify-content:center;font-size:12px;box-shadow:0 0 10px rgba(16,185,129,0.5);">📍</div>`,
  className: "", iconSize: [24, 24], iconAnchor: [12, 12],
});

// Component: Auto-recenter Map
function RecenterMap({ coords }) {
  const map = useMap();
  const firstRun = useRef(true);
  useEffect(() => {
    if (!coords) return;
    if (firstRun.current) {
      map.setView([coords.lat, coords.lon], 7);
      firstRun.current = false;
    }
  }, [coords, map]);
  return null;
}

// Helpers
function riskColor(score) {
  if (score > 0.6) return "#ef4444";
  if (score > 0.4) return "#f59e0b";
  return "#10b981";
}
function statusBadgeClass(status) {
  if (status === "HIGH RISK") return "badge-high";
  if (status === "WARNING") return "badge-warning";
  if (status === "REROUTED") return "badge-rerouted";
  return "badge-safe";
}
function aiLevelClass(level) {
  if (level === "CRITICAL") return "ai-critical";
  if (level === "HIGH") return "ai-high";
  if (level === "MODERATE") return "ai-moderate";
  return "ai-safe";
}

// Animated Risk Ring
function RiskRing({ score }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - score);
  const color = riskColor(score);
  return (
    <div className="risk-ring">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={r} className="risk-ring-track" />
        <circle cx="36" cy="36" r={r} className="risk-ring-fill" stroke={color} strokeDasharray={circ} strokeDashoffset={offset} style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
      </svg>
      <div className="risk-ring-label" style={{ color }}>{Math.round(score * 100)}%</div>
    </div>
  );
}

// ==========================================
// SEPARATE TAB COMPONENTS
// ==========================================

const FleetTab = ({ onSelectShipment, statusBadgeClass, riskColor }) => {
  const [fleet, setFleet] = useState([]);

  useEffect(() => {
    fetch(`${BASE_URL}/shipments`).then(r => r.json()).then(setFleet).catch(console.error);
  }, []);

  return (
    <div className="tab-pane">
      <h1>🚛 Fleet Management</h1>
      <p>Monitor all active deliveries across the NexusPath network.</p>
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Shipment ID</th>
              <th>Status</th>
              <th>Risk Score</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {fleet.map(s => (
              <tr key={s.shipment_id}>
                <td className="mono">{s.shipment_id}</td>
                <td><span className={`risk-status-badge ${statusBadgeClass(s.status)}`} style={{ fontSize: '11px', padding: '4px 8px' }}>{s.status}</span></td>
                <td style={{ color: riskColor(s.risk_score), fontWeight: 'bold' }}>{Math.round(s.risk_score * 100)}%</td>
                <td>
                  <button className="nexus-btn btn-ghost" onClick={() => onSelectShipment(s.shipment_id)}>
                    Track Live
                  </button>
                </td>
              </tr>
            ))}
            {fleet.length === 0 && <tr><td colSpan="4" style={{ textAlign: 'center', color: '#888' }}>No active shipments.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const HistoryTab = ({ currentShipmentId, riskColor }) => {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetch(`${BASE_URL}/shipments/${currentShipmentId}/history`)
      .then(r => r.json()).then(d => setHistory(d.history)).catch(console.error);
  }, [currentShipmentId]);

  return (
    <div className="tab-pane">
      <h1>📦 Delivery Audit Engine ({currentShipmentId})</h1>
      <p>Permanent ledger of AI intelligence events and interventions.</p>
      <div className="timeline">
        {history.length === 0 && <p style={{ color: '#888' }}>No audit logs found for this shipment.</p>}
        {history.map((log, i) => (
          <div key={i} className="timeline-item">
            <div className="timeline-time">{log.timestamp}</div>
            <div className="timeline-content">
              <div className="timeline-title" style={{ color: riskColor(log.risk_score) }}>
                {log.event_type.toUpperCase()} (Risk: {Math.round(log.risk_score * 100)}%)
              </div>
              <div className="timeline-desc">{log.reason}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AccountTab = () => {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch(`${BASE_URL}/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "admin", password: "password" })
    }).then(r => r.json()).then(setUser).catch(console.error);
  }, []);

  if (!user) return <div className="tab-pane"><div className="nexus-spinner"></div></div>;

  return (
    <div className="tab-pane">
      <h1>👤 Global Dispatcher Profile</h1>
      <div className="nexus-card" style={{ maxWidth: '400px', marginTop: '20px' }}>
        <div className="nexus-card-title">Personnel File</div>
        <p><b>Name:</b> {user.name}</p>
        <p><b>Role:</b> {user.role}</p>
        <p><b>Auth Token:</b> <code className="mono">{user.token.slice(0, 8)}...</code></p>
        <button className="nexus-btn btn-danger" style={{ marginTop: '15px', width: '100%' }}>Sign Out</button>
      </div>
    </div>
  );
};

const ScheduleTab = ({ BASE_URL, onDispatched }) => {
  const [shipmentId, setShipmentId] = useState(`SHP-${Math.floor(Math.random() * 9999)}`);
  const [origin, setOrigin] = useState("19.0760,72.8777");
  const [target, setTarget] = useState("18.5204,73.8567");
  const [loading, setLoading] = useState(false);

  const presets = [
    { label: "Kochi → Bangalore", o: "9.9312,76.2673", d: "12.9716,77.5946" },
    { label: "Mumbai → Pune", o: "19.0760,72.8777", d: "18.5204,73.8567" },
    { label: "Delhi → Jaipur", o: "28.6139,77.2090", d: "26.9124,75.7873" }
  ];

  const handleDispatch = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await fetch(`${BASE_URL}/shipments/${shipmentId}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin, destination: target })
      });
      onDispatched(shipmentId);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div className="tab-pane">
      <h1>➕ Dispatch Shipment</h1>
      <p>Schedule a new transport routing via the NexusPath logistics engine.</p>

      <div className="nexus-card" style={{ maxWidth: '500px', padding: '24px' }}>
        <form onSubmit={handleDispatch} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>SHIPMENT ID</label>
            <input type="text" value={shipmentId} onChange={e => setShipmentId(e.target.value)} style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>ORIGIN (Lat,Lon)</label>
            <input type="text" value={origin} onChange={e => setOrigin(e.target.value)} style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>DESTINATION (Lat,Lon)</label>
            <input type="text" value={target} onChange={e => setTarget(e.target.value)} style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }} />
          </div>

          <div style={{ display: 'flex', gap: '8px', margin: '10px 0', flexWrap: 'wrap' }}>
            {presets.map(p => (
              <button type="button" key={p.label} className="map-tag map-tag-alt" style={{ cursor: 'pointer' }} onClick={() => { setOrigin(p.o); setTarget(p.d); }}>
                {p.label}
              </button>
            ))}
          </div>

          <button type="submit" className="nexus-btn btn-green" disabled={loading} style={{ marginTop: '16px', padding: '14px' }}>
            {loading ? "INITIALIZING ROUTE..." : "🚀 DISPATCH TRUCK"}
          </button>
        </form>
      </div>
    </div>
  );
};

const AnalyticsTab = ({ BASE_URL }) => {
  const [fleet, setFleet] = useState([]);
  useEffect(() => {
    fetch(`${BASE_URL}/shipments`).then(r => r.json()).then(setFleet).catch(console.error);
  }, [BASE_URL]);

  const totalDelays = fleet.reduce((acc, s) => acc + (s.signals?.traffic_delay || 0), 0);
  const criticalCount = fleet.filter(s => s.status === "HIGH RISK").length;
  const avgRisk = fleet.length ? (fleet.reduce((acc, s) => acc + s.risk_score, 0) / fleet.length * 100).toFixed(1) : 0;

  return (
    <div className="tab-pane">
      <h1>📊 Delivery Estimations / Analytics</h1>
      <p>Live predictive analytics against baseline models.</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '40px' }}>
        <div className="nexus-card">
          <div className="nexus-card-title">Total Fleet Delay</div>
          <div style={{ fontSize: '32px', color: '#f59e0b', fontWeight: 'bold' }}>{totalDelays} <span style={{ fontSize: '16px' }}>min</span></div>
        </div>
        <div className="nexus-card" style={{ borderColor: criticalCount > 0 ? '#ef4444' : '' }}>
          <div className="nexus-card-title">Critical Shipments</div>
          <div style={{ fontSize: '32px', color: criticalCount > 0 ? '#ef4444' : '#10b981', fontWeight: 'bold' }}>{criticalCount}</div>
        </div>
        <div className="nexus-card">
          <div className="nexus-card-title">Average Fleet Risk</div>
          <div style={{ fontSize: '32px', color: '#6366f1', fontWeight: 'bold' }}>{avgRisk}%</div>
        </div>
      </div>

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Shipment ID</th>
              <th>System Status</th>
              <th>TomTom Traffic Delay</th>
              <th>Estimated Pushback</th>
            </tr>
          </thead>
          <tbody>
            {fleet.map(s => (
              <tr key={s.shipment_id}>
                <td className="mono">{s.shipment_id}</td>
                <td style={{ color: s.status === "SAFE" ? "#10b981" : "#ef4444" }}>{s.status}</td>
                <td><span style={{ color: s.signals?.traffic_delay > 15 ? '#ef4444' : '#fff' }}>{s.signals?.traffic_delay || 0} mins</span></td>
                <td>+ {(s.signals?.traffic_delay || 0) + Math.floor((s.signals?.weather_score || 0) * 20)} mins impact</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==========================================
// MAIN APP COMPONENT
// ==========================================
export default function App() {
  // Navigation State
  const [activeTab, setActiveTab] = useState("map"); // 'map', 'fleet', 'history', 'account'
  const [currentShipmentId, setCurrentShipmentId] = useState("SHP001");

  // Map/Live State
  const [shipment, setShipment] = useState(null);
  const [reroutes, setReroutes] = useState([]);
  const [recommended, setRecommended] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connError, setConnError] = useState(false);
  const started = useRef(false);

  // APIs based on current selection
  const API = `${BASE_URL}/shipments/${currentShipmentId}`;
  const WS_URL = `${WS_BASE_URL}/ws/${currentShipmentId}`;

  // ── WebSocket Connection for Live Map ──
  useEffect(() => {
    let ws;
    let reconnectTimer;
    // Reset tracker state smoothly
    setLoading(true);
    started.current = false;
    setReroutes([]);

    const connectWS = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnError(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setShipment(data);
          setLoading(false);
          setConnError(false);

          if (!started.current && (!data.route || data.route.length === 0)) {
            started.current = true;
            fetch(`${API}/start`, { method: "POST" }).catch(console.error);
          }

          if (data.reroute_options && data.reroute_options.length > 0) {
            setReroutes(prev => {
              if (prev.length === 0) {
                const rec = data.reroute_options.find(r => r.recommended);
                if (rec) { setRecommended(rec.id); setSelected(rec.id); }
                return data.reroute_options;
              }
              return prev;
            });
          }
        } catch (e) { console.error("WS Parse Error:", e); }
      };
      ws.onclose = () => {
        setConnError(true);
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWS, 3000);
      };
      ws.onerror = () => ws.close();
    };

    fetch(`${API}/state`).then(res => res.json()).then(data => {
      setShipment(data);
      setLoading(false);
    }).catch(() => setConnError(true));

    connectWS();
    return () => { if (ws) ws.close(); clearTimeout(reconnectTimer); };
  }, [currentShipmentId, API, WS_URL]);

  // Handle Tab Switch Actions
  const handleSelectShipment = (id) => {
    setCurrentShipmentId(id);
    setActiveTab("map");
  };

  // ══════════════════════════════════
  // RENDER: SIDEBAR NAVIGATION
  // ══════════════════════════════════
  const renderSidebar = () => (
    <nav className="dashboard-sidebar">
      <div className="sidebar-logo">
        <div className="nexus-logo-dot" /> N E X U S
      </div>
      <ul className="sidebar-nav">
        <li className={activeTab === 'map' ? 'active' : ''} onClick={() => setActiveTab('map')}>
          🗺️ Live Tracking
        </li>
        <li className={activeTab === 'fleet' ? 'active' : ''} onClick={() => setActiveTab('fleet')}>
          🚛 Fleet Logistics
        </li>
        <li className={activeTab === 'schedule' ? 'active' : ''} onClick={() => setActiveTab('schedule')}>
          ➕ Schedule Shipment
        </li>
        <li className={activeTab === 'analytics' ? 'active' : ''} onClick={() => setActiveTab('analytics')}>
          📊 Delivery Estimations
        </li>
        <li className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>
          📦 Delivery History
        </li>
        <li className={activeTab === 'account' ? 'active' : ''} onClick={() => setActiveTab('account')}>
          👤 My Account
        </li>
      </ul>
      <div className="sidebar-footer">
        Tracking: <br /><b style={{ color: 'white' }}>{currentShipmentId}</b>
      </div>
    </nav>
  );

  // ══════════════════════════════════
  // RENDER: LIVE MAP TAB (Original View context)
  // ══════════════════════════════════
  const renderMapTab = () => {
    if (connError) {
      return (
        <div className="nexus-loading">
          <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
          <p style={{ color: "var(--accent-red)", fontWeight: 600 }}>Backend Unreachable</p>
        </div>
      );
    }
    if (loading || !shipment) {
      return <div className="nexus-loading"><div className="nexus-spinner" /></div>;
    }

    const mainRoutePoints = (shipment.route || []).map(p => [p.lat, p.lon]);
    const currentPos = [shipment.current_location.lat, shipment.current_location.lon];
    const destPos = shipment.destination ? [shipment.destination.lat, shipment.destination.lon] : currentPos;
    const rColor = riskColor(shipment.risk_score);
    const activeReroutes = reroutes.length > 0 ? reroutes : (shipment.reroute_options || []);

    const altRoute = activeReroutes.find(r => r.id !== selected);
    const altPoints = altRoute ? altRoute.polyline.map(p => [p.latitude ?? p.lat, p.longitude ?? p.lon]) : [];

    const selRoute = activeReroutes.find(r => r.id === selected);
    const selPoints = selRoute ? selRoute.polyline.map(p => [p.latitude ?? p.lat, p.longitude ?? p.lon]) : [];

    const weather = shipment.weather || {};

    return (
      <div className="tab-map">
        <div className="nexus-map-pane" style={{ position: "relative" }}>
          <MapContainer center={currentPos} zoom={7} style={{ height: "100%", width: "100%" }} zoomControl={false}>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
            {mainRoutePoints.length > 0 && <Polyline positions={mainRoutePoints} color={rColor} weight={4} opacity={0.75} />}
            {altPoints.length > 0 && <Polyline positions={altPoints} color="#22d3ee" weight={3} opacity={0.5} dashArray="8 6" />}
            {selPoints.length > 0 && <Polyline positions={selPoints} color="#22d3ee" weight={4} opacity={0.9} />}

            <Marker position={currentPos} icon={truckIcon}>
              <Tooltip permanent direction="top" offset={[0, -16]}>
                <span style={{ fontSize: "11px" }}>{currentShipmentId}: {shipment.status}</span>
              </Tooltip>
            </Marker>

            {(shipment.status === "HIGH RISK" || shipment.status === "WARNING" || shipment.status === "CRITICAL") && (
              <Circle
                center={currentPos}
                radius={shipment.status === "HIGH RISK" ? 25000 : 12000}
                pathOptions={{
                  color: shipment.status === "WARNING" ? '#f59e0b' : '#ef4444',
                  fillColor: shipment.status === "WARNING" ? '#f59e0b' : '#ef4444',
                  fillOpacity: 0.15,
                  weight: 2,
                  dashArray: "10 5"
                }}
              />
            )}

            <Marker position={destPos} icon={destIcon} />
            <RecenterMap coords={shipment.current_location} />
          </MapContainer>

          <div className="map-overlay">
            <div className="map-tag map-tag-live"><div className="map-tag-dot" /> Live Route</div>
            {weather.temp_c && <div className="map-tag" style={{ background: "rgba(99,102,241,0.12)", borderColor: "rgba(99,102,241,0.4)" }}>🌤 {weather.description} ({weather.temp_c}°C)</div>}
          </div>
        </div>

        <aside className="nexus-panel">
          <div className="nexus-card">
            <div className="nexus-card-title">Risk Monitor</div>
            <div className="risk-gauge-wrap">
              <RiskRing score={shipment.risk_score} />
              <div className="risk-info">
                <div className={`risk-status-badge ${statusBadgeClass(shipment.status)}`}>{shipment.status}</div>
                <div className="risk-shipment-id">{currentShipmentId} ETA: {shipment.eta || "--"}m</div>
              </div>
            </div>
          </div>

          <div className="nexus-card">
            <div className="nexus-card-title">Telemetry Overview</div>
            <div className="signal-row">
              <span className="signal-label">Traffic Delay</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{
                  width: `${Math.min(shipment.signals.traffic_delay / 60 * 100, 100)}%`,
                  background: shipment.signals.traffic_delay > 30 ? "#ef4444" : "#6366f1"
                }} />
              </div>
              <span className="signal-value">{shipment.signals?.traffic_delay || 0}m</span>
            </div>
            <div className="signal-row">
              <span className="signal-label">Weather Score</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{
                  width: `${(shipment.signals.weather_score || 0) * 100}%`,
                  background: (shipment.signals.weather_score || 0) > 0.6 ? "#f59e0b" : "#10b981"
                }} />
              </div>
              <span className="signal-value">{parseFloat(shipment.signals?.weather_score || 0).toFixed(2)}</span>
            </div>
          </div>

          <div className="nexus-card">
            <div className="nexus-card-title">Operations</div>
            <div className="nexus-btn-row">
              <button className="nexus-btn btn-danger" onClick={() => fetch(`${API}/simulate-storm`, { method: 'POST' })}>🌩 Simulate Storm</button>
              <button className="nexus-btn btn-cyan" onClick={() => fetch(`${API}/pipeline`)}>⚡ Run Pipeline</button>
            </div>
          </div>

          {activeReroutes.length > 0 && (
            <div className="nexus-card">
              <div className="nexus-card-title">Reroute Available</div>
              <div className="route-options-grid">
                {activeReroutes.map(r => (
                  <div key={r.id} className={`route-card ${selected === r.id ? "selected" : ""}`} onClick={() => setSelected(r.id)}>
                    <div className="route-card-id">{r.id.toUpperCase()}</div>
                  </div>
                ))}
              </div>
              <button className="nexus-btn btn-green" style={{ width: '100%', marginTop: '8px' }}
                onClick={() => {
                  fetch(`${API}/confirm-reroute`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ route_id: selected }) })
                  setReroutes([]); setSelected(null);
                }}>Confirm Route</button>
            </div>
          )}
        </aside>
      </div>
    );
  };

  // MAIN LAYOUT WRAPPER
  return (
    <div className="nexus-shell with-sidebar">
      {renderSidebar()}
      <main className="nexus-main-content">
        {activeTab === 'map' && renderMapTab()}
        {activeTab === 'fleet' && <FleetTab onSelectShipment={handleSelectShipment} statusBadgeClass={statusBadgeClass} riskColor={riskColor} />}
        {activeTab === 'schedule' && <ScheduleTab BASE_URL={BASE_URL} onDispatched={handleSelectShipment} />}
        {activeTab === 'analytics' && <AnalyticsTab BASE_URL={BASE_URL} />}
        {activeTab === 'history' && <HistoryTab currentShipmentId={currentShipmentId} riskColor={riskColor} />}
        {activeTab === 'account' && <AccountTab />}
      </main>
    </div>
  );
}