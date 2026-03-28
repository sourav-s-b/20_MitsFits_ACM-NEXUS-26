import { useState, useEffect, useRef, useMemo } from "react";
import {
  MapContainer, TileLayer, Marker, Polyline, Circle, useMap, Tooltip, useMapEvents
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";
import { BRANDING } from "./branding";

const BASE_URL = "http://127.0.0.1:8000";
const WS_BASE_URL = "ws://127.0.0.1:8000";

// ── Fix Leaflet icon paths for Vite ──
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const LocationSearch = ({ placeholder, onSelect, BASE_URL }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (query.length < 3) { setResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${BASE_URL}/geocoding/search?query=${query}`);
        const data = await res.json();
        setResults(data);
      } catch (e) { console.error(e); }
    }, 500);
    return () => clearTimeout(timer);
  }, [query, BASE_URL]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <input
        type="text"
        placeholder={placeholder}
        value={query}
        onChange={e => { setQuery(e.target.value); setShow(true); }}
        onFocus={() => setShow(true)}
        style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }}
      />
      {show && results.length > 0 && (
        <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 1000, background: '#1e293b', border: '1px solid var(--border)', borderRadius: '4px', marginTop: '4px', overflow: 'hidden' }}>
          {results.map((r, i) => (
            <div
              key={i}
              className="search-result-item"
              onClick={() => { onSelect(r); setQuery(r.label); setShow(false); }}
              style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', borderBottom: i < results.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}
            >
              {r.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Icons
const truckIcon = new L.DivIcon({
  html: `<div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#a855f7,#6366f1);border:2px solid rgba(255,255,255,0.3);display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 12px rgba(168,85,247,0.7);">🚛</div>`,
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
      <p>Monitor all active deliveries across the {BRANDING.fullName} network.</p>
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
                  <button className="onyx-btn btn-ghost" onClick={() => onSelectShipment(s.shipment_id)}>
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

const AccountTab = ({ onLogout }) => {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch(`${BASE_URL}/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "admin", password: "password" })
    }).then(r => r.json()).then(setUser).catch(console.error);
  }, []);

  if (!user) return <div className="tab-pane"><div className="onyx-spinner"></div></div>;

  return (
    <div className="tab-pane">
      <h1>👤 Global Dispatcher Profile</h1>
      <div className="onyx-card" style={{ maxWidth: '400px', marginTop: '20px' }}>
        <div className="onyx-card-title">Personnel File</div>
        <p><b>Name:</b> {user.name}</p>
        <p><b>Role:</b> {user.role}</p>
        <p><b>Auth Token:</b> <code className="mono">{user.token.slice(0, 8)}...</code></p>
        <button
          type="button"
          className="onyx-btn btn-danger"
          style={{ marginTop: '15px', width: '100%' }}
          onClick={() => typeof onLogout === "function" && onLogout()}
        >
          Sign Out
        </button>
      </div>
    </div>
  );
};

const ScheduleTab = ({ BASE_URL, onDispatched, setPickingMode, pickingMode }) => {
  const [shipmentId, setShipmentId] = useState(`SHP-${Math.floor(Math.random() * 9999)}`);
  const [origin, setOrigin] = useState("19.0760,72.8777");
  const [target, setTarget] = useState("18.5204,73.8567");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (pickingMode === 'origin_selected') {
      setPickingMode(null);
    } else if (pickingMode === 'target_selected') {
      setPickingMode(null);
    }
  }, [origin, target]);

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
      <p>Schedule a new transport routing via the {BRANDING.fullName} logistics engine.</p>

      <div className="onyx-card" style={{ maxWidth: '600px', padding: '24px' }}>
        <form onSubmit={handleDispatch} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>SHIPMENT ID</label>
            <input type="text" value={shipmentId} onChange={e => setShipmentId(e.target.value)} style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>ORIGIN (Search or Pin)</label>
              <LocationSearch BASE_URL={BASE_URL} placeholder="Search origin..." onSelect={r => setOrigin(`${r.lat},${r.lon}`)} />
              <button
                type="button"
                className={`onyx-btn ${pickingMode === 'origin' ? 'btn-danger' : 'btn-cyan'}`}
                style={{ width: '100%', marginTop: '8px', fontSize: '12px', padding: '8px' }}
                onClick={() => setPickingMode(pickingMode === 'origin' ? null : 'origin')}
              >
                {pickingMode === 'origin' ? '🛑 Cancel Pinning' : '📍 Pin on Map'}
              </button>
              <div style={{ fontSize: '10px', color: '#666', marginTop: '4px' }}>Current: {origin}</div>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>DESTINATION (Search or Pin)</label>
              <LocationSearch BASE_URL={BASE_URL} placeholder="Search destination..." onSelect={r => setTarget(`${r.lat},${r.lon}`)} />
              <button
                type="button"
                className={`onyx-btn ${pickingMode === 'target' ? 'btn-danger' : 'btn-cyan'}`}
                style={{ width: '100%', marginTop: '8px', fontSize: '12px', padding: '8px' }}
                onClick={() => setPickingMode(pickingMode === 'target' ? null : 'target')}
              >
                {pickingMode === 'target' ? '🛑 Cancel Pinning' : '🏁 Pin on Map'}
              </button>
              <div style={{ fontSize: '10px', color: '#666', marginTop: '4px' }}>Current: {target}</div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', margin: '5px 0', flexWrap: 'wrap' }}>
            {presets.map(p => (
              <button type="button" key={p.label} className="map-tag map-tag-alt" style={{ cursor: 'pointer' }} onClick={() => { setOrigin(p.o); setTarget(p.d); }}>
                {p.label}
              </button>
            ))}
          </div>

          <button type="submit" className="onyx-btn btn-green" disabled={loading} style={{ marginTop: '10px', padding: '14px', fontSize: '15px' }}>
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
        <div className="onyx-card">
          <div className="onyx-card-title">Total Fleet Delay</div>
          <div style={{ fontSize: '32px', color: '#f59e0b', fontWeight: 'bold' }}>{totalDelays} <span style={{ fontSize: '16px' }}>min</span></div>
        </div>
        <div className="onyx-card" style={{ borderColor: criticalCount > 0 ? '#ef4444' : '' }}>
          <div className="onyx-card-title">Critical Shipments</div>
          <div style={{ fontSize: '32px', color: criticalCount > 0 ? '#ef4444' : '#10b981', fontWeight: 'bold' }}>{criticalCount}</div>
        </div>
        <div className="onyx-card">
          <div className="onyx-card-title">Average Fleet Risk</div>
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
export default function App({ onLogout }) {
  const [activeTab, setActiveTab] = useState("map");
  const [currentShipmentId, setCurrentShipmentId] = useState("SHP001");

  const [shipment, setShipment] = useState(null);
  const [reroutes, setReroutes] = useState([]);
  const [recommended, setRecommended] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connError, setConnError] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const [pickingMode, setPickingMode] = useState(null);
  const audioPlayed = useRef(false);
  const started = useRef(false);
  const currentIdRef = useRef(currentShipmentId);

  useEffect(() => {
    currentIdRef.current = currentShipmentId;
  }, [currentShipmentId]);

  const API = `${BASE_URL}/shipments/${currentShipmentId}`;
  const WS_URL = `${WS_BASE_URL}/ws/${currentShipmentId}`;

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
    setLoading(true);
    setShipment(null);
    started.current = false;
    setReroutes([]);
    setSelected(null); // FIX: clear selected on shipment switch

    const connectWS = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnError(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.shipment_id !== currentIdRef.current) return;

          setShipment(data);
          setLoading(false);
          setConnError(false);

          if (!started.current && (!data.route || data.route.length === 0)) {
            started.current = true;
            fetch(`${API}/start`, { method: "POST" }).catch(console.error);
          }

          // FIX: autopilot already acted — clear panel immediately, don't show confirm button
          if (data.status === "REROUTED") {
            setReroutes([]);
            setSelected(null);
            return;
          }

          if (data.reroute_options && data.reroute_options.length > 0) {
            setReroutes(data.reroute_options);
            if (!selected) {
              const rec = data.reroute_options.find(r => r.recommended);
              if (rec) { setRecommended(rec.id); setSelected(rec.id); }
            }
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

  // ── Polling Fallback ──
  useEffect(() => {
    if (!connError) return;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/state`);
        const data = await res.json();
        setShipment(data);
        // FIX: also clear panel in polling path
        if (data.status === "REROUTED") {
          setReroutes([]);
          setSelected(null);
          return;
        }
        if (data.reroute_options && data.reroute_options.length > 0 && reroutes.length === 0) {
          setReroutes(data.reroute_options);
        }
      } catch (e) { console.error("Polling error:", e); }
    };
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [connError, API, reroutes.length]);

  const handleConfirmReroute = async (routeId) => {
    try {
      const resp = await fetch(`${API}/confirm-reroute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ route_id: routeId })
      });
      if (resp.ok) {
        setReroutes([]);
        setSelected(null);
        const stateRes = await fetch(`${API}/state`);
        const stateData = await stateRes.json();
        setShipment(stateData);
      }
    } catch (e) {
      console.error("Confirmation Error:", e);
    }
  };

  const playBeep = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'square';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      osc.start();
      osc.stop(ctx.currentTime + 0.25);
    } catch (e) { }
  };

  useEffect(() => {
    let timer;
    if (shipment?.auto_reroute_armed && shipment?.auto_reroute_deadline) {
      const updateTimer = () => {
        const remaining = Math.max(0, Math.ceil(shipment.auto_reroute_deadline - (Date.now() / 1000)));
        setCountdown(remaining);
      };
      updateTimer();
      timer = setInterval(updateTimer, 500);
      if (!audioPlayed.current) {
        playBeep();
        audioPlayed.current = true;
      }
    } else {
      setCountdown(null);
      audioPlayed.current = false;
    }
    return () => clearInterval(timer);
  }, [shipment?.auto_reroute_armed, shipment?.auto_reroute_deadline]);

  const handleCancelAutoReroute = async () => {
    try {
      await fetch(`${API}/cancel-auto-reroute`, { method: "POST" });
    } catch (e) { console.error(e); }
  };

  const handleSelectShipment = (id) => {
    setCurrentShipmentId(id);
    setActiveTab("map");
  };

  const activeReroutes = shipment
    ? (reroutes.length > 0 ? reroutes : (shipment.reroute_options || []))
    : [];

  const mainRoutePoints = useMemo(() => {
    if (!shipment) return [];
    return (shipment.route || []).map(p => [p.latitude ?? p.lat ?? 0, p.longitude ?? p.lon ?? 0]);
  }, [shipment?.route?.length]);

  const altRoute = activeReroutes.find(r => r.id !== selected);
  const altPoints = useMemo(() => {
    return altRoute ? altRoute.polyline.map(p => [p.latitude ?? p.lat, p.longitude ?? p.lon]) : [];
  }, [altRoute]);

  const selRoute = activeReroutes.find(r => r.id === selected);
  const selPoints = useMemo(() => {
    return selRoute ? selRoute.polyline.map(p => [p.latitude ?? p.lat, p.longitude ?? p.lon]) : [];
  }, [selRoute]);

  const renderSidebar = () => (
    <nav className="dashboard-sidebar">
      <div className="sidebar-logo">
        <div className="onyx-logo-dot" /> {BRANDING.logoText}
      </div>
      <ul className="sidebar-nav">
        <li className={activeTab === 'map' ? 'active' : ''} onClick={() => setActiveTab('map')}>🗺️ Live Tracking</li>
        <li className={activeTab === 'fleet' ? 'active' : ''} onClick={() => setActiveTab('fleet')}>🚛 Fleet Logistics</li>
        <li className={activeTab === 'schedule' ? 'active' : ''} onClick={() => setActiveTab('schedule')}>➕ Schedule Shipment</li>
        <li className={activeTab === 'analytics' ? 'active' : ''} onClick={() => setActiveTab('analytics')}>📊 Delivery Estimations</li>
        <li className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>📦 Delivery History</li>
        <li className={activeTab === 'account' ? 'active' : ''} onClick={() => setActiveTab('account')}>👤 My Account</li>
      </ul>
      <div className="sidebar-footer">
        Tracking: <br /><b style={{ color: 'white' }}>{currentShipmentId}</b>
      </div>
    </nav>
  );

  const MapEvents = () => {
    useMapEvents({
      click: (e) => {
        if (pickingMode === 'origin') {
          window.dispatchEvent(new CustomEvent('map-click', { detail: { lat: e.latlng.lat, lon: e.latlng.lng, type: 'origin' } }));
        } else if (pickingMode === 'target') {
          window.dispatchEvent(new CustomEvent('map-click', { detail: { lat: e.latlng.lat, lon: e.latlng.lng, type: 'target' } }));
        }
      }
    });
    return null;
  };

  const renderMapTab = () => {
    if (connError) {
      return (
        <div className="onyx-loading">
          <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
          <p style={{ color: "var(--accent-red)", fontWeight: 600 }}>Backend Unreachable</p>
        </div>
      );
    }
    if (loading || !shipment) {
      return <div className="onyx-loading"><div className="onyx-spinner" /></div>;
    }

    const currentPos = [shipment.current_location?.lat ?? shipment.current_location?.latitude ?? 0, shipment.current_location?.lon ?? shipment.current_location?.longitude ?? 0];
    const destPos = shipment.destination ? [shipment.destination.lat ?? 0, shipment.destination.lon ?? 0] : currentPos;
    const rColor = riskColor(shipment.risk_score);
    const weather = shipment.weather || {};

    const handleGetReroute = async () => {
      try {
        const res = await fetch(`${API}/reroute`);
        const data = await res.json();
        const opts = data.options || data.routes || [];
        if (opts.length > 0) {
          setReroutes(opts);
          const rec = opts.find(r => r.recommended) || opts[0];
          setSelected(rec.id);
        } else {
          console.warn("Reroute: no options returned", data);
        }
      } catch (e) {
        console.error("Reroute fetch failed", e);
      }
    };

    return (
      <div className="tab-map">
        <div className="onyx-map-pane" style={{ position: "relative" }}>
          <MapContainer center={currentPos} zoom={7} style={{ height: "100%", width: "100%" }} zoomControl={false}>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
            <MapEvents />
            {mainRoutePoints.length > 0 && <Polyline positions={mainRoutePoints} color={rColor} weight={5} opacity={0.8} />}
            {activeReroutes.map(r => {
              if (r.id === selected) return null;
              const points = r.polyline.map(p => [p.latitude ?? p.lat ?? 0, p.longitude ?? p.lon ?? 0]);
              return <Polyline key={r.id} positions={points} color="#a855f7" weight={2} opacity={0.4} dashArray="10 10" />;
            })}
            {selPoints.length > 0 && <Polyline positions={selPoints} color="#a855f7" weight={6} opacity={1.0} dashArray="12 8" />}

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

        <aside className="onyx-panel">
          <div className="onyx-card scale-up">
            <div className="onyx-card-title">Risk Monitor</div>
            <div className="risk-gauge-wrap">
              <RiskRing score={shipment.risk_score} />
              <div className="risk-info">
                <div className={`risk-status-badge ${statusBadgeClass(shipment.status)}`}>{shipment.status}</div>
                <div className="risk-shipment-id">{currentShipmentId} &bull; {shipment.eta || "--"}m</div>
              </div>
            </div>

            <div style={{ marginTop: '15px', padding: '12px', background: 'rgba(0,0,0,0.3)', border: shipment.auto_pilot ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'all 0.3s' }}>
              <span style={{ fontSize: '13px', fontWeight: 'bold', color: shipment.auto_pilot ? '#10b981' : '#94a3b8' }}>{shipment.auto_pilot ? '🚀 Autopilot Active' : '🤖 Autopilot Ready'}</span>
              <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                <input type="checkbox" checked={!!shipment.auto_pilot} style={{ display: 'none' }} onChange={(e) => {
                  fetch(`${API}/autopilot`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: e.target.checked }) });
                }} />
                <div style={{ width: '44px', height: '24px', background: shipment.auto_pilot ? '#10b981' : '#3f3f46', borderRadius: '12px', position: 'relative', transition: 'background 0.3s' }}>
                  <div style={{ position: 'absolute', top: '2px', left: shipment.auto_pilot ? '22px' : '2px', width: '20px', height: '20px', background: 'white', borderRadius: '50%', transition: 'left 0.3s' }}></div>
                </div>
              </label>
            </div>
          </div>

          {shipment.ai_reason && (
            <div className="onyx-card ai-insight-card ripple">
              <div className="onyx-card-title" style={{ color: '#22d3ee', display: 'flex', alignItems: 'center', gap: '8px' }}>
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

          <div className="onyx-card">
            <div className="onyx-card-title">Telemetry Overview</div>
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

            {weather.temp_c !== undefined && (
              <div className="weather-telemetry" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
                  <span>🌡 {weather.temp_c}°C</span>
                  <span>💧 {weather.humidity}%</span>
                  <span>💨 {weather.wind_kph} km/h</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                  <span>👁 {weather.visibility_km} km vis</span>
                  {weather.rain_1h_mm > 0 && <span style={{ color: '#3b82f6' }}>🌧 {weather.rain_1h_mm}mm/h</span>}
                </div>
              </div>
            )}
          </div>

          <div className="onyx-card">
            <div className="onyx-card-title">Operations</div>
            <div className="onyx-btn-row" style={{ flexWrap: 'wrap', gap: '8px' }}>
              <button className="onyx-btn btn-danger" onClick={() => fetch(`${API}/simulate-storm`, { method: 'POST' })}>🌩 Storm</button>
              <button className="onyx-btn btn-danger" onClick={() => fetch(`${API}/simulate-accident`, { method: 'POST' })}>🚗 Accident</button>
              <button className="onyx-btn btn-danger" onClick={() => fetch(`${API}/simulate-roadblock`, { method: 'POST' })}>🚧 Roadblock</button>
              <button className="onyx-btn btn-cyan" onClick={() => fetch(`${API}/simulate-parade`, { method: 'POST' })}>🪩 Parade</button>
              <button className="onyx-btn btn-cyan" onClick={() => fetch(`${API}/simulate-construction`, { method: 'POST' })}>🏗️ Const.</button>
              <button className="onyx-btn btn-ghost" style={{ width: '100%' }} onClick={() => fetch(`${API}/pipeline`)}>⚡ Sync AI Pipeline</button>
            </div>
          </div>

          {(shipment.status === 'HIGH RISK' || shipment.status === 'WARNING') && (activeReroutes.length === 0) && shipment.shadow_route_ready && (
            <div className="onyx-card" style={{ border: "1px solid #ef4444", background: "rgba(239, 68, 68, 0.05)" }}>
              <div style={{ color: '#ef4444', fontWeight: 'bold', marginBottom: '8px', fontSize: '13px' }}>⚠️ ACTION REQUIRED</div>
              <p style={{ color: '#fca5a5', fontSize: '12px', marginBottom: '12px' }}>
                System has detected severe trajectory disruptions. Alternate routing intelligence standing by.
              </p>
              <button className="onyx-btn" style={{ background: '#ef4444', width: '100%' }} onClick={handleGetReroute}>
                Request Alternate Routes
              </button>
            </div>
          )}

          {/* FIX: hide entirely when REROUTED — autopilot already handled it, no manual button needed */}
          {activeReroutes.length > 0 && shipment.status !== "SAFE" && shipment.status !== "REROUTED" && (
            <div className="onyx-card scale-up">
              <div className="onyx-card-title">💡 Strategic Trajectories ({activeReroutes.length})</div>
              <div className="route-options-grid">
                {activeReroutes.map(r => (
                  <div key={r.id} className={`route-card ${selected === r.id ? "selected" : ""}`} onClick={() => setSelected(r.id)}>
                    <div className="route-card-id">{r.id.toUpperCase()}</div>
                    <div className="route-card-time" style={{ fontSize: '10px', color: '#94a3b8' }}>{r.travel_time_min}m</div>
                  </div>
                ))}
              </div>
              {shipment?.auto_reroute_armed && countdown !== null ? (
                <div style={{ textAlign: 'center', marginTop: '15px', padding: '15px', border: '1px solid #ff003c', borderRadius: '8px', background: 'rgba(255,0,60,0.05)', boxShadow: '0 0 15px rgba(255,0,60,0.3)' }}>
                  <h4 style={{ color: '#ff003c', margin: '0 0 8px 0', animation: 'pulse 1s infinite' }}>⚠️ Critical Hazard Ahead</h4>
                  <p style={{ color: '#fca5a5', fontSize: '13px', margin: '0 0 15px 0' }}>Rerouting in {countdown}s...</p>

                  <div style={{ position: 'relative', width: '64px', height: '64px', margin: '0 auto 15px auto' }}>
                    <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
                      <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="3" />
                      <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#ff003c" strokeWidth="3" strokeDasharray={`${((5 - countdown) / 5) * 100}, 100`} style={{ transition: 'stroke-dasharray 0.5s linear' }} />
                    </svg>
                  </div>

                  <button className="onyx-btn" onClick={handleCancelAutoReroute} style={{ width: '100%', background: '#ff003c', color: 'white', fontWeight: 'bold' }}>Cancel (SOP Override)</button>
                </div>
              ) : (
                <button className="onyx-btn btn-green" style={{ width: '100%', marginTop: '8px' }}
                  onClick={() => handleConfirmReroute(selected)}>
                  Confirm Route
                </button>
              )}
            </div>
          )}
        </aside>
      </div>
    );
  };

  return (
    <div className="onyx-shell with-sidebar">
      {renderSidebar()}
      <main className="onyx-main-content">
        {activeTab === 'map' && renderMapTab()}
        {activeTab === 'fleet' && <FleetTab fleet={fleet} onSelectShipment={handleSelectShipment} statusBadgeClass={statusBadgeClass} riskColor={riskColor} />}
        {activeTab === 'schedule' && <ScheduleTab BASE_URL={BASE_URL} onDispatched={handleSelectShipment} setPickingMode={setPickingMode} pickingMode={pickingMode} />}
        {activeTab === 'analytics' && <AnalyticsTab fleet={fleet} />}
        {activeTab === 'history' && <HistoryTab currentShipmentId={currentShipmentId} riskColor={riskColor} />}
        {activeTab === 'account' && <AccountTab onLogout={onLogout} />}
      </main>
    </div>
  );
}