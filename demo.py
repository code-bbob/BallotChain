#!/usr/bin/env python3
"""
TrueVote Demo Script
Demonstrates end-to-end voting workflow from registration to vote tally
"""

import requests
import hashlib
import secrets
import json
from crypto_utils import sign_vote, public_key_from_private_key

BASE_URL = "http://127.0.0.1:8001"


def hash_to_int_mod_n(value: str, modulus: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    hashed = int.from_bytes(digest, byteorder="big") % modulus
    return hashed if hashed > 0 else 1


def random_coprime_below(modulus: int) -> int:
    while True:
        candidate = secrets.randbelow(modulus - 1) + 1
        try:
            pow(candidate, -1, modulus)
            return candidate
        except ValueError:
            continue

def demo():
    print("\n" + "="*60)
    print("TrueVote Blockchain Voting - Demo Workflow")
    print("="*60 + "\n")
    
    # Create test wallets (simulating voter registration)
    print("1. CREATING VOTER WALLETS")
    print("-" * 40)
    
    voters = {}
    for voter_num in range(1, 4):
        import os
        private_key_bytes = os.urandom(32)
        import base64
        private_key_b64 = base64.b64encode(private_key_bytes).decode("ascii")
        public_key = public_key_from_private_key(private_key_b64)
        voter_id = f"V{voter_num:03d}"
        
        voters[voter_id] = {
            "private_key": private_key_b64,
            "public_key": public_key,
        }
        
        print(f"  {voter_id}: Generated keypair")
    
    # Authenticate admin for issuing registration codes (default local creds)
    print("\n2. ADMIN AUTHENTICATION")
    print("-" * 40)

    token = ""
    login_response = requests.post(
        f"{BASE_URL}/admin/login",
        json={"username": "admin", "password": "admin123", "expires_in_minutes": 60},
    )
    if login_response.status_code == 200:
        token = login_response.json().get("access_token", "")
        print("  ✓ Admin login success")
    else:
        print("  ✗ Admin login failed; cannot issue registration codes")
        print(f"    {login_response.text}")
        return

    # Fetch blind-sign public key once
    blind_key_response = requests.get(f"{BASE_URL}/voters/blind/public-key")
    if blind_key_response.status_code != 200:
        print(f"  ✗ Could not fetch blind-sign key: {blind_key_response.text}")
        return

    blind_key = blind_key_response.json()
    n = int(str(blind_key.get("n", "")).strip())
    e = int(str(blind_key.get("e", "")).strip())

    # Register voters using blind-signature workflow
    print("\n3. REGISTERING VOTERS (BLIND-SIGN)")
    print("-" * 40)
    
    for voter_id, keys in voters.items():
        issue_response = requests.post(
            f"{BASE_URL}/voters/codes/issue",
            json={
                "election_id": "student-union-2026",
                "expires_in_minutes": 60,
            },
            headers={"Authorization": f"Bearer {token}", "X-Admin-Token": token},
        )
        if issue_response.status_code != 200:
            print(f"  {voter_id}: ✗ code issue failed: {issue_response.text}")
            continue

        registration_code = issue_response.json().get("registration_code", "")
        serial_payload = {
            "v": 1,
            "election_id": "student-union-2026",
            "nonce": secrets.token_hex(16),
        }
        blind_serial = json.dumps(serial_payload, sort_keys=True, separators=(",", ":"))
        serial_hash = hash_to_int_mod_n(blind_serial, n)
        r = random_coprime_below(n)
        blinded_hash = (serial_hash * pow(r, e, n)) % n

        blind_sign_response = requests.post(
            f"{BASE_URL}/voters/blind/sign",
            json={
                "registration_code": registration_code,
                "election_id": "student-union-2026",
                "blinded_hash": str(blinded_hash),
            },
        )
        if blind_sign_response.status_code != 200:
            print(f"  {voter_id}: ✗ blind sign failed: {blind_sign_response.text}")
            continue

        blind_signature_hex = str(blind_sign_response.json().get("blind_signature", "")).strip()
        blind_signature_int = int(blind_signature_hex, 16)
        unblinded_signature = (blind_signature_int * pow(r, -1, n)) % n

        if pow(unblinded_signature, e, n) != serial_hash:
            print(f"  {voter_id}: ✗ local blind-sign verification failed")
            continue

        register_response = requests.post(
            f"{BASE_URL}/voters/register",
            json={
                "voter_id": voter_id,
                "voter_public_key": keys["public_key"],
                "election_id": "student-union-2026",
                "blind_serial": blind_serial,
                "blind_signature": str(unblinded_signature),
            },
        )

        if register_response.status_code == 200:
            print(f"  {voter_id}: ✓ Registered (blind-sign)")
        else:
            print(f"  {voter_id}: ✗ {register_response.text}")
    
    # Cast votes
    print("\n4. CASTING VOTES")
    print("-" * 40)
    
    votes = [
        ("V001", "Alice", "student-union-2026"),
        ("V002", "Bob", "student-union-2026"),
        ("V003", "Alice", "student-union-2026"),
        ("V001", "Bob", "board-election-2026"),
    ]
    
    for voter_id, candidate_id, election_id in votes:
        if voter_id not in voters:
            continue
        
        private_key = voters[voter_id]["private_key"]
        public_key = voters[voter_id]["public_key"]
        
        signature = sign_vote(voter_id, candidate_id, election_id, private_key)
        
        response = requests.post(
            f"{BASE_URL}/votes",
            json={
                "voter_id": voter_id,
                "candidate_id": candidate_id,
                "election_id": election_id,
                "voter_public_key": public_key,
                "signature": signature,
            }
        )
        
        if response.status_code == 200:
            print(f"  {voter_id} → {candidate_id} ({election_id}): ✓ Submitted")
        else:
            print(f"  {voter_id} → {candidate_id}: ✗ {response.json().get('detail', 'Error')}")
    
    # Get pending votes
    print("\n5. PENDING VOTES STATUS")
    print("-" * 40)
    
    response = requests.get(f"{BASE_URL}/chain")
    chain_data = response.json()
    pending_count = chain_data.get("pending_votes", 0)
    print(f"  Pending votes: {pending_count}")
    print(f"  Chain length: {len(chain_data.get('chain', []))}")
    
    # Mine block
    print("\n6. MINING BLOCK")
    print("-" * 40)
    
    response = requests.post(f"{BASE_URL}/mine/cluster?limit=100")
    if response.status_code == 200:
        mining_result = response.json()
        local = mining_result.get("local", mining_result)
        print(f"  ✓ {mining_result.get('message', 'cluster mining complete')}")
        print(f"    Hash: {local.get('hash', '')[:16]}...")
        print(f"    Nonce: {local.get('nonce')}")
        print(f"    Mining time: {local.get('mining_time_seconds', 0):.4f}s")
        print(f"    Votes in block: {len(local.get('votes', []))}")
    else:
        print(f"  ✗ Mining failed: {response.text}")
    
    # Get results
    print("\n7. ELECTION RESULTS")
    print("-" * 40)
    
    for election_id in ["student-union-2026", "board-election-2026"]:
        response = requests.get(f"{BASE_URL}/elections/{election_id}/results")
        if response.status_code == 200:
            results = response.json()
            print(f"\n  {election_id}:")
            print(f"    Total votes: {results['total_votes']}")
            for candidate, votes in sorted(results['results'].items()):
                print(f"      {candidate}: {votes} votes")
    
    # Display voter registry
    print("\n8. VOTER REGISTRY")
    print("-" * 40)
    
    response = requests.get(f"{BASE_URL}/voters")
    if response.status_code == 200:
        voters_data = response.json()
        print(f"  Registered voters: {voters_data['registered_voters']}")
        for voter_id in voters_data['voter_ids']:
            print(f"    - {voter_id}")
    
    # Display blockchain
    print("\n9. BLOCKCHAIN STATE")
    print("-" * 40)
    
    response = requests.get(f"{BASE_URL}/chain")
    chain_data = response.json()
    print(f"  Chain length: {len(chain_data['chain'])}")
    print(f"  Difficulty: {chain_data['difficulty']}")
    print(f"  Connected peers: {len(chain_data['nodes'])}")
    print(f"  Pending votes: {chain_data['pending_votes']}")
    
    print(f"\n  Recent blocks:")
    for block in chain_data['chain'][-3:]:
        print(f"    Block #{block['index']}: {len(block['transactions'])} votes, Hash: {block['hash'][:16]}...")
    
    print("\n" + "="*60)
    print("Demo Complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        demo()
    except requests.ConnectionError:
        print("ERROR: Cannot connect to backend at", BASE_URL)
        print("Make sure the FastAPI server is running:")
        print("  DIFFICULTY=3 uvicorn main:app --host 127.0.0.1 --port 8001")
    except Exception as e:
        print(f"ERROR: {e}")
