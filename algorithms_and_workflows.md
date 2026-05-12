# Algorithms & Workflows for Final Year Project

This document suggests algorithms and end-to-end workflows you can present for your blockchain-based voting system. It includes both standard techniques you can implement and explain, and one or more original algorithm ideas you can claim and defend as your contribution.

---

## 1. Recommended core algorithms (implement & explain)

- **Proof-of-Work (PoW)**
  - Purpose: basic consensus and fork-resolution for small private network.
  - What to show: block structure, hashing function, difficulty adjustment, mining loop, and chain validation.
  - Complexity: mining cost ~ O(work), validation O(n) for n blocks.
  - Demo idea: vary `DIFFICULTY` and show average time-to-mine and fork frequency.

- **Digital Signatures (Ed25519)**
  - Purpose: authenticate votes and ensure non-repudiation.
  - What to show: keypair generation, message canonicalization, sign/verify, signature transport (base64).
  - Complexity: sign/verify constant-time per message.
  - Demo: generate a keypair (CLI + browser), sign a vote, show server accepts/rejects forged signatures.

- **Voter Registry & One-Vote Enforcement**
  - Purpose: map registered voter IDs → public keys and enforce single vote per election.
  - What to show: registration API, server-side checks, persistent storage (JSON/DB), race conditions handling.
  - Demo: attempt double-vote, show rejection.

- **Merkle Tree for Transaction/Block Commit**
  - Purpose: efficient proofs of inclusion (optional) and compact auditing.
  - What to show: building a Merkle root for block payloads, simple inclusion proof verification.
  - Complexity: building O(m) for m transactions, proof size O(log m).
  - Demo: create a block with many votes and prove a particular vote is included.

- **P2P Propagation (simple gossip)**
  - Purpose: replicate blocks and pending votes across nodes.
  - What to show: peer discovery, push/pull gossip, simple anti-DoS measures.
  - Demo: start 3 nodes, broadcast a mined block from one node and show others accept.

---

## 2. Privacy & Anti-Replay techniques (advanced)

- **Canonical message + election-specific nonce/timestamp**
  - Purpose: prevent replay and ensure vote uniqueness across elections.
  - Implementation: include `election_id`, optional `timestamp` or `nonce` in signed payload; server rejects old timestamps/nonces.

- **Commit-Reveal (optional privacy enhancement)**
  - Purpose: conceal vote choice until tally time.
  - Workflow: 1) commit: user sends hash(commit_secret || vote) signed; 2) reveal: after commit phase, send vote + secret; server verifies hash.
  - Pro: prevents early tally inference; Con: complexity and user burden.

- **Mixnet / Verifiable Shuffle (research-level)**
  - Purpose: unlink voter public key from final vote to increase anonymity.
  - What to show in presentation: high-level design, pros/cons, and a small simulated shuffle of encrypted ballots.

---

## 3. Proposed original algorithm(s) you can claim as your contribution

Below are one or two practical original algorithms tailored to a small-scale academic voting blockchain. You can implement, evaluate, and present these as "your own algorithm".

### A. Adaptive Participation Proof (APP)

- Idea: an adaptive, low-cost participation-adjusted PoW that reduces energy waste in private voting networks while preserving fairness and resistance to trivial reorgs.
- Core concept: change mining difficulty per-node per-epoch based on (a) stake of historical honest participation and (b) recent mining share. Nodes with consistent valid participation get slightly lower difficulty to encourage liveness; nodes that suddenly dominate see difficulty increase.
- Workflow:
  1. Each node maintains a sliding window W of recent blocks claimed by all peers.
  2. Calculate a participation score P_node = f(valid_blocks_by_node_in_W, uptime_metric).
  3. For next epoch, node difficulty D_node = base_D * (1 + α*(meanP - P_node)), where α tunes how strongly difficulty adapts.
  4. Mining: each node mines with locally computed target; blocks include miner id (public key) and proof-of-work.
  5. On chain validation, peers recompute participation scores from the chain; if miner misreports identity, reject.
- Why original/defendable: APP trades uniform difficulty for participation-aware difficulty to improve liveness and reduce resource cost in permissioned networks; can be analyzed for fairness and attack surfaces.
- Evaluation metrics: block-latency, orphan rate, distribution equity, energy (work) saved vs plain PoW.
- Implementation notes: keep consensus simple — peers must compute identical participation scores from chain history to avoid equivocation.

### B. Bloom-Guard Vote Deduplication (BGVD)

- Idea: use a combination of a small in-memory Bloom filter plus persistent deduplication to quickly filter duplicate or replay vote submissions before heavy cryptographic verification.
- Workflow:
  1. Incoming vote: test Bloom filter for likely-duplicate (based on canonical_message hash + voter_public_key). If present, fast-reject or mark for persistent check.
  2. If Bloom reports new: perform full signature verification and persistent duplicate check (DB/JSON). On accept, add to Bloom and persist.
  3. Periodically rebuild Bloom from persisted accepted votes to refresh filter and handle false positives.
- Why original/defendable: practical optimization for high-throughput fronts; useful for demos showing latency reductions in front-end request handling.
- Evaluation: measure average request throughput and CPU cycles spent on signature verification with/without Bloom guard.

You can claim either APP or BGVD as your novel algorithm; both are practical, implementable, and measurable within a semester.

---

## 4. Suggested presentation workflows & demo scripts

- **Demo A — Full voting flow (end-to-end)**
  1. Start 3 nodes (node1,node2,node3).
  2. Generate a wallet in browser/CLI and register public key.
  3. Submit a signed vote via browser → observe pending votes on node UI.
  4. Mine a block on one node → broadcast → show chain on other nodes.
  5. Show tallying script reading chain and producing final counts.

- **Demo B — Signature security**
  1. Create wallet A (valid) and wallet B (different).
  2. Sign vote with A, submit — accepted.
  3. Attempt to submit same vote with B or with altered payload — show rejection.
  4. Show server logs and signature verification steps.

- **Demo C — Present your original algorithm (APP or BGVD)**
  1. Baseline run: run system with standard PoW or without Bloom guard; record metrics (latency, throughput, orphan rate).
  2. Enable APP or BGVD; run same load profile.
  3. Show comparative metrics and explain tradeoffs.

---

## 5. Slides / material structure (recommended)

1. Problem statement & requirements (security, liveness, auditability, privacy)
2. System architecture diagram (nodes, clients, APIs)
3. Core algorithms implemented (list from section 1)
4. Your original algorithm (detailed: motivation, design, pseudocode)
5. Experiments & metrics (what you measured and how)
6. Demo walkthrough (short, scripted)
7. Limitations, future work, ethical considerations
8. Conclusion and Q&A pointers

---

## 6. Quick pseudocode: Adaptive Participation Proof (APP)

```
# Pseudocode sketch (high-level)
for each epoch E:
  W = last_N_blocks()
  for each node in peers:
    P[node] = compute_participation_score(node, W)
  meanP = average(P.values())
  for local miner:
    D_local = base_D * (1 + alpha * (meanP - P[local]))
    mine_with_difficulty(D_local)

# On validation:
validate_block(block):
  if not valid_pow(block, block.miner_id, D_for_miner_from_chain):
    reject
  else accept
```


---

## 7. Next steps I can do for you

- Add diagrams (sequence and architecture) for any demo.
- Produce slide-ready bullet content for each slide.
- Implement a prototype of APP or BGVD in this repo and add benchmark scripts.

---

Good choices for a final-year project: pick one core algorithm to implement and thoroughly evaluate, plus one original idea (APP or BGVD) that you implement and measure. If you want, I can scaffold slides or start implementing APP or BGVD here.
