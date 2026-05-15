# Quick Start Guide

## Prerequisites
- Python 3.9+
- Node.js/npm
- Virtual environment created: `python -m venv venv`

## One-Minute Setup

### 1. Install Backend Dependencies
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies  
```bash
cd frontend
npm install
cd ..
```

### 3. Start Backend (One Terminal)
```bash
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=blockchain_data.json uvicorn main:app --host 127.0.0.1 --port 8001
```

### 4. Start Frontend (Another Terminal)
```bash
cd frontend
npm run dev
```

### 5. Open Browser
Navigate to: **http://localhost:5173**

## Using the System

### Admin Console
1. Click **⚙️ Admin Console**
2. Mine pending votes: Click **"Mine Pending Votes"**
3. View results: Enter election ID, click **"Load Results"**
4. Broadcast: Click **"Broadcast to Network"** (for multi-node setup)

### Voter Console
1. Click **🗳️ Voter Console**
2. **Create Wallet**: Click **"Generate New Wallet"** (generates Ed25519 keypair)
3. **Register**: Click **"Register This Wallet"** (one-time registration on node)
4. **Vote**: Enter candidate name + election ID, click **"Submit Vote"**
5. **Check Results**: Enter election ID, click **"View Results"**

## Demo Script
Run the automated demo to test all algorithms:
```bash
source venv/bin/activate
python demo.py
```

This script:
- Creates 3 voter wallets
- Registers them on the node
- Casts votes in multiple elections
- Mines a block with the votes
- Displays final vote tallies

## Multi-Node Testing

### Terminal 1 - Node 1
```bash
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json PEER_NODES="http://127.0.0.1:8002" uvicorn main:app --host 127.0.0.1 --port 8001
```

### Terminal 2 - Node 2
```bash
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json PEER_NODES="http://127.0.0.1:8001" uvicorn main:app --host 127.0.0.1 --port 8002
```

### Register Nodes
In frontend Admin Console:
1. Change base URL to `http://127.0.0.1:8001`
2. Mine a block on Node 1
3. Change base URL to `http://127.0.0.1:8002`
4. Verify Node 2 automatically synced the block

## Key Algorithms Demonstrated

✓ **Ed25519 Signatures**: Every vote is signed with voter's private key
✓ **Canonical Serialization**: Votes serialized deterministically (sorted JSON)
✓ **One-Vote Enforcement**: Can't vote twice in same election
✓ **Proof-of-Work**: Blocks require computational work (nonce search)
✓ **Block Validation**: All votes in block are re-verified
✓ **Consensus**: Longest-chain rule, automatic synchronization
✓ **Persistence**: JSON files survive restarts

## Troubleshooting

### "Cannot connect to backend"
- Make sure FastAPI is running on port 8001
- Check firewall allows localhost:8001

### "Address already in use"
- Change port: `--port 8002`
- Or kill existing process: `lsof -i :8001 | kill -9`

### Frontend build issues
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Wallet registration fails
- Make sure voter ID is unique
- Try enabling open registration: `OPEN_VOTER_REGISTRATION=true uvicorn main:app...`

## Architecture Overview

```
┌──────────────────────┐
│   React Frontend     │
│  (Admin/Voter UI)    │
└──────────┬───────────┘
           │ HTTP REST
           ▼
┌──────────────────────┐
│   FastAPI Backend    │
│ (Voting Logic)       │
└──────────┬───────────┘
           │
    ┌──────▼──────┬──────────┐
    ▼             ▼          ▼
  Block     Voter Registry  Pending
  Chain     (JSON)          Votes
```

## Performance Notes

- **Difficulty=3**: ~10-50ms mining time
- **Difficulty=4**: ~100-500ms mining time  
- **Difficulty=5**: ~1-10s mining time
- **Difficulty=6+**: > 10 seconds

Lower difficulty for faster testing, higher for more "work"

## Documentation

See `IMPLEMENTATION.md` for complete technical details, API endpoints, and architecture diagrams.
