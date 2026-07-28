function bytesToHex(bytes) {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function gcd(a, b) {
  let x = a;
  let y = b;
  while (y !== 0n) {
    const temp = x % y;
    x = y;
    y = temp;
  }
  return x;
}

function modPow(base, exponent, modulus) {
  if (modulus === 1n) return 0n;

  let result = 1n;
  let b = ((base % modulus) + modulus) % modulus;
  let e = exponent;

  while (e > 0n) {
    if ((e & 1n) === 1n) {
      result = (result * b) % modulus;
    }
    b = (b * b) % modulus;
    e >>= 1n;
  }

  return result;
}

function modInverse(value, modulus) {
  let t = 0n;
  let newT = 1n;
  let r = modulus;
  let newR = ((value % modulus) + modulus) % modulus;

  while (newR !== 0n) {
    const quotient = r / newR;
    [t, newT] = [newT, t - quotient * newT];
    [r, newR] = [newR, r - quotient * newR];
  }

  if (r !== 1n) {
    throw new Error("No modular inverse for blinding factor");
  }

  if (t < 0n) {
    t += modulus;
  }

  return t;
}

function randomBigIntBelow(maxExclusive) {
  if (maxExclusive <= 1n) {
    throw new Error("Invalid upper bound for random bigint generation");
  }

  const bitLength = maxExclusive.toString(2).length;
  const byteLength = Math.ceil(bitLength / 8);

  while (true) {
    const randomBytes = new Uint8Array(byteLength);
    crypto.getRandomValues(randomBytes);
    const randomValue = BigInt(`0x${bytesToHex(randomBytes)}`);
    if (randomValue > 0n && randomValue < maxExclusive) {
      return randomValue;
    }
  }
}

export async function sha256ToBigInt(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return BigInt(`0x${bytesToHex(new Uint8Array(digest))}`);
}

export function createBlindVoteMessage(candidate_id, election_id) {
  const nonceBytes = new Uint8Array(16);
  crypto.getRandomValues(nonceBytes);
  const nonce = bytesToHex(nonceBytes);
  const payload = {
    candidate_id: (candidate_id || "").trim(),
    election_id: (election_id || "").trim(),
    nonce,
  };
  return JSON.stringify(payload);
}

export async function createBlindVoteRequest(voteMessage, rsaPublicKey) {
  const n = BigInt(rsaPublicKey.n);
  const e = BigInt(rsaPublicKey.e);
  const voteHash = (await sha256ToBigInt(voteMessage)) % n;
  const targetHash = voteHash === 0n ? 1n : voteHash;

  let r = 0n;
  do {
    r = randomBigIntBelow(n);
  } while (gcd(r, n) !== 1n);

  const blindedHash = (targetHash * modPow(r, e, n)) % n;
  return {
    blinded_hash_hex: blindedHash.toString(16),
    r_hex: r.toString(16),
    vote_hash_hex: targetHash.toString(16),
  };
}

export function unblindVoteSignature(blindSignatureHex, rHex, rsaPublicKey) {
  const n = BigInt(rsaPublicKey.n);
  const blindSignature = BigInt(`0x${blindSignatureHex}`);
  const r = BigInt(`0x${rHex}`);
  const rInverse = modInverse(r, n);
  const signature = (blindSignature * rInverse) % n;
  return signature.toString(16);
}

export async function verifyBlindVoteSignature(voteMessage, signatureHex, rsaPublicKey) {
  const n = BigInt(rsaPublicKey.n);
  const e = BigInt(rsaPublicKey.e);
  const signature = BigInt(`0x${signatureHex}`);
  const voteHash = (await sha256ToBigInt(voteMessage)) % n;
  const targetHash = voteHash === 0n ? 1n : voteHash;
  const recoveredHash = modPow(signature, e, n);
  return recoveredHash === targetHash;
}

// Utility: parse nonce from a vote message JSON
export function parseNonceFromVoteMessage(voteMessage) {
  try {
    const parsed = JSON.parse(voteMessage);
    return parsed.nonce || "";
  } catch {
    return "";
  }
}
