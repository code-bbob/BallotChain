from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import secrets
from time import perf_counter, time
from typing import Any
from urllib.parse import urlparse

from block import Block
from crypto_utils import verify_rsa_blind_vote_signature


@dataclass
class Blockchain:
    difficulty: int = 3
    chain: list[Block] = field(default_factory=list)
    pending_transactions: list[dict[str, Any]] = field(default_factory=list)
    nodes: set[str] = field(default_factory=set)
    # One-time invitation codes issued by admin
    registration_codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Anti-replay: nonces from already-submitted votes
    used_nonces: set[str] = field(default_factory=set)
    # Admin RSA public key for verifying blind-signed votes
    admin_n: int = 0
    admin_e: int = 0

    def __post_init__(self) -> None:
        if not self.chain:
            genesis = self._create_genesis_block()
            self.chain.append(genesis)

    def _create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            timestamp=0.0,
            transactions=[],
            previous_hash="0",
        )
        genesis.hash = genesis.calculate_hash()
        return genesis

    @property
    def latest_block(self) -> Block:
        return self.chain[-1]

    def add_vote(
        self,
        candidate_id: str,
        election_id: str,
        nonce: str,
        signature: str,
    ) -> int:
        candidate_id = candidate_id.strip()
        election_id = election_id.strip()
        nonce = nonce.strip()
        signature = signature.strip()

        if not candidate_id:
            raise ValueError("candidate_id is required")
        if not election_id:
            raise ValueError("election_id is required")
        if not nonce:
            raise ValueError("nonce is required")
        if not signature:
            raise ValueError("signature is required")
        if self.admin_n <= 0 or self.admin_e <= 0:
            raise ValueError("admin public key not configured on this node")

        if self._is_nonce_used(nonce):
            raise ValueError("vote nonce has already been used")

        if not verify_rsa_blind_vote_signature(
            candidate_id,
            election_id,
            nonce,
            signature,
            self.admin_n,
            self.admin_e,
        ):
            raise ValueError("invalid vote signature")

        if self._has_nonce(nonce, self.pending_transactions):
            raise ValueError("vote with this nonce is already pending")
        if self.has_voted_nonce(nonce):
            raise ValueError("vote with this nonce already exists in the chain")

        self.pending_transactions.append(
            {
                "candidate_id": candidate_id,
                "election_id": election_id,
                "nonce": nonce,
                "signature": signature,
            }
        )
        return self.latest_block.index + 1

    def _registration_code_hash(self, registration_code: str) -> str:
        return hashlib.sha256(registration_code.strip().encode("utf-8")).hexdigest()

    def _cleanup_expired_registration_codes(self) -> None:
        current_time = time()
        expired_hashes = [
            code_hash
            for code_hash, entry in self.registration_codes.items()
            if float(entry.get("expires_at", 0)) <= current_time
        ]
        for code_hash in expired_hashes:
            self.registration_codes.pop(code_hash, None)

    def issue_invitation_code_for(self, election_id: str | None = None, expires_in_minutes: int = 60) -> dict[str, Any]:
        self._cleanup_expired_registration_codes()

        if expires_in_minutes < 1:
            raise ValueError("expires_in_minutes must be at least 1")

        registration_code = secrets.token_urlsafe(18)
        code_hash = self._registration_code_hash(registration_code)
        while code_hash in self.registration_codes:
            registration_code = secrets.token_urlsafe(18)
            code_hash = self._registration_code_hash(registration_code)

        issued_at = time()
        expires_at = issued_at + (expires_in_minutes * 60)
        entry: dict[str, Any] = {
            "issued_at": issued_at,
            "expires_at": expires_at,
        }
        if election_id:
            entry["election_id"] = str(election_id).strip()

        self.registration_codes[code_hash] = entry

        return {
            "registration_code": registration_code,
            "election_id": entry.get("election_id"),
            "issued_at": issued_at,
            "expires_at": expires_at,
        }

    def consume_invitation_code(self, registration_code: str, election_id: str | None = None) -> dict[str, Any]:
        registration_code = registration_code.strip()
        if not registration_code:
            raise ValueError("registration_code is required")

        self._cleanup_expired_registration_codes()

        code_hash = self._registration_code_hash(registration_code)
        entry = self.registration_codes.get(code_hash)
        if not entry:
            raise ValueError("invitation code is invalid or has already been used")

        entry_election = str(entry.get("election_id", "")).strip() or None
        if election_id is not None:
            provided_election = str(election_id).strip() or None
            if entry_election != provided_election:
                raise ValueError("invitation code does not match the specified election")

        self.registration_codes.pop(code_hash, None)
        return dict(entry)

    def _is_nonce_used(self, nonce: str) -> bool:
        return nonce.strip() in self.used_nonces

    def _mark_nonce_used(self, nonce: str) -> None:
        self.used_nonces.add(nonce.strip())

    def _has_nonce(
        self,
        nonce: str,
        votes: list[dict[str, Any]] | None = None,
    ) -> bool:
        vote_list = votes if votes is not None else self.pending_transactions
        nonce = nonce.strip()

        for vote in vote_list:
            if str(vote.get("nonce", "")).strip() == nonce:
                return True

        return False

    def has_voted_nonce(self, nonce: str) -> bool:
        nonce = nonce.strip()
        for block in self.chain:
            for vote in block.transactions:
                if not isinstance(vote, dict):
                    continue
                if str(vote.get("nonce", "")).strip() == nonce:
                    return True

        return False

    def _validate_vote_record(self, vote: dict[str, Any]) -> tuple[str, str, str]:
        candidate_id = str(vote.get("candidate_id", "")).strip()
        election_id = str(vote.get("election_id", "")).strip()
        nonce = str(vote.get("nonce", "")).strip()
        signature = str(vote.get("signature", "")).strip()

        if not candidate_id or not election_id:
            raise ValueError("vote contains required empty fields")
        if not nonce:
            raise ValueError("vote is missing nonce")
        if not signature:
            raise ValueError("vote is missing signature")

        if not verify_rsa_blind_vote_signature(
            candidate_id,
            election_id,
            nonce,
            signature,
            self.admin_n,
            self.admin_e,
        ):
            raise ValueError("vote contains invalid signature")

        return candidate_id, election_id, nonce

    def proof_of_work(self, block: Block, difficulty: int | None = None) -> float:
        applied_difficulty = difficulty if difficulty is not None else self.difficulty
        start_time = perf_counter()
        block.mine_block(applied_difficulty)
        elapsed = perf_counter() - start_time
        return elapsed

    def add_block(self, block: Block) -> None:
        previous_block = self.latest_block

        if block.previous_hash != previous_block.hash:
            raise ValueError("invalid previous hash linkage")

        if block.hash != block.calculate_hash():
            raise ValueError("invalid block hash")

        if not block.hash.startswith("0" * self.difficulty):
            raise ValueError("invalid proof-of-work")

        seen_nonces_in_block: set[str] = set()
        for vote in block.transactions:
            if not isinstance(vote, dict):
                raise ValueError("block contains malformed vote")

            _, _, nonce = self._validate_vote_record(vote)

            if nonce in seen_nonces_in_block:
                raise ValueError("block contains duplicate nonce")

            if self.has_voted_nonce(nonce):
                raise ValueError("block contains nonce already present in chain")

            seen_nonces_in_block.add(nonce)

        # Mark all nonces as used
        for vote in block.transactions:
            if isinstance(vote, dict):
                nonce = str(vote.get("nonce", "")).strip()
                if nonce:
                    self._mark_nonce_used(nonce)

        self.chain.append(block)

    def mine_pending_votes(self) -> tuple[Block | None, float | None]:
        if not self.pending_transactions:
            return None, None

        block = Block(
            index=len(self.chain),
            timestamp=time(),
            transactions=self.pending_transactions.copy(),
            previous_hash=self.latest_block.hash,
        )

        mining_time = self.proof_of_work(block)
        self.add_block(block)
        self.pending_transactions.clear()
        return block, mining_time

    def mine_pending_transactions(self) -> tuple[Block | None, float | None]:
        return self.mine_pending_votes()

    def register_node(self, node_url: str) -> None:
        parsed = urlparse(node_url)
        if parsed.scheme and parsed.netloc:
            normalized = f"{parsed.scheme}://{parsed.netloc}"
        elif parsed.path:
            normalized = f"http://{parsed.path}"
        else:
            raise ValueError("invalid node URL")

        self.nodes.add(normalized.rstrip("/"))

    def is_chain_valid(self, chain: list[Block] | None = None) -> bool:
        result = self.validate_chain_detailed(chain)
        return result["valid"]

    def validate_chain_detailed(self, chain: list[Block] | None = None) -> dict[str, Any]:
        chain_to_check = chain if chain is not None else self.chain
        blocks: list[dict[str, Any]] = []

        if not chain_to_check:
            return {"valid": False, "error": "chain is empty", "blocks": []}

        genesis = chain_to_check[0]
        genesis_errors: list[str] = []
        if genesis.hash != genesis.calculate_hash():
            genesis_errors.append("genesis hash does not match calculated hash")
        if genesis.previous_hash != "0":
            genesis_errors.append("genesis previous_hash is not '0'")

        blocks.append({
            "index": genesis.index,
            "hash": genesis.hash,
            "valid": len(genesis_errors) == 0,
            "errors": genesis_errors,
        })

        if genesis_errors:
            return {"valid": False, "error": genesis_errors[0], "blocks": blocks}

        seen_nonces: set[str] = set()

        for index in range(1, len(chain_to_check)):
            current = chain_to_check[index]
            previous = chain_to_check[index - 1]
            block_errors: list[str] = []

            if current.previous_hash != previous.hash:
                block_errors.append(
                    f"previous_hash mismatch: expected {previous.hash[:16]}... got {current.previous_hash[:16]}..."
                )

            expected_hash = current.calculate_hash()
            if current.hash != expected_hash:
                block_errors.append(
                    f"block hash invalid: stored {current.hash[:16]}... != calculated {expected_hash[:16]}..."
                )

            if not current.hash.startswith("0" * self.difficulty):
                block_errors.append(
                    f"proof-of-work invalid: hash {current.hash[:16]}... does not start with {'0' * self.difficulty}"
                )

            seen_nonces_in_block: set[str] = set()
            vote_errors: list[str] = []

            for tx_idx, vote in enumerate(current.transactions):
                if not isinstance(vote, dict):
                    vote_errors.append(f"vote[{tx_idx}]: malformed (not a dict)")
                    continue

                try:
                    _, _, nonce = self._validate_vote_record(vote)
                except ValueError as err:
                    vote_errors.append(f"vote[{tx_idx}]: {err}")
                    continue

                if nonce in seen_nonces_in_block:
                    vote_errors.append(f"vote[{tx_idx}]: duplicate nonce in block")
                if nonce in seen_nonces:
                    vote_errors.append(f"vote[{tx_idx}]: nonce already present in earlier block")

                seen_nonces_in_block.add(nonce)
                seen_nonces.add(nonce)

            if vote_errors:
                block_errors.extend(vote_errors)

            blocks.append({
                "index": current.index,
                "hash": current.hash,
                "transactions": len(current.transactions),
                "valid": len(block_errors) == 0,
                "errors": block_errors,
            })

            if block_errors:
                return {
                    "valid": False,
                    "error": block_errors[0],
                    "failed_at_block": current.index,
                    "blocks": blocks,
                }

        return {"valid": True, "error": None, "blocks": blocks}

    def tally_votes(
        self,
        election_id: str,
        include_pending: bool = True,
    ) -> dict[str, int]:
        election_id = election_id.strip()
        counts: dict[str, int] = {}

        def record_votes(votes: list[dict[str, Any]]) -> None:
            for vote in votes:
                if not isinstance(vote, dict):
                    continue

                if str(vote.get("election_id", "")).strip() != election_id:
                    continue

                candidate_id = str(vote.get("candidate_id", "")).strip()
                if not candidate_id:
                    continue

                counts[candidate_id] = counts.get(candidate_id, 0) + 1

        for block in self.chain:
            record_votes(block.transactions)

        if include_pending:
            record_votes(self.pending_transactions)

        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "difficulty": self.difficulty,
            "chain": [block.to_dict() for block in self.chain],
            "pending_transactions": self.pending_transactions,
            "nodes": sorted(self.nodes),
            "registration_codes": dict(self.registration_codes),
            "used_nonces": sorted(list(self.used_nonces)),
            "admin_n": self.admin_n,
            "admin_e": self.admin_e,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Blockchain":
        chain_data = data.get("chain", [])
        parsed_chain = [Block.from_dict(item) for item in chain_data]

        instance = cls(
            difficulty=int(data.get("difficulty", 3)),
            chain=parsed_chain,
            pending_transactions=list(data.get("pending_transactions", [])),
            nodes=set(data.get("nodes", [])),
            admin_n=int(data.get("admin_n", 0)),
            admin_e=int(data.get("admin_e", 0)),
        )

        raw_used = data.get("used_nonces", [])
        if isinstance(raw_used, (list, tuple, set)):
            instance.used_nonces = {str(item).strip() for item in raw_used if str(item).strip()}

        raw_codes = dict(data.get("registration_codes", {}))
        if raw_codes:
            instance.registration_codes = raw_codes

        if not instance.is_chain_valid(instance.chain):
            raise ValueError("persisted chain is invalid")

        return instance

    @classmethod
    def from_dict_unvalidated(cls, data: dict[str, Any]) -> "Blockchain":
        """Parse a persisted chain without pre-validating it.

        Useful for revalidation endpoints that need to report detailed
        per-block errors on a potentially tampered on-disk chain.
        """
        chain_data = data.get("chain", [])
        parsed_chain = [Block.from_dict(item) for item in chain_data]

        instance = cls(
            difficulty=int(data.get("difficulty", 3)),
            chain=parsed_chain,
            pending_transactions=list(data.get("pending_transactions", [])),
            nodes=set(data.get("nodes", [])),
            admin_n=int(data.get("admin_n", 0)),
            admin_e=int(data.get("admin_e", 0)),
        )

        raw_used = data.get("used_nonces", [])
        if isinstance(raw_used, (list, tuple, set)):
            instance.used_nonces = {str(item).strip() for item in raw_used if str(item).strip()}

        raw_codes = dict(data.get("registration_codes", {}))
        if raw_codes:
            instance.registration_codes = raw_codes

        return instance
