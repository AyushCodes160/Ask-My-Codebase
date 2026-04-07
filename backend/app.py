"""
FILE: backend/app.py
PURPOSE: FastAPI backend - exposes /load_repo, /ask, and /status
         endpoints connecting the repo cloner, RAG retrieval engine,
         and LoRA fine-tuned TinyLlama model.
RUN: uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import clone_repo as clone_module
import ingest
import rag
import model as model_module


# ═══════════════════════════════════════════════════════════════
# Pydantic schemas (request / response shapes)
# ═══════════════════════════════════════════════════════════════

class LoadRepoRequest(BaseModel):
    """Request body for POST /load_repo."""
    repo_url: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Full GitHub repository URL.",
        json_schema_extra={"examples": ["https://github.com/user/repo"]}
    )
    force_reclone: bool = Field(
        False,
        description="If true, delete existing clone and re-clone."
    )


class LoadRepoResponse(BaseModel):
    """Response body for POST /load_repo."""
    status:      str
    repo_name:   str
    total_chunks: int
    message:     str


class AskRequest(BaseModel):
    """Request body for POST /ask."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The user's question about the codebase.",
        json_schema_extra={"examples": ["How does the main function work?"]}
    )
    history: list[dict] = Field(
        default_factory=list,
        description="Optional chat history. Each object should have a 'role' and 'content'."
    )


class SourceItem(BaseModel):
    """A single retrieved source chunk."""
    file_path: str
    score:     float
    excerpt:   str


class AskResponse(BaseModel):
    """Response body for POST /ask."""
    answer:     str
    sources:    list[SourceItem]
    latency_ms: int


class StatusResponse(BaseModel):
    """Response body for GET /status."""
    index_loaded: bool
    model_loaded: bool
    chunk_count:  int
    embed_model:  str
    base_model:   str
    current_repo: str


# ═══════════════════════════════════════════════════════════════
# App lifecycle
# ═══════════════════════════════════════════════════════════════

# Track which repo is currently loaded
_current_repo = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load FAISS index on startup if it exists."""
    print("Starting up - checking for existing FAISS index...")
    try:
        rag._load_resources()
        print("FAISS index loaded successfully.")
    except FileNotFoundError:
        print("No FAISS index found. Load a repo via /load_repo first.")

    # Model is loaded lazily on first /ask call (avoids startup crashes)
    yield
    print("Shutting down.")


# ═══════════════════════════════════════════════════════════════
# FastAPI app
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="Code RAG API",
    description="Ask questions about any GitHub repository using RAG + LoRA.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════

@app.post("/load_repo", response_model=LoadRepoResponse)
async def load_repo(request: LoadRepoRequest):
    """
    Clone a GitHub repo, read all source files, and build a FAISS index.

    Steps:
        1. Clone the repo using GitPython (shallow clone)
        2. Find all .py, .js, .ts, .jsx, .tsx files
        3. Chunk the code and embed with SentenceTransformers
        4. Build and save the FAISS index
    """
    global _current_repo

    # ── Step 1: Clone the repo ────────────────────────────────
    try:
        repo_name = clone_module.extract_repo_name(request.repo_url)
        repo_path = clone_module.clone_repo(
            request.repo_url,
            force_reclone=request.force_reclone,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone repository: {e}"
        )

    # ── Step 2-4: Ingest and build index ──────────────────────
    try:
        total_chunks = ingest.build_index(repo_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest repository: {e}"
        )

    if total_chunks == 0:
        raise HTTPException(
            status_code=404,
            detail="No source code files found in the repository. "
                   "Make sure it contains .py, .js, .ts, .jsx, or .tsx files."
        )

    # Reload the FAISS index in memory
    try:
        rag.reload_index()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Index built but failed to reload: {e}"
        )

    _current_repo = repo_name

    return LoadRepoResponse(
        status="ok",
        repo_name=repo_name,
        total_chunks=total_chunks,
        message=f"Successfully indexed {total_chunks} code chunks from '{repo_name}'.",
    )


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Answer a question about the loaded codebase.

    Steps:
        1. Retrieve top-5 relevant code chunks from FAISS
        2. Build context from chunks
        3. Generate answer with the LoRA model
        4. Return answer + sources + latency
    """
    t_start = time.time()

    # ── Step 1: Retrieve relevant chunks ──────────────────────
    try:
        chunks = rag.retrieve(request.question, top_k=10)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"No index loaded: {e}. Load a repo first via /load_repo."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {e}")

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant code found. Try a different question."
        )

    # ── Step 2: Build context string ──────────────────────────
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Source {i} - {chunk['file_path']}]\n{chunk['chunk_text']}"
        )
    context = "\n\n".join(context_parts)

    # ── Step 3: Generate answer ───────────────────────────────
    try:
        answer = model_module.generate_answer(context, request.question, request.history)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Model not ready: {e}. Run train_lora.py or set USE_BASE_FALLBACK=true."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {e}")

    # ── Step 4: Build response ────────────────────────────────
    sources = [
        SourceItem(
            file_path=c["file_path"],
            score=round(c["score"], 4),
            excerpt=c["chunk_text"][:200],
        )
        for c in chunks
    ]

    latency_ms = int((time.time() - t_start) * 1000)

    return AskResponse(
        answer=answer,
        sources=sources,
        latency_ms=latency_ms,
    )


@app.get("/status", response_model=StatusResponse)
async def status():
    """Health check: reports whether index and model are loaded."""
    index_loaded = rag._faiss_index is not None
    model_loaded = model_module._model is not None

    chunk_count = 0
    if index_loaded:
        try:
            chunk_count = rag.get_chunk_count()
        except Exception:
            pass

    return StatusResponse(
        index_loaded=index_loaded,
        model_loaded=model_loaded,
        chunk_count=chunk_count,
        embed_model="sentence-transformers/all-MiniLM-L6-v2",
        base_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        current_repo=_current_repo,
    )


# ── Run directly with Python ─────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
