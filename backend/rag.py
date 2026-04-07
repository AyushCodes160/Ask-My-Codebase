# ============================================================
# FILE: backend/rag.py
# PURPOSE: Retrieve relevant code chunks from the FAISS vector
#          index using semantic similarity search.
# ============================================================

import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


# ── Configuration ────────────────────────────────────────────
INDEX_DIR   = "faiss_index"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── Module-level singletons (loaded once, reused every call) ─
_faiss_index = None
_metadata    = None
_embed_model = None


def _load_resources():
    """
    Load the FAISS index, metadata, and embedding model into
    module-level variables. Called automatically on the first
    retrieve() call.

    Raises:
        FileNotFoundError: If the FAISS index doesn't exist yet.
    """
    global _faiss_index, _metadata, _embed_model

    index_path    = os.path.join(INDEX_DIR, "index.faiss")
    metadata_path = os.path.join(INDEX_DIR, "metadata.json")

    # Check files exist
    if not os.path.isfile(index_path):
        raise FileNotFoundError(
            f"FAISS index not found at '{index_path}'. "
            "Load a repository first via /load_repo."
        )
    if not os.path.isfile(metadata_path):
        raise FileNotFoundError(
            f"Metadata not found at '{metadata_path}'. "
            "Load a repository first via /load_repo."
        )

    # Load FAISS index
    _faiss_index = faiss.read_index(index_path)

    # Load metadata
    with open(metadata_path, "r", encoding="utf-8") as f:
        _metadata = json.load(f)

    # Load embedding model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL)

    print(f"[RAG] Index loaded — {_faiss_index.ntotal} vectors, "
          f"{len(_metadata)} metadata entries.")


def reload_index():
    """
    Force-reload the FAISS index and metadata.
    Call this after ingesting a new repository.
    """
    global _faiss_index, _metadata
    _faiss_index = None
    _metadata    = None
    _load_resources()


def retrieve(question: str, top_k: int = 2) -> list[dict]:
    """
    Retrieve the top-k most relevant code chunks for a question.

    Steps:
        1. Convert the question into an embedding vector.
        2. Search the FAISS index for nearest neighbors.
        3. Return the matching chunks with metadata and scores.

    Args:
        question: The user's natural language question.
        top_k:    Number of top results to return (default: 5).

    Returns:
        List of dicts, each containing:
            - file_path:  Relative path to the source file.
            - chunk_text: The actual code chunk.
            - score:      Cosine similarity score (higher = more relevant).
    """
    global _faiss_index, _metadata, _embed_model

    # Lazy load resources on first call
    if _faiss_index is None:
        _load_resources()

    # ── Step 1: Embed the question ────────────────────────────
    query_vector = _embed_model.encode(
        [question],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    faiss.normalize_L2(query_vector)

    # ── Step 2: Search FAISS ──────────────────────────────────
    scores, indices = _faiss_index.search(query_vector, top_k)

    # ── Step 3: Build results ─────────────────────────────────
    results = []
    for i, idx in enumerate(indices[0]):
        if idx == -1:  # FAISS returns -1 for empty slots
            continue
        meta = _metadata[idx]
        results.append({
            "file_path":  meta["file_path"],
            "chunk_text": meta["chunk_text"],
            "score":      float(scores[0][i]),
        })

    return results


def get_chunk_count() -> int:
    """Return the number of chunks in the loaded index."""
    global _faiss_index
    if _faiss_index is None:
        _load_resources()
    return _faiss_index.ntotal


# ── Self-test ─────────────────────────────────────────────────
if __name__ == "__main__":
    test_question = "How does the main function work?"
    print(f"Testing retrieval for: '{test_question}'\n")
    try:
        results = retrieve(test_question, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"--- Result {i} (score: {r['score']:.4f}) ---")
            print(f"File: {r['file_path']}")
            print(f"Code:\n{r['chunk_text'][:300]}...\n")
    except FileNotFoundError as e:
        print(f"Error: {e}")
