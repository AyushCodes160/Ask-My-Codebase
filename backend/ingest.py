# ============================================================
# FILE: backend/ingest.py
# PURPOSE: Read source code files from a cloned repo, chunk them,
#          embed with SentenceTransformers, and store in a FAISS
#          index with metadata for fast retrieval.
# RUN: python ingest.py
# ============================================================

import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


# ── Configuration ────────────────────────────────────────────
INDEX_DIR      = "faiss_index"       # folder to save FAISS index + metadata
CHUNK_LINES    = 400                 # target lines per chunk
OVERLAP_LINES  = 50                  # line overlap between consecutive chunks
BATCH_SIZE     = 32                  # embedding batch size (controls RAM usage)
EMBED_MODEL    = "sentence-transformers/all-MiniLM-L6-v2"

# File extensions we want to index
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}

# Directories to skip (these are usually not useful for understanding code)
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", "env",
    ".venv", "dist", "build", ".next", ".nuxt", "coverage",
    ".tox", ".mypy_cache", ".pytest_cache", "egg-info",
    "static", "assets", "public", ".output", "out",
}

# Filename patterns to skip (minified files, generated code, lock files)
SKIP_FILE_PATTERNS = {
    ".min.js", ".min.css", ".bundle.js", ".chunk.js",
    ".d.ts", ".map", ".lock",
}


def _should_skip_file(filepath: str, filename: str) -> bool:
    """
    Return True if a file should be excluded from indexing.
    Filters out minified/generated files and UI boilerplate.
    """
    # Skip files matching known junk patterns
    lower = filename.lower()
    for pat in SKIP_FILE_PATTERNS:
        if lower.endswith(pat):
            return True

    # Skip auto-generated UI component libraries (shadcn/ui, radix, etc.)
    # These are boilerplate and not useful for understanding the codebase
    path_lower = filepath.replace("\\", "/").lower()
    skip_path_patterns = [
        "/components/ui/",       # shadcn/ui auto-generated components
        "/components/primitives/",
        "/test/",                # test files
        "/tests/",
        "/__tests__/",
        ".test.", ".spec.",      # test files by name
    ]
    for pat in skip_path_patterns:
        if pat in path_lower:
            return True

    # Skip very large files (likely minified/generated)
    try:
        size = os.path.getsize(filepath)
        if size > 100_000:  # > 100KB is almost certainly generated
            return True
    except OSError:
        pass

    # Skip files where the first line is excessively long (minified)
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
            if len(first_line) > 1000:  # likely minified
                return True
    except Exception:
        pass

    return False


def find_code_files(repo_path: str) -> list[str]:
    """
    Walk a repository directory and find all source code files.

    Skips common non-source directories like node_modules, .git, etc.

    Args:
        repo_path: Absolute path to the cloned repository.

    Returns:
        List of absolute file paths to source code files.
    """
    code_files = []

    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to skip unwanted directories
        # (os.walk respects this — it won't descend into removed dirs)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in CODE_EXTENSIONS:
                full_path = os.path.join(root, filename)
                if not _should_skip_file(full_path, filename):
                    code_files.append(full_path)

    return sorted(code_files)


def read_file_safe(file_path: str) -> str:
    """
    Read a file's contents, handling encoding errors gracefully.

    Args:
        file_path: Absolute path to the file.

    Returns:
        File contents as a string, or empty string if unreadable.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        print(f"  WARNING: Could not read '{file_path}': {e}")
        return ""


def chunk_code(text: str, chunk_lines: int = CHUNK_LINES,
               overlap_lines: int = OVERLAP_LINES) -> list[str]:
    """
    Split source code into overlapping line-based chunks.

    We chunk by lines (not words) because code structure is line-oriented.
    Each chunk preserves enough context via overlap to understand the code.

    Args:
        text:          Full file content.
        chunk_lines:   Number of lines per chunk.
        overlap_lines: Number of lines to repeat at the start of each chunk.

    Returns:
        List of chunk strings.
    """
    lines = text.split("\n")

    # If the file is smaller than one chunk, return it as-is
    if len(lines) <= chunk_lines:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(lines):
        end = start + chunk_lines
        chunk = "\n".join(lines[start:end])
        if chunk.strip():  # skip empty chunks
            chunks.append(chunk)
        start += chunk_lines - overlap_lines

    return chunks


def build_index(repo_path: str, index_dir: str = INDEX_DIR) -> int:
    """
    Main pipeline: find code files → chunk → embed → build FAISS index.

    Args:
        repo_path: Absolute path to the cloned repository.
        index_dir: Directory to save FAISS index and metadata.

    Returns:
        Total number of chunks indexed.
    """
    os.makedirs(index_dir, exist_ok=True)

    # ── Collect source code files ─────────────────────────────
    code_files = find_code_files(repo_path)
    if not code_files:
        print(f"No source code files found in '{repo_path}'.")
        return 0

    print(f"\nFound {len(code_files)} source file(s) in '{repo_path}'")

    # ── Read + chunk all files ────────────────────────────────
    all_chunks   = []   # list of chunk text strings
    all_metadata = []   # parallel list of metadata dicts

    for file_path in tqdm(code_files, desc="Reading files"):
        content = read_file_safe(file_path)
        if not content.strip():
            continue

        chunks = chunk_code(content)

        # Make the file path relative to the repo for readability
        rel_path = os.path.relpath(file_path, repo_path)

        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({
                "chunk_id":    len(all_metadata),  # global unique id
                "file_path":   rel_path,
                "chunk_index": i,                  # position within file
                "chunk_text":  chunk,
            })

        if len(chunks) > 0:
            print(f"  {rel_path}: {len(chunks)} chunk(s)")

    print(f"\nTotal chunks to embed: {len(all_chunks)}")

    if not all_chunks:
        print("No chunks to embed. Check that the repo has source code files.")
        return 0

    # ── Embed all chunks ──────────────────────────────────────
    print(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)

    print("Embedding chunks (this may take a minute)...")
    embeddings = model.encode(
        all_chunks,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,   # L2 normalize so dot product = cosine sim
    )
    embeddings = embeddings.astype(np.float32)

    # ── Build FAISS index ─────────────────────────────────────
    dim   = embeddings.shape[1]           # embedding dimension (384 for MiniLM)
    index = faiss.IndexFlatIP(dim)        # inner product (cosine after normalization)
    faiss.normalize_L2(embeddings)        # normalize again to be safe
    index.add(embeddings)

    # ── Save index and metadata ───────────────────────────────
    index_path    = os.path.join(index_dir, "index.faiss")
    metadata_path = os.path.join(index_dir, "metadata.json")

    faiss.write_index(index, index_path)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)

    print(f"\nDone!")
    print(f"  FAISS index saved to : {index_path}")
    print(f"  Metadata saved to    : {metadata_path}")
    print(f"  Total vectors        : {index.ntotal}")
    print(f"  Embedding dimension  : {dim}")

    return index.ntotal


# ── Self-test ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "repos"
        # Find the first repo in repos/
        if os.path.isdir(path):
            subdirs = [d for d in os.listdir(path)
                       if os.path.isdir(os.path.join(path, d))]
            if subdirs:
                path = os.path.join(path, subdirs[0])
            else:
                print("No repos found. Run clone_repo.py first.")
                sys.exit(1)

    print(f"Building index from: {path}")
    build_index(path)
