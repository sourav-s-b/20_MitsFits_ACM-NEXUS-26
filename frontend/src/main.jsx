/**
 * App entry
 * --------
 * Not logged in → `LoginPage` (animated intro + sign-in). No changes to your dashboard code.
 * Logged in     → `App` exactly as before (see AUTH_KEY in sessionStorage).
 */
import { StrictMode, useState, useCallback, useEffect } from "react";
import { createRoot } from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./index.css";
import LoginPage from "./LoginPage.jsx";
import App from "./App.jsx";

/** Session flag: only LoginPage until set; after that your original `App` runs. */
const AUTH_KEY = "onyxpath_authenticated";

function readAuthed() {
  try {
    if (new URLSearchParams(window.location.search).get("logout") === "1") {
      sessionStorage.removeItem(AUTH_KEY);
      return false;
    }
  } catch {
    /* ignore */
  }
  return sessionStorage.getItem(AUTH_KEY) === "1";
}

function Root() {
  const [authed, setAuthed] = useState(readAuthed);

  /** Strip ?logout=1 from the URL after first paint. */
  useEffect(() => {
    try {
      if (new URLSearchParams(window.location.search).get("logout") === "1") {
        window.history.replaceState({}, "", window.location.pathname || "/");
      }
    } catch {
      /* ignore */
    }
  }, []);

  const handleLoginSuccess = useCallback(() => {
    sessionStorage.setItem(AUTH_KEY, "1");
    setAuthed(true);
  }, []);

  const handleLogout = useCallback(() => {
    sessionStorage.removeItem(AUTH_KEY);
    setAuthed(false);
  }, []);

  if (!authed) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return <App onLogout={handleLogout} />;
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Root />
  </StrictMode>
);
