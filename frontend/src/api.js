const DEFAULT_BASE_URL = "http://127.0.0.1:8001";

function buildUrl(baseUrl, path) {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return { message: text || "Unexpected non-JSON response" };
}

async function request(baseUrl, path, options = {}) {
  const hasBody = options.body !== undefined && options.body !== null;

  const response = await fetch(buildUrl(baseUrl, path), {
    ...options,
    headers: {
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  });

  const payload = await parseResponse(response);

  if (!response.ok) {
    const message = payload?.detail || payload?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

export async function fetchChain(baseUrl = DEFAULT_BASE_URL) {
  return request(baseUrl, "/chain");
}

export async function fetchVoters(baseUrl = DEFAULT_BASE_URL) {
  return request(baseUrl, "/voters");
}

export async function issueRegistrationCode(baseUrl, payload, adminToken = "") {
  const headers = adminToken
    ? { Authorization: `Bearer ${adminToken}`, "X-Admin-Token": adminToken }
    : {};
  return request(baseUrl, "/voters/codes/issue", {
    method: "POST",
    headers,
    body: JSON.stringify(payload)
  });
}

export async function castVote(baseUrl, voteInput) {
  return request(baseUrl, "/votes", {
    method: "POST",
    body: JSON.stringify(voteInput)
  });
}

export async function fetchBlindPublicKey(baseUrl = DEFAULT_BASE_URL) {
  return request(baseUrl, "/voters/blind/public-key");
}

export async function requestBlindSignature(baseUrl, payload) {
  return request(baseUrl, "/voters/blind/sign", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function mineVotes(baseUrl, adminToken = "") {
  const headers = adminToken
    ? { Authorization: `Bearer ${adminToken}`, "X-Admin-Token": adminToken }
    : {};
  return request(baseUrl, "/mine", {
    method: "GET",
    headers
  });
}

export async function mineCluster(baseUrl, limit = 100, difficulty = null, adminToken = "") {
  const headers = adminToken
    ? { Authorization: `Bearer ${adminToken}`, "X-Admin-Token": adminToken }
    : {};
  const qs = `?limit=${encodeURIComponent(limit)}${
    difficulty !== null && difficulty !== undefined ? `&difficulty=${encodeURIComponent(difficulty)}` : ""
  }`;
  return request(baseUrl, `/mine/cluster${qs}`, {
    method: "POST",
    headers,
  });
}

export async function fetchElectionResults(baseUrl, electionId) {
  return request(baseUrl, `/elections/${encodeURIComponent(electionId)}/results`);
}

export async function revalidateChain(baseUrl = DEFAULT_BASE_URL) {
  return request(baseUrl, "/chain/revalidate");
}

export async function resolveConsensus(baseUrl) {
  return request(baseUrl, "/nodes/resolve");
}

export async function broadcastToNetwork(baseUrl, adminToken = "") {
  const headers = adminToken
    ? { Authorization: `Bearer ${adminToken}`, "X-Admin-Token": adminToken }
    : {};
  return request(baseUrl, "/broadcast", {
    method: "POST",
    headers
  });
}

export async function createElection(baseUrl, electionId, adminToken = "") {
  const headers = adminToken
    ? { Authorization: `Bearer ${adminToken}`, "X-Admin-Token": adminToken }
    : {};
  return request(baseUrl, "/elections", {
    method: "POST",
    headers,
    body: JSON.stringify({ election_id: electionId })
  });
}

export async function adminLogin(baseUrl, username, password, expiresInMinutes = 60) {
  return request(baseUrl, "/admin/login", {
    method: "POST",
    body: JSON.stringify({ username, password, expires_in_minutes: expiresInMinutes }),
  });
}

export { DEFAULT_BASE_URL };