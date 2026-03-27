import { useState, useEffect } from "react";
import { MapContainer, TileLayer, Marker, Polyline, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Helper component to auto-center map when truck moves
function RecenterMap({ coords }) {
  const map = useMap();
  useEffect(() => {
    if (coords) map.setView([coords.lat, coords.lon], map.getZoom());
  }, [coords]);
  return null;
}

function App() {
  const [shipment, setShipment] = useState(null);
  const [loading, setLoading] = useState(true);

  // 1. API Polling: Fetch state every 3 seconds 
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/state");
        const data = await response.json();
        setShipment(data);
        setLoading(false);
      } catch (err) {
        console.error("Error fetching shipment state:", err);
      }
    };

    fetchData(); // Initial fetch
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  // 2. Button Action: Trigger Event
  const handleTriggerEvent = async () => {
    await fetch("http://127.0.0.1:8000/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "traffic_spike" }),
    });
  };

  // 3. Button Action: Get and Confirm Reroute
  const handleReroute = async () => {
    // First, ask Decision Engine for options
    const res = await fetch("http://127.0.0.1:8000/reroute");
    const data = await res.json();
    
    if (data.options && data.options.length > 0) {
      // For demo, we automatically confirm the first alternative
      await fetch("http://127.0.0.1:8000/confirm-reroute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ route_id: data.options[0].id }),
      });
    }
  };

  if (loading || !shipment) return <div style={{color: "white", padding: "20px"}}>Loading Live Shipment Data...</div>;

  // Convert TomTom points {lat, lon} to Leaflet [lat, lon] arrays 
  const mainRoutePoints = shipment.route?.map(p => [p.lat, p.lon]) || [];
  const currentPos = [shipment.current_location.lat, shipment.current_location.lon];

  const getRiskColor = () => {
    if (shipment.risk_score > 0.6) return "#f87171"; // Red
    if (shipment.risk_score > 0.4) return "#fbbf24"; // Orange
    return "#34d399"; // Green
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#020617" }}>
      <div style={{ display: "flex", flex: 1 }}>
        
        {/* MAP SECTION */}
        <div style={{ width: "70%" }}>
          <MapContainer center={currentPos} zoom={7} style={{ height: "100%" }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            
            {/* Draw the full planned route */}
            {mainRoutePoints.length > 0 && <Polyline positions={mainRoutePoints} color="#3b82f6" weight={4} opacity={0.6} />}
            
            {/* Truck Marker */}
            <Marker position={currentPos} />
            <RecenterMap coords={shipment.current_location} />
          </MapContainer>
        </div>

        {/* SIDE PANEL */}
        <div style={{ width: "30%", padding: "20px", color: "#e2e8f0", overflowY: "auto" }}>
          <h2 style={{ color: "#fff" }}>Live Monitor</h2>
          
          <div style={{ background: "#1e293b", padding: "15px", borderRadius: "10px", marginBottom: "15px" }}>
            <p><b>ID:</b> {shipment.shipment_id}</p>
            <p><b>Status:</b> <span style={{ color: getRiskColor(), fontWeight: "bold" }}>{shipment.status}</span></p>
            <p><b>Risk Score:</b> {(shipment.risk_score * 100).toFixed(0)}%</p>
          </div>

          <div style={{ background: "#1e293b", padding: "15px", borderRadius: "10px", marginBottom: "15px" }}>
            <h3>Signals</h3>
            <p>Traffic Delay: {shipment.signals.traffic_delay}m</p>
            <p>Weather Score: {shipment.signals.weather_score}</p>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <button onClick={handleTriggerEvent} style={btnStyle("#f59e0b")}>Inject Risk</button>
            <button onClick={handleReroute} style={btnStyle("#22c55e")}>Reroute</button>
          </div>

          <h3 style={{ marginTop: "20px" }}>Active Alerts</h3>
          {shipment.alerts?.map((alert, i) => (
            <div key={i} style={{ fontSize: "0.8rem", borderLeft: `3px solid ${getRiskColor()}`, paddingLeft: "10px", marginBottom: "10px" }}>
              [{alert.timestamp}] {alert.reason}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const btnStyle = (bg) => ({
  flex: 1, padding: "12px", borderRadius: "8px", border: "none",
  background: bg, color: "#000", fontWeight: "bold", cursor: "pointer"
});

export default App;