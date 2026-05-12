import nacl from "tweetnacl";

const WALLET_STORAGE_KEY = "blockchain-voting-wallet";

function bytesToBase64(bytes) {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function toUrlSafeId(value) {
  return value.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function canonicalVoteMessage(voterId, candidateId, electionId) {
  return JSON.stringify({
    candidate_id: candidateId.trim(),
    election_id: electionId.trim(),
    voter_id: voterId.trim()
  });
}

export function loadWallet() {
  const raw = localStorage.getItem(WALLET_STORAGE_KEY);

  if (!raw) {
    return null;
  }

  try {
    const wallet = JSON.parse(raw);
    if (!wallet?.voterId || !wallet?.publicKey || !wallet?.secretKey) {
      return null;
    }
    return wallet;
  } catch {
    return null;
  }
}

export function saveWallet(wallet) {
  localStorage.setItem(WALLET_STORAGE_KEY, JSON.stringify(wallet));
}

export function clearWallet() {
  localStorage.removeItem(WALLET_STORAGE_KEY);
}

export function createWallet() {
  const seed = nacl.randomBytes(32);
  const keyPair = nacl.sign.keyPair.fromSeed(seed);
  const publicKeyBase64 = bytesToBase64(keyPair.publicKey);
  const secretKeyBase64 = bytesToBase64(keyPair.secretKey);
  const voterId = `wallet-${toUrlSafeId(publicKeyBase64).slice(0, 12)}`;

  return {
    voterId,
    publicKey: publicKeyBase64,
    secretKey: secretKeyBase64,
    createdAt: new Date().toISOString()
  };
}

export function signVote(wallet, candidateId, electionId) {
  if (!wallet) {
    throw new Error("Wallet is required to sign a vote");
  }

  const message = canonicalVoteMessage(wallet.voterId, candidateId, electionId);
  const signature = nacl.sign.detached(
    new TextEncoder().encode(message),
    base64ToBytes(wallet.secretKey)
  );

  return bytesToBase64(signature);
}
