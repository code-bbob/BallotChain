from __future__ import annotations

import logging
import os
import hashlib
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
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from block import Block
from blockchain import Blockchain
from storage import JsonStorage

# Demo instructions:
# 1) Run multiple nodes:
#    DIFFICULTY=3 BLOCKCHAIN_DATA=node1.json uvicorn main:app --host 127.0.0.1 --port 8001
#    DIFFICULTY=3 BLOCKCHAIN_DATA=node2.json uvicorn main:app --host 127.0.0.1 --port 8002
# 2) Admin issues invitation code:
#    curl -X POST "http://127.0.0.1:8001/voters/codes/issue" -H "X-Admin-Token: admin" -H "Content-Type: application/json" -d '{"election_id":"student-union-2026"}'
# 3) Voter blinds vote, gets admin signature, submits anonymously:
#    (see cast_blind_vote.py for the full flow)
# 4) Mine:
#    curl "http://127.0.0.1:8001/mine"
# 5) Register peers:
#    curl -X POST "http://127.0.0.1:8001/nodes/register" -H "Content-Type: application/json" -d '{"nodes":["http://127.0.0.1:8002"]}'
# 6) View results:
#    curl "http://127.0.0.1:8001/elections/student-union-2026/results"


class VoteIn(BaseModel):
    candidate_id: str = Field(min_length=1)
    election_id: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    signature: str = Field(min_length=1)


class NodeRegistrationIn(BaseModel):
    nodes: list[str]


class BlindSignIn(BaseModel):
    registration_code: str = Field(min_length=1)
    blinded_hash: str = Field(min_length=1)
    election_id: str | None = None


class RegistrationCodeIssueIn(BaseModel):
    election_id: str | None = None
    expires_in_minutes: int = Field(default=60, ge=1, le=10080)


class RegistrationCodeSyncIn(BaseModel):
    code_hash: str = Field(min_length=1)
    entry: dict[str, Any] = Field(default_factory=dict)


class RegistrationCodeConsumeIn(BaseModel):
    code_hash: str = Field(min_length=1)


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


def _normalize_multiline_secret(value: str) -> str:
    return value.replace("\\n", "\n").strip()


# --- Deterministic admin RSA key (dev fallback) -------------------------------
# When no ADMIN_RSA_PRIVATE_KEY_PEM is provided, each node derives the same key
# from the shared cluster secret (JWT_SECRET/ADMIN_TOKEN) so that every node
# signs votes with the same private key and verifies each other's votes without
# any extra configuration. Exports a "priv" seed label to keep p/q distinct.
_KEYGEN_SMALL_PRIMES = tuple(
    p for p in [
        2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53,
        59, 61, 67, 71, 73, 79, 83, 89, 97,
    ]
)
_KEYGEN_MR_BASES = (2, 3, 5, 7, 11, 13)


def _is_probable_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in _KEYGEN_SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for a in _KEYGEN_MR_BASES:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _deterministic_prime(seed: str, label: str, bits: int = 1024) -> int:
    counter = 0
    while True:
        digest = hashlib.sha256(f"{seed}:{label}:{counter}".encode("utf-8")).digest()
        while len(digest) < bits // 8:
            digest += hashlib.sha256(digest).digest()
        candidate = int.from_bytes(digest, "big") & ((1 << bits) - 1)
        candidate |= (1 << (bits - 1)) | 1  # top bit set + odd
        if _is_probable_prime(candidate):
            return candidate
        counter += 1


def _derive_admin_rsa_key(seed: str) -> rsa.RSAPrivateKey:
    p = _deterministic_prime(seed, "priv-p")
    counter = 0
    while True:
        q = _deterministic_prime(seed, f"priv-q-{counter}")
        if q != p:
            break
        counter += 1

    n = p * q
    e = 65537
    phi = (p - 1) * (q - 1)
    d = pow(e, -1, phi)
    numbers = rsa.RSAPrivateNumbers(
        p=p,
        q=q,
        d=d,
        dmp1=d % (p - 1),
        dmq1=d % (q - 1),
        iqmp=pow(q, -1, p),
        public_numbers=rsa.RSAPublicNumbers(e, n),
    )
    return numbers.private_key()


def _load_admin_rsa_private_key() -> rsa.RSAPrivateKey:
    pem_from_env = _normalize_multiline_secret(os.getenv("ADMIN_RSA_PRIVATE_KEY_PEM", ""))
    if pem_from_env:
        key = serialization.load_pem_private_key(pem_from_env.encode("utf-8"), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError("ADMIN_RSA_PRIVATE_KEY_PEM must contain an RSA private key")
        return key

    # Dev-friendly fallback: deterministic key shared across all cluster nodes.
    return _derive_admin_rsa_key(JWT_SECRET or "dev-secret")


ADMIN_RSA_PRIVATE_KEY = _load_admin_rsa_private_key()
ADMIN_RSA_PUBLIC_KEY = ADMIN_RSA_PRIVATE_KEY.public_key()
ADMIN_RSA_PUBLIC_NUMBERS = ADMIN_RSA_PUBLIC_KEY.public_numbers()
ADMIN_RSA_PRIVATE_NUMBERS = ADMIN_RSA_PRIVATE_KEY.private_numbers()
ADMIN_RSA_N = int(ADMIN_RSA_PUBLIC_NUMBERS.n)
ADMIN_RSA_E = int(ADMIN_RSA_PUBLIC_NUMBERS.e)
ADMIN_RSA_D = int(ADMIN_RSA_PRIVATE_NUMBERS.d)


def _parse_modular_int(value: str, field_name: str) -> int:
    text = value.strip().lower()
    if not text:
        raise ValueError(f"{field_name} is required")

    base = 16 if text.startswith("0x") else 10
    try:
        parsed = int(text, base)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid integer") from error

    if parsed <= 0 or parsed >= ADMIN_RSA_N:
        raise ValueError(f"{field_name} must be in range (0, n)")

    return parsed


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

# Set admin RSA public key on blockchain for vote signature verification
blockchain.admin_n = ADMIN_RSA_N
blockchain.admin_e = ADMIN_RSA_E

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
    # Allow when open registration or no admin protection configured
    if OPEN_VOTER_REGISTRATION in ("1", "true", "yes"):
        return
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


def broadcast_registration_code_to_peers(code_hash: str, entry: dict[str, Any]) -> dict[str, int]:
    """Push a freshly issued registration code to every peer node."""
    accepted = 0
    rejected = 0
    unreachable = 0

    for node in blockchain.nodes:
        try:
            response = requests.post(
                f"{node}/internal/registration-codes/receive",
                json={"code_hash": code_hash, "entry": entry},
                timeout=5,
            )
            if response.status_code == 200:
                accepted += 1
                _log_node_event(logging.INFO, "Registration code broadcast accepted by %s", node)
            else:
                rejected += 1
                _log_node_event(
                    logging.WARNING,
                    "Registration code broadcast rejected by %s: %s",
                    node,
                    response.text[:200],
                )
        except requests.RequestException:
            unreachable += 1
            _log_node_event(logging.WARNING, "Registration code broadcast unreachable for %s", node)

    return {
        "accepted": accepted,
        "rejected": rejected,
        "unreachable": unreachable,
    }


def broadcast_registration_code_consumed_to_peers(code_hash: str) -> dict[str, int]:
    """Tell every peer node that a registration code has been used up."""
    accepted = 0
    rejected = 0
    unreachable = 0

    for node in blockchain.nodes:
        try:
            response = requests.post(
                f"{node}/internal/registration-codes/consume",
                json={"code_hash": code_hash},
                timeout=5,
            )
            if response.status_code == 200:
                accepted += 1
                _log_node_event(logging.INFO, "Registration code consumption accepted by %s", node)
            else:
                rejected += 1
                _log_node_event(
                    logging.WARNING,
                    "Registration code consumption rejected by %s: %s",
                    node,
                    response.text[:200],
                )
        except requests.RequestException:
            unreachable += 1
            _log_node_event(logging.WARNING, "Registration code consumption unreachable for %s", node)

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


def _vote_identity(vote: dict[str, Any]) -> str:
    return str(vote.get("nonce", "")).strip()


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
    }


@app.get("/state/export")
def export_node_state() -> dict[str, Any]:
    """Return the raw persisted state exactly as stored on disk (e.g. node1.json)."""
    persisted_on_disk = storage.load()
    if persisted_on_disk is None:
        raise HTTPException(status_code=404, detail="No persisted state found on disk")
    return persisted_on_disk


@app.post("/voters/codes/issue")
def issue_registration_code(
    payload: RegistrationCodeIssueIn,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    assert_governance_access(x_admin_token, authorization)

    try:
        result = blockchain.issue_invitation_code_for(payload.election_id, payload.expires_in_minutes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()

    code_hash = blockchain._registration_code_hash(result["registration_code"])
    entry: dict[str, Any] = {
        "issued_at": result["issued_at"],
        "expires_at": result["expires_at"],
    }
    if result.get("election_id"):
        entry["election_id"] = result["election_id"]

    broadcast_result = broadcast_registration_code_to_peers(code_hash, entry)

    return {
        "message": "Registration code issued and shared with the cluster",
        "broadcast": broadcast_result,
        **result,
    }


@app.post("/internal/registration-codes/receive")
def receive_registration_code(payload: RegistrationCodeSyncIn) -> dict[str, Any]:
    """Internal: accept a registration code broadcast by a peer node."""
    code_hash = str(payload.code_hash).strip()
    if code_hash:
        blockchain.registration_codes[code_hash] = dict(payload.entry or {})
        persist_state()
        _log_node_event(logging.INFO, "Registration code received from peer (hash=%s...)", code_hash[:16])
    return {"message": "Registration code stored", "synced": True}


@app.post("/internal/registration-codes/consume")
def consume_registration_code(payload: RegistrationCodeConsumeIn) -> dict[str, Any]:
    """Internal: mark a registration code as used (broadcast by a peer node)."""
    code_hash = str(payload.code_hash).strip()
    removed = blockchain.registration_codes.pop(code_hash, None) if code_hash else None
    if removed is not None:
        persist_state()
        _log_node_event(logging.INFO, "Registration code consumed by peer (hash=%s...)", code_hash[:16])
    return {
        "message": "Registration code consumed",
        "removed": removed is not None,
        "synced": True,
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
def register_voter() -> dict[str, Any]:
    raise HTTPException(status_code=410, detail="Direct voter registration removed. Use blind-sign voting via POST /votes.")


@app.get("/voters/blind/public-key")
def get_blind_signature_public_key() -> dict[str, Any]:
    return {
        "algorithm": "RSA",
        "hash": "SHA-256",
        "e": str(ADMIN_RSA_E),
        "n": str(ADMIN_RSA_N),
        "e_hex": format(ADMIN_RSA_E, "x"),
        "n_hex": format(ADMIN_RSA_N, "x"),
        "modulus_bits": ADMIN_RSA_PUBLIC_KEY.key_size,
    }


@app.post("/voters/blind/sign")
def blind_sign_registration(payload: BlindSignIn) -> dict[str, Any]:
    try:
        entry = blockchain.consume_invitation_code(payload.registration_code, payload.election_id)

        entry_election = str(entry.get("election_id", "")).strip() or None
        blinded_hash_int = _parse_modular_int(payload.blinded_hash, "blinded_hash")
        blind_signature_int = pow(blinded_hash_int, ADMIN_RSA_D, ADMIN_RSA_N)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()

    code_hash = blockchain._registration_code_hash(payload.registration_code)
    broadcast_result = broadcast_registration_code_consumed_to_peers(code_hash)

    return {
        "message": "Blinded hash signed successfully",
        "election_id": entry_election,
        "blind_signature": format(blind_signature_int, "x"),
        "sync": broadcast_result,
    }


@app.post("/voters/receive")
def receive_voter_registration() -> dict[str, Any]:
    raise HTTPException(status_code=410, detail="Voter registration broadcasting removed.")


@app.get("/voters")
def list_voters() -> dict[str, Any]:
    return {
        "message": "Voter registry removed. See chain for anonymous votes.",
        "registered_voters": 0,
        "voter_ids": [],
    }


@app.post("/votes")
def cast_vote(vote: VoteIn) -> dict[str, Any]:
    try:
        index = blockchain.add_vote(
            vote.candidate_id,
            vote.election_id,
            vote.nonce,
            vote.signature,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    _log_node_event(
        logging.INFO,
        "Anonymous vote accepted: election=%s candidate=%s nonce=%s pending=%d",
        vote.election_id,
        vote.candidate_id,
        vote.nonce[:16],
        len(blockchain.pending_transactions),
    )

    try:
        broadcast_result = broadcast_transaction_to_peers(
            {
                "candidate_id": vote.candidate_id,
                "election_id": vote.election_id,
                "nonce": vote.nonce,
                "signature": vote.signature,
            }
        )
    except Exception:
        broadcast_result = {"accepted": 0, "rejected": 0, "unreachable": 0}
        _log_node_event(logging.WARNING, "Vote broadcast failed unexpectedly for nonce=%s", vote.nonce[:16])

    return {
        "message": f"Anonymous vote will be added to block {index}",
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
        if blockchain._has_nonce(vote.nonce, blockchain.pending_transactions):
            _log_node_event(
                logging.INFO,
                "Duplicate mempool vote ignored: nonce=%s",
                vote.nonce[:16],
            )
            return {"message": "vote already in mempool", "pending_votes": len(blockchain.pending_transactions)}

        index = blockchain.add_vote(
            vote.candidate_id,
            vote.election_id,
            vote.nonce,
            vote.signature,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    persist_state()
    _log_node_event(
        logging.INFO,
        "Anonymous vote accepted into mempool: nonce=%s pending=%d",
        vote.nonce[:16],
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
    persisted = storage.load()
    if persisted and "pending_transactions" in persisted:
        blockchain.pending_transactions = list(persisted["pending_transactions"])

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

    if incoming_block.index < blockchain.latest_block.index:
        return {
            "message": "Block already known or stale",
            "index": incoming_block.index,
        }

    if incoming_block.index == blockchain.latest_block.index:
        if incoming_block.hash == blockchain.latest_block.hash:
            return {
                "message": "Block already known",
                "index": incoming_block.index,
            }
        # Same index but different hash = tampered block
        _log_node_event(
            logging.WARNING,
            "Tampered block detected: index=%d local_hash=%s received_hash=%s",
            incoming_block.index,
            blockchain.latest_block.hash[:16],
            incoming_block.hash[:16],
        )
        raise HTTPException(
            status_code=400,
            detail=f"Rejected block: index {incoming_block.index} already exists with a different hash (possible tampering)",
        )

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
    disk_valid = True
    persisted_on_disk = storage.load()
    if persisted_on_disk:
        try:
            disk_blockchain = Blockchain.from_dict_unvalidated(persisted_on_disk)
            disk_valid = disk_blockchain.validate_chain_detailed()["valid"]
        except Exception:
            disk_valid = False

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

        if not blockchain.is_chain_valid(remote_chain):
            continue

        if remote_length > max_length or (not disk_valid and remote_length >= max_length):
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


@app.post("/chain/revalidate")
@app.get("/chain/revalidate")
def revalidate_chain() -> dict[str, Any]:
    """Read the persisted data file from disk and validate the full chain."""
    persisted_on_disk = storage.load()
    if not persisted_on_disk:
        return {"status": "invalid", "error": "no persisted chain found", "chain_length": 0, "blocks": []}

    try:
        disk_blockchain = Blockchain.from_dict_unvalidated(persisted_on_disk)
        result = disk_blockchain.validate_chain_detailed()
    except Exception as err:
        return {"status": "invalid", "error": str(err), "chain_length": 0, "blocks": []}

    status = "valid" if result["valid"] else "invalid"

    _log_node_event(
        logging.INFO if result["valid"] else logging.WARNING,
        "Chain revalidation: status=%s blocks=%d",
        status,
        len(disk_blockchain.chain),
    )

    return {
        "status": status,
        "chain_length": len(disk_blockchain.chain),
        "difficulty": disk_blockchain.difficulty,
        **result,
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
