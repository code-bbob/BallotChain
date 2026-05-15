# TrueVote Authentication & Authorization

## Authentication Model

TrueVote implements a **role-based access control (RBAC)** system with two user types:

### 1. **Regular Voters**
- **Identity**: Ed25519 public/private keypair (local wallet)
- **Registration**: One-time registration with `voter_id` + `public_key` on the node
- **Operations**:
  - ✓ View election results (`GET /elections/{id}/results`)
  - ✓ Cast signed votes (`POST /votes`)
  - ✓ Register wallet (`POST /voters/register` if open or with admin token)
- **Authentication**: Vote signatures (Ed25519) prove voter identity

### 2. **Administrators**
- **Identity**: Admin token (environment variable `ADMIN_TOKEN`)
- **Operations**:
  - ✓ Issue one-time registration codes (`POST /voters/codes/issue`)
   - ✓ Manage elections and node configuration
- **Authentication**: `X-Admin-Token` HTTP header

## Backend Authentication Flow

### Voter Registration
```
POST /voters/register
├─ If registration_code is provided
│  ├─ Hash code and look it up in the node database
│  ├─ Ensure the code matches the wallet/voter record
│  ├─ Consume the code by deleting it from storage
│  └─ Register the wallet public key
├─ Else if OPEN_VOTER_REGISTRATION=true
│  └─ Allow open registration (testing mode)
└─ Else
  └─ Reject request: registration_code is required
```

### Registration Code Issuance
```
POST /voters/codes/issue
├─ Check X-Admin-Token header when ADMIN_TOKEN is configured
├─ Issue a random one-time code for a voter_id
├─ Store only a hashed copy in the database with expiry
└─ Return the plaintext code once for delivery to the voter
```

### Mining and Broadcasting (Peer Actions)
```
GET /mine
├─ Any reachable node may mine its pending votes
├─ Proof-of-work and block validation still apply
└─ If a mined block is valid, it is broadcast to peers

POST /broadcast
├─ Any node may broadcast its latest block
├─ Peers validate the block before accepting it
└─ Consensus decides whether the chain advances
```

### Vote Submission (Anyone, must be registered + valid signature)
```
POST /votes
├─ Check voter is registered
├─ Verify Ed25519 signature
├─ Check (voter_id, election_id) not already voted
└─ If all pass, add vote to pending queue
```

## Frontend Authentication

### Admin Console
1. **Governance/configuration UI** for node and election administration
2. **Issue one-time registration codes** for verified voters
3. **Manage node settings** and monitor network state

### Voter Console
1. **Generate local wallet** (Ed25519 keypair, stored in browser)
2. **Receive a one-time code from the admin**
3. **Register wallet** by submitting the code plus the wallet public key
4. **Sign & cast votes** (Ed25519 signature proves identity)
5. **View results** (public, no auth needed)

## Environment Variables

### Enable/Disable Features
```bash
# Optional: Admin token for governance/configuration actions
ADMIN_TOKEN="secret-admin-key"

# Optional: Allow voters to register without admin token
OPEN_VOTER_REGISTRATION=true

# CORS settings
CORS_ALLOW_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

### Example Deployment Modes

**Mode 1: Open Registration (Testing)**
```bash
DIFFICULTY=3 OPEN_VOTER_REGISTRATION=true uvicorn main:app --host 127.0.0.1 --port 8001
```
- Voters self-register without admin approval
- Any node can mine and broadcast
- Good for demos and testing

**Mode 2: Controlled Registration (Production)**
```bash
DIFFICULTY=3 ADMIN_TOKEN="election-admin-2026" OPEN_VOTER_REGISTRATION=false uvicorn main:app --host 127.0.0.1 --port 8001
```
- Admin approves voter registrations
- Admin issues one-time registration codes
- Mining is open to participating nodes
- More secure for real elections

**Mode 3: Public Voting, Admin Mining**
```bash
DIFFICULTY=3 ADMIN_TOKEN="governance-key-2026" OPEN_VOTER_REGISTRATION=true uvicorn main:app --host 127.0.0.1 --port 8001
```
- Voters register freely
- Admin controls governance/configuration only
- Common production setup for a permissioned network

## Security Considerations

### Voter Authentication
- **Mechanism**: Ed25519 digital signatures
- **Proof**: Vote message signed with voter's private key
- **Verification**: Server re-verifies signature using registered public key
- **Non-repudiation**: Voter cannot deny having cast a specific vote

### Vote Integrity
- **Tampering prevention**: Canonical serialization + signature
- **Replay attack prevention**: Election ID included in signature
- **Double-voting prevention**: (voter_id, election_id) pair registry
- **Immutability**: Votes stored in PoW-protected blocks

### Admin Authentication
- **Token-based**: Simple shared secret (environment variable)
- **Improvements for production**:
  - Use OAuth2 / OIDC
  - JWT tokens with expiration
  - Multi-factor authentication (MFA)
  - Role-based access (multiple admin roles)

### What This System Does NOT Protect Against
- ❌ Private key compromise (if voter's key is leaked, attacker can vote as them)
- ❌ Voter coercion (voter could be forced to reveal their key)
- ❌ End-to-end privacy (votes are visible on-chain once mined)
- ❌ Admin token compromise (if ADMIN_TOKEN is leaked, attacker can alter governance/configuration)
- ❌ Registration code interception before first use (the code must be delivered securely)

### Recommendations for Real Elections
1. **Hardware wallets** for voter keys (security device stores key)
2. **Vote encryption** until election ends (zero-knowledge proofs)
3. **Distributed admin** (multiple signers required for governance changes)
4. **Voter privacy** (ring signatures or mixing protocols)
5. **Audit trail** (immutable logs of all operations)

## Testing Authentication

### Test 1: Voter Self-Registration
```bash
# Enable open registration
OPEN_VOTER_REGISTRATION=true DIFFICULTY=3 uvicorn main:app --port 8001

# Frontend: Voter Console → Create Wallet → Register
# Should succeed without admin token
```

### Test 2: Protected Mining
```bash
# Mining is open to any node
DIFFICULTY=3 uvicorn main:app --port 8001

# Frontend: Go to Governance Console and mine
# Should succeed without admin token
```

### Test 3: Vote Signature Verification
```python
# CLI test
python3 -c "
from crypto_utils import sign_vote, verify_vote_signature
voter_id = 'V001'
candidate_id = 'Alice'
election_id = 'election-2026'
private_key = '...'
public_key = '...'

sig = sign_vote(voter_id, candidate_id, election_id, private_key)
is_valid = verify_vote_signature(voter_id, candidate_id, election_id, public_key, sig)
print(f'Signature valid: {is_valid}')
"
```

## API Reference with Authentication

| Endpoint | Method | Admin Token | Public | Purpose |
|----------|--------|-------------|--------|---------|
| `/voters/register` | POST | Conditional* | Yes** | Register voter |
| `/voters` | GET | No | Yes | List voters |
| `/votes` | POST | No | Yes | Cast vote |
| `/elections/{id}/results` | GET | No | Yes | Get results |
| `/mine` | GET | No | Yes | Mine block |
| `/broadcast` | POST | No | Yes | Broadcast block |
| `/chain` | GET | No | Yes | Get blockchain |
| `/blocks/receive` | POST | No | Yes | Receive block (P2P) |
| `/chains/sync` | POST | No | Yes | Sync chain (P2P) |

*Conditional: Required if `OPEN_VOTER_REGISTRATION=false`
**Public: Yes if `OPEN_VOTER_REGISTRATION=true`, otherwise requires token

## Summary

- **Voters**: Identified by Ed25519 signatures, no shared password
- **Admins**: Identified by admin token (single shared secret)
- **Votes**: Cryptographically signed, cannot be forged or denied
- **Operations**: Governance actions may use admin token, while mining/broadcasting are peer actions
- **Production Ready**: Basic security in place, advanced features (OIDC, encryption) can be added
