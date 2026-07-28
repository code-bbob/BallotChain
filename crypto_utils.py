from __future__ import annotations

import hashlib
import json


def canonical_vote_message(candidate_id: str, election_id: str, nonce: str) -> bytes:
    payload = {
        "candidate_id": candidate_id.strip(),
        "election_id": election_id.strip(),
        "nonce": nonce.strip(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hash_vote_to_modulus(
    candidate_id: str,
    election_id: str,
    nonce: str,
    modulus: int,
) -> int:
    message = canonical_vote_message(candidate_id, election_id, nonce)
    digest = hashlib.sha256(message).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1


def verify_rsa_blind_vote_signature(
    candidate_id: str,
    election_id: str,
    nonce: str,
    signature_hex: str,
    n: int,
    e: int,
) -> bool:
    try:
        signature = int(signature_hex, 16)
        target_hash = hash_vote_to_modulus(candidate_id, election_id, nonce, n)
        recovered_hash = pow(signature, e, n)
        return recovered_hash == target_hash
    except Exception:
        return False
