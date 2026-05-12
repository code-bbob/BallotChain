from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: list[dict[str, Any]]
    previous_hash: str
    nonce: int = 0
    hash: str = field(default="")

    def calculate_hash(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def mine_block(self, difficulty: int) -> None:
        target = "0" * difficulty
        self.hash = self.calculate_hash()
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Block":
        return cls(
            index=int(data["index"]),
            timestamp=float(data["timestamp"]),
            transactions=list(data.get("transactions", [])),
            previous_hash=str(data["previous_hash"]),
            nonce=int(data.get("nonce", 0)),
            hash=str(data.get("hash", "")),
        )
