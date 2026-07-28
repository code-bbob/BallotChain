# Blind Signature Voting Flow

This document explains step-by-step how RSA blind signatures enable private
anonymous voting in this blockchain system. No voter identity is ever stored
on-chain.

## System Overview

```text
Voter                        Admin                         Blockchain
  |                            |                              |
  |  1. Request public key     |                              |
  |--------------------------->|                              |
  |<----- n, e ---------------|                              |
  |                            |                              |
  |  2. Create vote + nonce    |                              |
  |  3. Blind: m' = m * r^e   |                              |
  |  4. Send blinded + code    |                              |
  |--------------------------->|                              |
  |                            |  5. Verify invitation code   |
  |                            |  6. Sign: s' = (m')^d mod n |
  |<---- blind signature s' --|                              |
  |                            |                              |
  |  7. Unblind: s = s' * r^-1|                              |
  |  8. Submit vote + nonce    |                              |
  |--------------------------------------------------------->|
  |                            |    9. Verify: s^e == m mod n |
  |                            |   10. Check nonce unique     |
  |                            |   11. Add to mempool         |
```

## Cryptography Primer

RSA blind signatures use the standard RSA signing equation:

- `sign(m)` = `m^d mod n` (normal RSA signature)
- `blind(m, r)` = `m * r^e mod n` (voter blinds before sending)
- `unblind(s', r)` = `s' * r^(-1) mod n` (voter removes blinding)

where:
- `(e, n)` = RSA public key (known to everyone)
- `d` = RSA private key (known only to the admin)
- `r` = random blinding factor, coprime with `n` (chosen by voter, never revealed)

The math works because:

```
blind_sign(m') = (m * r^e)^d = m^d * r^(e*d) = m^d * r (mod n)
unblind(s') = m^d * r * r^(-1) = m^d (mod n)
```

The result `m^d mod n` is a valid RSA signature on `m`, but the admin
never saw `m` — they only saw `m'`.

---

## Step-by-Step Code Walkthrough

### Step 0: Admin RSA Key Generation

File: `main.py:120-138`

```python
ADMIN_RSA_PRIVATE_KEY = _load_admin_rsa_private_key()
ADMIN_RSA_PUBLIC_KEY = ADMIN_RSA_PRIVATE_KEY.public_key()
ADMIN_RSA_PUBLIC_NUMBERS = ADMIN_RSA_PUBLIC_KEY.public_numbers()
ADMIN_RSA_PRIVATE_NUMBERS = ADMIN_RSA_PRIVATE_KEY.private_numbers()
ADMIN_RSA_N = int(ADMIN_RSA_PUBLIC_NUMBERS.n)
ADMIN_RSA_E = int(ADMIN_RSA_PUBLIC_NUMBERS.e)
ADMIN_RSA_D = int(ADMIN_RSA_PRIVATE_NUMBERS.d)
```

The node generates (or loads from env) an RSA 2048-bit keypair at startup.
The public exponent `e = 65537` is standard for RSA. The private exponent `d`
and modulus `n` are extracted from the key.

### Step 1: Admin Issues an Invitation Code

File: `blockchain.py:112-140`

```python
def issue_invitation_code_for(self, election_id=None, expires_in_minutes=60):
    self._cleanup_expired_registration_codes()
    registration_code = secrets.token_urlsafe(18)
    code_hash = self._registration_code_hash(registration_code)
    while code_hash in self.registration_codes:
        registration_code = secrets.token_urlsafe(18)
        code_hash = self._registration_code_hash(registration_code)

    issued_at = time()
    expires_at = issued_at + (expires_in_minutes * 60)
    entry = {
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    if election_id:
        entry["election_id"] = str(election_id).strip()

    self.registration_codes[code_hash] = entry
    return {
        "registration_code": registration_code,
        "election_id": entry.get("election_id"),
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
```

Only the **hash** of the code is stored (SHA-256). The raw code is returned to
the caller and must be distributed out-of-band to the voter.

Endpoint: `POST /voters/codes/issue`

File: `main.py:581-598`

```python
@app.post("/voters/codes/issue")
def issue_registration_code(
    payload: RegistrationCodeIssueIn,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    assert_governance_access(x_admin_token, authorization)
    try:
        result = blockchain.issue_invitation_code_for(
            payload.election_id, payload.expires_in_minutes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    persist_state()
    return {"message": "Registration code issued", **result}
```

### Step 2: Voter Creates Vote Message with Nonce

The voter constructs a JSON message containing their choice and a random nonce.
The nonce prevents replay attacks and is chosen by the voter on their machine.

File: `cast_blind_vote.py:70-79` (Python CLI)

```python
nonce = secrets.token_hex(16)
vote_message = json.dumps(
    {
        "candidate_id": args.candidate_id.strip(),
        "election_id": args.election_id.strip(),
        "nonce": nonce,
    },
    sort_keys=True,
    separators=(",", ":"),
)
```

File: `frontend/src/wallet.js:80-90` (Browser)

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

The canonical form is `{"candidate_id":"...","election_id":"...","nonce":"..."}`.
The same serialization function must be used on both client and server.

### Step 3: Voter Blinds the Vote Hash

The voter hashes the vote message into the RSA modulus space, picks a random
blinding factor `r` coprime to `n`, and computes the blinded hash.

File: `cast_blind_vote.py:82-84`

```python
vote_hash = hash_to_int_mod_n(vote_message, n)
r = random_coprime_below(n)
blinded_hash = (vote_hash * pow(r, e, n)) % n
```

Where `hash_to_int_mod_n` is (file: `cast_blind_vote.py:37-40`):

```python
def hash_to_int_mod_n(value, modulus):
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1
```

And the blinding factor selection (file: `cast_blind_vote.py:43-51`):

```python
def random_coprime_below(modulus):
    while True:
        candidate = secrets.randbelow(modulus - 1) + 1
        if candidate < modulus and candidate > 0:
            try:
                pow(candidate, -1, modulus)
                return candidate
            except ValueError:
                continue
```

Frontend equivalent (file: `frontend/src/wallet.js:92-108`):

```javascript
export async function createBlindVoteRequest(voteMessage, rsaPublicKey) {
  const n = BigInt(rsaPublicKey.n);
  const e = BigInt(rsaPublicKey.e);
  const voteHash = (await sha256ToBigInt(voteMessage)) % n;
  const targetHash = voteHash === 0n ? 1n : voteHash;

  let r = 0n;
  do {
    r = randomBigIntBelow(n);
  } while (gcd(r, n) !== 1n);

  const blindedHash = (targetHash * modPow(r, e, n)) % n;
  return {
    blinded_hash_hex: blindedHash.toString(16),
    r_hex: r.toString(16),
    vote_hash_hex: targetHash.toString(16),
  };
}
```

The `r` value stays on the voter's machine — it is **never transmitted**.

### Step 4: Voter Sends Blinded Hash + Invitation Code to Admin

File: `cast_blind_vote.py:88-99`

```python
blind_sign_response = requests.post(
    f"{node}/voters/blind/sign",
    json={
        "registration_code": args.registration_code.strip(),
        "election_id": args.election_id.strip() or None,
        "blinded_hash": str(blinded_hash),
    },
    timeout=args.timeout,
)
```

Frontend equivalent (file: `frontend/src/VoterView.jsx:156-159`):

```javascript
const signResponse = await requestBlindSignature(baseUrl, {
  registration_code: registrationCode.trim(),
  election_id: electionId.trim() || undefined,
  blinded_hash: `0x${blindRequest.blinded_hash_hex}`,
});
```

### Step 5: Admin Validates Invitation Code and Blind-Signs

The admin endpoint consumes the invitation code (gating access), then
RSA-signs the blinded hash using the private exponent `d`.

File: `main.py:647-663`

```python
@app.post("/voters/blind/sign")
def blind_sign_registration(payload: BlindSignIn):
    try:
        entry = blockchain.consume_invitation_code(
            payload.registration_code, payload.election_id)

        entry_election = str(entry.get("election_id", "")).strip() or None
        blinded_hash_int = _parse_modular_int(payload.blinded_hash, "blinded_hash")
        blind_signature_int = pow(blinded_hash_int, ADMIN_RSA_D, ADMIN_RSA_N)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    persist_state()
    return {
        "message": "Blinded hash signed successfully",
        "election_id": entry_election,
        "blind_signature": format(blind_signature_int, "x"),
    }
```

The `consume_invitation_code` method validates and removes the code atomically
(file: `blockchain.py:142-161`):

```python
def consume_invitation_code(self, registration_code, election_id=None):
    registration_code = registration_code.strip()
    if not registration_code:
        raise ValueError("registration_code is required")

    self._cleanup_expired_registration_codes()

    code_hash = self._registration_code_hash(registration_code)
    entry = self.registration_codes.get(code_hash)
    if not entry:
        raise ValueError("invitation code is invalid or has already been used")

    entry_election = str(entry.get("election_id", "")).strip() or None
    if election_id is not None:
        provided_election = str(election_id).strip() or None
        if entry_election != provided_election:
            raise ValueError("invitation code does not match the specified election")

    self.registration_codes.pop(code_hash, None)
    return dict(entry)
```

The admin **never sees the vote** — only `blinded_hash`, which is `m * r^e mod n`,
a random-looking number that reveals no information about the original message.

### Step 6: Admin Returns Blind Signature

The server returns `blind_signature = (blinded_hash)^d mod n = (m * r^e)^d mod n`.

This is meaningless to anyone who doesn't know `r`.

### Step 7: Voter Unblinds the Signature

The voter multiplies the blind signature by `r^(-1) mod n`, removing the
blinding factor and recovering a valid RSA signature on the original vote hash.

File: `cast_blind_vote.py:108-115`

```python
blind_signature_int = int(
    str(blind_sign_response.json().get("blind_signature", "")).strip(), 16)
r_inverse = pow(r, -1, n)
unblinded_signature = (blind_signature_int * r_inverse) % n
```

Frontend equivalent (file: `frontend/src/wallet.js:111-118`):

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

### Step 8: Voter Verifies Locally (Optional)

The voter can verify the unblinded signature before submitting, catching tampering.

File: `cast_blind_vote.py:118-120`

```python
if pow(unblinded_signature, e, n) != vote_hash:
    print("Local verification failed for unblinded vote signature")
    return 1
```

Frontend equivalent (file: `frontend/src/VoterView.jsx:169-178`):

```javascript
const isValid = await verifyBlindVoteSignature(
  voteMessage, unblindedSignature, blindPublicKey
);
```

File: `frontend/src/wallet.js:120-128`:

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

### Step 9: Voter Submits Anonymous Vote

The vote is submitted with **no voter identity** — only the candidate choice,
election ID, nonce, and signature.

File: `cast_blind_vote.py:122-137`

```python
vote_response = requests.post(
    f"{node}/votes",
    json={
        "candidate_id": args.candidate_id.strip(),
        "election_id": args.election_id.strip(),
        "nonce": nonce,
        "signature": hex(unblinded_signature),
    },
    timeout=args.timeout,
)
```

Frontend equivalent (file: `frontend/src/VoterView.jsx:181-186`):

```javascript
await castVote(baseUrl, {
  candidate_id: candidateId.trim(),
  election_id: electionId.trim(),
  nonce,
  signature: `0x${unblindedSignature}`,
});
```

Pydantic model for validation (file: `main.py:39-43`):

```python
class VoteIn(BaseModel):
    candidate_id: str = Field(min_length=1)
    election_id: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    signature: str = Field(min_length=1)
```

### Step 10: Node Verifies and Records

The blockchain node verifies the RSA signature against the admin public key,
checks the nonce hasn't been used, then adds the vote to the mempool.

File: `main.py:681-688`

```python
def cast_vote(vote: VoteIn):
    try:
        index = blockchain.add_vote(
            vote.candidate_id,
            vote.election_id,
            vote.nonce,
            vote.signature,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    persist_state()
    return {
        "message": f"Anonymous vote will be added to block {index}",
        "pending_votes": len(blockchain.pending_transactions),
    }
```

File: `blockchain.py:47-97`

```python
def add_vote(self, candidate_id, election_id, nonce, signature):
    # ...validation...

    if self._is_nonce_used(nonce):
        raise ValueError("vote nonce has already been used")

    if not verify_rsa_blind_vote_signature(
        candidate_id, election_id, nonce, signature,
        self.admin_n, self.admin_e,
    ):
        raise ValueError("invalid vote signature")

    if self._has_nonce(nonce, self.pending_transactions):
        raise ValueError("vote with this nonce is already pending")
    if self.has_voted_nonce(nonce):
        raise ValueError("vote with this nonce already exists in the chain")

    self.pending_transactions.append({
        "candidate_id": candidate_id,
        "election_id": election_id,
        "nonce": nonce,
        "signature": signature,
        "timestamp": time(),
    })
    return self.latest_block.index + 1
```

File: `crypto_utils.py:28-42` — the RSA signature verification:

```python
def verify_rsa_blind_vote_signature(
    candidate_id: str,
    election_id: str,
    nonce: str,
    signature_hex: str,
    n: int,
    e: int,
) -> bool:
    try:
        signature = int(signature_hex, 16)
        target_hash = hash_vote_to_modulus(candidate_id, election_id, nonce, n)
        recovered_hash = pow(signature, e, n)
        return recovered_hash == target_hash
    except Exception:
        return False
```

The canonical hash function (file: `crypto_utils.py:7-25`):

```python
def canonical_vote_message(candidate_id, election_id, nonce):
    payload = {
        "candidate_id": candidate_id.strip(),
        "election_id": election_id.strip(),
        "nonce": nonce.strip(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hash_vote_to_modulus(candidate_id, election_id, nonce, modulus):
    message = canonical_vote_message(candidate_id, election_id, nonce)
    digest = hashlib.sha256(message).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1
```

### Step 11: Mining and On-Chain Storage

When a block is mined, the vote transactions are stored in the chain.
There is no `voter_id` or `voter_public_key` field — the on-chain record only
contains the vote data needed for verification and tallying.

File: `blockchain.py:88-96`

```python
self.pending_transactions.append({
    "candidate_id": candidate_id,
    "election_id": election_id,
    "nonce": nonce,
    "signature": signature,
    "timestamp": time(),
})
```

Example mined block data:

```json
{
    "index": 2,
    "transactions": [
        {
            "candidate_id": "bibhab",
            "election_id": "student-union-2026",
            "nonce": "7ddb708d411b15fd1ccea17d27dba387",
            "signature": "0x4a6edd6a60e7167ffa1865a7c366a647...",
            "timestamp": 1783302337.485604
        }
    ]
}
```

## Privacy Guarantees

| Property | Mechanism |
|---|---|
| **No voter ID on-chain** | Vote records contain only `{candidate_id, election_id, nonce, signature, timestamp}` |
| **Admin can't see vote content** | Blind signature operates on `m' = m * r^e mod n` — the admin signs a random-looking number |
| **No cryptographic linking** | The blinding factor `r` is chosen by the voter and never transmitted; no one can link the blinded value to the unblinded signature |
| **Replay prevention** | Each vote includes a unique nonce; the blockchain rejects duplicate nonces |

## Limitations

| Limitation | Explanation |
|---|---|
| **Per-person double voting** | The system enforces one-vote-per-invitation-code but cannot prevent one person from collecting multiple codes. Invitation code distribution must be trusted. |
| **Vote selling / coercion** | Because the voter holds both the blinding factor `r` and the final signature, they can prove how they voted (receipt-freeness is not guaranteed). |
| **Timing correlation** | If only one code is active and a vote arrives immediately after blind signing, an observer may guess the link (though there is no cryptographic evidence). |
