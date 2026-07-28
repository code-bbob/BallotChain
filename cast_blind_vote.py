from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cast an anonymous blind-signed vote on a blockchain voting node.",
    )
    parser.add_argument("candidate_id", help="Candidate to vote for")
    parser.add_argument("--election-id", default="student-union-2026", help="Election ID (default: student-union-2026)")
    parser.add_argument(
        "--node",
        default="http://127.0.0.1:8001",
        help="Base URL of the node (default: http://127.0.0.1:8001)",
    )
    parser.add_argument(
        "--registration-code",
        required=True,
        help="One-time blind-sign invitation code issued by the admin",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )
    return parser.parse_args()


def hash_to_int_mod_n(value: str, modulus: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1


def random_coprime_below(modulus: int) -> int:
    while True:
        candidate = secrets.randbelow(modulus - 1) + 1
        if candidate < modulus and candidate > 0:
            try:
                pow(candidate, -1, modulus)
                return candidate
            except ValueError:
                continue


def main() -> int:
    args = parse_args()
    node = args.node.rstrip("/")

    # 1) Fetch admin RSA public key
    try:
        key_response = requests.get(f"{node}/voters/blind/public-key", timeout=args.timeout)
        key_response.raise_for_status()
        key_data = key_response.json()
        n = int(str(key_data.get("n", "")).strip())
        e = int(str(key_data.get("e", "")).strip())
    except Exception as error:
        print(f"Failed to fetch blind-sign key: {error}", file=sys.stderr)
        return 1

    # 2) Create vote message with random nonce
    nonce = secrets.token_hex(16)
    vote_message = json.dumps(
        {
            "candidate_id": args.candidate_id.strip(),
            "election_id": args.election_id.strip(),
            "nonce": nonce,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    # 3) Blind the vote hash
    vote_hash = hash_to_int_mod_n(vote_message, n)
    r = random_coprime_below(n)
    blinded_hash = (vote_hash * pow(r, e, n)) % n

    # 4) Request blind signature from admin
    try:
        blind_sign_response = requests.post(
            f"{node}/voters/blind/sign",
            json={
                "registration_code": args.registration_code.strip(),
                "election_id": args.election_id.strip() or None,
                "blinded_hash": str(blinded_hash),
            },
            timeout=args.timeout,
        )
    except requests.RequestException as error:
        print(f"Blind-sign request failed: {error}", file=sys.stderr)
        return 1

    if not blind_sign_response.ok:
        print(
            f"Blind-sign endpoint returned {blind_sign_response.status_code}: {blind_sign_response.text}",
            file=sys.stderr,
        )
        return 1

    # 5) Unblind the signature
    try:
        blind_signature_int = int(str(blind_sign_response.json().get("blind_signature", "")).strip(), 16)
        r_inverse = pow(r, -1, n)
        unblinded_signature = (blind_signature_int * r_inverse) % n
    except Exception as error:
        print(f"Failed to unblind signature: {error}", file=sys.stderr)
        return 1

    # Local verification
    if pow(unblinded_signature, e, n) != vote_hash:
        print("Local verification failed for unblinded vote signature", file=sys.stderr)
        return 1

    # 6) Submit anonymous vote
    try:
        vote_response = requests.post(
            f"{node}/votes",
            json={
                "candidate_id": args.candidate_id.strip(),
                "election_id": args.election_id.strip(),
                "nonce": nonce,
                "signature": hex(unblinded_signature),
            },
            timeout=args.timeout,
        )
    except requests.RequestException as error:
        print(f"Vote submission failed: {error}", file=sys.stderr)
        return 1

    if vote_response.ok:
        data = vote_response.json()
        print(data.get("message", "Anonymous vote submitted"))
        print(f"candidate={args.candidate_id}")
        print(f"election={args.election_id}")
        print(f"nonce={nonce[:16]}...")
        return 0

    print(f"Node returned {vote_response.status_code}: {vote_response.text}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
