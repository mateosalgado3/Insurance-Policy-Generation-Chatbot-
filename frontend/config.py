"""Environment configuration for the Chainlit frontend.

Values are read from environment variables so the same code runs against
any backend host (local, Docker, Podman, staging) without code changes.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
ASK_ENDPOINT: str = f"{API_BASE_URL}/ask"
ASK_STREAM_ENDPOINT: str = f"{API_BASE_URL}/ask/stream"
DRAFT_ENDPOINT: str = f"{API_BASE_URL}/generate-policy"

# /health only reports process liveness. /ready reports whether the RAG can
# actually answer questions (OpenAI configured and index populated), so it
# is the endpoint used to drive the chat-start status message.
READY_ENDPOINT: str = f"{API_BASE_URL}/ready"
CONFIG_ENDPOINT: str = f"{API_BASE_URL}/config"

# Timeout for the /ask call, which involves retrieval plus an LLM call and
# can legitimately take longer than a typical HTTP request.
ASK_TIMEOUT_SECONDS: float = float(os.getenv("ASK_TIMEOUT_SECONDS", "30"))

# Timeout for the /ready and /config checks, expected to respond quickly.
STATUS_TIMEOUT_SECONDS: float = float(os.getenv("STATUS_TIMEOUT_SECONDS", "5"))

# Small delay between rendered SSE chunks. It creates a readable progressive
# response without materially increasing total latency.
STREAM_RENDER_DELAY_SECONDS: float = float(
    os.getenv("STREAM_RENDER_DELAY_SECONDS", "0.006")
)
