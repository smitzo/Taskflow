import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { CheckCircle2, KeyRound, LogIn, RefreshCw, UserPlus } from "lucide-react";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function App() {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    email: "ada@example.com",
    full_name: "Ada Lovelace",
    password: "StrongPass123",
  });
  const [tokens, setTokens] = useState(() => {
    const raw = localStorage.getItem("taskflow_tokens");
    return raw ? JSON.parse(raw) : null;
  });
  const [profile, setProfile] = useState(null);
  const [message, setMessage] = useState("Ready to connect to the auth API.");
  const [loading, setLoading] = useState(false);

  const isLoggedIn = Boolean(tokens?.access_token);

  const statusTone = useMemo(() => {
    if (message.toLowerCase().includes("failed") || message.toLowerCase().includes("invalid")) return "error";
    if (message.toLowerCase().includes("success") || message.toLowerCase().includes("loaded")) return "success";
    return "neutral";
  }, [message]);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function saveTokens(nextTokens) {
    setTokens(nextTokens);
    localStorage.setItem("taskflow_tokens", JSON.stringify(nextTokens));
  }

  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(tokens?.access_token ? { Authorization: `Bearer ${tokens.access_token}` } : {}),
        ...options.headers,
      },
      ...options,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.detail ?? "Request failed");
    }
    return body;
  }

  async function submitAuth(event) {
    event.preventDefault();
    setLoading(true);
    try {
      if (mode === "register") {
        await request("/auth/register", { method: "POST", body: JSON.stringify(form) });
        setMessage("Registration successful. You can log in now.");
        setMode("login");
      } else {
        const nextTokens = await request("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: form.email, password: form.password }),
        });
        saveTokens(nextTokens);
        setMessage("Login successful. Access token stored locally for this demo.");
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadProfile() {
    setLoading(true);
    try {
      const user = await request("/auth/me");
      setProfile(user);
      setMessage("Profile loaded from the protected /me endpoint.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshToken() {
    if (!tokens?.refresh_token) return;
    setLoading(true);
    try {
      const nextTokens = await request("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
        headers: {},
      });
      saveTokens(nextTokens);
      setMessage("Token refresh successful. Refresh token rotation is working.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  function signOut() {
    setTokens(null);
    setProfile(null);
    localStorage.removeItem("taskflow_tokens");
    setMessage("Signed out locally.");
  }

  return (
    <main className="shell">
      <section className="panel">
        <div className="brand-row">
          <div>
            <p className="eyebrow">TaskFlow</p>
            <h1>Auth dashboard</h1>
          </div>
          <span className={isLoggedIn ? "pill success" : "pill"}>{isLoggedIn ? "Token ready" : "Guest"}</span>
        </div>

        <div className="tabs" role="tablist" aria-label="Authentication mode">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
            <LogIn size={16} /> Login
          </button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
            <UserPlus size={16} /> Register
          </button>
        </div>

        <form onSubmit={submitAuth} className="form">
          <label>
            Email
            <input name="email" type="email" value={form.email} onChange={updateField} required />
          </label>

          {mode === "register" && (
            <label>
              Full name
              <input name="full_name" value={form.full_name} onChange={updateField} required minLength={2} />
            </label>
          )}

          <label>
            Password
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={updateField}
              required
              minLength={8}
            />
          </label>

          <button className="primary" disabled={loading} type="submit">
            <KeyRound size={17} /> {loading ? "Working..." : mode === "register" ? "Create account" : "Log in"}
          </button>
        </form>
      </section>

      {isLoggedIn && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Protected API</p>
              <h2>Current user</h2>
            </div>
            <CheckCircle2 size={22} />
          </div>

          <div className={`notice ${statusTone}`}>{message}</div>

          <div className="actions">
            <button onClick={loadProfile} disabled={loading} type="button">
              Load /me
            </button>
            <button onClick={refreshToken} disabled={!tokens?.refresh_token || loading} type="button">
              <RefreshCw size={16} /> Refresh
            </button>
            <button onClick={signOut} type="button">
              Sign out
            </button>
          </div>

          <pre className="profile">{profile ? JSON.stringify(profile, null, 2) : "No profile loaded yet."}</pre>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
