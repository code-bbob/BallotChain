import { useEffect, useState } from "react";
import AdminView from "./AdminView";
import VoterView from "./VoterView";
import AdminLogin from "./AdminLogin";

const MODE_STORAGE_KEY = "truevote.mode";
const ADMIN_TOKEN_STORAGE_KEY = "truevote.adminToken";

function readStoredValue(key, fallback = "") {
  if (typeof window === "undefined") {
    return fallback;
  }

  try {
    return window.localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

export default function App() {
  const [mode, setMode] = useState(() => readStoredValue(MODE_STORAGE_KEY, "select"));
  const [adminToken, setAdminToken] = useState(() => readStoredValue(ADMIN_TOKEN_STORAGE_KEY));

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      window.localStorage.setItem(MODE_STORAGE_KEY, mode);
      if (adminToken) {
        window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminToken);
      } else {
        window.localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
      }
    } catch {
      // Ignore storage failures and keep the in-memory session active.
    }
  }, [mode, adminToken]);

  const handleLogin = (token) => {
    setAdminToken(token);
    setMode("admin");
  };

  const handleLogout = () => {
    setAdminToken("");
    setMode("select");
  };

  const renderTopBar = (title, subtitle) => (
    <header className="topbar topbar-split">
      <div>
        <p className="eyebrow">TrueVote</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <button className="secondary" onClick={() => setMode("select")}>Back to hub</button>
      </div>
    </header>
  );

  if (mode === "admin") {
    return (
      <div className="page-shell admin-theme">
        <div className="page-frame">
          {renderTopBar(
            "Election Administration",
            "Manage voters, mine the cluster, and inspect the blockchain state."
          )}
          {!adminToken ? (
            <AdminLogin onLogin={handleLogin} onCancel={() => setMode("select")} />
          ) : (
            <AdminView adminToken={adminToken} setAdminToken={setAdminToken} onLogout={handleLogout} />
          )}
        </div>
      </div>
    );
  }

  if (mode === "voter") {
    return (
      <div className="page-shell voter-theme">
        <div className="page-frame">
          {renderTopBar(
            "Voting Console",
            "Blind-sign anonymous voting with live network feedback."
          )}
          <VoterView />
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell landing-theme">
      <div className="page-frame landing-frame">
        <header className="landing-header">
          <div>
            <p className="eyebrow">Blockchain voting</p>
            <div className="landing-brand-row">
              <h1>TrueVote</h1>
              <span className="status-chip">Live network demo</span>
            </div>
            <p className="landing-subtitle">
              Signed ballots, cluster mining, and peer replication presented as a clear product experience.
            </p>
          </div>

          <div className="landing-nav">
            <button className="ghost" onClick={() => setMode("admin")}>Governance</button>
            <button className="ghost" onClick={() => setMode("voter")}>Voting</button>
          </div>
        </header>

        <section className="hero-surface panel">
          <div className="hero-copy-block">
            <p className="eyebrow">Real-time election flow</p>
            <h2>Vote, mine, and verify in one coherent interface.</h2>
            <p className="hero-copy">
              The admin console issues blind-vote invitations, voters submit anonymous blind-signed ballots, and the network races to mine and propagate the winning block.
            </p>

            <div className="landing-actions">
              <button className="primary hero-button" onClick={() => setMode("admin")}>Open Governance Console</button>
              <button className="secondary hero-button" onClick={() => setMode("voter")}>Open Voter Console</button>
            </div>

            <div className="hero-pills">
              <span className="pill">Signed ballots</span>
              <span className="pill">Cluster mining</span>
              <span className="pill">Peer sync</span>
              <span className="pill">Live results</span>
            </div>

            <div className="landing-metrics">
              <div className="stat-card stat-card-compact">
                <p className="stat-label">Workflow</p>
                <p className="stat-value">Vote → Mempool → Mine</p>
              </div>
              <div className="stat-card stat-card-compact">
                <p className="stat-label">Consensus</p>
                <p className="stat-value">Winning chain wins</p>
              </div>
              <div className="stat-card stat-card-compact">
                <p className="stat-label">Visibility</p>
                <p className="stat-value">Blocks, hashes, peers</p>
              </div>
            </div>
          </div>

          <div className="hero-sidecard">
            <div className="hero-network-card">
              <p className="eyebrow">Live network</p>
              <h2>Observe the block race</h2>
              <p className="muted">
                Votes broadcast into mempools, miners compete, and the winning block propagates to every node.
              </p>
              <div className="network-steps">
                <div className="network-step">
                  <span>01</span>
                  <div>
                    <strong>Broadcast</strong>
                    <p>Pending votes are replicated to peers.</p>
                  </div>
                </div>
                <div className="network-step">
                  <span>02</span>
                  <div>
                    <strong>Mine</strong>
                    <p>Nodes race to solve the proof of work.</p>
                  </div>
                </div>
                <div className="network-step">
                  <span>03</span>
                  <div>
                    <strong>Sync</strong>
                    <p>The first valid block updates every chain.</p>
                  </div>
                </div>
              </div>
              <div className="mini-grid landing-mini-grid">
                <div>
                  <p className="stat-label">Flow</p>
                  <p className="stat-value">Vote → Mempool → Mine → Sync</p>
                </div>
                <div>
                  <p className="stat-label">Consensus</p>
                  <p className="stat-value">Chain wins</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="feature-grid">
          <article className="panel feature-card">
            <p className="eyebrow">Governance</p>
            <h2>Admin cockpit</h2>
            <p className="muted">Prepare blind-registration invitations, inspect the chain, and control mining from one focused dashboard.</p>
          </article>
          <article className="panel feature-card">
            <p className="eyebrow">Voting</p>
            <h2>Anonymous voting</h2>
            <p className="muted">Blind-sign your ballot locally, get admin authorization, and submit anonymously with instant feedback.</p>
          </article>
          <article className="panel feature-card">
            <p className="eyebrow">Transparency</p>
            <h2>Readable mining state</h2>
            <p className="muted">Track blocks, nonces, hashes, and pending votes as the network converges.</p>
          </article>
        </section>
      </div>
    </div>
  );
}
