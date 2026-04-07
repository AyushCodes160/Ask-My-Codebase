# Code RAG — GitHub Repo Code Explainer

A complete, beginner-friendly RAG (Retrieval-Augmented Generation) system to ask questions about any public GitHub repository. Uses FAISS for retrieval and a LoRA fine-tuned TinyLlama model for developer-style code explanations.

## Features
- **Auto-Cloning**: Paste a GitHub URL and it clones locally.
- **Code Ingestion**: Recursively reads Python, JS, TS, JSX, and TSX files.
- **Chunking & FAISS**: Splits code into lines, embeds using `all-MiniLM-L6-v2`, and stores in a local FAISS index.
- **LoRA Training Pipeline**: Includes a script to generated synthetic Q&A pairs and fine-tune your own LoRA adapter.
- **FastAPI Backend + React Frontend**: Full-stack application.

## 🚀 Setup Instructions

### 1. Prerequisites
- Python 3.10+ (recommend 3.12)
- Node.js 18+

### 2. Backend Setup
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Start Backend
Run this to use the raw TinyLlama base model (since training takes time):
```bash
cd backend
source venv/bin/activate
USE_BASE_FALLBACK=true uvicorn app:app --host 0.0.0.0 --port 8000
```
*(If on Mac ARM, set `PYTORCH_ENABLE_MPS_FALLBACK=1` if you encounter tensor errors).*

### 4. Frontend Setup
In a new terminal wrapper:
```bash
cd frontend
npm install
npm run dev
```
Open the provided `localhost` URL in your browser!

### 5. Training the LoRA Model (Optional)
If you want the model to sound more like a developer and perfectly reference files:
1. Load a repository via the frontend first (so `faiss_index` is created).
2. Stop the backend server.
3. Run the trainer:
```bash
cd backend
source venv/bin/activate
python train_lora.py
```
This takes a few hours on CPU. Once done, it saves to `lora_model/`. Restart the backend *without* `USE_BASE_FALLBACK=true` to use it.

## Architecture

1. **User inputs a repo URL**. Backend clones using GitPython.
2. **Ingestion (`ingest.py`)**. Code is split into line-chunks, embedded, and added to the FAISS DB.
3. **User asks a question**. Text is embedded.
4. **Retrieval (`rag.py`)**. FAISS finds top-5 most similar chunks.
5. **Generation (`model.py`)**. Context + Question + Prompt goes to TinyLlama + LoRA.
6. **Result**. User sees answer in React UI with source snippets!
