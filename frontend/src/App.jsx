import { useEffect, useMemo, useState } from "react";
import {
  castVote,
  DEFAULT_BASE_URL,
  fetchChain,
  fetchElectionResults,
  mineVotes,
  registerVoter,
  resolveConsensus
} from "./api";
import { clearWallet, createWallet, loadWallet, saveWallet, signVote } from "./wallet";

const VIEWS = {
  wallet: "Wallet",
  vote: "Vote",
  network: "Network",
  results: "Results",
  chain: "Chain"
};

function StatCard({ label, value, subtext }) {
  return (
    <div className="stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {subtext ? <p className="stat-subtext">{subtext}</p> : null}
    </div>
  );
}

function CandidateResultList({ results }) {
  const entries = Object.entries(results || {});

  if (!entries.length) {
    return <p className="muted">No votes have been counted for this election yet.</p>;
  }

  const topVotes = Math.max(...entries.map(([, votes]) => votes));

  return (
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
  );
}

function BlockList({ chainData }) {
  const blocks = chainData?.chain || [];

  if (!blocks.length) {
    return <p className="muted">No chain data available yet.</p>;
  }

  return (
    <div className="chain-list">
      {[...blocks].reverse().slice(0, 6).map((block) => (
        <article key={block.hash} className="chain-item">
          <div className="chain-item-head">
            <h3>Block #{block.index}</h3>
            <span>{new Date(block.timestamp * 1000).toLocaleString()}</span>
          </div>
          <p className="muted">Votes: {block.transactions.length}</p>
          <p className="hash-preview">{block.hash}</p>
          <div className="vote-chip-row">
            {block.transactions.slice(0, 3).map((vote, index) => (
              <div key={`${block.hash}-${index}`} className="vote-chip">
                {vote.voter_id || "?"} → {vote.candidate_id || "?"}
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function Sidebar({ activeView, setActiveView, loading }) {
  return (
    <aside className="sidebar panel">
      <div>
        <p className="eyebrow eyebrow-dark">Voting Console</p>
        <h2>Simple, signed voting</h2>
        <p className="muted">Create a local wallet, register it once, then vote without copying keys around.</p>
      </div>

      <nav className="nav-list" aria-label="Dashboard sections">
        {Object.entries(VIEWS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={activeView === key ? "nav-item active" : "nav-item"}
            onClick={() => setActiveView(key)}
            disabled={loading}
          >
            {label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

export default function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [activeView, setActiveView] = useState("wallet");
  const [wallet, setWallet] = useState(() => loadWallet());
  const [chainData, setChainData] = useState(null);
  const [resultsData, setResultsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [resultElectionId, setResultElectionId] = useState("student-union-2026");
  const [voteForm, setVoteForm] = useState({
    candidate_id: "",
    election_id: "student-union-2026"
  });

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
      chainLength: chainData.length,
      pendingVotes: chainData.pending_votes,
      peers: chainData.nodes?.length || 0,
      difficulty: chainData.difficulty,
      registeredVoters: chainData.registered_voters ?? "-"
    };
  }, [chainData]);

  async function refreshChain() {
    const data = await fetchChain(baseUrl);
    setChainData(data);
    return data;
  }

  async function refreshResults(electionId = resultElectionId) {
    if (!electionId.trim()) {
      setResultsData(null);
      return;
    }

    const data = await fetchElectionResults(baseUrl, electionId.trim());
    setResultsData(data);
  }

  async function syncWalletToNode(currentWallet = wallet) {
    if (!currentWallet) {
      throw new Error("Create a wallet first");
    }

    await registerVoter(baseUrl, {
      voter_id: currentWallet.voterId,
      voter_public_key: currentWallet.publicKey
    });
  }

  async function runAction(actionFn, successMessage) {
    setLoading(true);
    setActionError("");
    setActionMessage("");

    try {
      await actionFn();
      setActionMessage(successMessage);
      await refreshChain();
    } catch (error) {
      setActionError(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runAction(
      async () => {
        await refreshChain();
        await refreshResults(resultElectionId);
      },
      "Connected to node"
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (wallet) {
      setVoteForm((prev) => ({
        ...prev,
        election_id: prev.election_id || "student-union-2026"
      }));
    }
  }, [wallet]);

  useEffect(() => {
    if (activeView === "results") {
      refreshResults(resultElectionId).catch(() => undefined);
    }
  }, [activeView, resultElectionId]);

  const latestBlock = chainData?.chain?.[chainData.chain.length - 1];

  async function handleCreateWallet() {
    const nextWallet = createWallet();
    setWallet(nextWallet);
    saveWallet(nextWallet);
    setVoteForm((prev) => ({ ...prev, election_id: prev.election_id || "student-union-2026" }));

    try {
      await syncWalletToNode(nextWallet);
      setActionMessage("Wallet created and registered on the node");
      await refreshChain();
    } catch (error) {
      setActionError(error.message);
    }
  }

  function handleClearWallet() {
    clearWallet();
    setWallet(null);
    setActionMessage("Wallet removed from this browser");
    setActionError("");
  }

  async function handleCastVote() {
    if (!wallet) {
      throw new Error("Create a wallet first");
    }

    const signature = signVote(wallet, voteForm.candidate_id, voteForm.election_id);
    await castVote(baseUrl, {
      voter_id: wallet.voterId,
      candidate_id: voteForm.candidate_id,
      election_id: voteForm.election_id,
      voter_public_key: wallet.publicKey,
      signature
    });
  }

  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} setActiveView={setActiveView} loading={loading} />

      <div className="content-shell">
        <header className="topbar panel">
          <div>
            <p className="eyebrow eyebrow-dark">Blockchain Voting</p>
            <h1>Clean wallet-based voting</h1>
            <p className="subtitle subtitle-dark">
              Create a local wallet once, register it, and submit signed votes without handling raw keys.
            </p>
          </div>
          <div className="node-config compact">
            <label htmlFor="node-url">Node URL</label>
            <div className="input-row">
              <input
                id="node-url"
                type="url"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="http://127.0.0.1:8001"
              />
              <button
                type="button"
                onClick={() =>
                  runAction(async () => {
                    await refreshChain();
                    await refreshResults();
                  }, "Node refreshed")
                }
                disabled={loading}
              >
                Connect
              </button>
            </div>
          </div>
        </header>

        <section className="stats-grid">
          <StatCard label="Chain Length" value={networkStats.chainLength} />
          <StatCard label="Pending Votes" value={networkStats.pendingVotes} />
          <StatCard label="Peers" value={networkStats.peers} />
          <StatCard label="Difficulty" value={networkStats.difficulty} />
          <StatCard label="Registered Voters" value={networkStats.registeredVoters} />
        </section>

        {(actionMessage || actionError) && (
          <section className={`banner ${actionError ? "banner-error" : "banner-success"}`}>
            {actionError || actionMessage}
          </section>
        )}

        {activeView === "wallet" && (
          <section className="view-grid">
            <div className="panel">
              <h2>Wallet</h2>
              <p className="muted">Keep your vote signing private in this browser. No key pasting.</p>

              {wallet ? (
                <div className="wallet-card">
                  <div>
                    <p className="wallet-label">Wallet ID</p>
                    <h3>{wallet.voterId}</h3>
                    <p className="muted">Created {new Date(wallet.createdAt).toLocaleString()}</p>
                  </div>
                  <div className="wallet-key-block">
                    <p className="wallet-label">Public key</p>
                    <p className="hash-preview">{wallet.publicKey}</p>
                  </div>
                  <div className="stack-buttons inline-actions">
                    <button type="button" onClick={handleCreateWallet} disabled={loading}>
                      Recreate Wallet
                    </button>
                    <button type="button" className="ghost" onClick={handleClearWallet} disabled={loading}>
                      Remove Wallet
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() =>
                        runAction(async () => {
                          await syncWalletToNode();
                        }, "Wallet registered on node")
                      }
                      disabled={loading}
                    >
                      Register on Node
                    </button>
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <p>No wallet yet.</p>
                  <button type="button" onClick={handleCreateWallet} disabled={loading}>
                    Create Wallet
                  </button>
                </div>
              )}
            </div>

            <div className="panel">
              <h2>How it works</h2>
              <div className="info-list">
                <div className="info-row">
                  <span>1</span>
                  <p>Create a local wallet in your browser.</p>
                </div>
                <div className="info-row">
                  <span>2</span>
                  <p>Register the wallet key on the node once.</p>
                </div>
                <div className="info-row">
                  <span>3</span>
                  <p>Select Vote, choose a candidate, and submit a signed ballot.</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeView === "vote" && (
          <section className="view-grid">
            <div className="panel">
              <h2>Vote</h2>
              <p className="muted">Pick a candidate and the app signs the ballot with your local wallet.</p>

              <form
                className="form"
                onSubmit={(event) => {
                  event.preventDefault();
                  runAction(handleCastVote, "Signed vote submitted");
                }}
              >
                <label>
                  Candidate ID
                  <input
                    required
                    value={voteForm.candidate_id}
                    onChange={(event) =>
                      setVoteForm((prev) => ({ ...prev, candidate_id: event.target.value }))
                    }
                    placeholder="Alice"
                  />
                </label>
                <label>
                  Election ID
                  <input
                    required
                    value={voteForm.election_id}
                    onChange={(event) => {
                      setVoteForm((prev) => ({ ...prev, election_id: event.target.value }));
                      setResultElectionId(event.target.value);
                    }}
                    placeholder="student-union-2026"
                  />
                </label>
                <button type="submit" disabled={loading || !wallet}>
                  Submit Signed Vote
                </button>
              </form>

              {!wallet && <p className="notice">Create a wallet first to cast votes.</p>}
            </div>

            <div className="panel">
              <h2>Current ballot</h2>
              <div className="ballot-preview">
                <p><strong>Voter:</strong> {wallet?.voterId || "No wallet"}</p>
                <p><strong>Candidate:</strong> {voteForm.candidate_id || "—"}</p>
                <p><strong>Election:</strong> {voteForm.election_id || "—"}</p>
              </div>
            </div>
          </section>
        )}

        {activeView === "network" && (
          <section className="view-grid">
            <div className="panel">
              <h2>Network</h2>
              <p className="muted">Mine pending votes, resolve consensus, and refresh chain data.</p>
              <div className="stack-buttons">
                <button
                  type="button"
                  onClick={() =>
                    runAction(async () => {
                      await mineVotes(baseUrl);
                    }, "Mining completed")
                  }
                  disabled={loading}
                >
                  Mine Pending Votes
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() =>
                    runAction(async () => {
                      await resolveConsensus(baseUrl);
                    }, "Consensus resolved")
                  }
                  disabled={loading}
                >
                  Resolve Consensus
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() =>
                    runAction(async () => {
                      await refreshChain();
                      await refreshResults();
                    }, "Data refreshed")
                  }
                  disabled={loading}
                >
                  Refresh Data
                </button>
              </div>
            </div>

            <div className="panel">
              <h2>Network status</h2>
              <div className="mini-grid">
                <div>
                  <span className="wallet-label">Latest block</span>
                  <p>{latestBlock ? `#${latestBlock.index}` : "—"}</p>
                </div>
                <div>
                  <span className="wallet-label">Peers</span>
                  <p>{networkStats.peers}</p>
                </div>
                <div>
                  <span className="wallet-label">Registered voters</span>
                  <p>{networkStats.registeredVoters}</p>
                </div>
                <div>
                  <span className="wallet-label">Difficulty</span>
                  <p>{networkStats.difficulty}</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeView === "results" && (
          <section className="view-grid single-column">
            <div className="panel panel-wide">
              <div className="panel-head">
                <div>
                  <h2>Election Results</h2>
                  <p className="muted">Load a single election and inspect the current vote distribution.</p>
                </div>
                <div className="inline-input compact-input">
                  <input
                    value={resultElectionId}
                    onChange={(event) => setResultElectionId(event.target.value)}
                    placeholder="Enter election id"
                  />
                  <button
                    type="button"
                    className="ghost"
                    onClick={() =>
                      runAction(async () => {
                        await refreshResults(resultElectionId);
                      }, "Results refreshed")
                    }
                    disabled={loading}
                  >
                    Load
                  </button>
                </div>
              </div>

              {resultsData ? (
                <>
                  <div className="result-summary">
                    <StatCard label="Election ID" value={resultsData.election_id} />
                    <StatCard label="Total Votes" value={resultsData.total_votes} />
                    <StatCard label="Pending Votes" value={resultsData.pending_votes} />
                  </div>
                  <CandidateResultList results={resultsData.results} />
                </>
              ) : (
                <p className="muted">Load an election to see results.</p>
              )}
            </div>
          </section>
        )}

        {activeView === "chain" && (
          <section className="view-grid single-column">
            <div className="panel panel-wide">
              <h2>Chain Explorer</h2>
              <p className="muted">Recent blocks and a quick view of their vote payloads.</p>
              <BlockList chainData={chainData} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}