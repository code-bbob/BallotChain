# Run Everything Script

Quick-start your blockchain voting system with a single command!

## 🚀 Quick Start

### Linux / macOS
```bash
./run_all.sh
```

### Windows / All Platforms
```bash
python run_all.py
```

## What It Does

The script automatically:
1. ✓ Checks system requirements (Python 3, Node.js)
2. ✓ Creates Python virtual environment (if needed)
3. ✓ Installs all dependencies
4. ✓ Starts blockchain node(s)
5. ✓ Starts frontend dev server
6. ✓ Opens browser automatically

### Single Node Flow
```
Python venv
    ↓
Install dependencies
    ↓
Start 1 backend node (port 8001)
    ↓
Start frontend (port 5173)
    ↓
Open browser
```

### Multi-Node Local Flow
```
Python venv
    ↓
Install dependencies
    ↓
Start 3 nodes (8001, 8002, 8003) with peer connections
    ↓
Start frontend (port 5173)
    ↓
Open browser
```

### Docker Multi-Node Flow
```
Docker installed?
    ↓
docker-compose up -d (3 containers)
    ↓
Start frontend (port 5173)
    ↓
Open browser
```

## Usage

### Three Run Modes

#### 1. **Single Node** (Quick test)
```bash
python run_all.py
# or
python run_all.py --mode single
```
✓ Simple single-node setup  
✓ Fastest to start  
✓ Good for demos  
✓ **Default mode**

#### 2. **Multi-Node Local** (Test consensus)
```bash
python run_all.py --mode multi
```
✓ Runs 3 nodes locally  
✓ Nodes talk to each other  
✓ Test blockchain consensus  
✓ Takes ~5-10 seconds to start

#### 3. **Docker Multi-Node** (Production-like)
```bash
python run_all.py --mode docker
```
✓ Uses docker-compose  
✓ Containerized nodes  
✓ Fully isolated  
✓ Requires Docker installed

### With Custom Settings
```bash
# Custom difficulty and mode
python run_all.py --mode multi --difficulty 4

# Single node with custom port
python run_all.py --mode single --port 9000

# Docker without browser
python run_all.py --mode docker --no-browser
```

### All Options
```
--mode {single|docker|multi}  Run mode (default: single)
--difficulty N               Mining difficulty (default: 3)
--port PORT                 Backend port for single mode (default: 8001)
--no-browser                Don't automatically open browser
--peer-nodes NODES          Comma-separated peer nodes
```

## First Time Setup

On first run, the script will:
1. Create a Python virtual environment (may take 1-2 minutes)
2. Install ~20 Python packages
3. Install npm dependencies
4. Compile frontend assets

**Subsequent runs are much faster!**

## Accessing the System

Once running, open your browser to:
- **Frontend UI**: http://127.0.0.1:5173
- **API Swagger Docs**: http://127.0.0.1:8001/docs

## Immediate Things to Try

### Single Node Mode
Perfect for quick testing of the voting system:
1. Click **🗳️ Voter Console**
2. Click **"Generate New Wallet"**
3. Click **"Register This Wallet"**
4. Enter candidate name (e.g., "Alice") and election ID
5. Click **"Submit Vote"**
6. Go to **⚙️ Admin Console** → **"Mine Pending Votes"**
7. View results!

### Multi-Node Mode
Test blockchain consensus:
1. Follow steps 1-5 above (register and vote on Node 1)
2. In Admin Console → Change **Node URL** to `http://127.0.0.1:8001`
3. Click **"Mine Pending Votes"** (mines on Node 1)
4. Change **Node URL** to `http://127.0.0.1:8002`
5. **Verify**: You should see the same block! (automatic sync)
6. Change to `http://127.0.0.1:8003` → Block is there too!

### Docker Mode
Same as multi-node but fully containerized. Perfect for production testing.

## Examples by Scenario

**Scenario 1: Just want to test the voting UI**
```bash
python run_all.py
# Uses single node, fastest startup
```

**Scenario 2: Need to demo consensus/multi-node**
```bash
python run_all.py --mode multi
# 3 nodes talking to each other
```

**Scenario 3: Production-like setup with Docker**
```bash
python run_all.py --mode docker
# Requires: Docker and Docker Compose installed
```

**Scenario 4: High difficulty mining (slower but more realistic)**
```bash
python run_all.py --difficulty 5
# Default is difficulty 3 (faster)
```

**Scenario 5: Run without opening browser**
```bash
python run_all.py --no-browser
# Useful if running on remote server
```

## Stopping the System

Press **Ctrl+C** in the terminal. The script will:
- Stop the backend server
- Stop the frontend server
- Clean up gracefully

## Troubleshooting

### "Port 8001 already in use"
```bash
# Use a different port (single mode only)
python run_all.py --mode single --port 9000
```

### "Docker not found" (Docker mode)
```bash
# Install Docker from: https://www.docker.com/products/docker-desktop
# Then try:
python run_all.py --mode docker
```

### "npm not found"
Install Node.js from https://nodejs.org/

### "Python not found"
Install Python 3.9+ from https://www.python.org/

### Backend not responding
- First run needs time to install dependencies (2-3 minutes)
- Make sure all services started (check for error messages)
- Wait 5 seconds for backend to fully initialize
- Try: `python run_all.py --mode single` (simplest mode)

### Frontend shows "Cannot connect to backend"
- Both services need to be running (check no errors printed)
- Wait 5 seconds after startup for backend ready
- Try refreshing browser (F5)
- Check backend is on http://127.0.0.1:8001/docs

### Multi-node nodes not syncing
- Make sure all 3 nodes started (check terminal output)
- Wait 3 seconds after startup
- Try mining a block - it should broadcast to peers
- Check logs for connection errors

### Docker containers not starting
```bash
# Check if containers are running:
docker-compose ps

# View logs:
docker-compose logs -f

# Clean and restart:
docker-compose down
python run_all.py --mode docker
```

### "Address already in use" in Docker
```bash
# Stop all containers:
docker-compose down

# Or remove specific port binding (edit docker-compose.yml)
```

## What Each Script Does

### Bash Script (`run_all.sh`)
- **Platform**: Linux, macOS
- **Benefits**: Native shell integration, colored output
- **Run**: `./run_all.sh`

### Python Script (`run_all.py`)
- **Platform**: Linux, macOS, Windows
- **Benefits**: Cross-platform, more flexible options
- **Run**: `python run_all.py`

Both do the same thing - choose whichever you prefer!

## Manual Alternative (if script doesn't work)

### Single Node
**Terminal 1 - Backend:**
```bash
source venv/bin/activate
DIFFICULTY=3 uvicorn main:app --host 127.0.0.1 --port 8001
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Then open http://127.0.0.1:5173

### Multi-Node (3 terminals for 3 nodes)
**Terminal 1 - Node 1:**
```bash
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=data/node1.json PEER_NODES="http://127.0.0.1:8002,http://127.0.0.1:8003" uvicorn main:app --host 127.0.0.1 --port 8001
```

**Terminal 2 - Node 2:**
```bash
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=data/node2.json PEER_NODES="http://127.0.0.1:8001,http://127.0.0.1:8003" uvicorn main:app --host 127.0.0.1 --port 8002
```

**Terminal 3 - Node 3:**
```bash
source venv/bin/activate
DIFFICULTY=3 BLOCKCHAIN_DATA=data/node3.json PEER_NODES="http://127.0.0.1:8001,http://127.0.0.1:8002" uvicorn main:app --host 127.0.0.1 --port 8003
```

**Terminal 4 - Frontend:**
```bash
cd frontend
npm run dev
```

### Docker Multi-Node
```bash
docker-compose up
```
Then open http://127.0.0.1:5173 (you need to start frontend separately)

## More Options

### Run the Demo Script
Automatically tests the entire system:
```bash
source venv/bin/activate
python demo.py
```
This creates wallets, casts votes, mines blocks, and shows results.

### Compare All Run Modes

| Feature | Single | Multi-Local | Docker |
|---------|--------|-------------|--------|
| Startup Time | Fastest | Fast | Medium |
| Node Count | 1 | 3 | 3 |
| Consensus Test | ❌ | ✅ | ✅ |
| Docker Required | ❌ | ❌ | ✅ |
| Resource Usage | Low | Medium | Medium |
| Production-Like | ❌ | ⚠️ | ✅ |
| Best For | Testing UI | Learning | Deployment |

## System Architecture

```
┌─────────────────────┐
│   Browser (UI)      │
│  http://localhost   │
│       :5173         │
└──────────┬──────────┘
           │
     React Frontend
           │
    ┌──────┴──────┐
    │             │
    v             v
┌─────────┐  ┌──────────┐
│ Backend │  │ Blockchain
│ API     │  │ Mining
│ Port:   │  │ (PoW)
│ 8001    │  │
└─────────┘  └──────────┘
    │
    └─ Ed25519 Signatures
    └─ Canonical Serialization
    └─ One-Vote Enforcement
```

## Key Technologies

- **Backend**: Python, FastAPI, Uvicorn
- **Frontend**: React, Vite, TweetNaCl (Ed25519)
- **Cryptography**: Ed25519 signatures, SHA-256 hashing
- **Consensus**: Proof-of-Work (adjustable difficulty)

## Questions?

Check these files for more details:
- `QUICKSTART.md` - Step-by-step guide
- `workflow_description.md` - How the voting system works
- `IMPLEMENTATION.md` - Technical details
- `README.md` - Project overview
