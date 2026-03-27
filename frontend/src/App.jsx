import { useState, useEffect, useRef } from "react";
import {
  MapContainer, TileLayer, Marker, Polyline, useMap, Tooltip
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
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
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
  if (status === "HIGH RISK")  return "badge-high";
  if (status === "WARNING")    return "badge-warning";
  if (status === "REROUTED")   return "badge-rerouted";
  return "badge-safe";
}
function aiLevelClass(level) {
  if (level === "CRITICAL") return "ai-critical";
  if (level === "HIGH")     return "ai-high";
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
        <li className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>
          📦 Delivery History
        </li>
        <li className={activeTab === 'account' ? 'active' : ''} onClick={() => setActiveTab('account')}>
          👤 My Account
        </li>
      </ul>
      <div className="sidebar-footer">
        Tracking: <br /><b style={{color: 'white'}}>{currentShipmentId}</b>
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
                <div className="signal-bar-fill" style={{ width: `${Math.min((shipment.signals?.traffic_delay||0)/60*100, 100)}%`, background: shipment.signals?.traffic_delay > 30 ? "#ef4444" : "#6366f1" }} />
              </div>
              <span className="signal-value">{shipment.signals?.traffic_delay||0}m</span>
            </div>
            <div className="signal-row">
              <span className="signal-label">Weather Score</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{ width: `${(shipment.signals?.weather_score||0)*100}%`, background: (shipment.signals?.weather_score||0)>0.6 ? "#f59e0b" : "#10b981" }} />
              </div>
              <span className="signal-value">{parseFloat(shipment.signals?.weather_score||0).toFixed(2)}</span>
            </div>
          </div>

          <div className="nexus-card">
            <div className="nexus-card-title">Operations</div>
            <div className="nexus-btn-row">
              <button className="nexus-btn btn-danger" onClick={() => fetch(`${API}/simulate-storm`, {method: 'POST'})}>🌩 Simulate Storm</button>
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
              <button className="nexus-btn btn-green" style={{width:'100%', marginTop:'8px'}} 
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

  // ══════════════════════════════════
  // RENDER: FLEET OVERVIEW TAB
  // ══════════════════════════════════
  const FleetTab = () => {
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
                  <td><span className={`risk-status-badge ${statusBadgeClass(s.status)}`} style={{fontSize:'11px', padding: '4px 8px'}}>{s.status}</span></td>
                  <td style={{ color: riskColor(s.risk_score), fontWeight: 'bold' }}>{Math.round(s.risk_score * 100)}%</td>
                  <td>
                    <button className="nexus-btn btn-ghost" onClick={() => handleSelectShipment(s.shipment_id)}>
                      Track Live
                    </button>
                  </td>
                </tr>
              ))}
              {fleet.length === 0 && <tr><td colSpan="4" style={{textAlign:'center', color: '#888'}}>No active shipments.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // ══════════════════════════════════
  // RENDER: NOTIFICATIONS / HISTORY TAB
  // ══════════════════════════════════
  const HistoryTab = () => {
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
          {history.length === 0 && <p style={{color: '#888'}}>No audit logs found for this shipment.</p>}
          {history.map((log, i) => (
            <div key={i} className="timeline-item">
              <div className="timeline-time">{log.timestamp}</div>
              <div className="timeline-content">
                <div className="timeline-title" style={{color: riskColor(log.risk_score)}}>
                  {log.event_type.toUpperCase()} (Risk: {Math.round(log.risk_score*100)}%)
                </div>
                <div className="timeline-desc">{log.reason}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ══════════════════════════════════
  // RENDER: ACCOUNT PROFILE TAB
  // ══════════════════════════════════
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
          <button className="nexus-btn btn-danger" style={{marginTop:'15px', width: '100%'}}>Sign Out</button>
        </div>
      </div>
    );
  };

  // MAIN LAYOUT WRAPPER
  return (
    <div className="nexus-shell with-sidebar">
      {renderSidebar()}
      <main className="nexus-main-content">
        {activeTab === 'map' && renderMapTab()}
        {activeTab === 'fleet' && <FleetTab />}
        {activeTab === 'history' && <HistoryTab />}
        {activeTab === 'account' && <AccountTab />}
      </main>
    </div>
  );
}