import { useEffect, useState } from "react";
import {
  DEFAULT_BASE_URL,
  fetchChain,
  fetchElectionResults,
  mineCluster,
  broadcastToNetwork,
  issueRegistrationCode,
} from "./api";

function StatCard({ label, value, icon }) {
  const icons = {
    chain: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
      </svg>
    ),
    votes: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    peers: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" />
      </svg>
    ),
    difficulty: (
      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
      </svg>
    ),
  };

  const accentMap = {
    blue: "from-blue-500 to-blue-600 shadow-blue-500/20",
    teal: "from-teal-500 to-teal-600 shadow-teal-500/20",
    amber: "from-amber-500 to-orange-500 shadow-amber-500/20",
    purple: "from-purple-500 to-violet-500 shadow-purple-500/20",
  };

  return (
    <div className="p-4 rounded-xl bg-white/90 border border-slate-200/60 shadow-sm flex items-center gap-3">
      {icon && (
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${accentMap[icon] || accentMap.blue} flex items-center justify-center shrink-0 shadow-lg`}>
          {icons[icon]}
        </div>
      )}
      <div>
        <p className="text-[11px] text-slate-500 font-medium uppercase tracking-wider m-0">{label}</p>
        <p className="text-xl font-bold text-slate-900 mt-0.5 m-0">{value}</p>
      </div>
    </div>
  );
}

function ElectionResults({ electionId, results }) {
  if (!results) {
    return <p className="text-sm text-slate-400 m-0">No results yet for this election.</p>;
  }

  const entries = Object.entries(results || {});
  if (!entries.length) {
    return <p className="text-sm text-slate-400 m-0">No votes counted yet.</p>;
  }

  const topVotes = Math.max(...entries.map(([, votes]) => votes), 0);
  const totalVotes = entries.reduce((sum, [, votes]) => sum + votes, 0);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-slate-500 font-medium m-0">
        Results for <span className="font-semibold text-slate-700">{electionId}</span> &mdash; {totalVotes} total vote{totalVotes === 1 ? "" : "s"}
      </p>
      <ul className="flex flex-col gap-2 m-0 p-0 list-none">
        {entries.map(([candidate, votes]) => {
          const widthPercent = topVotes > 0 ? Math.round((votes / topVotes) * 100) : 0;
          const percentOfTotal = totalVotes > 0 ? Math.round((votes / totalVotes) * 100) : 0;

          return (
            <li key={candidate} className="p-3 rounded-xl bg-white/90 border border-slate-200/60">
              <div className="flex justify-between items-center gap-3 mb-1.5">
                <span className="text-sm font-medium text-slate-700">{candidate}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">{votes} vote{votes === 1 ? "" : "s"}</span>
                  <span className="text-xs font-bold text-slate-900 bg-slate-100 px-1.5 py-0.5 rounded-md">{percentOfTotal}%</span>
                </div>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-teal-500 to-blue-500 transition-all duration-500"
                  style={{ width: `${widthPercent}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function AdminView({ adminToken: initialAdminToken = "", setAdminToken, onLogout }) {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [adminToken, setLocalAdminToken] = useState(initialAdminToken || "");
  const [chainData, setChainData] = useState(null);
  const [resultsData, setResultsData] = useState(null);
  const [resultElectionId, setResultElectionId] = useState("student-union-2026");
  const [miningLoading, setMiningLoading] = useState(false);
  const [broadcastLoading, setBroadcastLoading] = useState(false);
  const [issueLoading, setIssueLoading] = useState(false);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [issueExpiresMinutes, setIssueExpiresMinutes] = useState("60");
  const [issueElectionId, setIssueElectionId] = useState("student-union-2026");
  const [issueCodeResult, setIssueCodeResult] = useState("");
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await fetchChain(baseUrl);
        setChainData(data);
      } catch {}
    }, 5000);
    fetchChain(baseUrl).then(setChainData).catch(() => {});
    return () => clearInterval(interval);
  }, [baseUrl]);

  const loadResults = async () => {
    try {
      setResultsLoading(true);
      setActionError("");
      const data = await fetchElectionResults(baseUrl, resultElectionId);
      setResultsData(data.results || {});
    } catch (err) {
      setActionError(`Failed to load results: ${err.message}`);
    } finally {
      setResultsLoading(false);
    }
  };

  const handleMine = async () => {
    try {
      setMiningLoading(true);
      setActionError("");
      setActionMessage("");
      const tokenToUse = adminToken || "";
      const result = await mineCluster(baseUrl, 100, null, tokenToUse);
      const minedHash = result?.local?.hash || result?.hash;
      setActionMessage(
        minedHash
          ? `Cluster mining finished. Hash: ${minedHash.substring(0, 16)}...`
          : result?.message || "Cluster mining started"
      );
    } catch (err) {
      setActionError(`Mining failed: ${err.message}`);
    } finally {
      setMiningLoading(false);
    }
  };

  const handleBroadcast = async () => {
    try {
      setBroadcastLoading(true);
      setActionError("");
      setActionMessage("");
      const tokenToUse = adminToken || "";
      const result = await broadcastToNetwork(baseUrl, tokenToUse);
      setActionMessage(
        `Broadcast sent! Accepted: ${result.accepted}, Rejected: ${result.rejected}, Unreachable: ${result.unreachable}`
      );
    } catch (err) {
      setActionError(`Broadcast failed: ${err.message}`);
    } finally {
      setBroadcastLoading(false);
    }
  };

  const handleIssueCode = async () => {
    try {
      setIssueLoading(true);
      setActionError("");
      setIssueCodeResult("");

      const tokenToUse = adminToken || "";
      const payload = {
        election_id: issueElectionId?.trim() || undefined,
        expires_in_minutes: Number(issueExpiresMinutes) || 60,
      };

      const result = await issueRegistrationCode(baseUrl, payload, tokenToUse);
      setIssueCodeResult(result.registration_code);
      setActionMessage("Blind-vote invitation prepared. Share it with the voter.");
    } catch (err) {
      const errorMessage =
        err?.message ||
        (typeof err === "string" ? err : JSON.stringify(err)) ||
        "Unknown error";
      setActionError(`Code issuance failed: ${errorMessage}`);
    } finally {
      setIssueLoading(false);
    }
  };

  useEffect(() => {
    setLocalAdminToken(initialAdminToken || "");
  }, [initialAdminToken]);

  const stats = {
    chainLength: chainData?.chain?.length ?? "-",
    pendingVotes: chainData?.pending_votes ?? "-",
    peers: chainData?.nodes?.length ?? "-",
    difficulty: chainData?.difficulty ?? "-",
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      <aside className="w-full lg:w-64 shrink-0 p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md lg:self-start lg:sticky lg:top-0 flex flex-col gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-blue-600 m-0">Administration</p>
          <h2 className="text-lg font-bold text-slate-900 mt-1 m-0">Election Control</h2>
          <p className="text-xs text-slate-500 mt-1">Manage elections, mine blocks, and broadcast consensus.</p>
        </div>

        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">Node URL</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://127.0.0.1:8001"
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          />
        </div>

        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-xs font-medium text-slate-500">Admin Token</label>
            <div className="group relative">
              <svg className="w-3.5 h-3.5 text-slate-400 cursor-help" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
              </svg>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                <div className="bg-slate-800 text-white text-[11px] rounded-lg px-3 py-2 whitespace-nowrap shadow-lg">
                  Shared secret used by the backend to
                  <br />authorize admin operations (mining,
                  <br />broadcasting, issuing codes). Default
                  <br />is usually &quot;admin&quot; when configured.
                  <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
                </div>
              </div>
            </div>
          </div>
          <input
            type="password"
            value={adminToken}
            onChange={(e) => {
              const v = e.target.value;
              setLocalAdminToken(v);
              if (setAdminToken) setAdminToken(v);
            }}
            placeholder="Required to issue codes if configured"
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          />
        </div>

        {adminToken && (
          <button
            onClick={() => {
              setLocalAdminToken("");
              if (setAdminToken) setAdminToken("");
              if (onLogout) onLogout();
            }}
            className="w-full px-4 py-2 rounded-full text-sm font-medium text-slate-700 bg-white/80 border border-slate-200/80 hover:bg-white transition-colors"
          >
            Log out
          </button>
        )}

        {chainData && (
          <div className="flex flex-col gap-2 pt-2 border-t border-slate-200/60">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider m-0">Live Network</p>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 rounded-xl bg-white/80 border border-slate-200/60">
                <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider m-0">Chain</p>
                <p className="text-base font-bold text-slate-900 mt-0.5 m-0">{stats.chainLength}</p>
              </div>
              <div className="p-2.5 rounded-xl bg-white/80 border border-slate-200/60">
                <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider m-0">Pending</p>
                <p className="text-base font-bold text-slate-900 mt-0.5 m-0">{stats.pendingVotes}</p>
              </div>
              <div className="p-2.5 rounded-xl bg-white/80 border border-slate-200/60">
                <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider m-0">Peers</p>
                <p className="text-base font-bold text-slate-900 mt-0.5 m-0">{stats.peers}</p>
              </div>
              <div className="p-2.5 rounded-xl bg-white/80 border border-slate-200/60">
                <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider m-0">Difficulty</p>
                <p className="text-base font-bold text-slate-900 mt-0.5 m-0">{stats.difficulty}</p>
              </div>
            </div>
          </div>
        )}
      </aside>

      <div className="flex-1 min-w-0 flex flex-col gap-4">
        {chainData && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Chain Length" value={stats.chainLength} icon="chain" />
            <StatCard label="Pending Votes" value={stats.pendingVotes} icon="votes" />
            <StatCard label="Connected Peers" value={stats.peers} icon="peers" />
            <StatCard label="Difficulty" value={stats.difficulty} icon="difficulty" />
          </div>
        )}

        {actionMessage && (
          <div className="p-3 rounded-xl bg-emerald-50/80 border border-emerald-200 text-emerald-700 text-sm font-medium flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {actionMessage}
          </div>
        )}
        {actionError && (
          <div className="p-3 rounded-xl bg-red-50/80 border border-red-200 text-red-700 text-sm font-medium flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {actionError}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-slate-800 to-slate-700 flex items-center justify-center shadow-lg">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 m-0">Mining & Broadcasting</h3>
                <p className="text-xs text-slate-500 mt-0.5">Collect pending votes into blocks and sync with peers.</p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={handleMine}
                disabled={miningLoading}
                className="flex-1 px-5 py-3 rounded-xl text-sm font-bold text-white bg-gradient-to-br from-slate-800 to-slate-900 shadow-lg shadow-slate-900/20 hover:from-slate-700 hover:to-slate-800 transition-all duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
                {miningLoading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Mining...
                  </span>
                ) : "Mine Pending Votes"}
              </button>
              <button
                onClick={handleBroadcast}
                disabled={broadcastLoading}
                className="flex-1 px-5 py-3 rounded-xl text-sm font-bold text-slate-700 bg-white border-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-all duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25z" />
                </svg>
                {broadcastLoading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Broadcasting...
                  </span>
                ) : "Broadcast to Network"}
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-200/60">
              <p className="text-xs text-slate-500 m-0">
                <span className="font-medium text-slate-600">Mining</span> collects pending votes into a new block with proof-of-work.{' '}
                <span className="font-medium text-slate-600">Broadcasting</span> shares the latest blocks with peer nodes.
              </p>
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-teal-500/20">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 m-0">Blind-Vote Invitation</h3>
                <p className="text-xs text-slate-500 mt-0.5">Issue a one-time code for a voter to get a blind signature.</p>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label>
                  <span className="text-xs text-slate-500 font-medium block mb-1">Election ID (optional)</span>
                  <input
                    type="text"
                    value={issueElectionId}
                    onChange={(e) => setIssueElectionId(e.target.value)}
                    placeholder="student-union-2026"
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                  />
                </label>
                <label>
                  <span className="text-xs text-slate-500 font-medium block mb-1">Expires (minutes)</span>
                  <input
                    type="number"
                    min="1"
                    max="10080"
                    value={issueExpiresMinutes}
                    onChange={(e) => setIssueExpiresMinutes(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                  />
                </label>
              </div>
              <button
                onClick={handleIssueCode}
                disabled={issueLoading}
                className="w-full px-5 py-2.5 rounded-full text-sm font-medium text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20 hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {issueLoading ? "Preparing..." : "Prepare Invitation"}
              </button>
            </div>

            {issueCodeResult && (
              <div className="p-3 rounded-xl bg-blue-50/80 border border-blue-200 text-blue-800 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-blue-600 m-0">Invitation Code</p>
                  <button
                    onClick={() => copyToClipboard(issueCodeResult)}
                    className="flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800 transition-colors bg-white/60 px-2 py-1 rounded-lg border border-blue-200/60"
                  >
                    {copied ? (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                        Copied
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                        </svg>
                        Copy
                      </>
                    )}
                  </button>
                </div>
                <p className="font-mono font-bold text-sm break-all m-0">{issueCodeResult}</p>
              </div>
            )}
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 m-0">Election Results</h3>
              <p className="text-xs text-slate-500 mt-0.5">View vote tallies by election.</p>
            </div>
          </div>

          <div className="flex items-end gap-3">
            <label className="flex-1 max-w-xs">
              <span className="text-xs text-slate-500 font-medium block mb-1">Election ID</span>
              <input
                type="text"
                value={resultElectionId}
                onChange={(e) => setResultElectionId(e.target.value)}
                placeholder="student-union-2026"
                className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
              />
            </label>
            <button
              onClick={loadResults}
              disabled={resultsLoading}
              className="px-5 py-2 rounded-full text-sm font-medium text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20 hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {resultsLoading ? "Loading..." : "View Results"}
            </button>
          </div>

          {resultsData ? (
            <ElectionResults electionId={resultElectionId} results={resultsData} />
          ) : (
            <div className="p-6 rounded-xl bg-slate-50/80 border border-slate-200/60 flex flex-col items-center gap-2 text-center">
              <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              </svg>
              <p className="text-sm text-slate-400 m-0">Select an election and click "View Results" to see vote counts.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
