#!/usr/bin/env python3
"""
benchmark.py — performance & scaling measurements for the TrueVote cluster.

Designed to be run on a QUIET machine (after a fresh reboot, nothing else
running) so the numbers are not polluted by CPU contention.

What it measures (and saves to a JSON report):

  1. Per-hash cost scaling (deterministic, no PoW luck):
     time to compute one block hash for k transactions, then the *expected*
     block time at the cluster difficulty (= 16^difficulty * per_hash).
     This is the clean "how does mining time scale with tx/block" curve.

  2. Per-operation timings (client-side round-trips incl. peer broadcast):
       - registration-code issuance
       - blind-signature issuance
       - vote casting

  3. End-to-end block creation + consensus sync for batch sizes k:
     cast k votes, mine them, record wall-clock block time and how long all
     3 nodes take to confirm the block.

Usage:
    # start the 3 nodes first (docker compose up -d, or run_all.sh), then:
    ./venv/bin/python benchmark.py --runs 5 \
        --batches 1,2,5,10,20,50 --json-out benchmark_report.json

Prints progress to stdout and writes the full report to benchmark_report.json.
Expected runtime: ~10-20 min (dominated by proof-of-work, which is random).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import secrets
import sys
import time
from statistics import mean
from typing import Any

import requests

from block import Block

DEFAULT_NODE = "http://127.0.0.1:8001"
DEFAULT_PEERS = "http://127.0.0.1:8002,http://127.0.0.1:8003"
DEFAULT_BATCHES = [1, 2, 5, 10, 20, 50]
DEFAULT_PERHASH_SIZES = [1, 2, 5, 10, 20, 50, 100]
DEFAULT_RUNS = 5
ELECTION = "bench-2026"


def hash_to_int_mod_n(value: str, modulus: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1


def random_coprime_below(modulus: int) -> int:
    while True:
        candidate = secrets.randbelow(modulus - 1) + 1
        try:
            pow(candidate, -1, modulus)
            return candidate
        except ValueError:
            continue


class Cluster:
    def __init__(self, node: str, peers: list[str], timeout: float = 30.0):
        self.node = node.rstrip("/")
        self.peers = [p.rstrip("/") for p in peers]
        self.nodes = [self.node] + self.peers
        self.timeout = timeout
        self.e = 0
        self.n = 0

    # ---- connection --------------------------------------------------------
    def healthcheck(self) -> dict[str, Any]:
        info = {}
        for node in self.nodes:
            try:
                resp = requests.get(f"{node}/chain", timeout=5)
                resp.raise_for_status()
                data = resp.json()
                info[node] = {"ok": True, "length": int(data["length"]), "difficulty": int(data["difficulty"]), "pending": int(data["pending_votes"])}
            except requests.RequestException as exc:
                info[node] = {"ok": False, "error": str(exc)}
        return info

    # ---- helpers -----------------------------------------------------------
    def chain_length(self, node: str | None = None) -> int:
        base = node or self.node
        resp = requests.get(f"{base}/chain", timeout=self.timeout)
        resp.raise_for_status()
        return int(resp.json()["length"])

    def pending(self, node: str | None = None) -> int:
        base = node or self.node
        resp = requests.get(f"{base}/chain", timeout=self.timeout)
        resp.raise_for_status()
        return int(resp.json()["pending_votes"])

    def wait_pending_zero(self, timeout: float = 90.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if all(self.pending(n) == 0 for n in self.nodes):
                    return True
            except requests.RequestException:
                pass
            time.sleep(0.5)
        return False

    def fetch_public_key(self) -> None:
        resp = requests.get(f"{self.node}/voters/blind/public-key", timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        self.n = int(str(data["n"]).strip())
        self.e = int(str(data["e"]).strip())

    # ---- operations --------------------------------------------------------
    def issue_code(self, election: str) -> tuple[float, str]:
        def _call():
            resp = requests.post(
                f"{self.node}/voters/codes/issue",
                json={"election_id": election, "expires_in_minutes": 120},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["registration_code"]

        start = time.perf_counter()
        code = _call()
        return time.perf_counter() - start, code

    def blind_sign_and_cast(self, candidate: str, election: str, code: str) -> dict[str, float]:
        """Full voter flow (blind sign then cast), timing each step client-side."""
        nonce = secrets.token_hex(16)
        vote_message = json.dumps(
            {"candidate_id": candidate, "election_id": election, "nonce": nonce},
            sort_keys=True,
            separators=(",", ":"),
        )
        vote_hash = hash_to_int_mod_n(vote_message, self.n)
        r = random_coprime_below(self.n)
        blinded_hash = (vote_hash * pow(r, self.e, self.n)) % self.n

        def _sign():
            resp = requests.post(
                f"{self.node}/voters/blind/sign",
                json={"registration_code": code, "election_id": election, "blinded_hash": str(blinded_hash)},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["blind_signature"]

        start = time.perf_counter()
        blind_signature_hex = _sign()
        sign_elapsed = time.perf_counter() - start

        blind_signature_int = int(blind_signature_hex, 16)
        r_inverse = pow(r, -1, self.n)
        unblinded = (blind_signature_int * r_inverse) % self.n
        if pow(unblinded, self.e, self.n) != vote_hash:
            raise RuntimeError("local blind-sign verification failed")

        def _cast():
            resp = requests.post(
                f"{self.node}/votes",
                json={"candidate_id": candidate, "election_id": election, "nonce": nonce, "signature": hex(unblinded)},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp

        start = time.perf_counter()
        _cast()
        cast_elapsed = time.perf_counter() - start

        return {"blind_sign": sign_elapsed, "cast": cast_elapsed}

    def mine_batch(self, limit: int) -> dict[str, Any]:
        """Mine up to `limit` pending votes. POST duration == block time
        (the endpoint mines synchronously and broadcasts before returning)."""
        target_len = self.chain_length() + 1
        start = time.perf_counter()
        resp = requests.post(f"{self.node}/mine/cluster", params={"limit": limit}, timeout=1800)
        resp.raise_for_status()
        block_time = time.perf_counter() - start
        body = resp.json()

        sync_start = time.perf_counter()
        synced = False
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if all(self.chain_length(n) >= target_len for n in self.nodes):
                    synced = True
                    break
            except requests.RequestException:
                pass
            time.sleep(0.2)
        sync_confirm = time.perf_counter() - sync_start if synced else None

        local = body.get("local") or {}
        return {
            "block_time_s": block_time,
            "sync_confirm_s": sync_confirm,
            "synced": synced,
            "server_mining_s": local.get("mining_time_seconds"),
            "local_message": local.get("message"),
            "total_txs": body.get("total_txs"),
            "peer_accepts": (body.get("peers") or {}).get("accepted"),
        }


def measure_per_hash(k: int, iters: int = 20000, reps: int = 5) -> float:
    """Best-case wall-clock time of one Block.calculate_hash() for k txs."""
    tx = {"candidate_id": "cand-bench", "election_id": ELECTION, "nonce": "deadbeef", "signature": "0x" + "ab" * 256}
    blk = Block(index=15, timestamp=1785659516.9, transactions=[dict(tx) for _ in range(k)], previous_hash="0" * 64)
    best = float("inf")
    for _ in range(reps):
        start = time.perf_counter()
        for _ in range(iters):
            blk.calculate_hash()
        best = min(best, (time.perf_counter() - start) / iters)
    return best


def block_serialized_bytes(k: int) -> int:
    tx = {"candidate_id": "cand-bench", "election_id": ELECTION, "nonce": "deadbeef", "signature": "0x" + "ab" * 256}
    blk = Block(index=15, timestamp=1785659516.9, transactions=[dict(tx) for _ in range(k)], previous_hash="0" * 64)
    payload = {
        "index": blk.index,
        "timestamp": blk.timestamp,
        "transactions": blk.transactions,
        "previous_hash": blk.previous_hash,
        "nonce": blk.nonce,
    }
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    cluster = Cluster(args.node, args.peers.split(","), timeout=args.timeout)
    print("cluster nodes: %s" % cluster.nodes, flush=True)

    health = cluster.healthcheck()
    for node, info in health.items():
        status = "OK len=%d diff=%d pending=%d" % (info["length"], info["difficulty"], info["pending"]) if info["ok"] else "UNREACHABLE: %s" % info["error"]
        print("  %-28s %s" % (node, status), flush=True)
    if not all(info["ok"] for info in health.values()):
        print("ERROR: one or more nodes are not reachable. Start the cluster first "
              "(e.g. `docker compose up -d` or `./run_all.sh`).", file=sys.stderr)
        sys.exit(1)

    cluster.fetch_public_key()
    difficulties = {info["difficulty"] for info in health.values()}
    difficulty = difficulties.pop() if len(difficulties) == 1 else None
    print("blind-sign key: RSA-%d bits | difficulty: %s" % (cluster.n.bit_length(), difficulty), flush=True)

    report: dict[str, Any] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "node": cluster.node,
        "peers": cluster.peers,
        "difficulty": difficulty,
        "modulus_bits": cluster.n.bit_length(),
        "chain_length_before": max(info["length"] for info in health.values()),
        "runs": args.runs,
        "batches": args.batches,
        "per_hash_scaling": [],
        "operations": {},
        "batch_scale": [],
        "summary": {},
    }

    # 1) Deterministic per-hash scaling (no PoW randomness)
    print("\n[1/3] Per-hash cost scaling (best-of-%d, %d iters each)" % (5, 20000), flush=True)
    base = None
    for k in args.perhash:
        per = measure_per_hash(k)
        rel = per / base if base else 1.0
        base = base or per
        exp = per * (16 ** difficulty) if difficulty else None
        row = {
            "k": k,
            "block_bytes": block_serialized_bytes(k),
            "per_hash_us": round(per * 1e6, 3),
            "hashrate_kH_s": round(1.0 / per / 1000, 2),
            "expected_block_s": round(exp, 2) if exp else None,
            "relative_per_hash": round(rel, 2),
        }
        report["per_hash_scaling"].append(row)
        print("  k=%3d  block=%6dB  per_hash=%9.2fus  exp_block@d%d=%9.2fs  hashrate=%7.1f kH/s"
              % (k, row["block_bytes"], row["per_hash_us"], difficulty, exp or 0, row["hashrate_kH_s"]), flush=True)

    # 2) Per-operation timings (1 warm-up run, then `runs` timed)
    print("\n[2/3] Per-operation timings (%d timed runs + 1 warm-up)" % args.runs, flush=True)
    op_times: dict[str, list[float]] = {"issue": [], "blind_sign": [], "cast": []}
    for run in range(args.runs + 1):
        issue_t, code = cluster.issue_code(ELECTION)
        flow = cluster.blind_sign_and_cast("cand-bench", ELECTION, code)
        if run > 0:
            op_times["issue"].append(issue_t)
            op_times["blind_sign"].append(flow["blind_sign"])
            op_times["cast"].append(flow["cast"])
        print("  run %2d: issue=%8.4fs blind_sign=%8.4fs cast=%8.4fs" % (run, issue_t, flow["blind_sign"], flow["cast"]), flush=True)

    def summ(vals: list[float]) -> dict[str, float]:
        return {"mean_s": round(mean(vals), 5), "min_s": round(min(vals), 5), "max_s": round(max(vals), 5), "n": len(vals)}

    report["operations"] = {
        "issue": summ(op_times["issue"]),
        "blind_sign": summ(op_times["blind_sign"]),
        "cast": summ(op_times["cast"]),
    }

    if not cluster.wait_pending_zero(timeout=60):
        print("  draining leftover warm-up votes...", flush=True)
        cluster.mine_batch(100)
        cluster.wait_pending_zero(timeout=120)

    # 3) Mining batch-size effect
    print("\n[3/3] Mining batch-size effect (%d runs per batch size)" % args.runs, flush=True)
    for k in args.batches:
        for run in range(1, args.runs + 1):
            if not cluster.wait_pending_zero(timeout=90):
                print("    !! leftover pending votes; draining", flush=True)
                cluster.mine_batch(100)
                cluster.wait_pending_zero(timeout=120)

            codes: list[str] = []
            for _ in range(k):
                _, code = cluster.issue_code(ELECTION)
                codes.append(code)
            for code in codes:
                cluster.blind_sign_and_cast("cand-bench", ELECTION, code)

            cluster.wait_pending_zero(timeout=90)
            pending_now = cluster.pending()
            res = cluster.mine_batch(k if pending_now >= k else pending_now)
            res.update({"k": k, "run": run})
            report["batch_scale"].append(res)

            sync = "%.3f" % res["sync_confirm_s"] if res["sync_confirm_s"] is not None else "TIMEOUT"
            svr = "%.3f" % res["server_mining_s"] if res["server_mining_s"] is not None else "peer-won"
            print("  k=%3d run=%d: block_time=%9.3fs  sync_confirm=%ss  synced=%s  server_mining=%ss"
                  % (k, run, res["block_time_s"], sync, res["synced"], svr), flush=True)

        # persist partial results after every batch so nothing is lost
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
        print("  (partial report saved)", flush=True)

    # summary
    rows: dict[int, list[dict]] = {}
    for item in report["batch_scale"]:
        rows.setdefault(item["k"], []).append(item)

    report["summary"]["block_time_by_k"] = {}
    for k in args.batches:
        items = rows[k]
        times = [i["block_time_s"] for i in items]
        syncs = [i["sync_confirm_s"] for i in items if i["sync_confirm_s"] is not None]
        report["summary"]["block_time_by_k"][k] = {
            "mean_s": round(mean(times), 3),
            "min_s": round(min(times), 3),
            "max_s": round(max(times), 3),
            "n": len(times),
            "votes_per_s": round(k / mean(times), 4),
            "sync_confirm_mean_s": round(mean(syncs), 4) if syncs else None,
        }

    with open(args.json_out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    return report


def print_report(report: dict[str, Any]) -> None:
    ops = report["operations"]
    print("\n" + "=" * 74)
    print("PER-OPERATION TIMINGS (client round-trip incl. peer broadcast)")
    print("=" * 74)
    print(f"{'operation':<26}{'mean (ms)':>10}{'min (ms)':>10}{'max (ms)':>10}{'runs':>6}")
    for key, label in [("issue", "Registration-code issuance"), ("blind_sign", "Blind-sign issuance"), ("cast", "Vote casting")]:
        s = ops[key]
        print(f"{label:<26}{s['mean_s'] * 1000:>10.3f}{s['min_s'] * 1000:>10.3f}{s['max_s'] * 1000:>10.3f}{s['n']:>6}")

    print("\n" + "=" * 74)
    print("PER-HASH COST / EXPECTED BLOCK TIME SCALING (deterministic)")
    print("=" * 74)
    diff = report.get("difficulty")
    print(f"{'tx/block':>8}{'block (B)':>10}{'per_hash (us)':>14}{'hashrate (kH/s)':>16}{'exp block @d%d (s)':>22}".replace("@d%d", "@d" + str(diff)))
    for row in report["per_hash_scaling"]:
        print(f"{row['k']:>8}{row['block_bytes']:>10}{row['per_hash_us']:>14.2f}{row['hashrate_kH_s']:>16.2f}{row['expected_block_s']:>22.2f}")

    print("\n" + "=" * 74)
    print("MEASURED BLOCK TIMES BY BATCH SIZE (end-to-end, incl. 3-node race)")
    print("=" * 74)
    summ = report["summary"]["block_time_by_k"]
    print(f"{'tx/block':>8}{'mean (s)':>10}{'min (s)':>10}{'max (s)':>10}{'votes/sec':>10}{'runs':>6}")
    for k in report["batches"]:
        s = summ[str(k)] if isinstance(summ, dict) and str(k) in summ else summ[k]
        print(f"{k:>8}{s['mean_s']:>10.3f}{s['min_s']:>10.3f}{s['max_s']:>10.3f}{s['votes_per_s']:>10.4f}{s['n']:>6}")

    print("\nRaw per-run data is in the JSON report (see --json-out).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the TrueVote cluster")
    parser.add_argument("--node", default=DEFAULT_NODE)
    parser.add_argument("--peers", default=DEFAULT_PEERS)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="timed runs per batch size (default: 5)")
    parser.add_argument("--batches", type=lambda s: [int(x) for x in s.split(",")], default=DEFAULT_BATCHES)
    parser.add_argument("--perhash", type=lambda s: [int(x) for x in s.split(",")], default=DEFAULT_PERHASH_SIZES)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json-out", default="benchmark_report.json")
    args = parser.parse_args()

    report = run_benchmark(args)
    print("\nREPORT COMPLETE -> %s" % args.json_out, flush=True)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
