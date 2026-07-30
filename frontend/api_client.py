"""HTTP client wrapper for the Insurance Policy RAG API.

This module is the only place in the frontend allowed to perform network
calls. It never talks to OpenAI or Qdrant directly, only to the FastAPI
backend, as required by the frontend specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from config import (
    ASK_ENDPOINT,
    ASK_TIMEOUT_SECONDS,
    CONFIG_ENDPOINT,
    READY_ENDPOINT,
    STATUS_TIMEOUT_SECONDS,
)


class ApiClientError(Exception):
    """Base exception for API client failures."""


class ApiTimeoutError(ApiClientError):
    """Raised when the backend does not respond within the configured timeout."""


class ApiUnavailableError(ApiClientError):
    """Raised when the backend cannot be reached at all."""


class ApiResponseError(ApiClientError):
    """Raised when the backend responds with a non-2xx status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API returned {status_code}: {detail}")


@dataclass(slots=True)
class AskResult:
    answer: str
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReadinessResult:
    """Mirrors the backend ReadinessResponse schema."""

    status: str
    openai_configured: bool
    index_ready: bool
    collection: str
    indexed_chunks: int
    detail: str | None = None


@dataclass(slots=True)
class ConfigResult:
    """Mirrors the backend ConfigResponse schema."""

    llm_model: str
    embedding_model: str
    vector_store: str
    collection: str
    top_k: int
    score_threshold: float | None
    openai_configured: bool


async def check_readiness() -> ReadinessResult | None:
    """Query /ready and return the parsed result.

    Returns None if the backend cannot be reached at all, since that is a
    distinct condition from the backend being reachable but not ready.
    The /ready endpoint returns HTTP 503 when not ready, so the response
    body is parsed regardless of status code.
    """
    try:
        async with httpx.AsyncClient(timeout=STATUS_TIMEOUT_SECONDS) as client:
            response = await client.get(READY_ENDPOINT)
    except httpx.RequestError:
        return None

    try:
        body = response.json()
    except ValueError:
        return None

    return ReadinessResult(
        status=body.get("status", "unknown"),
        openai_configured=body.get("openai_configured", False),
        index_ready=body.get("index_ready", False),
        collection=body.get("collection", ""),
        indexed_chunks=body.get("indexed_chunks", 0),
        detail=body.get("detail"),
    )


async def fetch_config() -> ConfigResult | None:
    """Query /config and return the parsed result, or None if unreachable."""
    try:
        async with httpx.AsyncClient(timeout=STATUS_TIMEOUT_SECONDS) as client:
            response = await client.get(CONFIG_ENDPOINT)
    except httpx.RequestError:
        return None

    if response.status_code != 200:
        return None

    body = response.json()
    return ConfigResult(
        llm_model=body.get("llm_model", ""),
        embedding_model=body.get("embedding_model", ""),
        vector_store=body.get("vector_store", ""),
        collection=body.get("collection", ""),
        top_k=body.get("top_k", 0),
        score_threshold=body.get("score_threshold"),
        openai_configured=body.get("openai_configured", False),
    )


async def ask_question(question: str, policy_id: str | None) -> AskResult:
    """Send a question to the backend and return the parsed result.

    Raises ApiTimeoutError, ApiUnavailableError, or ApiResponseError on
    failure so the caller can present an appropriate message to the user.
    """
    payload: dict[str, Any] = {"question": question}
    if policy_id:
        payload["policy_id"] = policy_id

    try:
        async with httpx.AsyncClient(timeout=ASK_TIMEOUT_SECONDS) as client:
            response = await client.post(ASK_ENDPOINT, json=payload)
    except httpx.TimeoutException as exc:
        raise ApiTimeoutError("The backend did not respond in time") from exc
    except httpx.RequestError as exc:
        raise ApiUnavailableError("The backend could not be reached") from exc

    if response.status_code != 200:
        detail = response.text
        try:
            body = response.json()
            detail = body.get("detail", detail)
        except ValueError:
            pass
        raise ApiResponseError(response.status_code, detail)

    body = response.json()
    return AskResult(
        answer=body.get("answer", ""),
        sources=body.get("sources", []),
        metadata=body.get("metadata", {}),
    )