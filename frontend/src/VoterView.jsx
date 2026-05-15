import { useEffect, useState } from "react";
import {
  castVote,
  DEFAULT_BASE_URL,
  fetchChain,
  fetchElectionResults,
  registerVoter,
  mineCluster,
} from "./api";
import { clearWallet, createWallet, loadWallet, saveWallet, signVote } from "./wallet";

function StatCard({ label, value, subtext }) {
  return (
    <div className="stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {subtext ? <p className="stat-subtext">{subtext}</p> : null}
    </div>
  );
}

function WalletSection({ wallet, onCreateWallet, onClearWallet }) {
  if (!wallet) {
    return (
      <div className="panel">
        <h3>Create Your Wallet</h3>
        <p className="muted">Generate a new wallet to sign and cast votes.</p>
        <button onClick={onCreateWallet}>Generate New Wallet</button>
        <div className="wallet-card">
          <p className="notice">
            Your wallet is stored locally in your browser. Keep your private key secret!
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <h3>Your Wallet</h3>
      <div className="wallet-card">
        <p className="wallet-label">Voter ID</p>
        <div className="wallet-key-block">
          <code style={{ wordBreak: "break-all" }}>{wallet.voter_id}</code>
        </div>
      </div>

      <div className="wallet-card">
        <p className="wallet-label">Public Key (for registration)</p>
        <div className="wallet-key-block">
          <code style={{ wordBreak: "break-all", fontSize: "0.75rem" }}>
            {wallet.public_key}
          </code>
        </div>
      </div>

      <div className="wallet-card">
        <p className="wallet-label">Private Key (KEEP SECRET!)</p>
        <div className="wallet-key-block" style={{ background: "#fef2f2", borderColor: "#fecaca" }}>
          <code style={{ wordBreak: "break-all", fontSize: "0.75rem", color: "#991b1b" }}>
            {wallet.private_key}
          </code>
        </div>
      </div>

      <button onClick={onClearWallet} className="ghost" style={{ marginTop: "0.75rem" }}>
        Clear Wallet
      </button>
    </div>
  );
}

function RegistrationSection({ wallet, baseUrl, onRegistered }) {
  const [isRegistered, setIsRegistered] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [registrationCode, setRegistrationCode] = useState("");
  const [registrationElectionId, setRegistrationElectionId] = useState("student-union-2026");

  const handleRegister = async () => {
    if (!wallet) {
      setError("Create a wallet first");
      return;
    }

    if (!registrationCode.trim()) {
      setError("Enter the registration code from the admin");
      return;
    }

    try {
      setLoading(true);
      setMessage("");
      setError("");
      await registerVoter(baseUrl, {
        voter_id: wallet.voter_id,
        voter_public_key: wallet.public_key,
        registration_code: registrationCode.trim(),
        election_id: registrationElectionId?.trim() || undefined,
      });
      setMessage("✓ Registered successfully!");
      setIsRegistered(true);
      setRegistrationCode("");
      onRegistered();
    } catch (err) {
      setError(`Registration failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3>Voter Registration</h3>
      <p className="muted">Use the one-time code issued by the admin to bind this wallet to your voter record.</p>
      {isRegistered || wallet?.registered ? (
        <div className="banner banner-success">✓ Your wallet is registered and ready to vote.</div>
      ) : (
        <div className="form">
          <label>
            Registration Code
            <input
              type="text"
              value={registrationCode}
              onChange={(e) => setRegistrationCode(e.target.value)}
              placeholder="Enter one-time code"
              disabled={!wallet || loading}
            />
          </label>
          <label>
            Election ID
            <input
              type="text"
              value={registrationElectionId}
              onChange={(e) => setRegistrationElectionId(e.target.value)}
              placeholder="student-union-2026"
              disabled={!wallet || loading}
            />
          </label>
          <button onClick={handleRegister} disabled={!wallet || loading}>
            {loading ? "Registering..." : "Register This Wallet"}
          </button>
          {message && <div className="banner banner-success" style={{ marginTop: "0.75rem" }}>{message}</div>}
          {error && <div className="banner banner-error" style={{ marginTop: "0.75rem" }}>{error}</div>}
        </div>
      )}
    </div>
  );
}

function VotingSection({ wallet, baseUrl, isRegistered }) {
  const [electionId, setElectionId] = useState("student-union-2026");
  const [candidateId, setCandidateId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleVote = async (e) => {
    e.preventDefault();

    if (!wallet || !isRegistered) {
      setError("Create and register wallet first");
      return;
    }

    if (!candidateId.trim()) {
      setError("Enter a candidate name");
      return;
    }

    try {
      setLoading(true);
      setMessage("");
      setError("");

      const signature = signVote(
        wallet.voter_id,
        candidateId,
        electionId,
        wallet.private_key
      );

      await castVote(baseUrl, {
        voter_id: wallet.voter_id,
        candidate_id: candidateId,
        election_id: electionId,
        voter_public_key: wallet.public_key,
        signature: signature,
      });

      setMessage(`✓ Vote for ${candidateId} in ${electionId} submitted!`);
      setCandidateId("");
    } catch (err) {
      setError(`Vote submission failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3>Cast Your Vote</h3>
      <form onSubmit={handleVote} className="form">
        <label>
          Election ID
          <input
            type="text"
            value={electionId}
            onChange={(e) => setElectionId(e.target.value)}
            placeholder="student-union-2026"
            disabled={!isRegistered}
          />
        </label>

        <label>
          Candidate Name
          <input
            type="text"
            value={candidateId}
            onChange={(e) => setCandidateId(e.target.value)}
            placeholder="e.g., Alice"
            disabled={!isRegistered}
          />
        </label>

        <button type="submit" disabled={!isRegistered || loading}>
          {loading ? "Submitting..." : "Submit Vote"}
        </button>
      </form>

      {message && <div className="banner banner-success">{message}</div>}
      {error && <div className="banner banner-error">{error}</div>}

      {!isRegistered && (
        <div className="notice">Register your wallet first before voting.</div>
      )}
    </div>
  );
}

function ResultsSection({ baseUrl }) {
  const [electionId, setElectionId] = useState("student-union-2026");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadResults = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await fetchElectionResults(baseUrl, electionId);
      setResults(data.results || {});
    } catch (err) {
      setError(`Failed to load results: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3>Election Results</h3>
      <div className="form">
        <label>
          Election ID
          <input
            type="text"
            value={electionId}
            onChange={(e) => setElectionId(e.target.value)}
            placeholder="student-union-2026"
          />
        </label>
        <button onClick={loadResults} disabled={loading}>
          {loading ? "Loading..." : "View Results"}
        </button>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      {results && Object.keys(results).length > 0 ? (
        <ul className="result-list">
          {Object.entries(results).map(([candidate, votes]) => {
            const total = Object.values(results).reduce((a, b) => a + b, 0);
            const percent = total > 0 ? Math.round((votes / total) * 100) : 0;
            return (
              <li key={candidate} className="result-item">
                <div className="result-header">
                  <span>{candidate}</span>
                  <strong>
                    {votes} vote{votes === 1 ? "" : "s"} ({percent}%)
                  </strong>
                </div>
                <div className="result-track">
                  <div className="result-fill" style={{ width: `${percent}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        results && <p className="muted">No votes counted yet for this election.</p>
      )}
    </div>
  );
}

export default function VoterView() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [wallet, setWallet] = useState(() => loadWallet());
  const [chainData, setChainData] = useState(null);
  const [isRegistered, setIsRegistered] = useState(false);
  const [mining, setMining] = useState(false);
  const [miningInfo, setMiningInfo] = useState(null);

  const handleCreateWallet = () => {
    const newWallet = createWallet();
    saveWallet(newWallet);
    setWallet(newWallet);
  };

  const handleClearWallet = () => {
    if (confirm("Are you sure? This will delete your local wallet.")) {
      clearWallet();
      setWallet(null);
      setIsRegistered(false);
    }
  };

  const handleRegistered = () => {
    setIsRegistered(true);
  };

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await fetchChain(baseUrl);
        setChainData(data);
      } catch {
        // Silent fail for polling
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [baseUrl]);

  useEffect(() => {
    return () => {
      // cleanup if unmounting while mining
      setMining(false);
    };
  }, []);

  const handleClusterMine = async () => {
    if (mining) return;
    const prevLength = chainData?.chain?.length || 0;
    const prevPending = chainData?.pending_votes || 0;
    setMining(true);
    setMiningInfo({ status: "starting" });

    try {
      const res = await mineCluster(baseUrl, 100);
      setMiningInfo({ status: "mining", response: res });

      // poll for chain change or pending txs decrease
      const start = Date.now();
      const pollId = setInterval(async () => {
        try {
          const data = await fetchChain(baseUrl);
          setChainData(data);
          if ((data.chain?.length || 0) > prevLength || (data.pending_votes || 0) < prevPending) {
            clearInterval(pollId);
            setMining(false);
            setMiningInfo((old) => ({ ...old, status: "finished", final: data, elapsed_ms: Date.now() - start }));
          }
        } catch (e) {
          // ignore
        }
      }, 1000);
    } catch (err) {
      setMining(false);
      setMiningInfo({ status: "error", error: err.message });
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar panel">
        <div>
          <p className="eyebrow eyebrow-dark">Voting</p>
          <h2>Cast Your Vote</h2>
          <p className="muted">
            Create a wallet, register, and submit cryptographically signed votes.
          </p>
        </div>

        <div className="node-config">
          <label className="wallet-label">Node URL</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://127.0.0.1:8001"
          />
          <div style={{ marginTop: "0.5rem" }}>
            <button onClick={handleClusterMine} disabled={mining}>
              {mining ? "Mining…" : "Mine (cluster)"}
            </button>
            {miningInfo && (
              <div style={{ marginTop: "0.5rem" }}>
                <small>
                  {miningInfo.status === "starting" && "Starting cluster mine..."}
                  {miningInfo.status === "mining" && `Mining started — peers: ${JSON.stringify(miningInfo.response?.peers || {})}`}
                  {miningInfo.status === "finished" && `Done in ${Math.round((miningInfo.elapsed_ms||0)/1000)}s`}
                  {miningInfo.status === "error" && `Error: ${miningInfo.error}`}
                </small>
              </div>
            )}
          </div>
        </div>

        {chainData && (
          <div style={{ marginTop: "1rem" }}>
            <p className="stat-label">Network Status</p>
            <div className="mini-grid">
              <div>
                <p className="stat-label">Chain Length</p>
                <p className="stat-value">{chainData.chain?.length || 0}</p>
              </div>
              <div>
                <p className="stat-label">Pending Votes</p>
                <p className="stat-value">{chainData.pending_votes || 0}</p>
              </div>
            </div>
          </div>
        )}
      </aside>

      <div className="content-shell">
        <div className="topbar">
          <div>
            <h1>Voting Console</h1>
            <p className="subtitle">Ed25519 signed, verifiable voting</p>
          </div>
        </div>

        <WalletSection
          wallet={wallet}
          onCreateWallet={handleCreateWallet}
          onClearWallet={handleClearWallet}
        />

        {wallet && (
          <>
            <RegistrationSection
              wallet={wallet}
              baseUrl={baseUrl}
              onRegistered={handleRegistered}
            />

            <div className="view-grid">
              <VotingSection wallet={wallet} baseUrl={baseUrl} isRegistered={isRegistered} />
              <ResultsSection baseUrl={baseUrl} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
