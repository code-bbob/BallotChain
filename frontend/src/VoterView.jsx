import { useEffect, useState } from "react";
import {
  castVote,
  DEFAULT_BASE_URL,
  fetchChain,
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

function BlindVoteSection({ baseUrl, connected }) {
  const [electionId, setElectionId] = useState("student-union-2026");
  const [candidateId, setCandidateId] = useState("");
  const [registrationCode, setRegistrationCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [blindPublicKey, setBlindPublicKey] = useState(null);
  const [keyStatus, setKeyStatus] = useState("");

  useEffect(() => {
    if (!connected) {
      setBlindPublicKey(null);
      setKeyStatus("");
      return;
    }

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
  }, [baseUrl, connected]);

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

      const voteMessage = createBlindVoteMessage(candidateId, electionId);
      const nonce = parseNonceFromVoteMessage(voteMessage);

      const blindRequest = await createBlindVoteRequest(voteMessage, blindPublicKey);

      const signResponse = await requestBlindSignature(baseUrl, {
        registration_code: registrationCode.trim(),
        election_id: electionId.trim() || undefined,
        blinded_hash: `0x${blindRequest.blinded_hash_hex}`,
      });

      const unblindedSignature = unblindVoteSignature(
        signResponse.blind_signature,
        blindRequest.r_hex,
        blindPublicKey
      );

      const isValid = await verifyBlindVoteSignature(
        voteMessage,
        unblindedSignature,
        blindPublicKey
      );

      if (!isValid) {
        throw new Error("Blind signature verification failed locally");
      }

      await castVote(baseUrl, {
        candidate_id: candidateId.trim(),
        election_id: electionId.trim(),
        nonce,
        signature: `0x${unblindedSignature}`,
      });

      setMessage(`\u2713 Anonymous vote for ${candidateId} in ${electionId} submitted!`);
      setCandidateId("");
      setRegistrationCode("");
    } catch (err) {
      setError(`Vote submission failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
      <div>
        <h3 className="text-base font-bold text-slate-900 m-0">Cast Your Anonymous Vote</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Your vote is blinded before sending to the admin, then unblinded and submitted
          anonymously. No identity is attached to the on-chain vote.
        </p>
      </div>

      {keyStatus && (
        <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200 text-amber-800 text-sm">
          {keyStatus}
        </div>
      )}

      <form onSubmit={handleBlindVote} className="flex flex-col gap-3">
        <label>
          <span className="text-xs text-slate-500 font-medium block mb-1">Registration Invitation</span>
          <input
            type="text"
            value={registrationCode}
            onChange={(e) => setRegistrationCode(e.target.value)}
            placeholder="Paste invitation from admin"
            disabled={loading}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 disabled:opacity-50"
          />
        </label>
        <label>
          <span className="text-xs text-slate-500 font-medium block mb-1">Election ID</span>
          <input
            type="text"
            value={electionId}
            onChange={(e) => setElectionId(e.target.value)}
            placeholder="student-union-2026"
            disabled={loading}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 disabled:opacity-50"
          />
        </label>
        <label>
          <span className="text-xs text-slate-500 font-medium block mb-1">Candidate Name</span>
          <input
            type="text"
            value={candidateId}
            onChange={(e) => setCandidateId(e.target.value)}
            placeholder="e.g., Alice"
            disabled={loading}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 disabled:opacity-50"
          />
        </label>

        <button
          type="submit"
          disabled={loading || !connected || !blindPublicKey}
          className="w-full px-5 py-2.5 rounded-full text-sm font-medium text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20 hover:opacity-90 transition-opacity disabled:opacity-50 mt-1"
        >
          {loading ? "Submitting..." : !connected ? "Connect to node first" : "Submit Anonymous Vote"}
        </button>
      </form>

      {message && (
        <div className="p-3 rounded-xl bg-emerald-50/80 border border-emerald-200 text-emerald-700 text-sm font-medium">
          {message}
        </div>
      )}
      {error && (
        <div className="p-3 rounded-xl bg-red-50/80 border border-red-200 text-red-700 text-sm font-medium">
          {error}
        </div>
      )}
    </div>
  );
}

export default function VoterView() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [chainData, setChainData] = useState(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    if (!connected) return;
    const interval = setInterval(async () => {
      try {
        const data = await fetchChain(baseUrl);
        setChainData(data);
      } catch {
        // Silent fail for polling
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [baseUrl, connected]);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      const data = await fetchChain(baseUrl);
      setChainData(data);
      setConnected(true);
    } catch (err) {
      setChainData(null);
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = () => {
    setConnected(false);
    setChainData(null);
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      <aside className="w-full lg:w-64 shrink-0 p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md lg:self-start lg:sticky lg:top-0 flex flex-col gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-blue-600 m-0">Voting</p>
          <h2 className="text-lg font-bold text-slate-900 mt-1 m-0">Cast Your Vote</h2>
          <p className="text-xs text-slate-500 mt-1">
            Blind-sign anonymous voting. No wallet or identity required.
          </p>
        </div>

        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">Node URL</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            disabled={connected}
            placeholder="http://127.0.0.1:8001"
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-sm text-slate-900 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-400"
          />
        </div>

        {!connected ? (
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full px-4 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20 hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {connecting ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Connecting...
              </span>
            ) : "Connect to Node"}
          </button>
        ) : (
          <>
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
              <span className="text-xs font-medium text-emerald-700">Connected</span>
            </div>
            <button
              onClick={handleDisconnect}
              className="w-full px-4 py-2 rounded-xl text-xs font-medium text-slate-700 bg-white/80 border border-slate-200/80 hover:bg-white transition-colors"
            >
              Disconnect
            </button>
            <p className="text-[10px] text-slate-400 m-0 text-center">Auto-refreshes every 5s</p>
          </>
        )}

        {connected && chainData && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider m-0">Network Status</p>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-3 rounded-xl bg-white/80 border border-slate-200/60">
                <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider m-0">Chain Length</p>
                <p className="text-lg font-bold text-slate-900 mt-0.5 m-0">{chainData.chain?.length || 0}</p>
              </div>
              <div className="p-3 rounded-xl bg-white/80 border border-slate-200/60">
                <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider m-0">Pending Votes</p>
                <p className="text-lg font-bold text-slate-900 mt-0.5 m-0">{chainData.pending_votes || 0}</p>
              </div>
            </div>
          </div>
        )}
      </aside>

      <div className="flex-1 min-w-0 flex flex-col gap-4">
        <BlindVoteSection baseUrl={baseUrl} connected={connected} />
      </div>
    </div>
  );
}
