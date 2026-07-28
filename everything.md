# BallotChain — Complete System Workflow

This document explains every component of the system from startup to vote
tallying, including the cryptographic foundations, data structures, API
endpoints, peer-to-peer networking, mining, consensus, and the blind
signature protocol that keeps votes anonymous.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Cryptographic Foundations](#2-cryptographic-foundations)
3. [Data Structures](#3-data-structures)
4. [Node Startup](#4-node-startup)
5. [Phase 1 — Admin Issues Invitation Codes](#5-phase-1--admin-issues-invitation-codes)
6. [Phase 2 — Voter Creates and Blinds a Vote](#6-phase-2--voter-creates-and-blinds-a-vote)
7. [Phase 3 — Admin Blind-Signs](#7-phase-3--admin-blind-signs)
8. [Phase 4 — Voter Unblinds and Submits](#8-phase-4--voter-unblinds-and-submits)
9. [Phase 5 — Blockchain Verifies the Vote](#9-phase-5--blockchain-verifies-the-vote)
10. [Phase 6 — Mining with Proof-of-Work](#10-phase-6--mining-with-proof-of-work)
11. [Phase 7 — Block Validation and Chain Linking](#11-phase-7--block-validation-and-chain-linking)
12. [Phase 8 — Peer-to-Peer Broadcast](#12-phase-8--peer-to-peer-broadcast)
13. [Phase 9 — Consensus Resolution](#13-phase-9--consensus-resolution)
14. [Phase 10 — Election Results](#14-phase-10--election-results)
15. [Phase 11 — Persistence and Recovery](#15-phase-11--persistence-and-recovery)
16. [End-to-End Sequence Diagram](#16-end-to-end-sequence-diagram)
17. [Anti-Replay Mechanism](#17-anti-replay-mechanism)
18. [Privacy Guarantees and Limitations](#18-privacy-guarantees-and-limitations)

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          React Frontend                              │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐               │
│  │  AdminView  │  │  VoterView   │  │  wallet.js      │              │
│  │  (code      │  │  (blind      │  │  (blind/unblind │              │
│  │  issuance)  │  │   vote UI)   │  │   crypto)       │              │
│  └─────┬──────┘  └──────┬───────┘  └────────┬───────┘               │
│        │                │                    │                       │
│        └────────────────┼────────────────────┘                       │
│                         │  HTTP fetch()                              │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────────────┐
│                    FastAPI Node 1                                    │
│  ┌──────────────────────┼───────────────────────────────────┐       │
│  │  main.py             │                                   │       │
│  │  ┌───────────────────┴────────────────────────────┐      │       │
│  │  │  Endpoints:                                     │      │       │
│  │  │  POST /voters/codes/issue  (admin auth)         │      │       │
│  │  │  GET  /voters/blind/public-key                  │      │       │
│  │  │  POST /voters/blind/sign   (validate code + sign)│     │       │
│  │  │  POST /votes               (anonymous vote)      │     │       │
│  │  │  GET  /mine                 (trigger mining)     │      │       │
│  │  │  POST /mine/cluster         (cluster mining)     │      │       │
│  │  │  GET  /chain                (view chain)         │      │       │
│  │  │  GET  /elections/{id}/results                   │      │       │
│  │  │  POST /blocks/receive       (peer block recv)    │      │       │
│  │  │  POST /mempool/receive      (peer vote recv)    │      │       │
│  │  │  POST /chains/sync          (longest chain)      │      │       │
│  │  │  POST /nodes/register       (add peers)          │      │       │
│  │  └──────────────────────────────────────────────────┘      │       │
│  │                                                           │       │
│  │  Blockchain instance                                     │       │
│  │  ┌──────────────────────────────────────────────┐        │       │
│  │  │  chain: [Block0, Block1, ...]                 │        │       │
│  │  │  pending_transactions: [{vote}, {vote}, ...]  │        │       │
│  │  │  registration_codes: {hash → entry}           │        │       │
│  │  │  used_nonces: {nonce1, nonce2, ...}           │        │       │
│  │  │  admin_n, admin_e  (RSA public key)           │        │       │
│  │  └──────────────────────────────────────────────┘        │       │
│  │                                                           │       │
│  │  RSA keypair (generated or loaded from env)               │       │
│  │  ┌──────────────────────────────────────────────┐        │       │
│  │  │  ADMIN_RSA_N, ADMIN_RSA_E  (public)          │        │       │
│  │  │  ADMIN_RSA_D               (private)         │        │       │
│  │  └──────────────────────────────────────────────┘        │       │
│  │                                                           │       │
│  │  JsonStorage → blockchain_data.json (on disk)             │       │
│  └───────────────────────────────────────────────────────────┘       │
└──────────────┬───────────────────────────────────────────────────────┘
               │  HTTP (peer-to-peer)
    ┌──────────┼──────────┐
    │          │          │
┌───┴───┐ ┌───┴───┐ ┌───┴───┐
│Node 2 │ │Node 3 │ │Node N │   (each runs identical FastAPI app)
└───────┘ └───────┘ └───────┘
```

Every node runs the same `main.py` FastAPI application. Each has its own
blockchain instance, its own RSA keypair (or shared via env), its own data
file, and a list of known peers.

---

## 2. Cryptographic Foundations

### 2.1 RSA 2048-bit Keys

The system uses standard RSA with a 2048-bit modulus and public exponent 65537.

```python
# main.py:120-138
def _load_admin_rsa_private_key():
    pem_from_env = os.getenv("ADMIN_RSA_PRIVATE_KEY_PEM", "")
    if pem_from_env:
        key = serialization.load_pem_private_key(pem_from_env.encode("utf-8"), password=None)
        return key
    # Dev fallback: ephemeral key generated fresh at startup
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

ADMIN_RSA_PRIVATE_KEY = _load_admin_rsa_private_key()
ADMIN_RSA_PUBLIC_KEY = ADMIN_RSA_PRIVATE_KEY.public_key()
ADMIN_RSA_N = int(ADMIN_RSA_PUBLIC_NUMBERS.n)  # 2048-bit modulus
ADMIN_RSA_E = int(ADMIN_RSA_PUBLIC_NUMBERS.e)  # = 65537
ADMIN_RSA_D = int(ADMIN_RSA_PRIVATE_NUMBERS.d)  # private exponent
```

The public key `(e, n)` is served via `GET /voters/blind/public-key` and
set on the blockchain instance so every node can verify vote signatures:

```python
# main.py:176-177
blockchain.admin_n = ADMIN_RSA_N
blockchain.admin_e = ADMIN_RSA_E
```

### 2.2 Blind Signature Scheme

The RSA blind signature protocol lets the admin sign a value without seeing
what it is. The math:

```
Blind:    m' = m · r^e  mod n      (voter computes, admin sees m')
Sign:     s' = (m')^d    mod n      (admin computes, returns s')
Unblind:  s  = s' · r⁻¹  mod n     (voter computes, recovers valid signature on m)
Verify:   s^e ≡ m        mod n      (any node verifies)
```

Where:
- `m` = vote hash in RSA modulus space
- `r` = random blinding factor chosen by voter, never transmitted
- `r⁻¹` = modular inverse of `r` mod `n`

### 2.3 SHA-256 Vote Hashing

Votes are hashed into the RSA modulus space using SHA-256:

```python
# crypto_utils.py:16-25
def hash_vote_to_modulus(candidate_id, election_id, nonce, modulus):
    message = canonical_vote_message(candidate_id, election_id, nonce)
    digest = hashlib.sha256(message).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1
```

The canonical serialization (JSON with sorted keys, no whitespace) ensures
client and server always produce the same byte sequence:

```python
# crypto_utils.py:7-13
def canonical_vote_message(candidate_id, election_id, nonce):
    payload = {
        "candidate_id": candidate_id.strip(),
        "election_id": election_id.strip(),
        "nonce": nonce.strip(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

### 2.4 Block Hashing (SHA-256 for PoW)

Blocks use a different hashing scheme — the entire block header (index,
timestamp, transactions, previous_hash, nonce) is SHA-256 hashed for
proof-of-work:

```python
# block.py:20-27
def calculate_hash(self):
    payload = {
        "index": self.index,
        "timestamp": self.timestamp,
        "transactions": self.transactions,
        "previous_hash": self.previous_hash,
        "nonce": self.nonce,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

---

## 3. Data Structures

### 3.1 Block

```python
@dataclass
class Block:
    index: int                              # position in the chain
    timestamp: float                        # UNIX time
    transactions: list[dict[str, Any]]      # vote records
    previous_hash: str                      # hash of the preceding block
    nonce: int = 0                          # PoW nonce
    hash: str = ""                          # SHA-256 of this block
```

Each block's `previous_hash` must equal the prior block's `hash`, forming
an immutable chain.

### 3.2 Vote Record (on-chain)

```json
{
    "candidate_id": "alice",
    "election_id": "student-union-2026",
    "nonce": "7ddb708d411b15fd1ccea17d27dba387",
    "signature": "0x4a6edd6a60e7167ffa1865a7c366a6478808d1198...",
    "timestamp": 1783302337.485604
}
```

There is **no voter_id**, **no voter_public_key**, and no link to any
identity. The `nonce` is the unique anti-replay identifier.

### 3.3 Blockchain State

```python
@dataclass
class Blockchain:
    difficulty: int                          # number of leading zeros required
    chain: list[Block]                       # ordered blocks
    pending_transactions: list[dict]         # votes waiting to be mined
    nodes: set[str]                          # known peer URLs
    registration_codes: dict[str, dict]      # SHA-256(code) → {election_id, issued_at, expires_at}
    used_nonces: set[str]                    # all nonces ever seen in chain
    admin_n: int                             # RSA modulus
    admin_e: int                             # RSA public exponent
```

### 3.4 Invitation Code Entry

```json
{
    "election_id": "student-union-2026",
    "issued_at": 1783302313.265,
    "expires_at": 1783305913.265
}
```

Only the **SHA-256 hash** of the raw code is stored. The plaintext code
is returned to the admin once and never stored.

---

## 4. Node Startup

### 4.1 RSA Key Loading

```python
# main.py:120-138
ADMIN_RSA_PRIVATE_KEY = _load_admin_rsa_private_key()
# Extract n, e, d from keypair
ADMIN_RSA_N = ...
ADMIN_RSA_E = ...
ADMIN_RSA_D = ...
```

Either loads a PEM from `ADMIN_RSA_PRIVATE_KEY_PEM` env var, or generates
an ephemeral 2048-bit key. In dev, the key is regenerated on restart
(unless PEM is set).

### 4.2 Chain Loading or Genesis Creation

```python
# main.py:158-170
storage = JsonStorage(DATA_FILE)
persisted = storage.load()

if persisted:
    blockchain = Blockchain.from_dict(persisted)   # validates chain integrity
else:
    blockchain = Blockchain(difficulty=DIFFICULTY)  # creates genesis block
```

If the data file doesn't exist (or contains invalid data), a fresh
blockchain with a genesis block is created.

### 4.3 Genesis Block

```python
# blockchain.py:32-39
def _create_genesis_block(self):
    genesis = Block(
        index=0,
        timestamp=time(),
        transactions=[],
        previous_hash="0",
    )
    genesis.hash = genesis.calculate_hash()
    return genesis
```

The genesis block has index 0, no transactions, and `previous_hash = "0"`.

### 4.4 Admin Key Propagation

```python
# main.py:176-177
blockchain.admin_n = ADMIN_RSA_N
blockchain.admin_e = ADMIN_RSA_E
```

The blockchain instance stores the admin RSA public key so it can verify
vote signatures during `add_vote()` and chain validation.

### 4.5 Peer Registration

```python
# main.py:262-277
def bootstrap_nodes_from_env():
    for peer in PEER_NODES_RAW.split(","):
        blockchain.register_node(peer)
```

Known peers from `PEER_NODES` env var are registered at startup.

### 4.6 FastAPI Startup Hook

```python
@app.on_event("startup")
def auto_register_peers():
    bootstrap_nodes_from_env()
```

---

## 5. Phase 1 — Admin Issues Invitation Codes

An invitation code is the gatekeeper for voting eligibility. One code =
one blind signature = one vote.

### API

```
POST /voters/codes/issue
Header: X-Admin-Token: <token>  OR  Authorization: Bearer <jwt>
Body: {"election_id": "student-union-2026", "expires_in_minutes": 60}

Response:
{
    "message": "Registration code issued",
    "registration_code": "Z5MN60M2PZ8ojDC-pynzgt8C",
    "election_id": "student-union-2026",
    "issued_at": 1783302317.988,
    "expires_at": 1783305917.988
}
```

### Server-side logic

```python
# blockchain.py:112-140
def issue_invitation_code_for(self, election_id, expires_in_minutes=60):
    self._cleanup_expired_registration_codes()

    registration_code = secrets.token_urlsafe(18)       # random 24-char code
    code_hash = self._registration_code_hash(registration_code)  # SHA-256
    while code_hash in self.registration_codes:          # avoid collision
        registration_code = secrets.token_urlsafe(18)
        code_hash = self._registration_code_hash(registration_code)

    issued_at = time()
    expires_at = issued_at + (expires_in_minutes * 60)
    entry = {
        "issued_at": issued_at,
        "expires_at": expires_at,
        "election_id": election_id,
    }
    self.registration_codes[code_hash] = entry          # store hash only
    return {"registration_code": registration_code, ...} # return plaintext
```

Key points:
- The raw code is returned in the response but **never stored** — only its
  SHA-256 hash is kept, so even database access can't recover codes.
- Expired codes are automatically cleaned up on every call.
- The admin distributes codes to voters through a trusted out-of-band channel.

### Access control

```python
# main.py:238-259
def assert_governance_access(x_admin_token, authorization=None):
    if OPEN_VOTER_REGISTRATION in ("1", "true", "yes"):
        return                              # dev mode: skip auth
    if not ADMIN_TOKEN and not JWT_SECRET:
        return                              # no auth configured
    if provided == ADMIN_TOKEN:
        return                              # legacy token match
    if authorization starts with "Bearer ":
        payload = _verify_jwt_token(token)
        if payload and payload.get("role") == "admin":
            return                          # valid JWT
    raise HTTPException(status_code=403)    # denied
```

---

## 6. Phase 2 — Voter Creates and Blinds a Vote

The voter constructs a vote, generates a random nonce, hashes the vote
into the RSA modulus space, picks a blinding factor, and computes the
blinded hash.

### Step 6.1 — Fetch the Admin Public Key

```
GET /voters/blind/public-key

Response:
{
    "algorithm": "RSA",
    "hash": "SHA-256",
    "e": "65537",
    "n": "21089...",
    "e_hex": "10001",
    "n_hex": "1f4d23...",
    "modulus_bits": 2048
}
```

### Step 6.2 — Create Vote Message with Random Nonce

**Python CLI** (`cast_blind_vote.py:70-79`):

```python
nonce = secrets.token_hex(16)   # 32-char random hex string
vote_message = json.dumps(
    {
        "candidate_id": "alice",
        "election_id": "student-union-2026",
        "nonce": "7ddb708d411b15fd1ccea17d27dba387",
    },
    sort_keys=True,
    separators=(",", ":"),
)
# Canonical form: {"candidate_id":"alice","election_id":"student-union-2026","nonce":"7ddb..."}
```

**Browser** (`wallet.js:80-90`):

```javascript
export function createBlindVoteMessage(candidate_id, election_id) {
    const nonceBytes = new Uint8Array(16);
    crypto.getRandomValues(nonceBytes);
    const nonce = bytesToHex(nonceBytes);
    const payload = {
        candidate_id: (candidate_id || "").trim(),
        election_id: (election_id || "").trim(),
        nonce,
    };
    return JSON.stringify(payload);
}
```

### Step 6.3 — Hash the Vote Message

**Python** (`cast_blind_vote.py:37-40`):

```python
def hash_to_int_mod_n(value, modulus):
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1
vote_hash = hash_to_int_mod_n(vote_message, n)
```

**JavaScript** (`wallet.js:75-78, 92-96`):

```javascript
const voteHash = (await sha256ToBigInt(voteMessage)) % n;
const targetHash = voteHash === 0n ? 1n : voteHash;
```

### Step 6.4 — Pick Blinding Factor and Blind

The voter picks a random `r` coprime to `n`, then computes the blinded
hash: `m' = vote_hash * r^e mod n`.

**Python** (`cast_blind_vote.py:43-51, 82-84`):

```python
def random_coprime_below(modulus):
    while True:
        candidate = secrets.randbelow(modulus - 1) + 1
        if candidate > 0 and candidate < modulus:
            try:
                pow(candidate, -1, modulus)   # test invertibility
                return candidate
            except ValueError:
                continue

r = random_coprime_below(n)
blinded_hash = (vote_hash * pow(r, e, n)) % n
```

**JavaScript** (`wallet.js:92-108`):

```javascript
let r = 0n;
do {
    r = randomBigIntBelow(n);
} while (gcd(r, n) !== 1n);

const blindedHash = (targetHash * modPow(r, e, n)) % n;
```

### Step 6.5 — Send to Admin

```python
# cast_blind_vote.py:88-99
requests.post(
    f"{node}/voters/blind/sign",
    json={
        "registration_code": "Z5MN60M2PZ8ojDC-pynzgt8C",
        "election_id": "student-union-2026",
        "blinded_hash": str(blinded_hash),     # large integer as string
    },
)
```

The voter sends **three things**: the invitation code, the election ID,
and the blinded hash. The voter keeps `r` secret.

---

## 7. Phase 3 — Admin Blind-Signs

The admin endpoint validates the invitation code, consumes it, and
returns a blind RSA signature on the blinded hash.

### API

```
POST /voters/blind/sign
Body: {
    "registration_code": "Z5MN60M2PZ8ojDC-pynzgt8C",
    "election_id": "student-union-2026",
    "blinded_hash": "3a8f2c..."
}

Response:
{
    "message": "Blinded hash signed successfully",
    "election_id": "student-union-2026",
    "blind_signature": "b1e9d4..."     // (blinded_hash)^d mod n
}
```

### Server-side logic

```python
# main.py:647-663
@app.post("/voters/blind/sign")
def blind_sign_registration(payload: BlindSignIn):
    # 1. Validate and consume invitation code
    entry = blockchain.consume_invitation_code(
        payload.registration_code, payload.election_id)

    # 2. Parse the blinded hash (must be in range 0 < m' < n)
    blinded_hash_int = _parse_modular_int(payload.blinded_hash, "blinded_hash")

    # 3. RSA sign: s' = (m')^d mod n
    blind_signature_int = pow(blinded_hash_int, ADMIN_RSA_D, ADMIN_RSA_N)

    persist_state()   # persist code removal
    return {
        "blind_signature": format(blind_signature_int, "hex"),
    }
```

### Invitation code consumption

```python
# blockchain.py:142-161
def consume_invitation_code(self, registration_code, election_id=None):
    code_hash = self._registration_code_hash(registration_code)
    entry = self.registration_codes.get(code_hash)
    if not entry:
        raise ValueError("invitation code is invalid or has already been used")

    # Verify election matches (if specified)
    if election_id is not None and entry_election != provided_election:
        raise ValueError("invitation code does not match the specified election")

    self.registration_codes.pop(code_hash, None)   # consume it
    return dict(entry)
```

The code is **removed** after use. Calling this endpoint with the same
code a second time will fail with HTTP 400.

---

## 8. Phase 4 — Voter Unblinds and Submits

### Step 8.1 — Unblind the Signature

The voter multiplies the blind signature by `r⁻¹ mod n` to recover a
valid RSA signature on the original vote hash.

**Python** (`cast_blind_vote.py:108-115`):

```python
blind_signature_int = int(blind_sign_response.json()["blind_signature"], 16)
r_inverse = pow(r, -1, n)
unblinded_signature = (blind_signature_int * r_inverse) % n
```

**JavaScript** (`wallet.js:111-118`):

```javascript
export function unblindVoteSignature(blindSignatureHex, rHex, rsaPublicKey) {
    const n = BigInt(rsaPublicKey.n);
    const blindSignature = BigInt(`0x${blindSignatureHex}`);
    const r = BigInt(`0x${rHex}`);
    const rInverse = modInverse(r, n);
    const signature = (blindSignature * rInverse) % n;
    return signature.toString(16);
}
```

### Step 8.2 — Local Verification (Optional)

Before submitting, the voter verifies the unblinded signature locally
to catch any tampering:

**Python** (`cast_blind_vote.py:118-120`):

```python
if pow(unblinded_signature, e, n) != vote_hash:
    print("Local verification failed")
    return 1
```

**JavaScript** (`wallet.js:120-128`):

```javascript
export async function verifyBlindVoteSignature(voteMessage, signatureHex, rsaPublicKey) {
    const n = BigInt(rsaPublicKey.n);
    const e = BigInt(rsaPublicKey.e);
    const signature = BigInt(`0x${signatureHex}`);
    const voteHash = (await sha256ToBigInt(voteMessage)) % n;
    const targetHash = voteHash === 0n ? 1n : voteHash;
    const recoveredHash = modPow(signature, e, n);
    return recoveredHash === targetHash;
}
```

### Step 8.3 — Submit the Anonymous Vote

**Python** (`cast_blind_vote.py:122-137`):

```python
requests.post(
    f"{node}/votes",
    json={
        "candidate_id": "alice",
        "election_id": "student-union-2026",
        "nonce": "7ddb708d411b15fd1ccea17d27dba387",
        "signature": hex(unblinded_signature),
    },
)
```

**Frontend** (`VoterView.jsx:181-186`):

```javascript
await castVote(baseUrl, {
    candidate_id: candidateId.trim(),
    election_id: electionId.trim(),
    nonce,
    signature: `0x${unblindedSignature}`,
});
```

The vote submission contains **no voter identity** — only the choice,
election, nonce, and signature.

---

## 9. Phase 5 — Blockchain Verifies the Vote

When `POST /votes` hits the server, `blockchain.add_vote()` runs three
checks before accepting:

### Check 1 — RSA Signature Verification

```python
# blockchain.py:73-81
if not verify_rsa_blind_vote_signature(
    candidate_id, election_id, nonce, signature,
    self.admin_n, self.admin_e,
):
    raise ValueError("invalid vote signature")
```

This calls into:

```python
# crypto_utils.py:28-42
def verify_rsa_blind_vote_signature(candidate_id, election_id, nonce, signature_hex, n, e):
    signature = int(signature_hex, 16)
    target_hash = hash_vote_to_modulus(candidate_id, election_id, nonce, n)
    recovered_hash = pow(signature, e, n)
    return recovered_hash == target_hash
```

It reconstructs the vote hash from the plaintext fields, then checks that
`signature^e mod n` equals that hash. If the admin signed it, this will
always pass.

### Check 2 — Nonce Not Used in Chain

```python
# blockchain.py:70-71
if self._is_nonce_used(nonce):
    raise ValueError("vote nonce has already been used")

# blockchain.py:163-164
def _is_nonce_used(self, nonce):
    return nonce.strip() in self.used_nonces
```

### Check 3 — Nonce Not Already Pending

```python
# blockchain.py:83-86
if self._has_nonce(nonce, self.pending_transactions):
    raise ValueError("vote with this nonce is already pending")
if self.has_voted_nonce(nonce):
    raise ValueError("vote with this nonce already exists in the chain")
```

### If All Checks Pass

```python
# blockchain.py:88-97
self.pending_transactions.append({
    "candidate_id": candidate_id,
    "election_id": election_id,
    "nonce": nonce,
    "signature": signature,
    "timestamp": time(),
})
return self.latest_block.index + 1
```

The vote enters the **mempool** — the list of pending transactions waiting
to be mined.

### Response

```python
# main.py:716-720
return {
    "message": "Anonymous vote will be added to block 2",
    "pending_votes": 5,
    "broadcast": {"accepted": 2, "rejected": 0, "unreachable": 0},
}
```

The vote is also broadcast to all known peers' mempools via:

```python
# main.py:335-366
def broadcast_transaction_to_peers(vote):
    for node in blockchain.nodes:
        requests.post(f"{node}/mempool/receive", json=vote, timeout=5)
```

---

## 10. Phase 6 — Mining with Proof-of-Work

Mining bundles pending votes into a new block and repeatedly hashes the
block header until the hash starts with `difficulty` leading zeros.

### Trigger

```
GET /mine
```

This triggers `_coordinate_cluster_mining()` which tells all peers to
start mining on the same transactions, then mines locally:

```python
# main.py:803-853
def _coordinate_cluster_mining(limit, difficulty):
    txs = list(blockchain.pending_transactions)[:limit]

    # Tell all peers to start mining
    for node in blockchain.nodes:
        requests.post(f"{node}/mine/remote", json={"transactions": txs, "difficulty": difficulty})

    # Mine locally
    local_result = _mine_transactions(txs, difficulty=difficulty, broadcast=True)
    return {"local": local_result, "peers": peer_results}
```

### Mining Loop

```python
# main.py:462-567
def _mine_transactions(transactions, difficulty, broadcast):
    block = Block(
        index=len(blockchain.chain),
        timestamp=time_now(),
        transactions=transactions,
        previous_hash=blockchain.latest_block.hash,
    )
    target = "0" * difficulty

    while not miner_stop_event.is_set():
        block.hash = block.calculate_hash()
        if block.hash.startswith(target):
            # Found a valid hash — add block to chain
            blockchain.add_block(block)
            _remove_mined_transactions_from_mempool(block.transactions)
            persist_state()
            # Broadcast to peers
            if broadcast:
                broadcast_block_to_peers(block)
            return {"message": "New vote block mined", "index": block.index, ...}
        block.nonce += 1
```

### Proof-of-Work

```python
# block.py:29-34
def mine_block(self, difficulty):
    target = "0" * difficulty
    self.hash = self.calculate_hash()
    while not self.hash.startswith(target):
        self.nonce += 1
        self.hash = self.calculate_hash()
```

The miner increments `nonce` repeatedly until the SHA-256 hash of the
block header starts with the required number of zeros. With `difficulty=5`
the hash must start with `00000`.

---

## 11. Phase 7 — Block Validation and Chain Linking

When a node receives a mined block (either locally or from a peer),
`add_block()` validates it fully before adding to the chain:

```python
# blockchain.py:243-301
def add_block(self, block):
    previous_block = self.latest_block

    # 1. Hash linkage: block must point to the latest block
    if block.previous_hash != previous_block.hash:
        raise ValueError("invalid previous hash linkage")

    # 2. Block integrity: hash must match recalculated hash
    if block.hash != block.calculate_hash():
        raise ValueError("invalid block hash")

    # 3. Proof-of-work: hash must meet difficulty target
    if not block.hash.startswith("0" * self.difficulty):
        raise ValueError("invalid proof-of-work")

    # 4. Vote validation: every vote must have valid RSA signature
    seen_nonces_in_block = set()
    for vote in block.transactions:
        _, _, nonce = self._validate_vote_record(vote)
        if nonce in seen_nonces_in_block:
            raise ValueError("block contains duplicate nonce")
        if self.has_voted_nonce(nonce):
            raise ValueError("block contains nonce already present in chain")
        seen_nonces_in_block.add(nonce)

    # 5. Mark all nonces as used
    for vote in block.transactions:
        self._mark_nonce_used(str(vote.get("nonce", "")).strip())

    self.chain.append(block)
```

The chain validity check (`is_chain_valid()`) also verifies every block
in the chain:

```python
# blockchain.py:311-345
def is_chain_valid(self, chain):
    genesis = chain[0]
    if genesis.hash != genesis.calculate_hash(): return False
    if genesis.previous_hash != "0": return False

    seen_nonces = set()
    for index in range(1, len(chain)):
        current = chain[index]
        previous = chain[index - 1]

        if current.previous_hash != previous.hash: return False
        if current.hash != current.calculate_hash(): return False
        if not current.hash.startswith("0" * self.difficulty): return False

        for vote in current.transactions:
            _, _, nonce = self._validate_vote_record(vote)
            if nonce in seen_nonces: return False
            seen_nonces.add(nonce)
    return True
```

---

## 12. Phase 8 — Peer-to-Peer Broadcast

### Vote Broadcast

When a vote is accepted, it is sent to all peers' mempools:

```python
# main.py:335-366
def broadcast_transaction_to_peers(vote):
    for node in blockchain.nodes:
        response = requests.post(f"{node}/mempool/receive", json=vote, timeout=5)
```

Receiving node validates the vote and adds it to its own mempool:

```python
# main.py:728-760
@app.post("/mempool/receive")
def mempool_receive(vote: VoteIn):
    if blockchain._has_nonce(vote.nonce, blockchain.pending_transactions):
        return {"message": "vote already in mempool"}   # idempotent
    index = blockchain.add_vote(vote.candidate_id, vote.election_id, vote.nonce, vote.signature)
    return {"message": "Vote accepted into mempool"}
```

### Block Broadcast

When a block is mined, it is sent to all peers:

```python
# main.py:289-332
def broadcast_block_to_peers(mined_block):
    for node in blockchain.nodes:
        response = requests.post(f"{node}/blocks/receive", json=mined_block.to_dict(), timeout=5)
        if response.status_code == 200:
            accepted += 1
        else:
            # If peer rejects the single block, try syncing entire chain
            sync_response = requests.post(f"{node}/chains/sync",
                json={"difficulty": blockchain.difficulty,
                      "chain": [b.to_dict() for b in blockchain.chain]})
```

Receiving node validates and appends the block:

```python
# main.py:889-933
@app.post("/blocks/receive")
def receive_block(block_payload: BlockIn):
    _stop_local_miner()    # stop competing mining
    incoming_block = Block.from_dict(block_payload.model_dump())

    if incoming_block.index <= blockchain.latest_block.index:
        return {"message": "Block already known or stale"}

    blockchain.add_block(incoming_block)   # full validation
    _remove_mined_transactions_from_mempool(incoming_block.transactions)
    return {"message": "Block accepted"}
```

---

## 13. Phase 9 — Consensus Resolution

Nodes can run `GET /nodes/resolve` to adopt the longest valid chain
across the network (Nakamoto consensus):

```python
# main.py:981-1017
@app.get("/nodes/resolve")
def resolve_nodes():
    longest_chain = None
    max_length = len(blockchain.chain)

    for node in blockchain.nodes:
        response = requests.get(f"{node}/chain", timeout=5)
        remote_chain = [Block.from_dict(item) for item in response.json()["chain"]]
        remote_length = response.json()["length"]

        if remote_length > max_length and blockchain.is_chain_valid(remote_chain):
            max_length = remote_length
            longest_chain = remote_chain

    if longest_chain is not None:
        blockchain.chain = longest_chain
        blockchain.pending_transactions.clear()
        persist_state()
        return {"message": "Chain was replaced by a longer valid chain"}

    return {"message": "Current chain is authoritative"}
```

A node can also push its chain to peers via `POST /chains/sync`:

```python
# main.py:936-959
@app.post("/chains/sync")
def sync_chain(payload: ChainSyncIn):
    remote_chain = [Block.from_dict(item) for item in payload.chain]
    if len(remote_chain) <= len(blockchain.chain):
        raise HTTPException(status_code=400, detail="Received chain is not longer")
    if not blockchain.is_chain_valid(remote_chain):
        raise HTTPException(status_code=400, detail="Received chain is invalid")
    blockchain.chain = remote_chain
    blockchain.difficulty = payload.difficulty
```

---

## 14. Phase 10 — Election Results

### API

```
GET /elections/student-union-2026/results

Response:
{
    "election_id": "student-union-2026",
    "total_votes": 5,
    "results": {"bibhab": 3, "anwesha": 1, "bibesh": 1},
    "pending_votes": 0,
    "include_pending": false
}
```

### Tallying Logic

```python
# blockchain.py:341-370
def tally_votes(self, election_id, include_pending=True):
    counts = {}

    def record_votes(votes):
        for vote in votes:
            if str(vote.get("election_id", "")).strip() != election_id:
                continue
            candidate_id = str(vote.get("candidate_id", "")).strip()
            counts[candidate_id] = counts.get(candidate_id, 0) + 1

    for block in self.chain:
        record_votes(block.transactions)       # mined votes

    if include_pending:
        record_votes(self.pending_transactions) # pending votes
    return counts
```

Tallying is straightforward because votes have no identity — it simply
counts all on-chain (and optionally pending) vote records for the given
election.

---

## 15. Phase 11 — Persistence and Recovery

### Saving

```python
# main.py:204-205
def persist_state():
    storage.save(blockchain.to_dict())

# storage.py:12-17
def save(self, data):
    if path.is_dir():
        shutil.rmtree(path)          # handle Docker bind-mount dirs
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
```

### Loading

```python
# main.py:158-170
storage = JsonStorage(DATA_FILE)
persisted = storage.load()

if persisted:
    blockchain = Blockchain.from_dict(persisted)
    # from_dict validates chain integrity via is_chain_valid()
else:
    blockchain = Blockchain(difficulty=DIFFICULTY)
```

### Serialized State

```python
# blockchain.py:372-386
def to_dict(self):
    return {
        "difficulty": self.difficulty,
        "chain": [block.to_dict() for block in self.chain],
        "pending_transactions": self.pending_transactions,
        "nodes": sorted(self.nodes),
        "registration_codes": dict(self.registration_codes),
        "used_nonces": sorted(list(self.used_nonces)),
        "admin_n": self.admin_n,
        "admin_e": self.admin_e,
    }
```

After restart:
- The chain is loaded and validated.
- Pending transactions are restored.
- Peer nodes are restored from the data file (and re-bootstrapped from env).
- Used nonces are restored (prevents replay after restart).
- Registration codes (if still unexpired) are restored.
- The admin RSA public key is set from the running instance (or env PEM).

---

## 16. End-to-End Sequence Diagram

```
Admin                Node 1                 Voter                 Node 2/3
  │                    │                      │                       │
  │  issue code        │                      │                       │
  │ ──────────────────>│                      │                       │
  │  code: Z5MN60M...  │                      │                       │
  │<────────────────── │                      │                       │
  │                    │                      │                       │
  │                    │  get public key      │                       │
  │                    │<─────────────────────│                       │
  │                    │  {n, e}              │                       │
  │                    │─────────────────────>│                       │
  │                    │                      │                       │
  │                    │                      │ create vote msg       │
  │                    │                      │ + random nonce        │
  │                    │                      │ blind: m' = m*r^e     │
  │                    │                      │                       │
  │                    │  blind sign          │                       │
  │                    │<─────────────────────│ (code + blinded_hash) │
  │  consume code      │  blind_signature    │                       │
  │  sign: s'=(m')^d   │─────────────────────>│                       │
  │                    │                      │                       │
  │                    │                      │ unblind: s = s'*r⁻¹  │
  │                    │                      │ verify: s^e == m      │
  │                    │                      │                       │
  │                    │  submit vote         │                       │
  │                    │<─────────────────────│ (candidate, election, │
  │                    │                      │  nonce, signature)    │
  │                    │                      │                       │
  │                    │  verify sig          │                       │
  │                    │  check nonce         │                       │
  │                    │  add to mempool      │                       │
  │                    │─────────────────────>│                       │
  │                    │  broadcast vote      │                       │
  │                    │  ─────────────────────────────────────────> │
  │                    │                      │                       │
  │                    │                      │      verify + add to  │
  │                    │                      │      mempool          │
  │                    │                      │                       │
  │                    │  mine: PoW           │                       │
  │                    │  find nonce s.t.     │                       │
  │                    │  SHA256 ≡ 000...     │                       │
  │                    │                      │                       │
  │                    │  block mined!        │                       │
  │                    │  broadcast block     │                       │
  │                    │  ─────────────────────────────────────────> │
  │                    │                      │                       │
  │                    │                      │      validate block   │
  │                    │                      │      + add to chain   │
  │                    │                      │                       │
  │                    │                      │                       │
  │  GET /results      │                      │                       │
  │ ──────────────────>│                      │                       │
  │  {alice: 3, bob:2} │                      │                       │
  │<────────────────── │                      │                       │
```

---

## 17. Anti-Replay Mechanism

Each vote carries a unique `nonce` — a 128-bit random value generated
by the voter. The system rejects duplicates at multiple levels:

### At vote submission (`add_vote`):

```python
# blockchain.py:70-71
if self._is_nonce_used(nonce):
    raise ValueError("vote nonce has already been used")

# blockchain.py:83-86
if self._has_nonce(nonce, self.pending_transactions):
    raise ValueError("vote with this nonce is already pending")
if self.has_voted_nonce(nonce):
    raise ValueError("vote with this nonce already exists in the chain")
```

### At block validation (`add_block`):

```python
# blockchain.py:264-278
for vote in block.transactions:
    _, _, nonce = self._validate_vote_record(vote)
    if nonce in seen_nonces_in_block:
        raise ValueError("block contains duplicate nonce")
    if self.has_voted_nonce(nonce):
        raise ValueError("block contains nonce already present in chain")
    seen_nonces_in_block.add(nonce)
```

### At chain validation (`is_chain_valid`):

```python
# blockchain.py:332-339
seen_nonces = set()
for index in range(1, len(chain)):
    for vote in chain[index].transactions:
        _, _, nonce = self._validate_vote_record(vote)
        if nonce in seen_nonces:
            return False
        seen_nonces.add(nonce)
```

### Nonce state in persistence:

```python
# blockchain.py:166-167
def _mark_nonce_used(self, nonce):
    self.used_nonces.add(nonce.strip())
```

The `used_nonces` set is saved to disk via `to_dict()` and restored via
`from_dict()`, ensuring nonces persist across restarts.

---

## 18. Privacy Guarantees and Limitations

### What the system protects

| Property | Mechanism |
|---|---|
| **No voter identity on-chain** | Vote records contain only `{candidate_id, election_id, nonce, signature, timestamp}` |
| **Admin can't see vote content** | Blind signing: admin signs `m' = m · r^e mod n` — a random-looking number |
| **No cryptographic link between code and vote** | The blinding factor `r` is chosen by voter and never transmitted; no one can link `m'` to the unblinded `s` |
| **Replay prevention** | Nonces are unique; duplicates rejected at submission, block validation, and chain validation |

### Known limitations

| Limitation | Explanation |
|---|---|
| **Per-person double voting** | The system enforces one-vote-per-code, but cannot prevent one person from obtaining multiple codes. This is controlled by the admin's code issuance policy. |
| **Vote selling / coercion** | The voter holds `r` and the final signature — they can prove how they voted to a third party. Receipt-freeness is not guaranteed. |
| **Timing correlation** | If only one code is active and a vote arrives immediately after blind signing, an observer may guess the link (no cryptographic evidence though). |
| **Ephemeral RSA key** | In dev mode, the RSA key is regenerated on restart. Set `ADMIN_RSA_PRIVATE_KEY_PEM` env var for persistence. |
