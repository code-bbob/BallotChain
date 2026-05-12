# Runserver — Start the project (backend, frontend, example flows)

This file tells you exactly how to get the whole project running locally for development and testing.

Prerequisites
- Linux/macOS (instructions use bash)
- Python 3.11+ (3.10 may work but 3.11+ recommended)
- Node.js 18+ and npm (or pnpm installed globally if you prefer)
- Optional: Docker & docker-compose if you want containerized nodes

Quick overview
1. Start the backend node(s) (FastAPI / uvicorn)
2. Start the frontend dev server (Vite)
3. Use CLI tools to generate wallet, register voter, cast votes, and mine

---

1) Backend — local development (virtualenv)

Open a terminal in the project root (`/home/bibhab/finalproject`):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Environment and default ports
- Backend default host/port shown here: `127.0.0.1:8001` (change `--port` to run more nodes)
- Frontend default dev server: `http://localhost:5173`

Basic single-node run (dev, open voter registration):

```bash
# recommended for frontend-first testing (allows auto-register from browser)
export OPEN_VOTER_REGISTRATION=true
export CORS_ALLOW_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
uvicorn main:app --host 127.0.0.1 --port 8001
```

If you want admin-protected registration, set an admin token instead:

```bash
export ADMIN_TOKEN="super-secret-token"
# do NOT set OPEN_VOTER_REGISTRATION
uvicorn main:app --host 127.0.0.1 --port 8001
```

Run multiple local nodes (example using different ports and data files):

```bash
# node 1
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json SELF_NODE_URL=http://127.0.0.1:8001 uvicorn main:app --host 127.0.0.1 --port 8001 &
# node 2
DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json SELF_NODE_URL=http://127.0.0.1:8002 PEER_NODES=http://127.0.0.1:8001 uvicorn main:app --host 127.0.0.1 --port 8002 &
# node 3
DIFFICULTY=3 BLOCKCHAIN_DATA=node3.json SELF_NODE_URL=http://127.0.0.1:8003 PEER_NODES="http://127.0.0.1:8001,http://127.0.0.1:8002" uvicorn main:app --host 127.0.0.1 --port 8003 &
```

After starting nodes, you can register peers via API if needed:

```bash
curl -X POST "http://127.0.0.1:8001/nodes/register" -H "Content-Type: application/json" -d '{"nodes":["http://127.0.0.1:8002"]}'
```

---

2) Frontend — dev server (Vite)

Install and run the frontend:

```bash
cd frontend
# with npm
npm install
npm run dev
# or with pnpm
pnpm install
pnpm dev
```

If you run the backend with default CORS origins above, the frontend requests should be allowed.

If backend rejects voter registration with a red banner, either:
- Start the backend with `OPEN_VOTER_REGISTRATION=true` (dev mode), or
- Configure the frontend to send the `X-Admin-Token` header (only if `ADMIN_TOKEN` is set on backend).

Example: start backend with CORS + open registration:

```bash
export OPEN_VOTER_REGISTRATION=true
export CORS_ALLOW_ORIGINS="http://localhost:5173"
uvicorn main:app --host 127.0.0.1 --port 8001
```

---

3) CLI tools — wallet generation, register, vote, mine

Generate a wallet (CLI):

```bash
# Creates wallet.json or prints keys depending on script implementation
python generate_wallet.py --output wallet.json
```

Register a voter (if admin token required):

```bash
# if backend has ADMIN_TOKEN set
python register_voter.py --wallet wallet.json --voter-id V001 --admin-token super-secret-token
# if OPEN_VOTER_REGISTRATION=true you can omit --admin-token
python register_voter.py --wallet wallet.json --voter-id V001
```

Submit a signed vote (CLI):

```bash
python add_vote.py --wallet wallet.json --voter-id V001 --candidate Alice --election student-union-2026
```

Mine pending votes:

```bash
# hit the mine endpoint or run the mine command
curl "http://127.0.0.1:8001/mine"
```

Check chain & results:

```bash
# view chain summary
curl "http://127.0.0.1:8001/chain"
# get election results
curl "http://127.0.0.1:8001/elections/student-union-2026/results"
```

---

4) Docker-compose (optional)

If you prefer containers, `docker-compose.yml` is present. Build and run:

```bash
docker compose up --build
# or the legacy command
# docker-compose up --build
```

Environment variables can be supplied via an `.env` file or in the compose file. Check the compose file for details.

---

5) Troubleshooting

CORS errors from browser:
- Ensure `CORS_ALLOW_ORIGINS` includes the frontend origin (e.g. `http://localhost:5173`).
- Restart the backend after changing `CORS_ALLOW_ORIGINS`.

Red "registration rejected" banner:
- Backend is protecting registration with `ADMIN_TOKEN`. For development either:
  - Start backend with `OPEN_VOTER_REGISTRATION=true`, or
  - Set `ADMIN_TOKEN` on backend and configure the frontend to send `X-Admin-Token` header (or register via CLI using `--admin-token`).

Backend not reachable from frontend:
- Confirm backend host/port match frontend API base URL in `frontend/src/api.js`.
- If running backend on a different host (VM/WSL), ensure host binding and CORS are configured.

Duplicate vote accepted unexpectedly:
- Confirm `BLOCKCHAIN_DATA` files are unique per node and that each node's `voter_registry` reflects accurate registration.
- Race conditions: avoid simultaneous double-posts; implement single-threaded processing or DB transactions if necessary.

Signature verification fails:
- Ensure client and server use the same canonicalization function. See `crypto_utils.canonical_vote_message()` for the canonical format used by the server.

---

6) Quick development tips
- Use `OPEN_VOTER_REGISTRATION=true` while developing the frontend to avoid admin token friction.
- Increase `DIFFICULTY` if you want longer mining times for demo; lower it (e.g., 2-3) for fast local mines.
- Keep the virtualenv active when running backend to ensure correct `cryptography` and runtime packages are used.

---

7) Example single-step sequence (copy-paste test)

```bash
# in project root
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
export OPEN_VOTER_REGISTRATION=true
export CORS_ALLOW_ORIGINS="http://localhost:5173"
uvicorn main:app --host 127.0.0.1 --port 8001 &
# in a new tab
cd frontend && npm install && npm run dev &
# in another tab once frontend is running, make a wallet (CLI)
python generate_wallet.py --output wallet.json
# register and vote (if not auto-registered by UI)
python register_voter.py --wallet wallet.json --voter-id V001
python add_vote.py --wallet wallet.json --voter-id V001 --candidate Alice --election student-union-2026
# mine block
curl "http://127.0.0.1:8001/mine"
# view results
curl "http://127.0.0.1:8001/elections/student-union-2026/results"
```

---

If you want, I can now:
- Update the frontend to include `X-Admin-Token` automatically from a config file when present, or
- Add a one-click `start-dev.sh` script that starts backend + frontend with sane defaults.


