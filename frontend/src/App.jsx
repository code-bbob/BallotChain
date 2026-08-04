import { useEffect, useState } from "react";
import AdminView from "./AdminView";
import VoterView from "./VoterView";
import AdminLogin from "./AdminLogin";
import TransparencyView from "./TransparencyView";

const MODE_STORAGE_KEY = "BallotChain.mode";
const ADMIN_TOKEN_STORAGE_KEY = "BallotChain.adminToken";

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

  const renderTopBar = (title, subtitle) => (
    <header className="flex items-center justify-between gap-4 py-1 pb-3">
      <div>
        <p className="text-xs font-bold uppercase tracking-widest text-blue-600 m-0">BallotChain</p>
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mt-0.5 m-0">{title}</h1>
        <p className="text-sm text-slate-500 mt-0.5 m-0 max-w-prose">{subtitle}</p>
      </div>
      <div className="flex gap-2 items-center shrink-0">
        <button className="rounded-full px-4 py-2 text-sm bg-white/80 border border-slate-200/80 text-slate-700 hover:bg-white transition-colors" onClick={() => setMode("select")}>Back to hub</button>
      </div>
    </header>
  );

  if (mode === "admin") {
    return (
      <div className="min-h-screen p-4 sm:p-6">
        <div className="mx-auto max-w-7xl flex flex-col gap-4">
          {renderTopBar(
            "Election Administration",
            "Manage voters, mine the cluster, and inspect the blockchain state."
          )}
          {!adminToken ? (
            <AdminLogin onLogin={handleLogin} onCancel={() => setMode("select")} />
          ) : (
            <AdminView adminToken={adminToken} />
          )}
        </div>
      </div>
    );
  }

  if (mode === "voter") {
    return (
      <div className="min-h-screen p-4 sm:p-6">
        <div className="mx-auto max-w-7xl flex flex-col gap-4">
          {renderTopBar(
            "Voting Console",
            "Blind-sign anonymous voting with live network feedback."
          )}
          <VoterView />
        </div>
      </div>
    );
  }

  if (mode === "transparency") {
    return (
      <div className="min-h-screen p-4 sm:p-6">
        <div className="mx-auto max-w-7xl flex flex-col gap-4">
          <header className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-blue-600 m-0">BallotChain</p>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mt-0.5 m-0">Transparency Console</h1>
            </div>
            <button className="rounded-full px-4 py-2 text-sm bg-white/80 border border-slate-200/80 text-slate-700 hover:bg-white transition-colors shrink-0" onClick={() => setMode("select")}>Back to hub</button>
          </header>
          <TransparencyView />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <header className="flex items-center justify-between py-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">BallotChain</h1>
            <p className="text-sm text-slate-500">Blockchain voting demo</p>
          </div>
          <nav className="flex gap-2">
            <button className="rounded-full px-4 py-2 text-sm bg-white/70 border border-slate-200/80 text-slate-900" onClick={() => setMode("admin")}>Governance</button>
            <button className="rounded-full px-4 py-2 text-sm bg-white/70 border border-slate-200/80 text-slate-900" onClick={() => setMode("voter")}>Voting</button>
            <button className="rounded-full px-4 py-2 text-sm bg-white/70 border border-slate-200/80 text-slate-900" onClick={() => setMode("transparency")}>Transparency</button>
          </nav>
        </header>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center py-8 relative z-10">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-blue-600">Anonymous blind-sign voting</p>
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight tracking-tighter mt-3 mb-4">Vote. Mine. Verify.</h2>
            <p className="text-slate-500 leading-relaxed max-w-prose mb-2">
              The admin console issues blind-vote invitations. Voters submit anonymous
              blind-signed ballots. The network mines and propagates the winning block.
            </p>
            <div className="flex gap-3 flex-wrap">
              <button className="rounded-full px-6 py-3 text-sm font-medium text-white bg-gradient-to-r from-teal-600 to-blue-600 shadow-lg shadow-blue-600/20" onClick={() => setMode("admin")}>Governance Console</button>
              <button className="rounded-full px-6 py-3 text-sm font-medium text-slate-900 bg-white/80 border border-slate-200/80" onClick={() => setMode("voter")}>Voter Console</button>
              <button className="rounded-full px-6 py-3 text-sm font-medium text-slate-900 bg-white/80 border border-slate-200/80" onClick={() => setMode("transparency")}>Transparency Console</button>
            </div>
          </div>
          <div className="vis-panel">
            <div className="vis-panel-header">
              <span className="vis-ph-dot" />
              <span className="vis-ph-dot" />
              <span className="vis-ph-dot" />
              <span className="vis-ph-label">live:blockchain</span>
            </div>
            <div className="vis-blocks">
              <div className="vis-block">
                <span className="vis-block-num">#21</span>
                <div className="vis-block-info">
                  <span className="vis-block-label">Block 0x4a1f&hellip;b3e2</span>
                  <span className="vis-block-hash">Nonce: 0x0000&hellip;a9f4 &middot; 12 txns</span>
                </div>
                <span className="vis-block-status mined">mined</span>
              </div>
              <div className="vis-block">
                <span className="vis-block-num">#22</span>
                <div className="vis-block-info">
                  <span className="vis-block-label">Block 0x7c3d&hellip;f801</span>
                  <span className="vis-block-hash">Nonce: 0x0000&hellip;b2e7 &middot; 8 txns</span>
                </div>
                <span className="vis-block-status mined">mined</span>
              </div>
              <div className="vis-block">
                <span className="vis-block-num">#23</span>
                <div className="vis-block-info">
                  <span className="vis-block-label">Block 0x9e5a&hellip;4c3b</span>
                  <span className="vis-block-hash">&diams; mining &hellip; 0x0000&hellip;1e</span>
                </div>
                <span className="vis-block-status mining">mining</span>
              </div>
              <div className="vis-block">
                <span className="vis-block-num">#24</span>
                <div className="vis-block-info">
                  <span className="vis-block-label">Mempool</span>
                  <span className="vis-block-hash">3 pending votes &middot; 0xb8f&hellip;</span>
                </div>
                <span className="vis-block-status pending">pending</span>
              </div>
            </div>
          </div>
        </section>

        <div className="relative w-screen ml-[calc(-50vw+50%)] px-6 lg:px-8 py-8 border-y border-slate-200/30">
          <div className="max-w-7xl mx-auto flex items-center justify-center">
            <div className="flex flex-col items-center gap-2">
              <span className="size-13 rounded-full bg-gradient-to-br from-teal-600 to-blue-600 text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-600/20">01</span>
              <span className="text-sm font-semibold">Vote</span>
            </div>
            <span className="w-16 h-0.5 bg-gradient-to-r from-blue-600 to-teal-600/20 mb-6" />
            <div className="flex flex-col items-center gap-2">
              <span className="size-13 rounded-full bg-gradient-to-br from-teal-600 to-blue-600 text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-600/20">02</span>
              <span className="text-sm font-semibold">Mempool</span>
            </div>
            <span className="w-16 h-0.5 bg-gradient-to-r from-blue-600 to-teal-600/20 mb-6" />
            <div className="flex flex-col items-center gap-2">
              <span className="size-13 rounded-full bg-gradient-to-br from-teal-600 to-blue-600 text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-600/20">03</span>
              <span className="text-sm font-semibold">Mine</span>
            </div>
            <span className="w-16 h-0.5 bg-gradient-to-r from-blue-600 to-teal-600/20 mb-6" />
            <div className="flex flex-col items-center gap-2">
              <span className="size-13 rounded-full bg-gradient-to-br from-teal-600 to-blue-600 text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-600/20">04</span>
              <span className="text-sm font-semibold">Sync</span>
            </div>
          </div>
        </div>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6 relative z-10">
          <article className="p-6 rounded-2xl bg-white/70 backdrop-blur-md border border-slate-200/10 flex flex-col gap-2">
            <span className="text-xs font-extrabold text-blue-600 tracking-widest">01</span>
            <h3 className="text-lg font-semibold">Governance</h3>
            <p className="text-sm text-slate-500 leading-relaxed">Prepare blind-registration invitations, inspect the chain, and control mining from one dashboard.</p>
          </article>
          <article className="p-6 rounded-2xl bg-white/70 backdrop-blur-md border border-slate-200/10 flex flex-col gap-2">
            <span className="text-xs font-extrabold text-blue-600 tracking-widest">02</span>
            <h3 className="text-lg font-semibold">Voting</h3>
            <p className="text-sm text-slate-500 leading-relaxed">Blind-sign your ballot locally, get admin authorization, and submit anonymously with instant feedback.</p>
          </article>
          <article className="p-6 rounded-2xl bg-white/70 backdrop-blur-md border border-slate-200/10 flex flex-col gap-2">
            <span className="text-xs font-extrabold text-blue-600 tracking-widest">03</span>
            <h3 className="text-lg font-semibold">Transparency</h3>
            <p className="text-sm text-slate-500 leading-relaxed">Track blocks, nonces, hashes, and pending votes as the network converges in real time.</p>
          </article>
        </section>
      </div>
    </div>
  );
}
