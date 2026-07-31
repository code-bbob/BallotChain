import { useEffect, useMemo, useState } from "react";
import { DEFAULT_BASE_URL, fetchChain, fetchNodeState, revalidateChain, resolveConsensus } from "./api";

function humanizeError(msg) {
  if (!msg) return "An unknown error occurred";
  return msg
    .replace(/!=/g, "mismatch at")
    .replace(/failed to match previous hash/g, "hash chain broken")
    .replace(/invalid proof of work/g, "proof of work invalid")
    .replace(/No chain/g, "The chain is empty")
    .replace(/not found/g, "was not found");
}

function Toast({ message, type, onDismiss }) {
  if (!message) return null;
  const styles = {
    success: "bg-emerald-50 border-emerald-200 text-emerald-800",
    error: "bg-red-50 border-red-200 text-red-800",
    info: "bg-blue-50 border-blue-200 text-blue-800",
  };
  const icons = {
    success: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
    error: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z",
    info: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  };
  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl border ${styles[type] || styles.info}`}>
      <svg className="w-5 h-5 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d={icons[type] || icons.info} />
      </svg>
      <p className="text-sm flex-1 m-0">{message}</p>
      <button onClick={onDismiss} className="opacity-50 hover:opacity-100 shrink-0 p-0.5">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="p-4 rounded-xl bg-white/80 border border-slate-200/60">
      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider m-0">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1 m-0">{value}</p>
    </div>
  );
}

function BlockRow({ block, defaultExpanded }) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const time = new Date(block.timestamp * 1000);
  const dateStr = time.toLocaleDateString();
  const timeStr = time.toLocaleTimeString();

  return (
    <div className="border border-slate-200/60 rounded-xl bg-white/90 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-slate-50/50 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2 w-24 shrink-0">
          <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-500 to-blue-500 text-white text-[11px] font-bold flex items-center justify-center shrink-0">
            {block.index}
          </span>
          <svg
            className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </div>
        <div className="flex-1 grid grid-cols-5 gap-4 text-xs items-center min-w-0">
          <div className="col-span-2 min-w-0">
            <p className="font-mono text-slate-700 font-semibold break-all m-0 leading-relaxed">{block.hash || "-"}</p>
          </div>
          <div>
            <p className="text-slate-500 m-0">{dateStr} {timeStr}</p>
          </div>
          <div>
            <p className="text-slate-500 m-0">
              Nonce: <span className="font-mono text-slate-700">{block.nonce}</span>
            </p>
          </div>
          <div className="text-right">
            <span className="inline-flex items-center gap-1 text-teal-700 font-medium">
              <svg className="w-3.5 h-3.5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {block.transactions.length}
            </span>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-200/60 bg-slate-50/50">
          <div className="px-4 py-2.5">
            <div className="flex items-center gap-6 text-[11px] text-slate-500 mb-2.5 pb-2 border-b border-slate-200/50">
              <span><span className="font-medium text-slate-600">Previous Hash:</span> <span className="font-mono break-all">{block.previous_hash || "-"}</span></span>
            </div>

            {block.transactions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[10px] text-slate-500 uppercase tracking-wider">
                      <th className="text-left font-medium pb-1.5 pr-2">#</th>
                      <th className="text-left font-medium pb-1.5 pr-3">Candidate</th>
                      <th className="text-left font-medium pb-1.5 pr-3">Election</th>
                      <th className="text-left font-medium pb-1.5 pr-3">Nonce</th>
                      <th className="text-left font-medium pb-1.5">Signature</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200/50">
                    {block.transactions.map((vote, i) => (
                      <tr key={i} className="hover:bg-white/60">
                        <td className="py-1.5 pr-2 text-slate-400 font-mono text-[10px] align-top">{i + 1}</td>
                        <td className="py-1.5 pr-3 font-medium text-slate-800 align-top">{vote.candidate_id}</td>
                        <td className="py-1.5 pr-3 text-slate-600 align-top">{vote.election_id}</td>
                        <td className="py-1.5 pr-3 font-mono text-[10px] text-slate-500 align-top break-all max-w-[200px]">{vote.nonce || "-"}</td>
                        <td className="py-1.5 font-mono text-[10px] text-slate-400 align-top break-all max-w-[280px]">0x{vote.signature || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400 m-0 py-1 text-center">Genesis block — no transactions</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ValidationBlockRow({ block }) {
  return (
    <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${
      block.valid ? "bg-emerald-100/50 text-emerald-800" : "bg-red-100/50 text-red-800"
    }`}>
      <span className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${
        block.valid ? "bg-emerald-200 text-emerald-700" : "bg-red-200 text-red-700"
      }`}>
        {block.valid ? (
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        )}
      </span>
      <span className="font-semibold shrink-0">Block #{block.index}</span>
      <span className="text-[10px] font-mono text-slate-500 truncate">{block.hash?.substring(0, 12)}..</span>
      {!block.valid && block.errors?.length > 0 && (
        <span className="ml-auto text-red-600 font-medium">
          {humanizeError(block.errors[0])}
        </span>
      )}
    </div>
  );
}

export default function TransparencyView() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [chainData, setChainData] = useState(null);
  const [revalidationData, setRevalidationData] = useState(null);
  const [consensusData, setConsensusData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [revalidationLoading, setRevalidationLoading] = useState(false);
  const [consensusLoading, setConsensusLoading] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const addToast = (message, type = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  };

  const dismissToast = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const handleConnect = async () => {
    try {
      setConnecting(true);
      const data = await fetchChain(baseUrl);
      setChainData(data);
      setConnected(true);
      addToast(`Connected to node — chain length ${data.chain?.length || 0}`, "success");
    } catch (err) {
      addToast(humanizeError(err.message), "error");
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = () => {
    setConnected(false);
    setChainData(null);
  };

  const handleDownloadState = async () => {
    try {
      setDownloading(true);
      const state = await fetchNodeState(baseUrl);
      const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `node-state-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addToast(`State downloaded — ${state.chain?.length || 0} blocks`, "success");
    } catch (err) {
      addToast(`Download failed: ${err.message}`, "error");
    } finally {
      setDownloading(false);
    }
  };

  const networkStats = useMemo(() => {
    if (!chainData) return { chainLength: "-", pendingVotes: "-", peers: "-", difficulty: "-" };
    return {
      chainLength: chainData.chain?.length || 0,
      pendingVotes: chainData.pending_votes ?? "-",
      peers: chainData.nodes?.length || 0,
      difficulty: chainData.difficulty ?? "-",
    };
  }, [chainData]);

  const loadChainData = async () => {
    try {
      setLoading(true);
      const data = await fetchChain(baseUrl);
      setChainData(data);
    } catch (err) {
      addToast(humanizeError(err.message), "error");
    } finally {
      setLoading(false);
    }
  };

  const handleRevalidate = async () => {
    try {
      setRevalidationLoading(true);
      setRevalidationData(null);
      const result = await revalidateChain(baseUrl);
      setRevalidationData(result);
      if (result.status === "valid") {
        addToast(`Chain valid — ${result.chain_length} blocks verified on disk`, "success");
      } else {
        addToast(
          `Chain broken at block ${result.failed_at_block ?? "?"} — ${humanizeError(result.error)}`,
          "error"
        );
      }
    } catch (err) {
      addToast(humanizeError(err.message), "error");
    } finally {
      setRevalidationLoading(false);
    }
  };

  const handleResolveConsensus = async () => {
    try {
      setConsensusLoading(true);
      setConsensusData(null);
      const result = await resolveConsensus(baseUrl);
      setConsensusData(result);
      const replaced = result.message?.includes("replaced");
      addToast(
        replaced ? "Chain updated from peers" : "Current chain is authoritative",
        replaced ? "success" : "info"
      );
      await loadChainData();
    } catch (err) {
      addToast(humanizeError(err.message), "error");
    } finally {
      setConsensusLoading(false);
    }
  };

  useEffect(() => {
    if (!connected) return;
    const interval = setInterval(() => {
      fetchChain(baseUrl).then(setChainData).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [connected, baseUrl]);

  const blocks = useMemo(() => {
    if (!chainData?.chain) return [];
    return [...chainData.chain].reverse();
  }, [chainData]);

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      <aside className="w-full lg:w-56 shrink-0 p-4 lg:p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md lg:self-start lg:sticky lg:top-0 flex flex-col gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-blue-600 m-0">Transparency</p>
          <h2 className="text-lg font-bold text-slate-900 mt-1 m-0">Chain Explorer</h2>
          <p className="text-xs text-slate-500 mt-1">Inspect every block and vote end-to-end.</p>
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
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={handleDownloadState}
                disabled={downloading}
                className="px-3 py-2 rounded-xl text-xs font-medium text-slate-700 bg-white/80 border border-slate-200/80 hover:bg-white transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                {downloading ? "..." : "State"}
              </button>
              <button
                onClick={handleDisconnect}
                className="px-3 py-2 rounded-xl text-xs font-medium text-slate-700 bg-white/80 border border-slate-200/80 hover:bg-white transition-colors"
              >
                Disconnect
              </button>
            </div>
            <p className="text-[10px] text-slate-400 m-0 text-center">Auto-refreshes every 5s</p>
          </>
        )}

        <div className="pt-2 border-t border-slate-200/60">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider m-0 mb-1">How it works</p>
          <p className="text-[10px] text-slate-400 m-0 leading-relaxed">
            Blocks are listed newest-first. Click any block to expand it and inspect every vote inside. Use &ldquo;State&rdquo; to download the raw node JSON and verify it yourself.
          </p>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col gap-4">
        <div className="flex flex-col gap-3">
          {toasts.map((t) => (
            <Toast key={t.id} message={t.message} type={t.type} onDismiss={() => dismissToast(t.id)} />
          ))}
        </div>

        {!connected ? (
          <div className="p-10 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col items-center justify-center gap-3 text-center">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center">
              <svg className="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
              </svg>
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 m-0">Not connected</h3>
              <p className="text-sm text-slate-500 mt-1 max-w-sm">
                Enter a node URL and click &ldquo;Connect to Node&rdquo; to inspect its blockchain and download its raw state.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Chain Length" value={networkStats.chainLength} />
            <StatCard label="Pending Votes" value={networkStats.pendingVotes} />
            <StatCard label="Connected Peers" value={networkStats.peers} />
            <StatCard label="Difficulty" value={networkStats.difficulty} />
          </div>
        )}

        <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 m-0">Blockchain State</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {!connected
                  ? "Connect to a node to inspect its chain."
                  : blocks.length > 0
                    ? `${blocks.length} block${blocks.length === 1 ? "" : "s"} — newest first. Click a block to view transactions.`
                    : "No blocks yet. Start mining to see the chain."}
              </p>
            </div>
          </div>

          {!connected ? (
            <div className="flex items-center justify-center h-32 text-sm text-slate-400">
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              No data. Click &ldquo;Connect to Node&rdquo; in the sidebar.
            </div>
          ) : blocks.length > 0 ? (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-4 px-4 py-1.5 text-[10px] text-slate-400 uppercase tracking-wider font-medium">
                <span className="w-24 shrink-0" />
                <span className="flex-1 grid grid-cols-5 gap-4">
                  <span className="col-span-2">Hash</span>
                  <span>Timestamp</span>
                  <span>Nonce</span>
                  <span className="text-right">Votes</span>
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                {blocks.map((block) => (
                  <BlockRow key={block.hash} block={block} />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-32 text-sm text-slate-400">
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              No blocks yet. Start mining to see the chain.
            </div>
          )}
        </div>

        <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 m-0">Revalidate Chain</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Reads the chain from disk and checks every block end-to-end: hash integrity,
              previous-hash linkage, proof-of-work difficulty, and vote validity.
            </p>
          </div>

          <button
            onClick={handleRevalidate}
            disabled={revalidationLoading || !connected}
            className="w-full sm:w-auto px-5 py-2.5 rounded-full text-sm font-medium text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20 hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {revalidationLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Validating...
              </span>
            ) : "Revalidate Chain from Disk"}
          </button>

          {revalidationData && (
            <div className={`p-4 rounded-xl border ${
              revalidationData.status === "valid"
                ? "bg-emerald-50/80 border-emerald-200"
                : "bg-red-50/80 border-red-200"
            }`}>
              <div className="flex items-start gap-3 mb-3">
                <span className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  revalidationData.status === "valid" ? "bg-emerald-100 text-emerald-600" : "bg-red-100 text-red-600"
                }`}>
                  {revalidationData.status === "valid" ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                </span>
                <div>
                  <p className={`text-sm font-bold m-0 ${
                    revalidationData.status === "valid" ? "text-emerald-800" : "text-red-800"
                  }`}>
                    {revalidationData.status === "valid"
                      ? "Chain integrity verified"
                      : revalidationData.error
                        ? `Block #${revalidationData.blocks?.filter(b => !b.valid)[0]?.index ?? "?"} — ${humanizeError(revalidationData.error)}`
                        : "Chain invalid"}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {revalidationData.chain_length} block{revalidationData.chain_length !== 1 ? "s" : ""} checked
                    {revalidationData.difficulty != null ? ` at difficulty ${revalidationData.difficulty}` : ""}
                    {revalidationData.status === "valid" ? " — every hash, link, and proof-of-work passed" : ""}
                  </p>
                </div>
              </div>

              {(revalidationData.blocks?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1.5">
                    Per-block validation
                  </p>
                  {revalidationData.blocks.map((b) => (
                    <ValidationBlockRow key={b.index} block={b} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 m-0">Resolve Consensus</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Contacts every registered peer node and requests their chain. Compares lengths (longest valid chain wins)
              and replaces the local chain if a longer valid one is found. Only valid chains (verified proof-of-work,
              hash linkage) are accepted.
            </p>
          </div>

          <button
            onClick={handleResolveConsensus}
            disabled={consensusLoading || !connected}
            className="w-full sm:w-auto px-5 py-2.5 rounded-full text-sm font-medium text-slate-700 bg-white/80 border border-slate-200/80 hover:bg-white transition-colors disabled:opacity-50"
          >
            {consensusLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Resolving...
              </span>
            ) : "Resolve Consensus with Peers"}
          </button>

          {consensusData && (
            <div className="p-4 rounded-xl border bg-blue-50/80 border-blue-200">
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-blue-100 text-blue-600">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </span>
                <div>
                  <p className="text-sm font-bold text-blue-800 m-0">{consensusData.message}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {consensusData.new_length != null
                      ? `Chain replaced — new length: ${consensusData.new_length} blocks`
                      : `Chain retained — length: ${consensusData.length} blocks`}
                  </p>
                </div>
              </div>

              {(consensusData.chain?.length ?? 0) > 0 && (
                <details className="mt-3">
                  <summary className="text-xs text-blue-600 cursor-pointer font-medium hover:text-blue-700">
                    Show blocks after consensus
                  </summary>
                  <div className="mt-2 space-y-1">
                    {consensusData.chain.map((b) => (
                      <div key={b.hash} className="flex items-center gap-2 text-xs text-slate-600 bg-white/60 px-3 py-2 rounded-lg">
                        <span className="font-semibold text-slate-800 shrink-0">Block #{b.index}</span>
                        <span className="font-mono text-[10px] text-slate-400 truncate">{b.hash?.substring(0, 14)}..</span>
                        <span className="ml-auto text-slate-400">{b.transactions.length} votes</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
