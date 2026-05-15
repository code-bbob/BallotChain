# 5.1 Implementation

## 5.1.1 Tools and Technologies Used

### i) Frontend Architecture

**React with JavaScript ES6+**
React is used as the core framework for building a modular single-page application with separate Admin (Governance Console) and Voter (Voting Console) components. The implementation leverages React hooks (useState, useEffect, useMemo) for state management, eliminating class-based component boilerplate. The functional component pattern ensures maintainability and code reusability across the voting interface.

**Local Wallet Generation (TweetNaCl + Ed25519)**
Client-side Ed25519 keypair generation is handled using nacl.sign.keyPair.fromSeed(), ensuring that private keys are generated and stored exclusively in browser local storage and never transmitted to the server. Public keys are exported in base64 format for registration with the backend node. Vote messages are canonicalized deterministically and signed locally before submission to the backend.

**HTTP Client with Request/Response Handling**
A custom HTTP API wrapper (api.js) manages REST communication with backend nodes, providing request validation and error handling at the client level. The client handles one-time registration code submission, code consumption, vote submission, and chain synchronization requests.

**Responsive UI Without External Frameworks**
The interface uses HTML5 semantic structure with native CSS3 Grid and Flexbox for responsive layout. A custom stylesheet provides consistent theming across both Admin and Voter views. This approach eliminates dependencies on external UI libraries (Bootstrap, Tailwind, Material UI), keeping the interface implementation transparent and lightweight.

### ii) Backend Infrastructure

**FastAPI with Python 3.9+**
The backend implements RESTful API endpoints for wallet registration, vote submission, mining operations, block broadcast, and chain synchronization. Request validation is enforced using Pydantic models (VoteIn, VoterRegistrationIn, RegistrationCodeIssueIn, BlockIn, ChainSyncIn). CORS middleware enables cross-origin client requests, and Uvicorn serves as the ASGI application server.

**Ed25519 Digital Signature Implementation**
Vote authentication uses Ed25519 digital signatures via the cryptography library. Vote messages are serialized canonically (JSON with sorted keys and compact separators) to ensure deterministic signatures. The server verifies every incoming vote signature using the voter's registered public key before accepting the vote into the pending pool. Signature verification serves as a trust boundary that rejects malformed or forged votes.

**One-Time Registration Code System**
The system enforces eligibility control through one-time registration codes issued by the admin. Codes are stored as hashed values in the blockchain state and issued through a dedicated endpoint (POST /voters/codes/issue). Voters consume codes during registration (POST /voters/register with code parameter), and consumed codes are atomically deleted to enforce single-use constraint. This prevents wallet re-registration and ensures strict one-wallet-per-voter eligibility.

### iii) Custom Blockchain Implementation

**Proof-of-Work Mining Engine**
Mining is implemented as a nonce-search algorithm that iterates until a SHA256 hash satisfies a configurable difficulty target (leading zeros). Each block contains an index, timestamp, list of vote transactions, the previous block hash, a nonce, and the computed block hash. Hash linkage between sequential blocks enforces tamper detection and chain integrity. Mining execution time is measured for performance tracking.

**Vote Validation and Duplicate Prevention**
The system enforces multi-layer validation: voter registration status, public key matching, cryptographic signature verification, and per-election uniqueness. Duplicate detection operates on persistent state (blockchain.voter_registry and confirmed blocks) rather than in-memory state alone. A (voter_id, election_id) tuple registry prevents any voter from voting more than once in the same election. Pending votes are separated from mined blocks to enable atomic block creation.

**Peer-to-Peer Consensus**
Peer nodes register with each other and broadcast mined blocks across the network. The block receive endpoint validates incoming blocks before appending them to the local chain. A chain sync endpoint allows nodes to reconcile state by accepting longer valid chains. Consensus is achieved using the longest-chain rule: a longer valid chain replaces a shorter one, enabling automatic fork resolution.

**Persistence Layer**
Blockchain state is stored in JSON format (blockchain_data.json for single-node deployments, node*.json for multi-node networks). State is saved atomically after every operation: vote acceptance, voter registration, mining, block receipt, and chain synchronization. On node restart, state is recovered via the from_dict() constructor, which validates chain integrity. This filesystem-based approach requires no external database.

### iv) Cryptographic Foundation

**Ed25519 Digital Signatures**
Every vote is signed with the voter's private key before submission. The backend verifies the signature using the voter's registered public key. Signature failure results in vote rejection; malformed or forged votes never enter the pending pool. This provides non-repudiation: a voter cannot later deny having cast a specific vote.

**Canonical Vote Message Format**
Voter identity, candidate identifier, and election identifier are serialized deterministically using JSON with sorted keys and compact separators. This ensures that identical vote data always produces identical signatures, enabling reproducible verification and preventing tampering at the network layer.

### v) No External Blockchain or Crypto Platforms

This implementation is entirely self-contained and does not depend on:
- Ethereum, Bitcoin, or any public blockchain infrastructure
- MetaMask, Coinbase Wallet, or other browser-based crypto wallets
- Solidity or smart contract languages
- Web3.js, ethers.js, or other blockchain JavaScript libraries
- Third-party key management or hosting services

All cryptographic operations, block production, and consensus logic are custom-implemented using standard libraries (cryptography, hashlib, nacl) and remain fully under project control.
