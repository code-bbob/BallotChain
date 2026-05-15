#!/usr/bin/env python3
"""
TrueVote Demo Script
Demonstrates end-to-end voting workflow from registration to vote tally
"""

import requests
import json
from pathlib import Path
from crypto_utils import sign_vote, public_key_from_private_key, canonical_vote_message

BASE_URL = "http://127.0.0.1:8001"

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
    
    # Register voters
    print("\n2. REGISTERING VOTERS")
    print("-" * 40)
    
    for voter_id, keys in voters.items():
        response = requests.post(
            f"{BASE_URL}/voters/register",
            json={
                "voter_id": voter_id,
                "voter_public_key": keys["public_key"],
            }
        )
        if response.status_code == 200:
            print(f"  {voter_id}: ✓ Registered")
        else:
            print(f"  {voter_id}: ✗ {response.text}")
    
    # Cast votes
    print("\n3. CASTING VOTES")
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
    print("\n4. PENDING VOTES STATUS")
    print("-" * 40)
    
    response = requests.get(f"{BASE_URL}/chain")
    chain_data = response.json()
    pending_count = chain_data.get("pending_votes", 0)
    print(f"  Pending votes: {pending_count}")
    print(f"  Chain length: {len(chain_data.get('chain', []))}")
    
    # Mine block
    print("\n5. MINING BLOCK")
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
    print("\n6. ELECTION RESULTS")
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
    print("\n7. VOTER REGISTRY")
    print("-" * 40)
    
    response = requests.get(f"{BASE_URL}/voters")
    if response.status_code == 200:
        voters_data = response.json()
        print(f"  Registered voters: {voters_data['registered_voters']}")
        for voter_id in voters_data['voter_ids']:
            print(f"    - {voter_id}")
    
    # Display blockchain
    print("\n8. BLOCKCHAIN STATE")
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
