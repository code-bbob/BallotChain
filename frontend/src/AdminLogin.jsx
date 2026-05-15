import { useState } from "react";
import { adminLogin, DEFAULT_BASE_URL } from "./api";

export default function AdminLogin({ baseUrl = DEFAULT_BASE_URL, onLogin, onCancel }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await adminLogin(baseUrl, username, password);
      if (res && res.access_token) {
        onLogin(res.access_token);
      } else {
        setError("Login failed: no token received");
      }
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="auth-shell panel">
      <div className="auth-rail">
        <p className="eyebrow">Secure access</p>
        <h2>Admin Login</h2>
        <p className="muted">
          Sign in to manage elections, issue codes, and coordinate cluster mining.
        </p>

        <div className="auth-highlights">
          <div className="auth-highlight">
            <strong>Persisted session</strong>
            <span>Reloading the page keeps your admin session in place.</span>
          </div>
          <div className="auth-highlight">
            <strong>Network control</strong>
            <span>Mine, broadcast, and inspect the blockchain from one dashboard.</span>
          </div>
        </div>
      </div>

      <div className="auth-panel">
        <div className="auth-header">
          <div>
            <p className="eyebrow">Admin session</p>
            <h3>Enter your credentials</h3>
          </div>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        <div className="form auth-form">
          <label>
            Username
            <input
              placeholder="admin"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>

          <label>
            Password
            <input
              placeholder="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleLogin();
                }
              }}
            />
          </label>

          <div className="action-row">
            <button className="primary" onClick={handleLogin} disabled={loading}>
              {loading ? "Logging in..." : "Login"}
            </button>
            {onCancel && (
              <button className="secondary" onClick={onCancel} disabled={loading}>
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
