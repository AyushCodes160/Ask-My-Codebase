FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for git cloning repos
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend files
COPY . .

# Create necessary directories
RUN mkdir -p repos uploads faiss_index doc_faiss_index link_faiss_index

# HF Spaces requires port 7860
EXPOSE 7860

# Run FastAPI on port 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
