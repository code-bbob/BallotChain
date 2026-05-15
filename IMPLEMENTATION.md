# TrueVote: Complete Implementation Guide

## Project Status ✓

The full TrueVote blockchain voting system is now implemented with:

### Backend (Python/FastAPI)
- ✓ Ed25519 digital signature verification
- ✓ Canonical vote serialization
- ✓ One-vote-per-election enforcement with persistent registry
- ✓ Proof-of-Work (PoW) mining algorithm
- ✓ Block validation with signature re-verification
- ✓ Longest-chain consensus
- ✓ JSON-based persistence and recovery
- ✓ Peer-to-peer block propagation
- ✓ Admin and voter registration endpoints

### Frontend (React)
- ✓ **Admin Console**: Mining, broadcasting, election management
- ✓ **Voter Console**: Wallet management, voter registration, vote casting
- ✓ Mode selector for switching between Admin and Voter roles
- ✓ Real-time blockchain state monitoring
- ✓ Election results visualization
- ✓ Registered voter registry display

## Running the System

### 1. Start Backend Nodes

**Terminal 1 - Node 1:**
```bash
cd /home/bibhab/finalproject
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json uvicorn main:app --host 127.0.0.1 --port 8001
```

**Terminal 2 - Node 2 (optional for consensus testing):**
```bash
cd /home/bibhab/finalproject
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json uvicorn main:app --host 127.0.0.1 --port 8002
```

**Terminal 3 - Node 3 (optional):**
```bash
cd /home/bibhab/finalproject
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=node3.json uvicorn main:app --host 127.0.0.1 --port 8003
```

### 2. Start Frontend Dev Server

```bash
cd /home/bibhab/finalproject/frontend
npm install  # if needed
npm run dev
```

The frontend will start at `http://localhost:5173`

### 3. Use the Application

**Landing Page:**
- Choose between **Admin Console** or **Voter Console**

**Admin Console:**
1. Configure node URL (default: `http://127.0.0.1:8001`)
2. Mine pending votes into blocks
3. Broadcast blocks to network peers
4. View blockchain state and results
5. Monitor registered voters

**Voter Console:**
1. Configure node URL
2. Create a local wallet (Ed25519 keypair)
3. Register wallet on the node (once)
4. Cast signed votes in any election
5. View election results

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (5173)                     │
│  ┌──────────────┐              ┌──────────────┐             │
│  │ Admin View   │              │ Voter View   │             │
│  │ - Mine       │              │ - Register   │             │
│  │ - Broadcast  │              │ - Cast Vote  │             │
│  │ - Results    │              │ - Monitor    │             │
│  └──────────────┘              └──────────────┘             │
└────────────┬────────────────────────────┬────────────────────┘
             │ HTTP REST API              │
       ┌─────▼────────────────────────────▼─────────┐
       │  FastAPI Backend (8001/8002/8003)           │
       │                                             │
       │  ┌───────────────────────────────────────┐  │
       │  │ Cryptography Layer                    │  │
       │  │ - Ed25519 signing/verification       │  │
       │  │ - Canonical vote serialization       │  │
       │  │ - Base64 encoding                    │  │
       │  └───────────────────────────────────────┘  │
       │                                             │
       │  ┌───────────────────────────────────────┐  │
       │  │ Blockchain Layer                      │  │
       │  │ - PoW mining (SHA256 nonce search)   │  │
       │  │ - Block validation                   │  │
       │  │ - Chain management                   │  │
       │  │ - Consensus (longest-chain)          │  │
       │  └───────────────────────────────────────┘  │
       │                                             │
       │  ┌───────────────────────────────────────┐  │
       │  │ Persistence Layer                     │  │
       │  │ - JSON file storage                  │  │
       │  │ - Voter registry                     │  │
       │  │ - Block chain                        │  │
       │  │ - Pending votes                      │  │
       │  └───────────────────────────────────────┘  │
       └─────────────────────────────────────────────┘
             │ P2P Communication
       ┌─────▼────────────────────────────────────────┐
       │ Peer Nodes (consensus network)               │
       │ /blocks/receive - block propagation          │
       │ /chains/sync - chain synchronization         │
       │ /nodes/resolve - consensus            │
       └──────────────────────────────────────────────┘
```

## API Endpoints

### Voter Management
- `POST /voters/register` - Register voter public key
- `GET /voters` - List registered voters

### Voting
- `POST /votes` - Cast a signed vote
- `GET /elections/{election_id}/results` - Get vote tallies

### Mining & Consensus
- `GET /mine` - Mine pending votes into a block
- `POST /broadcast` - Broadcast latest block to peers
- `GET /chain` - Get full blockchain state

### Peer Communication
- `POST /blocks/receive` - Receive block from peer
- `POST /chains/sync` - Synchronize full chain
- `POST /nodes/register` - Register peer node
- `GET /nodes/resolve` - Resolve consensus

## Algorithms Implemented

### 1. Vote Authentication (Ed25519)
- Voter creates vote locally
- Serializes vote in canonical form (sorted JSON)
- Signs with Ed25519 private key
- Server verifies using public key

### 2. Duplicate Prevention
- Node maintains (voter_id, election_id) pair registry
- Before accepting vote, checks registry
- Rejects if pair already exists
- Persisted in JSON for crash recovery

### 3. Proof-of-Work Mining
- Collects pending verified votes
- Searches for nonce where SHA256(header || nonce) satisfies difficulty
- Difficulty = N leading zero bits (configurable)
- Block immutability through computational proof

### 4. Block Validation
- Verifies proof-of-work condition
- Re-verifies all vote signatures
- Checks no double-votes in block
- Validates chain linkage

### 5. Consensus
- Longest-valid-chain rule
- All nodes converge on same canonical state
- Automatic peer synchronization

### 6. Persistence
- JSON serialization of blockchain, voter registry, pending votes
- Atomic saves on state changes
- Recovery validation on startup
- Survives node restarts

## Testing Workflow

### Single-Node Test
1. Start Node 1
2. In Voter Console: Create wallet → Register → Cast vote
3. In Admin Console: Mine block → View results
4. Verify vote appears in block and election results

### Multi-Node Test
1. Start 3 nodes
2. Register nodes with each other (POST /nodes/register)
3. Cast votes on Node 1
4. Mine block on Node 1
5. Node 1 broadcasts to Nodes 2 & 3
6. Verify all 3 nodes have same chain state
7. View results on any node

## Configuration

### Environment Variables
```bash
DIFFICULTY=3          # PoW difficulty (leading zero bits)
BLOCKCHAIN_DATA=...   # JSON file path for persistence
PEER_NODES=...        # Comma-separated peer URLs for bootstrap
ADMIN_TOKEN=...       # Optional admin auth token
CORS_ALLOW_ORIGINS=... # CORS whitelist
OPEN_VOTER_REGISTRATION=true  # Allow unrestricted registration
```

### Example Multi-Node Setup
```bash
# Terminal 1
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json PEER_NODES="http://127.0.0.1:8002,http://127.0.0.1:8003" SELF_NODE_URL="http://127.0.0.1:8001" uvicorn main:app --host 127.0.0.1 --port 8001

# Terminal 2
DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json PEER_NODES="http://127.0.0.1:8001,http://127.0.0.1:8003" SELF_NODE_URL="http://127.0.0.1:8002" uvicorn main:app --host 127.0.0.1 --port 8002

# Terminal 3
DIFFICULTY=3 BLOCKCHAIN_DATA=node3.json PEER_NODES="http://127.0.0.1:8001,http://127.0.0.1:8002" SELF_NODE_URL="http://127.0.0.1:8003" uvicorn main:app --host 127.0.0.1 --port 8003
```

## Files Overview

### Core Backend
- `main.py` - FastAPI application with REST endpoints
- `blockchain.py` - Blockchain logic, mining, validation
- `block.py` - Block model and hashing
- `crypto_utils.py` - Ed25519 signing/verification, canonicalization
- `storage.py` - JSON persistence layer

### Core Frontend
- `frontend/src/App.jsx` - Mode selector (Admin/Voter)
- `frontend/src/AdminView.jsx` - Election management console
- `frontend/src/VoterView.jsx` - Voting console
- `frontend/src/api.js` - HTTP client library
- `frontend/src/wallet.js` - Local wallet management
- `frontend/src/styles.css` - UI styling

### Documentation
- `FinalReport Truevote.docx` - Final project report (cleaned, algorithms added)
- `update.md` - Technical specification document
- `workflow_description.md` - End-to-end voting flow
- `algorithms_and_workflows.md` - Algorithm documentation
- `README.md` - Quick start guide
- `IMPLEMENTATION.md` - This file

## Summary

**TrueVote** is a fully functional blockchain-based voting system featuring:
- Cryptographically signed votes (Ed25519)
- Immutable vote records via Proof-of-Work
- Distributed consensus across peer nodes
- Duplicate vote prevention
- Persistent state with crash recovery
- Clean separation of Admin and Voter roles
- Complete web UI for both roles

All algorithms described in the final report have been implemented in working code.
