# Frontend (React + Vite)

This is the web dashboard for the blockchain voting backend.

## Features

- Cast vote form (`/votes`)
- Mine pending votes (`/mine`)
- Resolve consensus (`/nodes/resolve`)
- Election result view (`/elections/{election_id}/results`)
- Chain explorer with latest blocks (`/chain`)

## Run

```bash
cd /home/bibhab/finalproject/frontend
npm install
npm run dev
```

By default it runs on `http://127.0.0.1:5173`.

## Backend Requirement

Start at least one backend node first, for example:

```bash
cd /home/bibhab/finalproject
DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json uvicorn main:app --host 127.0.0.1 --port 8001
```

Then set Node URL in the UI (default is `http://127.0.0.1:8001`).