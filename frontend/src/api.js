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

export async function castVote(baseUrl, voteInput) {
  return request(baseUrl, "/votes", {
    method: "POST",
    body: JSON.stringify(voteInput)
  });
}

export async function registerVoter(baseUrl, voterInput) {
  return request(baseUrl, "/voters/register", {
    method: "POST",
    body: JSON.stringify(voterInput)
  });
}

export async function mineVotes(baseUrl) {
  return request(baseUrl, "/mine");
}

export async function fetchElectionResults(baseUrl, electionId) {
  return request(baseUrl, `/elections/${encodeURIComponent(electionId)}/results`);
}

export async function resolveConsensus(baseUrl) {
  return request(baseUrl, "/nodes/resolve");
}

export { DEFAULT_BASE_URL };