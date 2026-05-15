from __future__ import annotations

import logging
import os
from typing import Any

import requests
import jwt
from datetime import datetime, timedelta
import threading
import random
from time import time as time_now
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
    registration_code: str = Field(default="")
    election_id: str | None = None


class VoterReplicationIn(BaseModel):
    voter_id: str = Field(min_length=1)
    voter_public_key: str = Field(min_length=1)
    election_id: str | None = None


class RegistrationCodeIssueIn(BaseModel):
    voter_id: str = Field(min_length=1)
    election_id: str | None = None
    expires_in_minutes: int = Field(default=60, ge=1, le=10080)


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    expires_in_minutes: int = Field(default=60, ge=1, le=1440)


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


class RemoteMineIn(BaseModel):
    transactions: list[dict[str, Any]]
    difficulty: int | None = None


DIFFICULTY = int(os.getenv("DIFFICULTY", "3"))
DATA_FILE = os.getenv("BLOCKCHAIN_DATA", "blockchain_data.json")
PEER_NODES_RAW = os.getenv("PEER_NODES", "")
SELF_NODE_URL = os.getenv("SELF_NODE_URL", "").rstrip("/")
NODE_LABEL = os.getenv("NODE_LABEL", SELF_NODE_URL or os.getenv("HOSTNAME", "node")).strip()
MINING_PROGRESS_INTERVAL = int(os.getenv("MINING_PROGRESS_INTERVAL", "50000"))
CORS_ALLOW_ORIGINS_RAW = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
)

# Legacy shared secret (optional)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

# Optional admin username/password for JWT login
# Default to a local development credential when not set
ADMIN_USER = os.getenv("ADMIN_USER", "admin").strip()
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123").strip()

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", (ADMIN_TOKEN or "dev-secret")).strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
# When set to a truthy value (e.g. "true"), voter registration is open
# and does not require the admin token. Keep empty/disabled for production.
OPEN_VOTER_REGISTRATION = os.getenv("OPEN_VOTER_REGISTRATION", "").strip().lower()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s")
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


def _node_tag() -> str:
    return NODE_LABEL or "node"


def _log_node_event(level: int, message: str, *args: Any) -> None:
    logger.log(level, "[%s] " + message, _node_tag(), *args)


def persist_state() -> None:
    storage.save(blockchain.to_dict())


def _verify_jwt_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def assert_admin_access(x_admin_token: str | None) -> None:
    # If open registration is enabled, skip admin token requirement.
    if OPEN_VOTER_REGISTRATION in ("1", "true", "yes"):
        return

    # If no admin token or JWT configured, allow access (dev-friendly).
    if not ADMIN_TOKEN and not JWT_SECRET:
        return

    provided = (x_admin_token or "").strip()
    if provided == ADMIN_TOKEN:
        return

    # Try to treat provided as bearer token (in case header was reused)
    if provided.lower().startswith("bearer "):
        token = provided.split(" ", 1)[1].strip()
        if token and _verify_jwt_token(token):
            return

    raise HTTPException(status_code=403, detail="Admin token required")


def assert_governance_access(x_admin_token: str | None, authorization: str | None = None) -> None:
    # Allow when no admin protection configured
    if not ADMIN_TOKEN and not JWT_SECRET:
        return

    # If legacy header matches, allow
    provided = (x_admin_token or "").strip()
    if provided and provided == ADMIN_TOKEN:
        return

    # Accept Authorization: Bearer <jwt>
    if authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            payload = _verify_jwt_token(token)
            if payload and payload.get("role") == "admin":
                return

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
        _log_node_event(logging.INFO, "Registered %d peer nodes from environment", added)

    return added


@app.on_event("startup")
def auto_register_peers() -> None:
    bootstrap_nodes_from_env()
    if blockchain.nodes:
        _log_node_event(logging.INFO, "Bootstrapped peers: %s", ", ".join(sorted(blockchain.nodes)))


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
                _log_node_event(logging.INFO, "Block broadcast accepted by %s", node)
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
                    _log_node_event(logging.INFO, "Block sync accepted by %s", node)
                else:
                    rejected += 1
                    _log_node_event(
                        logging.WARNING,
                        "Block broadcast rejected by %s: %s",
                        node,
                        response.text[:200],
                    )
        except requests.RequestException:
            unreachable += 1
            _log_node_event(logging.WARNING, "Block broadcast unreachable for %s", node)

    return {
        "accepted": accepted,
        "rejected": rejected,
        "unreachable": unreachable,
    }


def broadcast_transaction_to_peers(vote: dict[str, Any]) -> dict[str, int]:
    accepted = 0
    rejected = 0
    unreachable = 0

    for node in blockchain.nodes:
        try:
            response = requests.post(
                f"{node}/mempool/receive",
                json=vote,
                timeout=5,
            )
            if response.status_code == 200:
                accepted += 1
                _log_node_event(logging.INFO, "Vote broadcast accepted by %s", node)
            else:
                rejected += 1
                _log_node_event(
                    logging.WARNING,
                    "Vote broadcast rejected by %s: %s",
                    node,
                    response.text[:200],
                )
        except requests.RequestException:
            unreachable += 1
            _log_node_event(logging.WARNING, "Vote broadcast unreachable for %s", node)

    return {
        "accepted": accepted,
        "rejected": rejected,
        "unreachable": unreachable,
    }


def broadcast_voter_to_peers(voter: dict[str, Any]) -> dict[str, int]:
    accepted = 0
    rejected = 0
    unreachable = 0

    for node in blockchain.nodes:
        try:
            response = requests.post(
                f"{node}/voters/receive",
                json=voter,
                timeout=5,
            )
            if response.status_code == 200:
                accepted += 1
                _log_node_event(logging.INFO, "Voter registration accepted by %s", node)
            else:
                rejected += 1
                _log_node_event(
                    logging.WARNING,
                    "Voter registration rejected by %s: %s",
                    node,
                    response.text[:200],
                )
        except requests.RequestException:
            unreachable += 1
            _log_node_event(logging.WARNING, "Voter registration unreachable for %s", node)

    return {
        "accepted": accepted,
        "rejected": rejected,
        "unreachable": unreachable,
    }


# Mining coordination primitives for this node
miner_thread: threading.Thread | None = None
miner_stop_event = threading.Event()
miner_lock = threading.Lock()
miner_active = False


def _claim_mining_slot() -> bool:
    global miner_active

    with miner_lock:
        if miner_active:
            return False

        miner_active = True
        miner_stop_event.clear()
        return True


def _release_mining_slot() -> None:
    global miner_active, miner_thread

    with miner_lock:
        miner_active = False
        if threading.current_thread() is miner_thread:
            miner_thread = None
        miner_stop_event.clear()


def _vote_identity(vote: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(vote.get("voter_id", "")).strip(),
        str(vote.get("candidate_id", "")).strip(),
        str(vote.get("election_id", "")).strip(),
        str(vote.get("voter_public_key", "")).strip(),
        str(vote.get("signature", "")).strip(),
    )


def _remove_mined_transactions_from_mempool(transactions: list[dict[str, Any]]) -> int:
    if not transactions:
        return 0

    mined_identities = {_vote_identity(tx) for tx in transactions if isinstance(tx, dict)}
    if not mined_identities:
        return 0

    before_count = len(blockchain.pending_transactions)
    blockchain.pending_transactions = [
        tx
        for tx in blockchain.pending_transactions
        if not isinstance(tx, dict) or _vote_identity(tx) not in mined_identities
    ]
    return before_count - len(blockchain.pending_transactions)


def _stop_local_miner() -> None:
    try:
        miner_stop_event.set()
    except Exception:
        pass


def _start_local_miner(transactions: list[dict[str, Any]], difficulty: int | None = None) -> dict[str, Any]:
    """Start a background miner thread that attempts proof-of-work on the given transactions.

    This function returns immediately after scheduling the worker. The worker will
    check `miner_stop_event` periodically and stop if it is set (e.g., when another
    node broadcasts a mined block).
    """

    global miner_thread

    if not _claim_mining_slot():
        return {"message": "miner already running"}

    with miner_lock:
        if miner_thread and miner_thread.is_alive():
            _release_mining_slot()
            return {"message": "miner already running"}

        def worker():
            try:
                _log_node_event(
                    logging.INFO,
                    "Background miner thread started: txs=%d difficulty=%s",
                    len(transactions),
                    difficulty if difficulty is not None else blockchain.difficulty,
                )
                _mine_transactions(transactions, difficulty=difficulty, broadcast=True)
            finally:
                _release_mining_slot()

        miner_thread = threading.Thread(target=worker, daemon=True)
        miner_thread.start()

    return {"message": "mining_started"}


def _mine_transactions(
    transactions: list[dict[str, Any]],
    difficulty: int | None = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    applied_difficulty = difficulty if difficulty is not None else blockchain.difficulty
    block = Block(
        index=len(blockchain.chain),
        timestamp=time_now(),
        transactions=[dict(tx) for tx in transactions],
        previous_hash=blockchain.latest_block.hash,
    )
    target = "0" * applied_difficulty
    attempts = 0
    started_at = time_now()

    _log_node_event(
        logging.INFO,
        "Mining started: txs=%d difficulty=%d index=%d previous_hash=%s",
        len(transactions),
        applied_difficulty,
        block.index,
        block.previous_hash[:16],
    )

    while not miner_stop_event.is_set():
        block.hash = block.calculate_hash()
        attempts += 1

        if attempts == 1 or attempts % MINING_PROGRESS_INTERVAL == 0:
            _log_node_event(
                logging.INFO,
                "Mining progress: attempts=%d nonce=%d hash=%s",
                attempts,
                block.nonce,
                block.hash[:16],
            )

        if block.hash.startswith(target):
            try:
                blockchain.add_block(block)
                _remove_mined_transactions_from_mempool(block.transactions)
                persist_state()
            except Exception as error:
                miner_stop_event.set()
                _log_node_event(logging.WARNING, "Mined block rejected locally: %s", error)
                return {
                    "message": "block_rejected",
                    "reason": str(error),
                    "index": block.index,
                    "nonce": block.nonce,
                    "hash": block.hash,
                    "difficulty": applied_difficulty,
                }

            broadcast_result = None
            if broadcast:
                broadcast_result = broadcast_block_to_peers(block)

            elapsed = time_now() - started_at
            _log_node_event(
                logging.INFO,
                "Mining completed first: index=%d nonce=%d hash=%s elapsed=%.2fs",
                block.index,
                block.nonce,
                block.hash[:16],
                elapsed,
            )
            _log_node_event(
                logging.INFO,
                "Winning block details: index=%d nonce=%d hash=%s txs=%d",
                block.index,
                block.nonce,
                block.hash,
                len(block.transactions),
            )
            return {
                "message": "New vote block mined",
                "index": block.index,
                "hash": block.hash,
                "nonce": block.nonce,
                "previous_hash": block.previous_hash,
                "votes": block.transactions,
                "mining_time_seconds": round(elapsed, 6),
                "difficulty": applied_difficulty,
                "broadcast": broadcast_result,
            }

        block.nonce += 1

    elapsed = time_now() - started_at
    _log_node_event(
        logging.INFO,
        "Mining stopped: index=%d nonce=%d attempts=%d elapsed=%.2fs",
        block.index,
        block.nonce,
        attempts,
        elapsed,
    )
    return {
        "message": "mining_stopped",
        "reason": "another node found the block",
        "index": block.index,
        "nonce": block.nonce,
        "difficulty": applied_difficulty,
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


@app.post("/voters/codes/issue")
def issue_registration_code(
    payload: RegistrationCodeIssueIn,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    assert_governance_access(x_admin_token, authorization)

    try:
        result = blockchain.issue_registration_code_for(
            payload.voter_id, payload.election_id, payload.expires_in_minutes
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    return {
        "message": "Registration code issued",
        **result,
    }


@app.post("/admin/login")
def admin_login(payload: AdminLoginIn) -> dict[str, Any]:
    # Validate credentials
    username = payload.username.strip()
    password = payload.password.strip()

    valid = False
    # If explicit admin username/password provided, use them
    if ADMIN_USER and ADMIN_PASS:
        valid = username == ADMIN_USER and password == ADMIN_PASS
    # Fallback: allow login using legacy ADMIN_TOKEN as password for 'admin'
    elif ADMIN_TOKEN:
        valid = username == "admin" and password == ADMIN_TOKEN

    if not valid:
        raise HTTPException(status_code=403, detail="Invalid admin credentials")

    expires = int(payload.expires_in_minutes)
    exp = datetime.utcnow() + timedelta(minutes=expires)
    token = jwt.encode({"sub": username, "role": "admin", "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": expires,
    }


@app.post("/voters/register")
def register_voter(
    payload: VoterRegistrationIn,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    try:
        registration_code = payload.registration_code.strip()
        election_id = payload.election_id

        if registration_code:
            blockchain.register_voter_with_code(
                payload.voter_id,
                payload.voter_public_key,
                registration_code,
                election_id,
            )
        elif OPEN_VOTER_REGISTRATION in ("1", "true", "yes"):
            blockchain.register_voter(payload.voter_id, payload.voter_public_key)
        else:
            raise ValueError("registration_code is required")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    broadcast_result = broadcast_voter_to_peers(
        {
            "voter_id": payload.voter_id.strip(),
            "voter_public_key": payload.voter_public_key.strip(),
            "election_id": payload.election_id,
        }
    )
    return {
        "message": "Voter registered",
        "voter_id": payload.voter_id.strip(),
        "registered_voters": len(blockchain.voter_registry),
        "broadcast": broadcast_result,
    }


@app.post("/voters/receive")
def receive_voter_registration(payload: VoterReplicationIn) -> dict[str, Any]:
    try:
        if payload.election_id is None:
            blockchain.register_voter(payload.voter_id, payload.voter_public_key)
        else:
            voter_id = payload.voter_id.strip()
            voter_public_key = payload.voter_public_key.strip()
            election_id = payload.election_id.strip() if payload.election_id else None

            if not voter_id:
                raise ValueError("voter_id is required")
            if not voter_public_key:
                raise ValueError("voter_public_key is required")

            existing_public_key = blockchain.voter_registry.get(voter_id)
            if existing_public_key and existing_public_key != voter_public_key:
                raise ValueError("voter_id is already registered with a different public key")

            blockchain.voter_registry[voter_id] = voter_public_key
            if election_id:
                if voter_id not in blockchain.voter_elections:
                    blockchain.voter_elections[voter_id] = set()
                blockchain.voter_elections[voter_id].add(election_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    _log_node_event(
        logging.INFO,
        "Voter registration received: voter=%s election=%s",
        payload.voter_id,
        payload.election_id or "global",
    )
    return {"message": "Voter registration accepted", "voter_id": payload.voter_id.strip()}


@app.get("/voters")
def list_voters() -> dict[str, Any]:
    return {
        "registered_voters": len(blockchain.voter_registry),
        "voter_ids": sorted(blockchain.voter_registry.keys()),
        "voter_registry": dict(blockchain.voter_registry),
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

    # Persist local state
    persist_state()
    _log_node_event(
        logging.INFO,
        "Vote accepted locally: voter=%s election=%s candidate=%s pending=%d",
        vote.voter_id,
        vote.election_id,
        vote.candidate_id,
        len(blockchain.pending_transactions),
    )

    # Broadcast this vote to peers' mempools so they can compete to mine it
    try:
        broadcast_result = broadcast_transaction_to_peers(
            {
                "voter_id": vote.voter_id,
                "candidate_id": vote.candidate_id,
                "election_id": vote.election_id,
                "voter_public_key": vote.voter_public_key,
                "signature": vote.signature,
                "timestamp": str(datetime.utcnow().timestamp()),
            }
        )
    except Exception:
        broadcast_result = {"accepted": 0, "rejected": 0, "unreachable": 0}
        _log_node_event(logging.WARNING, "Vote broadcast failed unexpectedly for voter=%s", vote.voter_id)

    return {
        "message": f"Vote will be added to block {index}",
        "pending_votes": len(blockchain.pending_transactions),
        "broadcast": broadcast_result,
    }


@app.post("/transactions")
def create_transaction(vote: VoteIn) -> dict[str, Any]:
    return cast_vote(vote)


@app.post("/mempool/receive")
def mempool_receive(vote: VoteIn) -> dict[str, Any]:
    """Endpoint for peers to send pending votes into this node's mempool.

    Peers SHOULD call this to propagate new votes; this endpoint validates
    the vote and appends it to `blockchain.pending_transactions` if valid.
    """
    try:
        # If this exact voter already has a pending vote for the same election, ignore
        if blockchain._has_vote(vote.voter_id, vote.election_id, blockchain.pending_transactions):
            _log_node_event(
                logging.INFO,
                "Duplicate mempool vote ignored: voter=%s election=%s",
                vote.voter_id,
                vote.election_id,
            )
            return {"message": "vote already in mempool", "pending_votes": len(blockchain.pending_transactions)}

        # Re-use the same validation flow as cast_vote but do NOT rebroadcast
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
    _log_node_event(
        logging.INFO,
        "Vote accepted into mempool: voter=%s election=%s pending=%d",
        vote.voter_id,
        vote.election_id,
        len(blockchain.pending_transactions),
    )
    return {"message": "Vote accepted into mempool", "pending_votes": len(blockchain.pending_transactions)}


@app.post("/mempool/broadcast")
def mempool_broadcast() -> dict[str, Any]:
    """Broadcast all locally pending transactions to peers' mempools."""
    if not blockchain.pending_transactions:
        return {"message": "No pending transactions to broadcast", "total": 0}

    _log_node_event(logging.INFO, "Broadcasting %d pending transactions to peers", len(blockchain.pending_transactions))
    results = {"accepted": 0, "rejected": 0, "unreachable": 0}
    for tx in list(blockchain.pending_transactions):
        res = broadcast_transaction_to_peers(tx)
        results["accepted"] += res.get("accepted", 0)
        results["rejected"] += res.get("rejected", 0)
        results["unreachable"] += res.get("unreachable", 0)

    return {"message": "Mempool broadcast completed", **results, "total": len(blockchain.pending_transactions)}


@app.get("/mempool")
def get_mempool() -> dict[str, Any]:
    return {
        "pending_transactions": blockchain.pending_transactions,
        "count": len(blockchain.pending_transactions),
    }


@app.post("/mine/remote")
def mine_remote(payload: RemoteMineIn) -> dict[str, Any]:
    """Start mining on this node using the provided transactions (called by peers)."""
    if not payload.transactions:
        raise HTTPException(status_code=400, detail="no transactions provided")

    _log_node_event(
        logging.INFO,
        "Remote mining request received: txs=%d difficulty=%s",
        len(payload.transactions),
        payload.difficulty if payload.difficulty is not None else blockchain.difficulty,
    )
    return _start_local_miner(payload.transactions, payload.difficulty)


def _coordinate_cluster_mining(limit: int = 100, difficulty: int | None = None) -> dict[str, Any]:
    if not blockchain.pending_transactions:
        return {"message": "No pending transactions to mine", "total": 0}

    txs = list(blockchain.pending_transactions)[: int(limit)]

    peer_results = {"accepted": 0, "rejected": 0, "unreachable": 0}
    for node in blockchain.nodes:
        try:
            peer_txs = list(txs)
            random.shuffle(peer_txs)
            response = requests.post(
                f"{node}/mine/remote",
                json={"transactions": peer_txs, "difficulty": difficulty},
                timeout=5,
            )
            if response.status_code == 200:
                peer_results["accepted"] += 1
                _log_node_event(logging.INFO, "Peer mining started on %s", node)
            else:
                peer_results["rejected"] += 1
                _log_node_event(
                    logging.WARNING,
                    "Peer mining rejected by %s: %s",
                    node,
                    response.text[:200],
                )
        except requests.RequestException:
            peer_results["unreachable"] += 1
            _log_node_event(logging.WARNING, "Peer mining unreachable on %s", node)

    if not _claim_mining_slot():
        return {
            "message": "Mining already in progress",
            "total_txs": len(txs),
            "peers": peer_results,
        }

    try:
        local_txs = list(txs)
        random.shuffle(local_txs)
        local_result = _mine_transactions(local_txs, difficulty=difficulty, broadcast=True)
    finally:
        _release_mining_slot()

    return {
        "message": local_result.get("message", "cluster_mining_complete"),
        "local": local_result,
        "peers": peer_results,
        "total_txs": len(txs),
    }


@app.post("/mine/cluster")
def mine_cluster(limit: int = 100, difficulty: int | None = None) -> dict[str, Any]:
    """Coordinate a cluster mining run using the same transactions on every node."""
    return _coordinate_cluster_mining(limit=limit, difficulty=difficulty)


@app.get("/elections/{election_id}/results")
def election_results(election_id: str, include_pending: bool = False) -> dict[str, Any]:
    """Return election results.

    By default `include_pending` is False so only confirmed (mined) votes
    are counted. Set `?include_pending=true` to include unmined pending votes.
    """
    totals = blockchain.tally_votes(election_id, include_pending=include_pending)
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
        "include_pending": include_pending,
    }


@app.get("/mine")
def mine() -> dict[str, Any]:
    return _coordinate_cluster_mining(limit=100, difficulty=None)


@app.post("/blocks/receive")
def receive_block(block_payload: BlockIn) -> dict[str, Any]:
    # Stop any ongoing local mining - another node found a block
    _stop_local_miner()
    _log_node_event(
        logging.INFO,
        "Received block broadcast: index=%d nonce=%d hash=%s",
        block_payload.index,
        block_payload.nonce,
        block_payload.hash[:16],
    )

    incoming_block = Block.from_dict(block_payload.model_dump())

    if incoming_block.index <= blockchain.latest_block.index:
        return {
            "message": "Block already known or stale",
            "index": incoming_block.index,
        }

    try:
        blockchain.add_block(incoming_block)
        _remove_mined_transactions_from_mempool(incoming_block.transactions)
        persist_state()
        _log_node_event(logging.INFO, "Block accepted: index=%d hash=%s", incoming_block.index, incoming_block.hash[:16])
        return {
            "message": "Block accepted",
            "index": incoming_block.index,
            "hash": incoming_block.hash,
        }
    except ValueError as error:
        _log_node_event(
            logging.WARNING,
            "Block rejected: index=%d prev=%s hash=%s latest_index=%d latest_hash=%s reason=%s",
            incoming_block.index,
            incoming_block.previous_hash[:16],
            incoming_block.hash[:16],
            blockchain.latest_block.index,
            blockchain.latest_block.hash[:16],
            error,
        )
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
    included_transactions = []
    for blk in remote_chain:
        included_transactions.extend(blk.transactions)

    _remove_mined_transactions_from_mempool(included_transactions)
    persist_state()
    _log_node_event(logging.INFO, "Chain synchronized: length=%d", len(blockchain.chain))

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
    _log_node_event(logging.INFO, "Registered nodes: %s", ", ".join(sorted(blockchain.nodes)))
    return {
        "message": "Nodes registered",
        "total_nodes": sorted(blockchain.nodes),
    }


@app.get("/nodes/resolve")
def resolve_nodes() -> dict[str, Any]:
    _log_node_event(logging.INFO, "Consensus resolution requested")
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


@app.post("/broadcast")
def broadcast_latest_block() -> dict[str, Any]:
    if not blockchain.chain or len(blockchain.chain) < 2:
        return {
            "message": "No blocks to broadcast (only genesis)",
            "accepted": 0,
            "rejected": 0,
            "unreachable": 0,
        }
    
    latest_block = blockchain.latest_block
    result = broadcast_block_to_peers(latest_block)
    
    return {
        "message": "Latest block broadcasted",
        "block_index": latest_block.index,
        "block_hash": latest_block.hash,
        **result,
    }
