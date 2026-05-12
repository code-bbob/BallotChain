from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value.strip(), validate=True)
    except Exception as error:  # pragma: no cover - defensive decode wrapper
        raise ValueError("Invalid base64 value") from error


def canonical_vote_message(voter_id: str, candidate_id: str, election_id: str) -> bytes:
    payload = {
        "candidate_id": candidate_id.strip(),
        "election_id": election_id.strip(),
        "voter_id": voter_id.strip(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def public_key_from_private_key(private_key_b64: str) -> str:
    private_key_bytes = _decode_base64(private_key_b64)
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(public_key_bytes).decode("ascii")


def sign_vote(
    voter_id: str,
    candidate_id: str,
    election_id: str,
    private_key_b64: str,
) -> str:
    private_key_bytes = _decode_base64(private_key_b64)
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    signature = private_key.sign(
        canonical_vote_message(voter_id, candidate_id, election_id),
    )
    return base64.b64encode(signature).decode("ascii")


def verify_vote_signature(
    voter_id: str,
    candidate_id: str,
    election_id: str,
    public_key_b64: str,
    signature_b64: str,
) -> bool:
    try:
        public_key_bytes = _decode_base64(public_key_b64)
        signature_bytes = _decode_base64(signature_b64)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(
            signature_bytes,
            canonical_vote_message(voter_id, candidate_id, election_id),
        )
        return True
    except Exception:
        return False


def is_valid_public_key(public_key_b64: str) -> bool:
    try:
        public_key_bytes = _decode_base64(public_key_b64)
        Ed25519PublicKey.from_public_bytes(public_key_bytes)
        return True
    except Exception:
        return False


def generate_wallet_keys() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    return (
        base64.b64encode(private_key_bytes).decode("ascii"),
        base64.b64encode(public_key_bytes).decode("ascii"),
    )
