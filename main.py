from __future__ import annotations

import logging
import os
from typing import Any

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from block import Block
from blockchain import Blockchain
from storage import JsonStorage

# Demo instructions:
# 1) Run multiple nodes:
#    DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json uvicorn main:app --host 127.0.0.1 --port 8001
#    DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json uvicorn main:app --host 127.0.0.1 --port 8002
# 2) Cast a vote:
#    curl -X POST "http://127.0.0.1:8001/votes" -H "Content-Type: application/json" -d '{"voter_id":"V001","candidate_id":"Alice","election_id":"student-union-2026"}'
# 3) Mine:
#    curl "http://127.0.0.1:8001/mine"
# 4) Register peers:
#    curl -X POST "http://127.0.0.1:8001/nodes/register" -H "Content-Type: application/json" -d '{"nodes":["http://127.0.0.1:8002"]}'
# 5) View results:
#    curl "http://127.0.0.1:8001/elections/student-union-2026/results"


class VoteIn(BaseModel):
    voter_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    election_id: str = Field(min_length=1)
    voter_public_key: str = Field(min_length=1)
    signature: str = Field(min_length=1)


class NodeRegistrationIn(BaseModel):
    nodes: list[str]


class VoterRegistrationIn(BaseModel):
    voter_id: str = Field(min_length=1)
    voter_public_key: str = Field(min_length=1)


class BlockIn(BaseModel):
    index: int
    timestamp: float
    transactions: list[dict[str, Any]]
    previous_hash: str
    nonce: int
    hash: str


class ChainSyncIn(BaseModel):
    difficulty: int
    chain: list[dict[str, Any]]
    voter_registry: dict[str, str] = Field(default_factory=dict)


DIFFICULTY = int(os.getenv("DIFFICULTY", "3"))
DATA_FILE = os.getenv("BLOCKCHAIN_DATA", "blockchain_data.json")
PEER_NODES_RAW = os.getenv("PEER_NODES", "")
SELF_NODE_URL = os.getenv("SELF_NODE_URL", "").rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
CORS_ALLOW_ORIGINS_RAW = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
)

# When set to a truthy value (e.g. "true"), voter registration is open
# and does not require the admin token. Keep empty/disabled for production.
OPEN_VOTER_REGISTRATION = os.getenv("OPEN_VOTER_REGISTRATION", "").strip().lower()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

storage = JsonStorage(DATA_FILE)
persisted = storage.load()

if persisted:
    try:
        blockchain = Blockchain.from_dict(persisted)
        logger.info("Loaded persisted chain from %s", DATA_FILE)
    except Exception:
        logger.warning("Persisted chain in %s is invalid; starting fresh", DATA_FILE)
        blockchain = Blockchain(difficulty=DIFFICULTY)
else:
    logger.info("No persisted chain found at %s; starting fresh", DATA_FILE)
    blockchain = Blockchain(difficulty=DIFFICULTY)

if blockchain.difficulty != DIFFICULTY:
    blockchain.difficulty = DIFFICULTY

app = FastAPI(title="Blockchain Voting Node", version="2.0.0")

cors_allow_origins = [
    origin.strip()
    for origin in CORS_ALLOW_ORIGINS_RAW.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def persist_state() -> None:
    storage.save(blockchain.to_dict())


def assert_admin_access(x_admin_token: str | None) -> None:
    # If open registration is enabled, skip admin token requirement.
    if OPEN_VOTER_REGISTRATION in ("1", "true", "yes"):
        return

    # If no admin token configured, allow access (dev-friendly).
    if not ADMIN_TOKEN:
        return

    provided = (x_admin_token or "").strip()
    if provided != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")


def bootstrap_nodes_from_env() -> int:
    added = 0
    for peer in [node.strip() for node in PEER_NODES_RAW.split(",") if node.strip()]:
        if SELF_NODE_URL and peer.rstrip("/") == SELF_NODE_URL:
            continue
        if peer.rstrip("/") in blockchain.nodes:
            continue
        try:
            blockchain.register_node(peer)
            added += 1
        except ValueError:
            continue

    if added > 0:
        persist_state()

    return added


@app.on_event("startup")
def auto_register_peers() -> None:
    bootstrap_nodes_from_env()


def broadcast_block_to_peers(mined_block: Block) -> dict[str, int]:
    accepted = 0
    rejected = 0
    unreachable = 0

    for node in blockchain.nodes:
        try:
            response = requests.post(
                f"{node}/blocks/receive",
                json=mined_block.to_dict(),
                timeout=5,
            )
            if response.status_code == 200:
                accepted += 1
            else:
                sync_response = requests.post(
                    f"{node}/chains/sync",
                    json={
                        "difficulty": blockchain.difficulty,
                        "chain": [block.to_dict() for block in blockchain.chain],
                        "voter_registry": blockchain.voter_registry,
                    },
                    timeout=5,
                )
                if sync_response.status_code == 200:
                    accepted += 1
                else:
                    rejected += 1
        except requests.RequestException:
            unreachable += 1

    return {
        "accepted": accepted,
        "rejected": rejected,
        "unreachable": unreachable,
    }


@app.get("/chain")
def get_chain() -> dict[str, Any]:
    return {
        "length": len(blockchain.chain),
        "difficulty": blockchain.difficulty,
        "pending_votes": len(blockchain.pending_transactions),
        "chain": [block.to_dict() for block in blockchain.chain],
        "nodes": sorted(blockchain.nodes),
        "registered_voters": len(blockchain.voter_registry),
    }


@app.post("/voters/register")
def register_voter(
    payload: VoterRegistrationIn,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    assert_admin_access(x_admin_token)

    try:
        blockchain.register_voter(payload.voter_id, payload.voter_public_key)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    return {
        "message": "Voter registered",
        "voter_id": payload.voter_id.strip(),
        "registered_voters": len(blockchain.voter_registry),
    }


@app.get("/voters")
def list_voters() -> dict[str, Any]:
    return {
        "registered_voters": len(blockchain.voter_registry),
        "voter_ids": sorted(blockchain.voter_registry.keys()),
    }


@app.post("/votes")
def cast_vote(vote: VoteIn) -> dict[str, Any]:
    try:
        index = blockchain.add_vote(
            vote.voter_id,
            vote.candidate_id,
            vote.election_id,
            vote.voter_public_key,
            vote.signature,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    return {
        "message": f"Vote will be added to block {index}",
        "pending_votes": len(blockchain.pending_transactions),
    }


@app.post("/transactions")
def create_transaction(vote: VoteIn) -> dict[str, Any]:
    return cast_vote(vote)


@app.get("/elections/{election_id}/results")
def election_results(election_id: str) -> dict[str, Any]:
    totals = blockchain.tally_votes(election_id)
    total_votes = sum(totals.values())
    return {
        "election_id": election_id,
        "total_votes": total_votes,
        "results": dict(sorted(totals.items(), key=lambda item: (-item[1], item[0]))),
        "pending_votes": sum(
            1
            for vote in blockchain.pending_transactions
            if str(vote.get("election_id", "")).strip() == election_id
        ),
    }


@app.get("/mine")
def mine() -> dict[str, Any]:
    mined_block, mining_time = blockchain.mine_pending_votes()

    if mined_block is None or mining_time is None:
        return {"message": "No pending votes to mine"}

    broadcast_result = broadcast_block_to_peers(mined_block)
    persist_state()
    return {
        "message": "New vote block mined",
        "index": mined_block.index,
        "hash": mined_block.hash,
        "nonce": mined_block.nonce,
        "previous_hash": mined_block.previous_hash,
        "votes": mined_block.transactions,
        "mining_time_seconds": round(mining_time, 6),
        "difficulty": blockchain.difficulty,
        "broadcast": broadcast_result,
    }


@app.post("/blocks/receive")
def receive_block(block_payload: BlockIn) -> dict[str, Any]:
    incoming_block = Block.from_dict(block_payload.model_dump())

    if incoming_block.index <= blockchain.latest_block.index:
        return {
            "message": "Block already known or stale",
            "index": incoming_block.index,
        }

    try:
        blockchain.add_block(incoming_block)
        blockchain.pending_transactions = [
            vote
            for vote in blockchain.pending_transactions
            if vote not in incoming_block.transactions
        ]
        persist_state()
        return {
            "message": "Block accepted",
            "index": incoming_block.index,
            "hash": incoming_block.hash,
        }
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"Rejected block: {error}",
        ) from error


@app.post("/chains/sync")
def sync_chain(payload: ChainSyncIn) -> dict[str, Any]:
    remote_chain = [Block.from_dict(item) for item in payload.chain]

    if len(remote_chain) <= len(blockchain.chain):
        raise HTTPException(status_code=400, detail="Received chain is not longer")

    if not blockchain.is_chain_valid(remote_chain):
        raise HTTPException(status_code=400, detail="Received chain is invalid")

    blockchain.chain = remote_chain
    blockchain.difficulty = payload.difficulty
    blockchain.voter_registry = {
        voter_id.strip(): public_key.strip()
        for voter_id, public_key in payload.voter_registry.items()
        if voter_id.strip() and public_key.strip()
    }
    blockchain.pending_transactions.clear()
    persist_state()

    return {
        "message": "Chain synchronized",
        "length": len(blockchain.chain),
    }


@app.post("/nodes/register")
def register_nodes(payload: NodeRegistrationIn) -> dict[str, Any]:
    if not payload.nodes:
        raise HTTPException(status_code=400, detail="No nodes provided")

    try:
        for node in payload.nodes:
            blockchain.register_node(node)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    return {
        "message": "Nodes registered",
        "total_nodes": sorted(blockchain.nodes),
    }


@app.get("/nodes/resolve")
def resolve_nodes() -> dict[str, Any]:
    longest_chain: list[Block] | None = None
    max_length = len(blockchain.chain)

    for node in blockchain.nodes:
        try:
            response = requests.get(f"{node}/chain", timeout=5)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            continue

        remote_length = int(payload.get("length", 0))
        remote_chain_raw = payload.get("chain", [])
        remote_chain = [Block.from_dict(item) for item in remote_chain_raw]

        if remote_length > max_length and blockchain.is_chain_valid(remote_chain):
            max_length = remote_length
            longest_chain = remote_chain

    if longest_chain is not None:
        blockchain.chain = longest_chain
        blockchain.pending_transactions.clear()
        persist_state()
        return {
            "message": "Chain was replaced by a longer valid chain",
            "new_length": len(blockchain.chain),
            "chain": [block.to_dict() for block in blockchain.chain],
        }

    return {
        "message": "Current chain is authoritative",
        "length": len(blockchain.chain),
        "chain": [block.to_dict() for block in blockchain.chain],
    }
