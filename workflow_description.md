# Project Workflow — How the system works (short, direct)

This file describes the end-to-end workflow of your voting blockchain. It's written plainly so you can drop it into your report or present it live.

## 1. High-level summary
- User creates a *wallet* → keypair (private key + public key) is generated locally.
- Wallet registers the public key with a node (auto-register if allowed).
- User constructs a vote (candidate, election_id, voter_id), the wallet canonicalizes the message and signs it with the private key.
- The signed vote (message fields + base64 public key + base64 signature) is submitted to a node.
- Node verifies signature, checks voter registration and duplicate-vote rules, then accepts or rejects the vote.
- Accepted votes enter the `pending_votes` pool; miners collect pending votes and run Proof-of-Work to create a block.
- Mined block is broadcast to peers; peers validate PoW + signatures + inclusion rules and append to chain.
- Final tallying reads the confirmed chain and computes results.

## 2. Detailed step-by-step workflow

1) Wallet creation (client-side)
- Action: user clicks "Create Wallet" (browser) or runs `python generate_wallet.py` (CLI).
- Result: an Ed25519 keypair is produced.
- Storage: private key stays local (encrypted in browser/localStorage or saved to an encrypted file CLI). Public key is derived and exported (base64).
- Files in repo: [generate_wallet.py](generate_wallet.py) and [frontend/src/wallet.js](frontend/src/wallet.js).

2) (Optional) Auto-registration of public key
- Action: UI sends `POST /voters/register` with `{ voter_id, voter_public_key }`.
- Server action: node records mapping `voter_id -> public_key` in the persistent voter registry.
- When `ADMIN_TOKEN` protection is enabled, registration may require the admin token (for controlled deployments).
- Files: [main.py](main.py) endpoint `/voters/register`, persistence in [storage.py](storage.py).

3) Vote creation and signing (client)
- Action: user fills vote form (candidate_id, election_id, voter_id).
- Canonicalization: client calls a deterministic serializer to produce `message_bytes` (sorted keys, UTF-8, fixed numeric format). See `crypto_utils.canonical_vote_message()`.
- Signing: client computes `signature = Sign(private_key, message_bytes)` (Ed25519). Signature is encoded base64.
- Payload sent: JSON including vote fields plus `voter_public_key` (base64) and `signature` (base64).
- Files: [frontend/src/api.js](frontend/src/api.js), [frontend/src/wallet.js](frontend/src/wallet.js), [crypto_utils.py](crypto_utils.py).

4) Server-side verification and duplicate check
- Server receives POST `/votes` with payload.
- Steps the server performs (in order):
  a) Validate required fields exist and base64-decode public key and signature.
  b) Canonicalize the message fields exactly the same way as the client and recompute `message_bytes`.
  c) Verify signature: `Verify(public_key, message_bytes, signature)` (Ed25519). If verification fails → reject with "invalid vote signature".
  d) Check registration: look up `voter_id` or `voter_public_key` in the voter registry. If not registered → reject with "voter is not registered" (unless system allows open registration).
  e) Duplicate detection: check persistent store if this `voter_id` already voted for `election_id` (one-vote-per-election). If duplicate → reject with "voter has already voted".
  f) If all checks pass → append vote to `pending_votes` and return success (optionally broadcast to peers).
- Files: [main.py](main.py), [blockchain.py](blockchain.py), [storage.py](storage.py), [crypto_utils.py](crypto_utils.py).

5) Duplicate detection details
- Persistent check: server keeps accepted vote records (by voter_id + election_id) in storage; this is the canonical source of truth.
- Fast-path optimization (optional): an in-memory Bloom filter is used to quickly detect likely duplicates and avoid heavy signature work (see the BGVD idea in `algorithms_and_workflows.md` if implemented).
- Race conditions: if two submissions arrive concurrently, the node must atomically check-and-insert (file-based lock or single-threaded queue or small DB transaction) to avoid double-acceptance.
- Files: [blockchain.py](blockchain.py) enforces `has_voted()` and duplicate checks.

6) Mining and Proof-of-Work (PoW)
- Miner collects pending votes into a candidate block.
- Miner repeatedly increments `nonce` and computes `hash(block_header || nonce)` until hash meets the difficulty target (e.g., leading zero bits).
- On success, miner creates a block with the included votes and a cryptographic hash -> appends to local chain and broadcasts block to peers.
- Peers validate block: check PoW target, verify included vote signatures again, confirm no double-votes within the new block given chain history, then append if valid.
- Files: [block.py](block.py), [blockchain.py](blockchain.py). Difficulty param in config/env `DIFFICULTY`.

7) Post-mining: propagation and finality
- Propagation: node sends the newly mined block to its peers via `/receive-new-block` endpoints.
- Finality: this system uses probabilistic finality like classic PoW — the deeper a block is in the chain, the more certain the included votes are final.
- Tallying: any node can scan the canonical chain and tally votes for each election.

## 3. How verification works (concise)
- Signature verification uses Ed25519: server recomputes canonical message bytes and calls `public_key.verify(signature, message_bytes)`.
- Registration proof: a registered mapping `voter_id -> public_key` must exist before acceptance (unless open registration is permitted).
- Duplicate-proof: server checks chain + accepted votes store for prior votes from same `voter_id` for same `election_id`.
- Block validation: includes re-check of all vote signatures and duplicate rules (to prevent a malicious miner from inserting bad votes). If any included vote fails verification, the block is rejected.

## 4. Failure cases and how system responds
- Invalid signature: vote rejected immediately.
- Unregistered public key: rejected (or queued for admin review if you implement that flow).
- Duplicate attempt: rejected with explicit error.
- Miner includes invalid vote in block: peers reject the block; miner loses work.
- Conflicting simultaneous accepted blocks: peers resolve by chain length (most cumulative work).

## 5. Which parts are your own code vs. imported/standard libraries

Own code (implemented in this repo)
- Voter registration flow and one-vote-per-election enforcement: [main.py](main.py), [blockchain.py](blockchain.py), [storage.py](storage.py).
- Canonicalization helper & vote serialization logic: `crypto_utils.canonical_vote_message()` in [crypto_utils.py](crypto_utils.py).
- Application-level duplicate handling and race protections: logic in [blockchain.py](blockchain.py) and `storage.py` persistence decisions.
- (Optionally) Any original algorithm you add, for example:
  - Adaptive Participation Proof (APP) — if you implemented it: additions in [blockchain.py](blockchain.py) and new helper files.
  - Bloom-Guard Vote Deduplication (BGVD) — if implemented: new module and changes to vote ingestion path.

Imported / standard cryptography & utility code (not your own)
- Ed25519 implementation: provided by Python cryptography library (`cryptography.hazmat.primitives.asymmetric.ed25519`) or libsodium / tweetnacl (frontend). Do NOT reimplement these algorithms — cite them.
- Base64 encoding/decoding and JSON serialization: standard library modules (`base64`, `json`).
- HTTP server framework: `FastAPI` / `uvicorn` used for API and routing.
- Frontend signing helper: `tweetnacl` (npm) — used in browser.

## 6. Short notes you can paste into slides (summary bullets)
- Wallet = locally-generated Ed25519 keypair (private stays local; public is registered).
- Client canonicalizes vote JSON and signs bytes with private key → sends vote+public_key+signature.
- Node verifies signature + registration + duplicate rules → accepts to pending pool.
- Miner collects pending votes, solves PoW, broadcasts block; peers re-verify signatures and append valid blocks.
- Original contributions: candidate algorithms implemented by you (APP or BGVD or other), server-side canonicalization and duplicate-handling logic.

---

If you want, I can:
- Convert this into a one-page slide or speaker notes.
- Implement BGVD or APP and mark changed files.
- Add command examples for manual testing (`generate_wallet.py`, `register_voter.py`, `add_vote.py`).

Progress update: created `workflow_description.md` with the full flow and mapping of original vs imported components. Next: add CLI example commands and finish storage/security best-practices notes (if you want).