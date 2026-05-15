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

function canonicalVoteMessage(voter_id, candidate_id, election_id) {
  return JSON.stringify({
    candidate_id: candidate_id.trim(),
    election_id: election_id.trim(),
    voter_id: voter_id.trim(),
  });
}

export function loadWallet() {
  const raw = localStorage.getItem(WALLET_STORAGE_KEY);

  if (!raw) return null;

  try {
    const wallet = JSON.parse(raw);
    if (!wallet?.voter_id || !wallet?.public_key || !wallet?.private_key) return null;
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
  const privateKeyBase64 = bytesToBase64(keyPair.secretKey);
  const voter_id = `wallet-${toUrlSafeId(publicKeyBase64).slice(0, 12)}`;

  return {
    voter_id,
    public_key: publicKeyBase64,
    private_key: privateKeyBase64,
    created_at: new Date().toISOString(),
  };
}

export function signVote(voter_id, candidate_id, election_id, private_key_b64) {
  if (!voter_id || !private_key_b64) throw new Error("Wallet and private key required to sign");

  const message = canonicalVoteMessage(voter_id, candidate_id, election_id);
  const signature = nacl.sign.detached(new TextEncoder().encode(message), base64ToBytes(private_key_b64));
  return bytesToBase64(signature);
}
