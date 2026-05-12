from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, time
from typing import Any
from urllib.parse import urlparse

from block import Block
from crypto_utils import is_valid_public_key, verify_vote_signature


@dataclass
class Blockchain:
    difficulty: int = 3
    chain: list[Block] = field(default_factory=list)
    pending_transactions: list[dict[str, Any]] = field(default_factory=list)
    nodes: set[str] = field(default_factory=set)
    voter_registry: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chain:
            genesis = self._create_genesis_block()
            self.chain.append(genesis)

    def _create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            timestamp=time(),
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
        voter_id: str,
        candidate_id: str,
        election_id: str,
        voter_public_key: str,
        signature: str,
    ) -> int:
        voter_id = voter_id.strip()
        candidate_id = candidate_id.strip()
        election_id = election_id.strip()
        voter_public_key = voter_public_key.strip()
        signature = signature.strip()

        if not voter_id:
            raise ValueError("voter_id is required")
        if not candidate_id:
            raise ValueError("candidate_id is required")
        if not election_id:
            raise ValueError("election_id is required")
        if not voter_public_key:
            raise ValueError("voter_public_key is required")
        if not signature:
            raise ValueError("signature is required")

        registered_public_key = self.voter_registry.get(voter_id)
        if not registered_public_key:
            raise ValueError("voter is not registered")
        if registered_public_key != voter_public_key:
            raise ValueError("voter_public_key does not match registered voter key")

        known_public_key = self._public_key_for_voter(voter_id)
        if known_public_key and known_public_key != voter_public_key:
            raise ValueError("voter_id is already bound to a different public key")

        if not verify_vote_signature(
            voter_id,
            candidate_id,
            election_id,
            voter_public_key,
            signature,
        ):
            raise ValueError("invalid vote signature")

        if self._has_vote(voter_id, election_id, self.pending_transactions):
            raise ValueError("voter has already submitted a pending vote for this election")
        if self.has_voted(voter_id, election_id):
            raise ValueError("voter has already voted in this election")

        self.pending_transactions.append(
            {
                "voter_id": voter_id,
                "candidate_id": candidate_id,
                "election_id": election_id,
                "voter_public_key": voter_public_key,
                "signature": signature,
                "timestamp": time(),
            }
        )
        return self.latest_block.index + 1

    def register_voter(self, voter_id: str, voter_public_key: str) -> None:
        voter_id = voter_id.strip()
        voter_public_key = voter_public_key.strip()

        if not voter_id:
            raise ValueError("voter_id is required")
        if not voter_public_key:
            raise ValueError("voter_public_key is required")
        if not is_valid_public_key(voter_public_key):
            raise ValueError("voter_public_key is not a valid Ed25519 key")

        existing_public_key = self.voter_registry.get(voter_id)
        if existing_public_key and existing_public_key != voter_public_key:
            raise ValueError("voter_id is already registered with a different public key")

        self.voter_registry[voter_id] = voter_public_key

    def add_transaction(self, sender: str, receiver: str, amount: float) -> int:
        raise ValueError(
            "Legacy transaction API is disabled. Use signed votes via add_vote().",
        )

    def _public_key_for_voter(self, voter_id: str) -> str | None:
        for vote in self.pending_transactions:
            if not isinstance(vote, dict):
                continue
            if str(vote.get("voter_id", "")).strip() == voter_id:
                public_key = str(vote.get("voter_public_key", "")).strip()
                if public_key:
                    return public_key

        for block in self.chain:
            for vote in block.transactions:
                if not isinstance(vote, dict):
                    continue
                if str(vote.get("voter_id", "")).strip() == voter_id:
                    public_key = str(vote.get("voter_public_key", "")).strip()
                    if public_key:
                        return public_key

        return None

    def _validate_vote_record(self, vote: dict[str, Any]) -> tuple[str, str, str, str]:
        voter_id = str(vote.get("voter_id", "")).strip()
        candidate_id = str(vote.get("candidate_id", "")).strip()
        election_id = str(vote.get("election_id", "")).strip()
        voter_public_key = str(vote.get("voter_public_key", "")).strip()
        signature = str(vote.get("signature", "")).strip()

        if not voter_id or not candidate_id or not election_id:
            raise ValueError("vote contains required empty fields")
        if not voter_public_key:
            raise ValueError("vote is missing voter_public_key")
        if not signature:
            raise ValueError("vote is missing signature")

        if not verify_vote_signature(
            voter_id,
            candidate_id,
            election_id,
            voter_public_key,
            signature,
        ):
            raise ValueError("vote contains invalid signature")

        return voter_id, candidate_id, election_id, voter_public_key

    def _has_vote(
        self,
        voter_id: str,
        election_id: str,
        votes: list[dict[str, Any]] | None = None,
    ) -> bool:
        vote_list = votes if votes is not None else self.pending_transactions

        for vote in vote_list:
            if (
                str(vote.get("voter_id", "")).strip() == voter_id
                and str(vote.get("election_id", "")).strip() == election_id
            ):
                return True

        return False

    def has_voted(self, voter_id: str, election_id: str) -> bool:
        for block in self.chain:
            for vote in block.transactions:
                if not isinstance(vote, dict):
                    continue
                if (
                    str(vote.get("voter_id", "")).strip() == voter_id
                    and str(vote.get("election_id", "")).strip() == election_id
                ):
                    return True

        return False

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

        seen_votes_in_block: set[tuple[str, str]] = set()
        for vote in block.transactions:
            if not isinstance(vote, dict):
                raise ValueError("block contains malformed vote")

            voter_id, _, election_id, voter_public_key = self._validate_vote_record(vote)
            vote_key = (voter_id, election_id)

            registered_public_key = self.voter_registry.get(voter_id)
            if not registered_public_key:
                raise ValueError("block contains vote for unregistered voter")
            if registered_public_key != voter_public_key:
                raise ValueError("block contains vote with key not matching voter registry")

            if vote_key in seen_votes_in_block:
                raise ValueError("block contains duplicate vote by same voter in election")

            known_public_key = self._public_key_for_voter(voter_id)
            if known_public_key and known_public_key != voter_public_key:
                raise ValueError("block contains voter with mismatched public key")

            if self.has_voted(voter_id, election_id):
                raise ValueError("block contains vote already present in chain")

            seen_votes_in_block.add(vote_key)

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
        #naya block create hanxa, ani proof of work apply garda hash calculate garxa, ani block ma hash set garxa, ani block add garxa, ani pending transactions clear garxa

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
        chain_to_check = chain if chain is not None else self.chain

        if not chain_to_check:
            return False

        genesis = chain_to_check[0]
        if genesis.hash != genesis.calculate_hash():
            return False
        if genesis.previous_hash != "0":
            return False

        seen_votes_chain: set[tuple[str, str]] = set()
        voter_key_map: dict[str, str] = dict(self.voter_registry)

        for index in range(1, len(chain_to_check)):
            current = chain_to_check[index]
            previous = chain_to_check[index - 1]

            if current.previous_hash != previous.hash:
                return False

            if current.hash != current.calculate_hash():
                return False

            if not current.hash.startswith("0" * self.difficulty):
                return False

            seen_votes_in_block: set[tuple[str, str]] = set()

            for vote in current.transactions:
                if not isinstance(vote, dict):
                    return False

                try:
                    voter_id, _, election_id, voter_public_key = self._validate_vote_record(vote)
                except ValueError:
                    return False

                vote_key = (voter_id, election_id)

                if vote_key in seen_votes_in_block:
                    return False

                if vote_key in seen_votes_chain:
                    return False

                registered_public_key = self.voter_registry.get(voter_id)
                if not registered_public_key:
                    return False
                if registered_public_key != voter_public_key:
                    return False

                stored_public_key = voter_key_map.get(voter_id)
                if stored_public_key != voter_public_key:
                    return False
                voter_key_map[voter_id] = voter_public_key
                seen_votes_in_block.add(vote_key)
                seen_votes_chain.add(vote_key)

        return True

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
            "voter_registry": dict(sorted(self.voter_registry.items())),
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
            voter_registry={
                str(voter_id).strip(): str(public_key).strip()
                for voter_id, public_key in dict(data.get("voter_registry", {})).items()
                if str(voter_id).strip() and str(public_key).strip()
            },
        )

        if not instance.voter_registry:
            for block in instance.chain:
                for vote in block.transactions:
                    if not isinstance(vote, dict):
                        continue
                    voter_id = str(vote.get("voter_id", "")).strip()
                    voter_public_key = str(vote.get("voter_public_key", "")).strip()
                    if voter_id and voter_public_key:
                        instance.voter_registry[voter_id] = voter_public_key

        for voter_id, public_key in instance.voter_registry.items():
            if not is_valid_public_key(public_key):
                raise ValueError(f"invalid voter key in registry for {voter_id}")

        if not instance.is_chain_valid(instance.chain):
            raise ValueError("persisted chain is invalid")

        return instance
