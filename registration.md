# Blind-Signature Anonymous Voting (RSA) in This Project

This document describes the implemented voting flow using RSA blind signatures.

## Goal

We want the voter to cast an anonymous ballot. The voter blinds their vote before asking the admin to sign it. The admin signs without seeing the vote contents. The voter later submits the unblinded vote with a valid admin signature — no voter identity is attached.

- Admin has RSA key pair: public `(e, n)`, private `(d, n)`.
- Voter creates a vote message `M = {candidate_id, election_id, nonce}` and blinds `H(M)` before asking admin to sign.
- Admin signs only the blinded value.
- Voter unblinds and obtains a valid RSA signature on `H(M)`.
- Voter submits `(candidate_id, election_id, nonce, signature)` to the blockchain. No voter_id or public key is included.

## Key Math

Let:

- `H` be SHA-256 interpreted as an integer
- `M` be the canonical JSON vote message: `{"candidate_id":"...","election_id":"...","nonce":"..."}`
- `r` be random blinding factor with `gcd(r, n) = 1`

### 1) Hash the vote message

$$
V = H(M) \bmod n
$$

(If `V = 0`, we map it to `1` to stay in `(0, n)`.)

### 2) Blind the hash (voter side)

$$
B = V \cdot r^e \bmod n
$$

`B` is sent to admin. Admin cannot recover `V` without knowing `r`.

### 3) Blind-sign (admin side)

$$
B' = B^d \bmod n
$$

Using RSA:

$$
B' = (V \cdot r^e)^d \equiv V^d \cdot r \pmod n
$$

Admin returns `B'`.

### 4) Unblind (voter side)

Compute inverse `r^{-1} mod n`, then:

$$
\sigma = B' \cdot r^{-1} \bmod n
$$

So:

$$
\sigma \equiv V^d \pmod n
$$

This is a valid RSA signature on `V = H(M)`.

### 5) Verify (server side at vote submission)

Server checks:

$$
\sigma^e \bmod n \stackrel{?}{=} H(M) \bmod n
$$

If true, the blind-signed vote is valid.

## Anti-replay

Each vote message contains a random `nonce` (16 bytes hex). The blockchain tracks which nonces have been used and rejects duplicates. Since each voter gets exactly one invitation code, each voter can submit at most one vote.

## Protocol Flow

### Admin-side invitation code issuance

Admin issues a one-time invitation code:

- `POST /voters/codes/issue`

Returns a code that authorizes one blind-sign request.

### Blind-sign public key discovery

Voter fetches RSA blind-sign public key:

- `GET /voters/blind/public-key`

Returns `n`, `e` (decimal), plus metadata.

### Blind-sign request

Voter computes `B = V \cdot r^e mod n` and sends:

- `POST /voters/blind/sign`

Payload:

```json
{
  "registration_code": "one-time-code",
  "election_id": "student-union-2026",
  "blinded_hash": "0x..."
}
```

Server behavior:

1. Validates and consumes invitation code.
2. Signs blinded hash with RSA private exponent `d`.
3. Returns `blind_signature` (hex string).

### Client unblinding and local verification

Client computes:

$$
\sigma = B' \cdot r^{-1} \bmod n
$$

Then local verification:

$$
\sigma^e \bmod n = H(M) \bmod n
$$

### Anonymous vote submission

Voter submits the unblinded vote:

- `POST /votes`

Payload:

```json
{
  "candidate_id": "Alice",
  "election_id": "student-union-2026",
  "nonce": "a1b2c3d4e5f6...",
  "signature": "0x..."
}
```

Server checks:

1. All fields are non-empty.
2. `nonce` is not already used (anti-replay).
3. RSA verification passes (`sig^e mod n == H({candidate_id, election_id, nonce}) mod n`).
4. Vote is appended to mempool.

### Mining and chain validation

When blocks are mined, each vote in the block is re-validated:

1. RSA signature is verified against the canonical vote message.
2. Nonce uniqueness is enforced within the block and across the chain.

## Where It Is Implemented

- Backend RSA blind-sign and endpoints: `main.py`
- Anonymous vote state persistence: `blockchain.py`
- Frontend blind-sign math and voting flow: `frontend/src/wallet.js`, `frontend/src/VoterView.jsx`, `frontend/src/api.js`
- CLI voting tool: `cast_blind_vote.py`

## Security Notes

- If `ADMIN_RSA_PRIVATE_KEY_PEM` is not provided, server generates an ephemeral RSA key at startup. For stable production behavior, set `ADMIN_RSA_PRIVATE_KEY_PEM`.
- Blind signatures hide `H(M)` at signing time, but metadata (timing, source IP) can still correlate requests at application level.
- **Vote selling**: The voter possesses `(M, signature)` and can prove their vote to a third party. This is inherent to blind-signature voting.
- **No coercion resistance**: Same reason — someone can force a voter to reveal their vote receipt.
- This is a practical demo implementation; production hardening would include stronger privacy transport, audit controls, and optional ZK-style eligibility proofs.

## Quick End-to-End Example

1. Admin issues invitation code:
   - `POST /voters/codes/issue`
2. Voter fetches RSA public params:
   - `GET /voters/blind/public-key`
3. Voter creates vote message, computes blinded hash, and requests blind signature:
   - `POST /voters/blind/sign`
4. Voter unblinds signature locally.
5. Voter submits anonymous vote:
   - `POST /votes`
6. Admin mines the pending block:
   - `GET /mine`

Result: votes are anonymous on-chain. No voter identity is stored.
