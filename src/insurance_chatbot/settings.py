"""Centralized runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _score_threshold() -> float | None:
    raw_value = os.getenv("RAG_SCORE_THRESHOLD", "").strip()
    if not raw_value:
        return None
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("RAG_SCORE_THRESHOLD must be a number") from exc
    if not 0 <= value <= 1:
        raise ValueError("RAG_SCORE_THRESHOLD must be between 0 and 1")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret runtime settings plus the API key kept in memory only."""

    openai_api_key: str
    chat_model: str
    embedding_model: str
    qdrant_path: Path
    qdrant_collection: str
    top_k: int
    score_threshold: float | None

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")
        raw_path = Path(os.getenv("QDRANT_PATH", "data/index/qdrant"))
        qdrant_path = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini").strip(),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip(),
            qdrant_path=qdrant_path.resolve(),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "queplan_policies").strip(),
            top_k=_positive_int("RAG_TOP_K", 5),
            score_threshold=_score_threshold(),
        )

    def require_openai(self) -> None:
        if not self.openai_configured:
            raise RuntimeError("OPENAI_API_KEY is not configured")
