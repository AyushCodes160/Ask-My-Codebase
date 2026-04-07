// ============================================================
// FILE: frontend/src/api.js
// PURPOSE: Fetch wrappers for the FastAPI backend endpoints.
// ============================================================

const API_URL = "http://localhost:8000";

/**
 * Load a GitHub repository — clones it and builds the FAISS index.
 *
 * @param {string} repoUrl - Full GitHub URL (e.g., "https://github.com/user/repo")
 * @param {boolean} forceReclone - If true, delete existing clone and re-clone
 * @returns {Promise<object>} Response from /load_repo
 */
export async function loadRepo(repoUrl, forceReclone = false) {
  const res = await fetch(`${API_URL}/load_repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      force_reclone: forceReclone,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to load repository");
  }

  return res.json();
}

/**
 * Ask a question about the loaded codebase.
 *
 * @param {string} question - The user's question
 * @returns {Promise<object>} Response from /ask
 */
export async function askQuestion(question, history = []) {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to get answer");
  }

  return res.json();
}

/**
 * Get the backend status — index loaded, model loaded, chunk count.
 *
 * @returns {Promise<object>} Response from /status
 */
export async function getStatus() {
  const res = await fetch(`${API_URL}/status`);
  if (!res.ok) throw new Error("Backend not reachable");
  return res.json();
}
