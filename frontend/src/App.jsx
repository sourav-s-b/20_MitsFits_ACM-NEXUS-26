import { useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function App() {
  const route = [
    [9.9312, 76.2673],
    [10.5, 76.8],
    [11.5, 77.5],
    [12.9716, 77.5946],
  ];

  const altRoute = [
    [9.9312, 76.2673],
    [10.2, 76.5],
    [11.2, 77.2],
    [12.9716, 77.5946],
  ];

  const [showAlt, setShowAlt] = useState(false);
  const [risk, setRisk] = useState(0.2);
  const [timeline, setTimeline] = useState([
    "10:00 - Shipment started",
  ]);

  const handleEvent = () => {
    setRisk(0.8);
    setTimeline((prev) => [
      ...prev,
      "13:15 - Traffic spike detected",
    ]);
  };

  const handleReroute = () => {
    setShowAlt(true);
    setTimeline((prev) => [
      ...prev,
      "13:20 - Reroute triggered",
    ]);
  };

  const getRiskColor = () => {
    if (risk > 0.6) return "red";
    if (risk > 0.4) return "orange";
    return "green";
  };

  const getRiskText = () => {
    if (risk > 0.6) return "HIGH RISK";
    if (risk > 0.4) return "MEDIUM";
    return "SAFE";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial" }}>

      {/* TOP SECTION */}
      <div style={{ display: "flex", flex: 1 }}>

        {/* MAP */}
        <div style={{ width: "70%" }}>
          <MapContainer center={route[0]} zoom={6} style={{ height: "100%" }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <Polyline positions={route} color="blue" />
            {showAlt && <Polyline positions={altRoute} color="red" />}
            <Marker position={route[0]} />
          </MapContainer>
        </div>

        {/* RIGHT PANEL */}
        <div style={{
          width: "30%",
          padding: "20px",
          background: "#0f172a",
          color: "#e2e8f0",
          display: "flex",
          flexDirection: "column",
          gap: "20px"
        }}>

          {/* Shipment Card */}
          <div style={{ background: "#1e293b", padding: "15px", borderRadius: "10px" }}>
            <h3>Shipment</h3>
            <p><b>ID:</b> SHP001</p>
            <p><b>From:</b> Kochi</p>
            <p><b>To:</b> Bangalore</p>
            <p><b>ETA:</b> 180 mins</p>
          </div>

          {/* Risk Card */}
          <div style={{ background: "#1e293b", padding: "15px", borderRadius: "10px" }}>
            <h3>Risk Status</h3>
            <p style={{
              color: getRiskColor(),
              fontSize: "18px",
              fontWeight: "bold"
            }}>
              {getRiskText()}
            </p>
          </div>

          {/* Alerts */}
          <div style={{ background: "#1e293b", padding: "15px", borderRadius: "10px" }}>
            <h3>Alerts</h3>
            {risk > 0.6 ? (
              <p style={{ color: "#f87171" }}>⚠ Traffic congestion ahead</p>
            ) : (
              <p style={{ color: "#94a3b8" }}>No alerts</p>
            )}
          </div>

          {/* Buttons */}
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={handleEvent}
              style={{
                flex: 1,
                padding: "10px",
                borderRadius: "8px",
                border: "none",
                background: "#f59e0b",
                color: "#000",
                fontWeight: "bold",
                cursor: "pointer"
              }}
            >
              Trigger Event
            </button>

            <button
              onClick={handleReroute}
              style={{
                flex: 1,
                padding: "10px",
                borderRadius: "8px",
                border: "none",
                background: "#22c55e",
                color: "#000",
                fontWeight: "bold",
                cursor: "pointer"
              }}
            >
              REROUTE
            </button>
          </div>

        </div>
      </div>

      {/* TIMELINE */}
      <div style={{
        height: "160px",
        background: "#020617",
        color: "#e2e8f0",
        padding: "15px",
        overflowY: "auto"
      }}>
        <h3 style={{ marginBottom: "10px" }}>Timeline</h3>

        {timeline.map((item, index) => (
          <div key={index} style={{
            padding: "6px 0",
            borderBottom: "1px solid #1e293b"
          }}>
            {item}
          </div>
        ))}
      </div>

    </div>
  );
}
export default App;