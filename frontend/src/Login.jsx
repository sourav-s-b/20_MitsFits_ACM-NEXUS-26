import { useState } from "react";

const BASE_URL = "http://127.0.0.1:8000";

export default function Login({ onLogin }) {
    const [username, setUsername] = useState("admin");
    const [password, setPassword] = useState("password");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const res = await fetch(`${BASE_URL}/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();

            if (data.token) {
                onLogin(data); // 🔥 THIS switches to main app
            } else {
                setError("Invalid credentials");
            }
        } catch (err) {
            setError("Backend not running");
        }

        setLoading(false);
    };

    return (
        <div style={styles.container}>
            <form style={styles.card} onSubmit={handleLogin}>
                <h2 style={{ marginBottom: "10px" }}>🚛 Fleet Login</h2>

                <input
                    style={styles.input}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Username"
                />

                <input
                    type="password"
                    style={styles.input}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                />

                {error && <p style={styles.error}>{error}</p>}

                <button style={styles.button} disabled={loading}>
                    {loading ? "Logging in..." : "Login"}
                </button>
            </form>
        </div>
    );
}

const styles = {
    container: {
        height: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#0f172a"
    },
    card: {
        background: "#111827",
        padding: "30px",
        borderRadius: "10px",
        width: "300px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        color: "white",
        boxShadow: "0 0 20px rgba(0,0,0,0.5)"
    },
    input: {
        padding: "10px",
        borderRadius: "5px",
        border: "none",
        outline: "none"
    },
    button: {
        padding: "10px",
        background: "#6366f1",
        color: "white",
        border: "none",
        cursor: "pointer",
        borderRadius: "5px"
    },
    error: {
        color: "#ef4444",
        fontSize: "12px"
    }
};