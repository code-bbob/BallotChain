import { useEffect, useState } from "react";
import {
  castVote,
  DEFAULT_BASE_URL,
  fetchChain,
  fetchElectionResults,
  mineCluster,
  fetchBlindPublicKey,
  requestBlindSignature,
} from "./api";
import {
  createBlindVoteMessage,
  createBlindVoteRequest,
  unblindVoteSignature,
  verifyBlindVoteSignature,
  parseNonceFromVoteMessage,
} from "./wallet";

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

function BlindVoteSection({ baseUrl }) {
  const [electionId, setElectionId] = useState("student-union-2026");
  const [candidateId, setCandidateId] = useState("");
  const [registrationCode, setRegistrationCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [blindPublicKey, setBlindPublicKey] = useState(null);
  const [keyStatus, setKeyStatus] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadBlindKey = async () => {
      try {
        setKeyStatus("Fetching blind-sign public key...");
        const key = await fetchBlindPublicKey(baseUrl);
        if (!cancelled) {
          setBlindPublicKey(key);
          setKeyStatus("");
        }
      } catch (err) {
        if (!cancelled) {
          setBlindPublicKey(null);
          setKeyStatus(`Could not fetch blind-sign key: ${err.message}`);
        }
      }
    };

    loadBlindKey();
    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  const handleBlindVote = async (e) => {
    e.preventDefault();

    if (!candidateId.trim()) {
      setError("Enter a candidate name");
      return;
    }

    if (!electionId.trim()) {
      setError("Enter an election ID");
      return;
    }

    if (!registrationCode.trim()) {
      setError("Enter your registration invitation code from the admin");
      return;
    }

    if (!blindPublicKey?.n || !blindPublicKey?.e) {
      setError("Blind-sign key unavailable from node");
      return;
    }

    try {
      setLoading(true);
      setMessage("");
      setError("");

      // Step 1: Create blind vote message with random nonce
      const voteMessage = createBlindVoteMessage(candidateId, electionId);
      const nonce = parseNonceFromVoteMessage(voteMessage);

      // Step 2: Blind the vote hash
      const blindRequest = await createBlindVoteRequest(voteMessage, blindPublicKey);

      // Step 3: Request admin blind signature
      const signResponse = await requestBlindSignature(baseUrl, {
        registration_code: registrationCode.trim(),
        election_id: electionId.trim() || undefined,
        blinded_hash: `0x${blindRequest.blinded_hash_hex}`,
      });

      // Step 4: Unblind the signature
      const unblindedSignature = unblindVoteSignature(
        signResponse.blind_signature,
        blindRequest.r_hex,
        blindPublicKey
      );

      // Step 5: Verify locally (optional — catches tampering early)
      const isValid = await verifyBlindVoteSignature(
        voteMessage,
        unblindedSignature,
        blindPublicKey
      );

      if (!isValid) {
        throw new Error("Blind signature verification failed locally");
      }

      // Step 6: Submit anonymous vote
      await castVote(baseUrl, {
        candidate_id: candidateId.trim(),
        election_id: electionId.trim(),
        nonce,
        signature: `0x${unblindedSignature}`,
      });

      setMessage(`✓ Anonymous vote for ${candidateId} in ${electionId} submitted!`);
      setCandidateId("");
      setRegistrationCode("");
    } catch (err) {
      setError(`Vote submission failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3>Cast Your Anonymous Vote</h3>
      <p className="muted">
        Your vote is blinded before sending to the admin, then unblinded and submitted
        anonymously. No identity is attached to the on-chain vote.
      </p>

      {keyStatus && <div className="notice">{keyStatus}</div>}

      <form onSubmit={handleBlindVote} className="form">
        <label>
          Registration Invitation
          <input
            type="text"
            value={registrationCode}
            onChange={(e) => setRegistrationCode(e.target.value)}
            placeholder="Paste invitation from admin"
            disabled={loading}
          />
        </label>
        <label>
          Election ID
          <input
            type="text"
            value={electionId}
            onChange={(e) => setElectionId(e.target.value)}
            placeholder="student-union-2026"
            disabled={loading}
          />
        </label>
        <label>
          Candidate Name
          <input
            type="text"
            value={candidateId}
            onChange={(e) => setCandidateId(e.target.value)}
            placeholder="e.g., Alice"
            disabled={loading}
          />
        </label>

        <button type="submit" disabled={loading || !blindPublicKey}>
          {loading ? "Submitting..." : "Submit Anonymous Vote"}
        </button>
      </form>

      {message && <div className="banner banner-success">{message}</div>}
      {error && <div className="banner banner-error">{error}</div>}
    </div>
  );
}

export default function VoterView() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [chainData, setChainData] = useState(null);
  const [mining, setMining] = useState(false);
  const [miningInfo, setMiningInfo] = useState(null);

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

  const handleClusterMine = async () => {
    if (mining) return;
    const prevLength = chainData?.chain?.length || 0;
    const prevPending = chainData?.pending_votes || 0;
    setMining(true);
    setMiningInfo({ status: "starting" });

    try {
      const res = await mineCluster(baseUrl, 100);
      setMiningInfo({ status: "mining", response: res });

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
            Blind-sign anonymous voting. No wallet or identity required.
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
            <p className="subtitle">Blind-signature anonymous voting</p>
          </div>
        </div>

        <BlindVoteSection baseUrl={baseUrl} />

        <div className="view-grid">
          <div />
          <ResultsSection baseUrl={baseUrl} />
        </div>
      </div>
    </div>
  );
}
