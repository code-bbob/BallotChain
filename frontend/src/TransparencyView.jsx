import { useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_BASE_URL, fetchChain, revalidateChain, resolveConsensus } from "./api";

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

function BlockCard({ block }) {
  return (
    <div className="w-56 p-3.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md">
          #{block.index}
        </span>
        <span className="text-[10px] text-slate-400 font-mono">
          {new Date(block.timestamp * 1000).toLocaleTimeString()}
        </span>
      </div>
      <div className="space-y-0.5 text-[11px] font-mono text-slate-500">
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 w-4 shrink-0">H</span>
          <span className="truncate">{block.hash?.substring(0, 12)}..</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 w-4 shrink-0">N</span>
          <span className="truncate">{String(block.nonce).substring(0, 14)}</span>
        </div>
      </div>
      <div className="flex items-center gap-1.5 mt-1.5 pt-1.5 border-t border-slate-100">
        <svg className="w-3 h-3 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="text-[11px] font-medium text-teal-700">{block.transactions.length} votes</span>
      </div>
    </div>
  );
}

function RowArrow() {
  return (
    <div className="flex items-center shrink-0">
      <svg className="w-5 h-5 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
      </svg>
      <div className="w-4 h-px bg-gradient-to-r from-slate-300 to-transparent" />
    </div>
  );
}

function TurnArrow() {
  return (
    <div className="flex justify-end pr-2.5 -mb-2 -mt-2">
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" className="text-slate-300">
        <path
          d="M4 14 C4 8, 10 6, 16 6 L22 6"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"
        />
        <path
          d="M18 2 L22 6 L18 10"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"
        />
        <path
          d="M24 10 L24 16"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"
        />
        <path
          d="M20 14 L24 18 L28 14"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"
        />
      </svg>
    </div>
  );
}

function ChainFlow({ chainData }) {
  const containerRef = useRef(null);
  const [blocksPerRow, setBlocksPerRow] = useState(4);

  const blocks = chainData?.chain || [];

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => {
      const cardWidth = 264;
      const count = Math.max(1, Math.floor(el.clientWidth / cardWidth));
      setBlocksPerRow(count);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [blocks.length]);

  if (!blocks.length) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-slate-400">
        <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
        No blocks yet. Start mining to see the chain.
      </div>
    );
  }

  const display = [...blocks].reverse().slice(0, 24);
  const rows = [];
  for (let i = 0; i < display.length; i += blocksPerRow) {
    rows.push(display.slice(i, i + blocksPerRow));
  }

  return (
    <div ref={containerRef} className="w-full">
      {rows.map((row, ri) => (
        <div key={ri} className="flex flex-col">
          <div className="flex flex-wrap items-center">
            {row.map((block, bi) => (
              <div key={block.hash} className="flex items-center">
                <BlockCard block={block} />
                {bi < row.length - 1 && <RowArrow />}
              </div>
            ))}
          </div>
          {ri < rows.length - 1 && <TurnArrow />}
        </div>
      ))}
      {blocks.length > 24 && (
        <p className="text-xs text-slate-400 mt-2">+{blocks.length - 24} more blocks</p>
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

  const addToast = (message, type = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  };

  const dismissToast = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));

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

  useEffect(() => { loadChainData(); }, [baseUrl]);

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      <aside className="w-full lg:w-56 shrink-0 p-4 lg:p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md lg:self-start lg:sticky lg:top-0 flex flex-col gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-blue-600 m-0">Transparency</p>
          <h2 className="text-lg font-bold text-slate-900 mt-1 m-0">Chain Explorer</h2>
          <p className="text-xs text-slate-500 mt-1">Inspect the blockchain state and validate integrity.</p>
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
        <button
          onClick={loadChainData}
          disabled={loading}
          className="w-full px-4 py-2 rounded-xl text-sm font-medium bg-white/80 text-slate-700 border border-slate-200/80 hover:bg-white transition-colors disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col gap-4">
        <div className="flex flex-col gap-3">
          {toasts.map((t) => (
            <Toast key={t.id} message={t.message} type={t.type} onDismiss={() => dismissToast(t.id)} />
          ))}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Chain Length" value={networkStats.chainLength} />
          <StatCard label="Pending Votes" value={networkStats.pendingVotes} />
          <StatCard label="Connected Peers" value={networkStats.peers} />
          <StatCard label="Difficulty" value={networkStats.difficulty} />
        </div>

        <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 m-0">Blockchain State</h3>
            <p className="text-xs text-slate-500 mt-0.5">Blocks flowing from newest (top row) to oldest (bottom row)</p>
          </div>
          <ChainFlow chainData={chainData} />
        </div>

        <div className="p-5 rounded-2xl bg-white/70 border border-slate-200/60 backdrop-blur-md flex flex-col gap-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 m-0">Revalidate Chain</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Reads the chain from disk (not from memory) and checks every block end-to-end: hash integrity,
              previous-hash linkage, proof-of-work difficulty, and vote validity. Reports first failure with details.
            </p>
          </div>

          <button
            onClick={handleRevalidate}
            disabled={revalidationLoading}
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
            disabled={consensusLoading}
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
