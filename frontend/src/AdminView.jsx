import { useEffect, useMemo, useState } from "react";
import {
  DEFAULT_BASE_URL,
  fetchChain,
  fetchElectionResults,
  mineCluster,
  fetchVoters,
  broadcastToNetwork,
  createElection,
  issueRegistrationCode,
} from "./api";

function StatCard({ label, value, subtext }) {
  return (
    <div className="stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {subtext ? <p className="stat-subtext">{subtext}</p> : null}
    </div>
  );
}

function BlockList({ chainData }) {
  const blocks = chainData?.chain || [];

  if (!blocks.length) {
    return <p className="muted">No blocks yet.</p>;
  }

  return (
    <div className="chain-list">
      {[...blocks].reverse().slice(0, 10).map((block) => (
        <article key={block.hash} className="chain-item">
          <div className="chain-item-head">
            <h3>Block #{block.index}</h3>
            <span>{new Date(block.timestamp * 1000).toLocaleString()}</span>
          </div>
          <p className="muted">Votes: {block.transactions.length}</p>
          <p className="hash-preview">Hash: {block.hash.substring(0, 16)}...</p>
          <p className="hash-preview">Nonce: {block.nonce}</p>
          {block.transactions.length > 0 && (
            <div className="vote-chip-row">
              {block.transactions.slice(0, 5).map((vote, index) => (
                <div key={`${block.hash}-${index}`} className="vote-chip">
                  {vote.voter_id} → {vote.candidate_id}
                </div>
              ))}
              {block.transactions.length > 5 && (
                <div className="vote-chip">+{block.transactions.length - 5} more</div>
              )}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

function VoterRegistry({ voters, totalVoters }) {
  return (
    <div className="info-list">
      <p className="stat-label">Registered Voters: {totalVoters}</p>
      {totalVoters === 0 ? (
        <p className="muted">No voters registered yet.</p>
      ) : (
        <div style={{ marginTop: "0.75rem", maxHeight: "200px", overflowY: "auto" }}>
          {Object.entries(voters || {}).slice(0, 15).map(([voterId, pubKey]) => (
            <div key={voterId} className="info-row">
              <span>✓</span>
              <div>
                <strong>{voterId}</strong>
                <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0 0" }}>
                  {pubKey.substring(0, 20)}...
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ElectionResults({ electionId, results }) {
  if (!results) {
    return <p className="muted">No results yet for this election.</p>;
  }

  const entries = Object.entries(results || {});
  if (!entries.length) {
    return <p className="muted">No votes counted yet.</p>;
  }

  const topVotes = Math.max(...entries.map(([, votes]) => votes), 0);
  const totalVotes = entries.reduce((sum, [, votes]) => sum + votes, 0);

  return (
    <div>
      <p className="stat-label">Results for {electionId} (Total: {totalVotes})</p>
      <ul className="result-list">
        {entries.map(([candidate, votes]) => {
          const widthPercent = topVotes > 0 ? Math.round((votes / topVotes) * 100) : 0;

          return (
            <li key={candidate} className="result-item">
              <div className="result-header">
                <span>{candidate}</span>
                <strong>
                  {votes} vote{votes === 1 ? "" : "s"}
                </strong>
              </div>
              <div className="result-track">
                <div className="result-fill" style={{ width: `${widthPercent}%` }} />
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
  const [voters, setVoters] = useState({});
  const [resultsData, setResultsData] = useState(null);
  const [resultElectionId, setResultElectionId] = useState("student-union-2026");
  const [newElectionId, setNewElectionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [issueVoterId, setIssueVoterId] = useState("");
  const [issueExpiresMinutes, setIssueExpiresMinutes] = useState("60");
  const [issueElectionId, setIssueElectionId] = useState("student-union-2026");
  const [issueCodeResult, setIssueCodeResult] = useState("");

  const networkStats = useMemo(() => {
    if (!chainData) {
      return {
        chainLength: "-",
        pendingVotes: "-",
        peers: "-",
        difficulty: "-",
        registeredVoters: "-"
      };
    }

    return {
      chainLength: chainData.chain?.length || 0,
      pendingVotes: chainData.pending_votes,
      peers: chainData.nodes?.length || 0,
      difficulty: chainData.difficulty,
      registeredVoters: Object.keys(voters).length || 0
    };
  }, [chainData, voters]);

  const loadChainData = async () => {
    try {
      setLoading(true);
      setActionError("");
      const data = await fetchChain(baseUrl);
      setChainData(data);
    } catch (err) {
      setActionError(`Failed to load chain: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadVoters = async () => {
    try {
      const data = await fetchVoters(baseUrl);
      setVoters(data.voter_registry || {});
    } catch (err) {
      setActionError(`Failed to load voters: ${err.message}`);
    }
  };

  const loadResults = async () => {
    try {
      setLoading(true);
      const data = await fetchElectionResults(baseUrl, resultElectionId);
      setResultsData(data.results || {});
    } catch (err) {
      setActionError(`Failed to load results: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleMine = async () => {
    try {
      setLoading(true);
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
      await loadChainData();
    } catch (err) {
      setActionError(`Mining failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleBroadcast = async () => {
    try {
      setLoading(true);
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
      setLoading(false);
    }
  };

  const handleIssueCode = async () => {
    try {
      setLoading(true);
      setActionError("");
      setIssueCodeResult("");

      if (!issueVoterId.trim()) {
        throw new Error("Enter a voter ID");
      }

      const tokenToUse = adminToken || "";
      const result = await issueRegistrationCode(
        baseUrl,
        {
          voter_id: issueVoterId.trim(),
          election_id: issueElectionId?.trim() || undefined,
          expires_in_minutes: Number(issueExpiresMinutes) || 60,
        },
        tokenToUse
      );

      setIssueCodeResult(result.registration_code);
      setActionMessage(
        `Registration code issued for ${result.voter_id}. Share it with the voter.`
      );
    } catch (err) {
      setActionError(`Code issuance failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Load once on mount (or when `baseUrl` changes). Manual refresh available.
    loadChainData();
    loadVoters();
    return () => {};
  }, [baseUrl]);

  // Keep local token in sync with prop updates to avoid input flicker
  useEffect(() => {
    setLocalAdminToken(initialAdminToken || "");
  }, [initialAdminToken]);

  return (
    <div className="app-shell">
      <aside className="sidebar panel">
        <div>
          <p className="eyebrow eyebrow-dark">Administration</p>
          <h2>Election Control</h2>
          <p className="muted">Manage elections, mine blocks, and broadcast consensus.</p>
        </div>

        <div className="node-config">
          <label className="wallet-label">Node URL</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://127.0.0.1:8001"
          />
        </div>

        <div className="node-config">
          <label className="wallet-label">Admin Token</label>
          <input
            type="password"
            value={adminToken}
            onChange={(e) => {
              const v = e.target.value;
              setLocalAdminToken(v);
              if (setAdminToken) setAdminToken(v);
            }}
            placeholder="Required to issue codes if configured"
          />
        </div>
        {adminToken && (
          <div style={{ marginTop: "0.5rem" }}>
            <button
              className="secondary"
              onClick={() => {
                setLocalAdminToken("");
                if (setAdminToken) setAdminToken("");
                if (onLogout) onLogout();
              }}
            >
              Log out
            </button>
          </div>
        )}

      </aside>

      <div className="content-shell">
        <div className="topbar topbar-split">
          <div>
            <h1>Election Administration</h1>
            <p className="subtitle">Mining, broadcasting, and result aggregation</p>
          </div>
          <div className="topbar-actions">
            <button className="secondary" onClick={loadChainData} disabled={loading}>
              Refresh
            </button>
          </div>
        </div>

        {actionMessage && <div className="banner banner-success">{actionMessage}</div>}
        {actionError && <div className="banner banner-error">{actionError}</div>}

        <div className="stats-grid">
          <StatCard label="Chain Length" value={networkStats.chainLength} />
          <StatCard label="Pending Votes" value={networkStats.pendingVotes} />
          <StatCard label="Connected Peers" value={networkStats.peers} />
          <StatCard label="Difficulty" value={networkStats.difficulty} />
          <StatCard label="Registered Voters" value={networkStats.registeredVoters} />
        </div>

        <div className="view-grid">
          <div className="panel">
            <h3>Mining & Broadcasting</h3>
            <button className="primary" onClick={handleMine} disabled={loading}>
              {loading ? "Processing..." : "Mine Pending Votes"}
            </button>
            <button className="secondary stack-action" onClick={handleBroadcast} disabled={loading}>
              Broadcast to Network
            </button>
            <p className="notice">
              Mining collects pending votes into a block. Broadcasting shares the latest blocks with peers.
            </p>
          </div>

          <div className="panel">
            <h3>Issue Registration Code</h3>
            <div className="form">
              <label>
                Voter ID
                <input
                  type="text"
                  value={issueVoterId}
                  onChange={(e) => setIssueVoterId(e.target.value)}
                  placeholder="wallet-voter id"
                />
              </label>
              <label>
                Election ID (optional)
                <input
                  type="text"
                  value={issueElectionId}
                  onChange={(e) => setIssueElectionId(e.target.value)}
                  placeholder="student-union-2026"
                />
              </label>
              <label>
                Expiry Minutes
                <input
                  type="number"
                  min="1"
                  max="10080"
                  value={issueExpiresMinutes}
                  onChange={(e) => setIssueExpiresMinutes(e.target.value)}
                />
              </label>
              <button className="primary" onClick={handleIssueCode} disabled={loading}>
                Issue One-Time Code
              </button>
            </div>
            {issueCodeResult && (
              <div className="notice" style={{ wordBreak: "break-all" }}>
                Code: <strong>{issueCodeResult}</strong>
              </div>
            )}
          </div>

          <div className="panel">
            <h3>Election Results</h3>
            <div className="form">
              <label>
                Election ID
                <input
                  type="text"
                  value={resultElectionId}
                  onChange={(e) => setResultElectionId(e.target.value)}
                  placeholder="student-union-2026"
                />
              </label>
              <button className="primary" onClick={loadResults} disabled={loading}>
                Load Results
              </button>
            </div>
          </div>
        </div>

        <div className="panel panel-wide">
          <h3>Blockchain State</h3>
          <button className="secondary stack-action" onClick={loadChainData} disabled={loading}>
            Refresh Blockchain
          </button>
          <BlockList chainData={chainData} />
        </div>

        <div className="view-grid">
          <div className="panel">
            <VoterRegistry voters={voters} totalVoters={networkStats.registeredVoters} />
          </div>

          <div className="panel">
            {resultsData && (
              <ElectionResults electionId={resultElectionId} results={resultsData} />
            )}
            {!resultsData && (
              <p className="muted">Select an election and click "Load Results" to view vote counts.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
