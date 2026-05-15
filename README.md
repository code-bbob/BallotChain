# Blockchain Voting App (FastAPI)

An educational blockchain-based voting system for a final-year project.

## Features

- Block + Blockchain classes
- SHA-256 hashing over all block fields
- Proof-of-Work with configurable difficulty
- Pending vote pool
- One-vote-per-voter-per-election validation
- Ed25519 digital signature verification per vote
- Voter public-key registry (only registered keys can vote)
- FastAPI endpoints for casting votes and viewing results
- Peer-node registration + longest-chain consensus
- Automatic mined-block broadcast to registered peers
- Automatic peer bootstrap from environment (`PEER_NODES`)
- Local JSON persistence and startup recovery

## Project Structure

- `block.py` – Block model and hashing
- `blockchain.py` – Core blockchain logic, PoW, validation, vote tallying
- `storage.py` – JSON persistence helper
- `main.py` – FastAPI node API
- `crypto_utils.py` – Wallet/key/signature utilities
- `generate_wallet.py` – Helper script to generate voter wallet keys
- `register_voter.py` – Helper script to register voter public keys
- `add_vote.py` – Helper script for signed vote submission

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Install Frontend (React)

```bash
cd /home/bibhab/finalproject/frontend
npm install
```

## Run a Node

Difficulty is configurable using `DIFFICULTY`, storage file using `BLOCKCHAIN_DATA`.
Port is configurable via `uvicorn --port`.
Frontend origins allowed for browser requests are configurable via `CORS_ALLOW_ORIGINS` (comma-separated URLs).
Set `ADMIN_TOKEN` to protect voter registration endpoint (`/voters/register`).

```bash
cd /home/bibhab/finalproject
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json uvicorn main:app --host 127.0.0.1 --port 8001
```

Example with explicit CORS origins:

```bash
cd /home/bibhab/finalproject
CORS_ALLOW_ORIGINS="http://127.0.0.1:5173,http://localhost:5173" uvicorn main:app --host 127.0.0.1 --port 8001
```

Example with admin token enabled:

```bash
cd /home/bibhab/finalproject
ADMIN_TOKEN="change-me" uvicorn main:app --host 127.0.0.1 --port 8001
```

## Run Frontend Dashboard

Start backend first, then run frontend in another terminal:

```bash
cd /home/bibhab/finalproject/frontend
npm run dev
```

Open `http://127.0.0.1:5173` and keep Node URL as `http://127.0.0.1:8001` (or set your running node URL).

## Run Multiple Nodes (Example)

Open separate terminals:

```bash
cd /home/bibhab/finalproject
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json uvicorn main:app --host 127.0.0.1 --port 8001
```

```bash
cd /home/bibhab/finalproject
DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json uvicorn main:app --host 127.0.0.1 --port 8002
```

```bash
cd /home/bibhab/finalproject
DIFFICULTY=3 BLOCKCHAIN_DATA=node3.json uvicorn main:app --host 127.0.0.1 --port 8003
```

## Run Multiple Nodes with Docker (Recommended)

Build and start 3 nodes:

```bash
cd /home/bibhab/finalproject
docker compose up --build -d
```

Docker services are preconfigured with `PEER_NODES`, so each node auto-registers the other two on startup.
The Docker setup now uses `DIFFICULTY=5` so mining stays visible for longer during a demo.

Check containers:

```bash
docker compose ps
```

Follow logs for a specific node:

```bash
docker compose logs -f node1
docker compose logs -f node2
docker compose logs -f node3
```

You can also use the container names directly:

```bash
docker logs -f blockchain-node1
docker logs -f blockchain-node2
docker logs -f blockchain-node3
```

Check node chains:

```bash
curl "http://127.0.0.1:8001/chain"
curl "http://127.0.0.1:8002/chain"
curl "http://127.0.0.1:8003/chain"
```

Stop and remove containers:

```bash
docker compose down
```

Reset chain data volumes:

```bash
docker compose down -v
```

## Cast a Vote

Generate a wallet first (one per voter):

```bash
cd /home/bibhab/finalproject
python generate_wallet.py --out wallets/V001.json
```

Register the voter public key on the node:

```bash
cd /home/bibhab/finalproject
python register_voter.py V001 --wallet-file wallets/V001.json --node http://127.0.0.1:8001
```

If your node uses `ADMIN_TOKEN`, add `--admin-token`:

```bash
cd /home/bibhab/finalproject
python register_voter.py V001 --wallet-file wallets/V001.json --node http://127.0.0.1:8001 --admin-token change-me
```

Then submit a signed vote:

```bash
cd /home/bibhab/finalproject
python add_vote.py V001 Alice student-union-2026 --wallet-file wallets/V001.json --node http://127.0.0.1:8001
```

Or use raw `curl` with signed payload values:

```bash
curl -X POST "http://127.0.0.1:8001/votes" \
  -H "Content-Type: application/json" \
  -d '{"voter_id":"V001","candidate_id":"Alice","election_id":"student-union-2026","voter_public_key":"<base64-public-key>","signature":"<base64-signature>"}'
```

List registered voters:

```bash
curl "http://127.0.0.1:8001/voters"
```

The legacy `add_transaction.py` script now delegates to the same vote helper for backward compatibility.

## Mine a Vote Block

```bash
curl "http://127.0.0.1:8001/mine"
```

This now coordinates cluster mining: the node that receives the request starts mining locally and sends the same pending transactions to the other nodes at the same time.

Or use the helper script:

```bash
cd /home/bibhab/finalproject
python mine_and_broadcast.py --node http://127.0.0.1:8001
```

## View Election Results

```bash
curl "http://127.0.0.1:8001/elections/student-union-2026/results"
```

## Register Peers (Optional)

When using the provided Docker Compose file, this step is optional because peers auto-register at startup.

```bash
curl -X POST "http://127.0.0.1:8001/nodes/register" \
  -H "Content-Type: application/json" \
  -d '{"nodes":["http://127.0.0.1:8002","http://127.0.0.1:8003"]}'
```

Register peers on other nodes too (for two-way propagation):

```bash
curl -X POST "http://127.0.0.1:8002/nodes/register" \
  -H "Content-Type: application/json" \
  -d '{"nodes":["http://127.0.0.1:8001","http://127.0.0.1:8003"]}'

curl -X POST "http://127.0.0.1:8003/nodes/register" \
  -H "Content-Type: application/json" \
  -d '{"nodes":["http://127.0.0.1:8001","http://127.0.0.1:8002"]}'
```

When running with Docker Compose, register peers using service DNS names (`http://node1:8001`, `http://node2:8002`, `http://node3:8003`) so containers can reach each other internally.

After peer registration, mining on one node auto-broadcasts updates:
- tries `POST /blocks/receive` (single block push)
- falls back to `POST /chains/sync` (full-chain sync if peer is behind)

## Trigger Consensus

```bash
curl "http://127.0.0.1:8001/nodes/resolve"
```

## View Chain

```bash
curl "http://127.0.0.1:8001/chain"
```

## Notes

- This is an educational simulation, not production-grade e-voting security.
- Votes are now accepted only with valid Ed25519 signatures tied to the voter's public key.
- For a stronger final-year presentation, you can add voter authentication, election admin panels, and a results dashboard on top of this core.
