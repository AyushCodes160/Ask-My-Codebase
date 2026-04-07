"""
FILE: backend/model.py
PURPOSE: Generate intelligent, well-summarized answers using Groq's
         free LLM API (Llama 3.3 70B). Blazing fast responses (~1-2s).
RUN: python model.py   (runs a quick self-test)
"""

import os
import time
from groq import Groq

# ── Load API key from .env file if present ───────────────────
def _load_env():
    """Load .env file variables into os.environ."""
    env_path = os.path.join(os.path.dirname(__file__) or ".", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

_load_env()

# ── Configuration ────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL_ID = "llama-3.3-70b-versatile"  # Free on Groq, very capable

# ── Module-level singleton ───────────────────────────────────
_client = None
_model = "groq-llama3"  # Sentinel so app.py status check works


def _get_client() -> Groq:
    """Lazily initialize the Groq client."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to backend/.env or "
                "set it as an environment variable."
            )
        _client = Groq(api_key=GROQ_API_KEY)
        print(f"[model.py] Groq client ready (model: {MODEL_ID})")
    return _client


def generate_answer(context: str, question: str, history: list[dict] = None) -> str:
    """
    Generate a well-summarized, developer-friendly answer using Groq.

    Args:
        context:  Concatenated text of the top-k retrieved code chunks.
        question: The user's natural language question.

    Returns:
        Generated answer string.
    """
    t0 = time.time()
    client = _get_client()

    # Trim context to stay within token limits
    max_context_chars = 6000
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + "\n... (truncated)"

    system_msg = (
        "You are an expert code analyst. You analyze source code repositories "
        "and provide clear, well-structured, developer-friendly explanations.\n\n"
        "Rules:\n"
        "- Give concise but thorough answers (4-8 sentences for simple questions, "
        "more for summaries)\n"
        "- Always reference specific file names, function names, and class names\n"
        "- Use markdown formatting: **bold** for emphasis, `code` for names, "
        "bullet points for lists\n"
        "- For summary questions, describe the project's purpose, architecture, "
        "key components, and tech stack\n"
        "- For 'how does X work' questions, trace the code flow step by step\n"
        "- Be specific and technical but easy to understand"
    )

    user_msg = f"Question: {question}\n\nRelevant code context:\n{context}"

    messages = [{"role": "system", "content": system_msg}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            max_tokens=500,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
        elapsed = time.time() - t0
        print(f"[model.py] Groq response in {elapsed*1000:.0f}ms")
        return answer.strip()

    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            return (
                "⏳ Rate limit reached on Groq's free tier. "
                "Please wait 30-60 seconds and try again."
            )
        if "authentication" in error_msg.lower() or "401" in error_msg:
            return (
                "🔑 Invalid Groq API key. Please check your key at "
                "https://console.groq.com/keys"
            )
        raise


# ── Self-test ─────────────────────────────────────────────────
if __name__ == "__main__":
    test_context = (
        "[Source 1 - server/app.py]\n"
        "# FastAPI backend for voice AI agent\n"
        '"""Main application server."""\n'
        "from fastapi import FastAPI\n"
        "import uvicorn\n\n"
        "app = FastAPI()\n\n"
        "class VoiceAgent:\n"
        "    def __init__(self):\n"
        "        self.model = None\n\n"
        "    async def process_audio(self, audio):\n"
        "        pass\n"
    )

    print("Running Groq self-test...")
    for q in [
        "Give me a summary about this repo",
        "How does the voice agent work?",
    ]:
        print(f"\nQ: {q}")
        try:
            answer = generate_answer(test_context, q)
            print(f"A: {answer}\n")
        except Exception as e:
            print(f"Error: {e}")
