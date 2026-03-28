import { useState, useEffect } from "react";
import "./LoginPage.css";
import { BRANDING } from "./branding";

const BASE_URL = "http://127.0.0.1:8000";

const BOOT_MS = 2400;
const BOOT_EXIT_MS = 650;

function LoginBackgroundMotion() {
  return (
    <div className="login-motion" aria-hidden>
      <div className="login-motion__aurora" />
      <div className="login-motion__grid" />
      <svg
        className="login-motion__svg"
        viewBox="0 0 1200 780"
        preserveAspectRatio="xMidYMid slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="login-route-grad-a" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.15" />
            <stop offset="50%" stopColor="#a855f7" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="login-route-grad-b" x1="100%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.2" />
            <stop offset="45%" stopColor="#a855f7" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <path
          className="login-motion__path login-motion__path--primary"
          fill="none"
          stroke="url(#login-route-grad-a)"
          strokeWidth="1.5"
          strokeLinecap="round"
          d="M -40 520 C 180 380 320 620 520 440 S 780 200 980 360 S 1150 480 1280 320"
        />
        <path
          className="login-motion__path login-motion__path--secondary"
          fill="none"
          stroke="url(#login-route-grad-b)"
          strokeWidth="1.25"
          strokeLinecap="round"
          d="M 1240 180 C 1000 260 880 120 640 280 S 400 520 200 400 S 40 300 -60 420"
        />
        <path
          className="login-motion__path login-motion__path--ghost"
          fill="none"
          stroke="rgba(99, 102, 241, 0.22)"
          strokeWidth="1"
          strokeDasharray="4 14"
          d="M 100 700 Q 400 520 700 620 T 1180 540"
        />
      </svg>
      <div className="login-motion__nodes">
        <span className="login-motion__node" style={{ top: "18%", left: "12%" }} />
        <span className="login-motion__node" style={{ top: "62%", left: "22%" }} />
        <span className="login-motion__node" style={{ top: "28%", right: "18%" }} />
        <span className="login-motion__node" style={{ bottom: "20%", right: "28%" }} />
      </div>
      <div className="login-motion__scan" />
      <div className="login-motion__vignette" />
    </div>
  );
}

/** Full-screen motion at first paint; fades away to reveal the sign-in form. */
function LoginBootOverlay({ phase }) {
  if (phase === "done") return null;

  return (
    <div
      className={`login-boot ${phase === "exiting" ? "login-boot--exit" : ""}`}
      aria-hidden="true"
    >
      <div className="login-boot__rings" />
      <div className="login-boot__core">
        <div className="login-boot__logo-mark">
          <span className="login-boot__logo-glow" />
          OP
        </div>
        <p className="login-boot__brand">{BRANDING.fullName}</p>
        <p className="login-boot__tagline">{BRANDING.tagline}</p>
      </div>
      <div className="login-boot__track" aria-hidden>
        <div className="login-boot__fill" />
      </div>
      <p className="login-boot__status">
        <span className="login-boot__status-dot" />
        Initializing routing mesh…
      </p>
    </div>
  );
}

export default function LoginPage({ onLoginSuccess }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [bootPhase, setBootPhase] = useState(() =>
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "done"
      : "playing"
  );

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const t1 = window.setTimeout(() => setBootPhase("exiting"), BOOT_MS);
    const t2 = window.setTimeout(() => setBootPhase("done"), BOOT_MS + BOOT_EXIT_MS);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  /** Show the real sign-in form — also during boot *exit* so it crossfades with the overlay (avoids a blank gap). */
  const showLoginForm = bootPhase !== "playing";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok && data.token) {
        if (typeof onLoginSuccess === "function") {
          onLoginSuccess(data);
        }
        return;
      }

      setError(data.detail || data.message || "Invalid credentials or server error.");
    } catch {
      setError("Cannot reach the server. Start the backend or check the URL.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`onyx-login ${showLoginForm ? "onyx-login--ready" : ""}`}>
      <LoginBackgroundMotion />
      <div className="onyx-login__grain" />
      <LoginBootOverlay phase={bootPhase} />

      <div className="onyx-login__wrap">
        <div className="onyx-login__brand">
          <div className="onyx-login__logo-mark" aria-hidden>
            <span className="onyx-login__logo-pulse" />
            OP
          </div>
          <p className="onyx-login__kicker">
            <span className="onyx-login__kicker-dot" />
            {BRANDING.name} — fleet telemetry
          </p>
          <h1 className="onyx-login__title">
            Routes stay <span>ahead of risk</span>
          </h1>
          <p className="onyx-login__subtitle">
            Sign in to <strong>{BRANDING.fullName}</strong> — {BRANDING.tagline}.
          </p>
        </div>

        <div className="onyx-login__card">
          <div className="onyx-login__card-glow" />
          <p className="onyx-login__card-title">Dispatcher sign in</p>
          <form onSubmit={handleSubmit}>
            <div className="onyx-login__field">
              <label className="onyx-login__label" htmlFor="onyx-user">
                Username
              </label>
              <input
                id="onyx-user"
                className="onyx-login__input"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
              />
            </div>
            <div className="onyx-login__field">
              <label className="onyx-login__label" htmlFor="onyx-pass">
                Password
              </label>
              <input
                id="onyx-pass"
                className="onyx-login__input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
              />
            </div>

            {error ? <div className="onyx-login__error">{error}</div> : null}

            <button className="onyx-login__submit" type="submit" disabled={loading}>
              <span className="onyx-login__submit-shine" />
              {loading ? "Authenticating…" : "Enter command center"}
            </button>
          </form>

          <p className="onyx-login__hint">
            Demo: <strong>admin</strong> / <strong>password</strong> with the API running on port 8000.
          </p>
        </div>
      </div>

      <footer className="onyx-login__footer">{BRANDING.fullName}</footer>
    </div>
  );
}
