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
    <div className="flex items-center justify-center p-4">
      <div className="w-full max-w-md flex flex-col gap-6">
        <div className="text-center">
          <div className="inline-flex items-center justify-center size-14 rounded-2xl bg-gradient-to-br from-teal-600 to-blue-600 text-white shadow-lg shadow-blue-600/20 mb-4">
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 m-0">Admin Login</h1>
          <p className="text-sm text-slate-500 mt-1.5 max-w-sm mx-auto">
            Sign in to manage elections, issue registration codes, mine blocks, and control the network.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white/80 border border-slate-200/60 shadow-sm backdrop-blur-md flex flex-col gap-5">
          {error && (
            <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm">
              <svg className="w-5 h-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-slate-700">Username</label>
              <input
                placeholder="admin"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-slate-700">Password</label>
              <input
                placeholder="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLogin();
                }}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleLogin}
              disabled={loading}
              className="flex-1 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20 hover:opacity-90 transition-all disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
            {onCancel && (
              <button
                onClick={onCancel}
                disabled={loading}
                className="px-5 py-2.5 rounded-xl text-sm font-medium text-slate-700 bg-white border border-slate-200/80 hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="p-3.5 rounded-xl bg-white/60 border border-slate-200/40 flex flex-col gap-1">
            <span className="text-xs font-bold text-slate-800">Persisted session</span>
            <span className="text-[11px] text-slate-500 leading-relaxed">Reloading keeps your admin session in place.</span>
          </div>
          <div className="p-3.5 rounded-xl bg-white/60 border border-slate-200/40 flex flex-col gap-1">
            <span className="text-xs font-bold text-slate-800">Network control</span>
            <span className="text-[11px] text-slate-500 leading-relaxed">Mine, broadcast, and inspect from one dashboard.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
