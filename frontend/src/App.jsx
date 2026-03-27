import { useState, useEffect, useRef, useMemo } from "react";
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

const FleetTab = ({ fleet, onSelectShipment, statusBadgeClass, riskColor }) => {
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

const AnalyticsTab = ({ fleet }) => {
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
// COLLISION AVOIDANCE TAB
// ==========================================
const CollisionTab = ({ fleet }) => {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lookahead, setLookahead] = useState(3);
  const [safeDist, setSafeDist] = useState(1.0);
  const [autoMode, setAutoMode] = useState(false);
  const autoRef = useRef(null);

  // Build payload from live fleet data
  const buildPayload = () => {
    const trucks = fleet
      .filter(f => f.current_location)
      .map(f => ({
        shipment_id: f.shipment_id,
        lat: f.current_location.lat ?? f.current_location.latitude,
        lon: f.current_location.lon ?? f.current_location.longitude,
        speed_kmh: 60,
        // Assign a demo heading based on shipment_id hash for visual variety
        heading_deg: (f.shipment_id.charCodeAt(f.shipment_id.length - 1) * 37) % 360,
      }));
    return { trucks, lookahead_minutes: lookahead, safe_distance_km: safeDist };
  };

  const runPrediction = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/collision/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      console.error("Collision predict failed:", e);
    }
    setLoading(false);
  };

  // Auto-scan every 5s
  useEffect(() => {
    if (autoMode) {
      runPrediction();
      autoRef.current = setInterval(runPrediction, 5000);
    } else {
      clearInterval(autoRef.current);
    }
    return () => clearInterval(autoRef.current);
  }, [autoMode, fleet, lookahead, safeDist]);

  const severityColor = (s) => s === "HIGH" ? "#ef4444" : s === "MODERATE" ? "#f59e0b" : "#22d3ee";

  return (
    <div className="tab-pane">
      <h1>🛡️ Predictive Collision Avoidance</h1>
      <p>Predict inter-truck conflicts 2–5 minutes before they occur and auto-suggest reroutes.</p>

      {/* Controls */}
      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "24px", alignItems: "flex-end" }}>
        <div>
          <label style={{ display: "block", marginBottom: "6px", fontSize: "11px", color: "var(--text-muted)" }}>LOOKAHEAD (min)</label>
          <input type="number" min="1" max="10" value={lookahead}
            onChange={e => setLookahead(Number(e.target.value))}
            style={{ width: "80px", padding: "8px", background: "rgba(0,0,0,0.3)", border: "1px solid var(--border)", color: "white", borderRadius: "4px" }} />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: "6px", fontSize: "11px", color: "var(--text-muted)" }}>SAFE DISTANCE (km)</label>
          <input type="number" min="0.1" max="5" step="0.1" value={safeDist}
            onChange={e => setSafeDist(Number(e.target.value))}
            style={{ width: "90px", padding: "8px", background: "rgba(0,0,0,0.3)", border: "1px solid var(--border)", color: "white", borderRadius: "4px" }} />
        </div>
        <button className="nexus-btn btn-cyan" onClick={runPrediction} disabled={loading}>
          {loading ? "⏳ Scanning..." : "⚡ Run Scan"}
        </button>
        <button
          className={`nexus-btn ${autoMode ? "btn-danger" : "btn-green"}`}
          onClick={() => setAutoMode(v => !v)}>
          {autoMode ? "⏹ Stop Auto-Scan" : "🔄 Auto-Scan (5s)"}
        </button>
      </div>

      {/* Fleet summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        <div className="nexus-card">
          <div className="nexus-card-title">Trucks Analyzed</div>
          <div style={{ fontSize: "28px", fontWeight: "bold", color: "#6366f1" }}>
            {result ? result.total_trucks_analyzed : fleet.filter(f => f.current_location).length}
          </div>
        </div>
        <div className="nexus-card" style={{ borderColor: result && !result.all_clear ? "#ef4444" : "" }}>
          <div className="nexus-card-title">Collision Risks</div>
          <div style={{ fontSize: "28px", fontWeight: "bold", color: result && !result.all_clear ? "#ef4444" : "#10b981" }}>
            {result ? result.collision_pairs.length : "—"}
          </div>
        </div>
        <div className="nexus-card">
          <div className="nexus-card-title">System Status</div>
          <div style={{
            fontSize: "14px", fontWeight: "bold", marginTop: "6px",
            color: result ? (result.all_clear ? "#10b981" : "#ef4444") : "#888"
          }}>
            {result ? (result.all_clear ? "✅ ALL CLEAR" : "⚠️ RISKS DETECTED") : "Not scanned yet"}
          </div>
        </div>
        <div className="nexus-card">
          <div className="nexus-card-title">Last Scan</div>
          <div style={{ fontSize: "20px", fontWeight: "bold", color: "#22d3ee" }}>
            {result ? result.timestamp : "—"}
          </div>
        </div>
      </div>

      {/* Collision pairs */}
      {result && result.collision_pairs.length === 0 && (
        <div className="nexus-card" style={{ borderColor: "#10b981", background: "rgba(16,185,129,0.05)", textAlign: "center", padding: "32px" }}>
          <div style={{ fontSize: "32px", marginBottom: "8px" }}>✅</div>
          <div style={{ color: "#10b981", fontWeight: "bold", fontSize: "16px" }}>All Clear — No Collision Risks Detected</div>
          <p style={{ color: "#888", marginTop: "8px", fontSize: "13px" }}>
            All {result.total_trucks_analyzed} trucks have safe predicted separations within the {result.lookahead_minutes}-minute window.
          </p>
        </div>
      )}

      {result && result.collision_pairs.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {result.collision_pairs.map((pair, i) => (
            <div key={i} className="nexus-card" style={{ borderColor: severityColor(pair.severity), background: `rgba(${pair.severity === "HIGH" ? "239,68,68" : pair.severity === "MODERATE" ? "245,158,11" : "34,211,238"},0.05)` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
                <div>
                  <div style={{ color: severityColor(pair.severity), fontWeight: "bold", fontSize: "14px", marginBottom: "6px" }}>
                    {pair.severity === "HIGH" ? "🔴" : pair.severity === "MODERATE" ? "🟡" : "🔵"} {pair.severity} RISK — {pair.truck_a} ↔ {pair.truck_b}
                  </div>
                  <div style={{ color: "#ccc", fontSize: "12px", marginBottom: "4px" }}>
                    Current gap: <b style={{ color: "white" }}>{pair.current_distance_km} km</b>
                    &nbsp;→ Predicted in {result.lookahead_minutes}min: <b style={{ color: severityColor(pair.severity) }}>{pair.predicted_distance_km} km</b>
                    &nbsp;(safe: {result.safe_distance_km} km)
                  </div>
                  <div style={{ color: "#22d3ee", fontSize: "12px", marginTop: "6px" }}>
                    💡 {pair.suggested_action}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "28px", fontWeight: "bold", color: severityColor(pair.severity) }}>
                    {Math.round(pair.collision_probability * 100)}%
                  </div>
                  <div style={{ fontSize: "11px", color: "#888" }}>collision prob.</div>
                  <div style={{ fontSize: "11px", color: "#888", marginTop: "4px" }}>
                    Conflict in ~{pair.time_to_conflict_min}min
                  </div>
                </div>
              </div>

              {/* Conflict zone */}
              <div style={{ marginTop: "12px", padding: "8px", background: "rgba(0,0,0,0.3)", borderRadius: "4px", fontSize: "11px", color: "#888", fontFamily: "monospace" }}>
                Conflict zone: {pair.conflict_zone.lat}°N, {pair.conflict_zone.lon}°E
              </div>
            </div>
          ))}
        </div>
      )}

      {!result && (
        <div className="nexus-card" style={{ textAlign: "center", padding: "40px", color: "#888" }}>
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>🛡️</div>
          <p>Click <b style={{ color: "white" }}>Run Scan</b> to analyse current fleet positions for collision risks.</p>
          <p style={{ fontSize: "12px", marginTop: "8px" }}>
            Uses dead-reckoning to predict where each truck will be in {lookahead} minutes.
          </p>
        </div>
      )}
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
  const currentIdRef = useRef(currentShipmentId);

  useEffect(() => {
    currentIdRef.current = currentShipmentId;
  }, [currentShipmentId]);

  // APIs based on current selection
  const API = `${BASE_URL}/shipments/${currentShipmentId}`;
  const WS_URL = `${WS_BASE_URL}/ws/${currentShipmentId}`;

  // Global Fleet State (for drawing all trucks and tabs)
  const [fleet, setFleet] = useState([]);

  useEffect(() => {
    const fetchFleet = () => fetch(`${BASE_URL}/shipments`).then(r => r.json()).then(setFleet).catch(e => console.error("Fleet fetch error:", e));
    fetchFleet();
    const interval = setInterval(fetchFleet, 3000);
    return () => clearInterval(interval);
  }, []);

  // ── WebSocket Connection for Live Map ──
  useEffect(() => {
    let ws;
    let reconnectTimer;
    // Reset tracker state smoothly
    setLoading(true);
    setShipment(null); // Clear previous shipment data immediately
    started.current = false;
    setReroutes([]);

    const connectWS = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnError(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // CRITICAL: Double-check against ref to prevent stale closure updates/glitches
          if (data.shipment_id !== currentIdRef.current) return;

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
        <li className={activeTab === 'collision' ? 'active' : ''} onClick={() => setActiveTab('collision')}>
          🛡️ Collision AI
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

    const mainRoutePoints = (shipment.route || []).map(p => [p.latitude ?? p.lat ?? 0, p.longitude ?? p.lon ?? 0]);

    const currentPos = [shipment.current_location?.lat ?? shipment.current_location?.latitude ?? 0, shipment.current_location?.lon ?? shipment.current_location?.longitude ?? 0];
    const destPos = shipment.destination ? [shipment.destination.lat ?? 0, shipment.destination.lon ?? 0] : currentPos;
    const rColor = riskColor(shipment.risk_score);
    const activeReroutes = reroutes.length > 0 ? reroutes : (shipment.reroute_options || []);

<<<<<<< HEAD
    const altRoute = activeReroutes.find(r => r.id !== selected);
    const altPoints = altRoute ? altRoute.polyline.map(p => [p.latitude ?? p.lat ?? 0, p.longitude ?? p.lon ?? 0]) : [];

=======
>>>>>>> 41a02ee5eaf8543ddb34ee440af4cbfb13762a4e
    const selRoute = activeReroutes.find(r => r.id === selected);
    const selPoints = selRoute ? selRoute.polyline.map(p => [p.latitude ?? p.lat ?? 0, p.longitude ?? p.lon ?? 0]) : [];

    const weather = shipment.weather || {};

    const handleGetReroute = async () => {
      try {
        const res = await fetch(`${API}/reroute`);
        const data = await res.json();
        if (data.routes && data.routes.length > 0) {
          setReroutes(data.routes);
          setSelected(data.routes[0].id);
        }
      } catch (e) {
        console.error("Reroute fetch failed", e);
      }
    };

    return (
      <div className="tab-map">
        <div className="nexus-map-pane" style={{ position: "relative" }}>
          <MapContainer center={currentPos} zoom={7} style={{ height: "100%", width: "100%" }} zoomControl={false}>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
            {mainRoutePoints.length > 0 && <Polyline positions={mainRoutePoints} color={rColor} weight={5} opacity={0.8} />}
            {activeReroutes.map(r => {
              if (r.id === selected) return null;
              const points = r.polyline.map(p => [p.latitude ?? p.lat ?? 0, p.longitude ?? p.lon ?? 0]);
              return <Polyline key={r.id} positions={points} color="#22d3ee" weight={3} opacity={0.4} dashArray="10 10" />;
            })}
            {selPoints.length > 0 && <Polyline positions={selPoints} color="#22d3ee" weight={6} opacity={1.0} dashArray="12 8" />}

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

            {/* Render secondary fleet trucks on the map */}
            {fleet.map(f => {
              if (f.shipment_id === currentShipmentId) return null;
              if (!f.current_location) return null;
              return (
                <Marker key={f.shipment_id} position={[f.current_location.lat ?? f.current_location.latitude, f.current_location.lon ?? f.current_location.longitude]} icon={truckIcon}>
                  <Tooltip direction="top" offset={[0, -16]}>
                    <span style={{ fontSize: "11px" }}>{f.shipment_id}: {f.status}</span>
                  </Tooltip>
                </Marker>
              );
            })}
          </MapContainer>

          <div className="map-overlay">
            <div className="map-tag map-tag-live"><div className="map-tag-dot" /> Live Route</div>
            {weather.temp_c && <div className="map-tag" style={{ background: "rgba(99,102,241,0.12)", borderColor: "rgba(99,102,241,0.4)" }}>🌤 {weather.description} ({weather.temp_c}°C)</div>}
          </div>
        </div>

        <aside className="nexus-panel">
          <div className="nexus-card scale-up">
            <div className="nexus-card-title">Risk Monitor</div>
            <div className="risk-gauge-wrap">
              <RiskRing score={shipment.risk_score} />
              <div className="risk-info">
                <div className={`risk-status-badge ${statusBadgeClass(shipment.status)}`}>{shipment.status}</div>
                <div className="risk-shipment-id">{currentShipmentId} &bull; {shipment.eta || "--"}m</div>
              </div>
            </div>
          </div>

          {shipment.ai_reason && (
            <div className="nexus-card ai-insight-card ripple">
              <div className="nexus-card-title" style={{ color: '#22d3ee', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '16px' }}>🧠</span> AI REASONING / SOP
              </div>
              <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: '1.5', margin: '8px 0' }}>
                {shipment.ai_reason}
              </p>
              {shipment.is_compound && (
                <div className="map-tag" style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: '#ef4444', color: '#ef4444', fontSize: '10px', marginTop: '8px' }}>
                  ⚠️ COMPOUND HAZARD DETECTED
                </div>
              )}
            </div>
          )}

          <div className="nexus-card">
            <div className="nexus-card-title">Telemetry Overview</div>
            <div className="signal-row">
              <span className="signal-label">Traffic Delay</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{
                  width: `${Math.min((shipment.signals?.traffic_delay || 0) / 60 * 100, 100)}%`,
                  background: (shipment.signals?.traffic_delay || 0) > 30 ? "#ef4444" : "#6366f1"
                }} />
              </div>
              <span className="signal-value">{shipment.signals?.traffic_delay || 0}m</span>
            </div>
            <div className="signal-row">
              <span className="signal-label">Weather Score</span>
              <div className="signal-bar-track">
                <div className="signal-bar-fill" style={{
                  width: `${(shipment.signals?.weather_score || 0) * 100}%`,
                  background: (shipment.signals?.weather_score || 0) > 0.6 ? "#f59e0b" : "#10b981"
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

          {shipment.status === 'HIGH RISK' && (activeReroutes.length === 0) && shipment.shadow_route_ready && (
            <div className="nexus-card" style={{ border: "1px solid #ef4444", background: "rgba(239, 68, 68, 0.05)" }}>
              <div style={{ color: '#ef4444', fontWeight: 'bold', marginBottom: '8px', fontSize: '13px' }}>⚠️ ACTION REQUIRED</div>
              <p style={{ color: '#fca5a5', fontSize: '12px', marginBottom: '12px' }}>
                System has detected severe trajectory disruptions. Alternate routing intelligence standing by.
              </p>
              <button className="nexus-btn" style={{ background: '#ef4444', width: '100%' }} onClick={handleGetReroute}>
                Request Alternate Routes
              </button>
            </div>
          )}

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
        {activeTab === 'fleet' && <FleetTab fleet={fleet} onSelectShipment={handleSelectShipment} statusBadgeClass={statusBadgeClass} riskColor={riskColor} />}
        {activeTab === 'schedule' && <ScheduleTab BASE_URL={BASE_URL} onDispatched={handleSelectShipment} />}
        {activeTab === 'analytics' && <AnalyticsTab fleet={fleet} />}
        {activeTab === 'history' && <HistoryTab currentShipmentId={currentShipmentId} riskColor={riskColor} />}
        {activeTab === 'collision' && <CollisionTab fleet={fleet} />}
        {activeTab === 'account' && <AccountTab />}
      </main>
    </div>
  );
}