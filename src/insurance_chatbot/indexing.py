"""Idempotent PDF-to-Qdrant indexing for the QuePlan policy corpus."""

from __future__ import annotations

import argparse
import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from openai import APIConnectionError, AuthenticationError, OpenAI, RateLimitError
from pypdf import PdfReader
from qdrant_client import QdrantClient, models

from insurance_chatbot.settings import PROJECT_ROOT, Settings


ARTICLE_RE = re.compile(r"(?im)^\s*((?:art(?:í|i)culo|article)\s+(?:n[°ºo]\s*)?\d+[\w.-]*)")
WHITESPACE_RE = re.compile(r"\s+")
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
CHARS_PER_TOKEN = 4
INDEX_VERSION = "openai-page-article-v1-1024-154"


@dataclass(frozen=True, slots=True)
class PolicyChunk:
    point_id: str
    chunk_id: str
    text: str
    policy_id: str
    filename: str
    page: int
    article: str | None
    document_hash: str

    def payload(self) -> dict[str, str | int | None]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "policy_id": self.policy_id,
            "filename": self.filename,
            "page": self.page,
            "article": self.article,
            "document_hash": self.document_hash,
        }


@dataclass(frozen=True, slots=True)
class IndexSummary:
    documents: int
    chunks: int
    collection: str
    embedding_model: str


def _normalize(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _window_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split long text with deterministic overlap, preferring word boundaries."""
    normalized = _normalize(text)
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        hard_end = min(start + max_chars, len(normalized))
        end = hard_end
        if hard_end < len(normalized):
            boundary = normalized.rfind(" ", start + max_chars // 2, hard_end)
            if boundary > start:
                end = boundary
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(end - overlap_chars, start + 1)
        while start < len(normalized) and normalized[start].isspace():
            start += 1
    return chunks


def extract_policy_chunks(
    path: Path,
    *,
    chunk_size_tokens: int = 1024,
    chunk_overlap_tokens: int = 154,
) -> list[PolicyChunk]:
    """Extract article-aware, page-citable chunks from one PDF."""
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be greater than zero")
    if not 0 <= chunk_overlap_tokens < chunk_size_tokens:
        raise ValueError(
            "chunk_overlap_tokens must be non-negative and smaller than chunk_size_tokens"
        )

    document_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    policy_id = path.stem
    max_chars = chunk_size_tokens * CHARS_PER_TOKEN
    overlap_chars = chunk_overlap_tokens * CHARS_PER_TOKEN
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        reader.decrypt("")

    chunks: list[PolicyChunk] = []
    current_article: str | None = None
    for page_number, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        matches = list(ARTICLE_RE.finditer(raw_text))
        segments: list[tuple[str | None, str]] = []
        if matches:
            if raw_text[: matches[0].start()].strip():
                segments.append((current_article, raw_text[: matches[0].start()]))
            for index, match in enumerate(matches):
                current_article = _normalize(match.group(1))
                end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
                segments.append((current_article, raw_text[match.start() : end]))
        elif raw_text.strip():
            segments.append((current_article, raw_text))

        for article, segment in segments:
            for window in _window_text(segment, max_chars, overlap_chars):
                ordinal = len(chunks) + 1
                chunk_id = f"{policy_id}-p{page_number:03d}-c{ordinal:04d}"
                identity = f"{document_hash}:{page_number}:{ordinal}:{window}"
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
                chunks.append(
                    PolicyChunk(
                        point_id=point_id,
                        chunk_id=chunk_id,
                        text=window,
                        policy_id=policy_id,
                        filename=path.name,
                        page=page_number,
                        article=article,
                        document_hash=document_hash,
                    )
                )
    return chunks


def _batches(items: Sequence[PolicyChunk], size: int) -> Iterable[Sequence[PolicyChunk]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _vector_size(collection: object) -> int | None:
    vectors = collection.config.params.vectors  # type: ignore[attr-defined]
    if isinstance(vectors, models.VectorParams):
        return int(vectors.size)
    return None


def _document_is_current(
    client: QdrantClient,
    *,
    collection_name: str,
    filename: str,
    document_hash: str,
    embedding_model: str,
) -> bool:
    records, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="filename",
                    match=models.MatchValue(value=filename),
                )
            ]
        ),
        limit=1,
        with_payload=["document_hash", "embedding_model", "index_version"],
        with_vectors=False,
    )
    if not records:
        return False
    payload = records[0].payload or {}
    return (
        payload.get("document_hash") == document_hash
        and payload.get("embedding_model") == embedding_model
        and payload.get("index_version") == INDEX_VERSION
    )


def index_policies(
    input_dir: Path,
    *,
    settings: Settings,
    openai_client: OpenAI | None = None,
    qdrant_client: QdrantClient | None = None,
    batch_size: int = 64,
    recreate: bool = False,
) -> IndexSummary:
    """Embed and upsert all PDFs, replacing stale chunks per document."""
    settings.require_openai()
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    paths = sorted(input_dir.rglob("*.pdf"))
    if not paths:
        raise RuntimeError(f"No PDF files found under {input_dir}")

    chunks_by_document = {path.name: extract_policy_chunks(path) for path in paths}
    if any(not chunks for chunks in chunks_by_document.values()):
        empty = [name for name, chunks in chunks_by_document.items() if not chunks]
        raise RuntimeError(f"No extractable text in: {', '.join(empty)}")

    openai_client = openai_client or OpenAI(api_key=settings.openai_api_key)
    qdrant_client = qdrant_client or QdrantClient(path=str(settings.qdrant_path))
    if recreate and qdrant_client.collection_exists(settings.qdrant_collection):
        qdrant_client.delete_collection(settings.qdrant_collection)

    total_chunks = 0
    for filename, document_chunks in chunks_by_document.items():
        document_hash = document_chunks[0].document_hash
        if qdrant_client.collection_exists(settings.qdrant_collection) and _document_is_current(
            qdrant_client,
            collection_name=settings.qdrant_collection,
            filename=filename,
            document_hash=document_hash,
            embedding_model=settings.embedding_model,
        ):
            total_chunks += len(document_chunks)
            continue

        embedded_points: list[models.PointStruct] = []
        for batch in _batches(document_chunks, batch_size):
            embedding_response = openai_client.embeddings.create(
                model=settings.embedding_model,
                input=[chunk.text for chunk in batch],
            )
            vectors = [item.embedding for item in embedding_response.data]
            if len(vectors) != len(batch):
                raise RuntimeError("OpenAI returned an unexpected embedding count")

            if not qdrant_client.collection_exists(settings.qdrant_collection):
                qdrant_client.create_collection(
                    collection_name=settings.qdrant_collection,
                    vectors_config=models.VectorParams(
                        size=len(vectors[0]),
                        distance=models.Distance.COSINE,
                    ),
                )
            else:
                collection = qdrant_client.get_collection(settings.qdrant_collection)
                existing_size = _vector_size(collection)
                if existing_size is not None and existing_size != len(vectors[0]):
                    raise RuntimeError(
                        "Qdrant vector size does not match the embedding model; "
                        "rerun with --recreate"
                    )

            embedded_points.extend(
                models.PointStruct(
                    id=chunk.point_id,
                    vector=vector,
                    payload={
                        **chunk.payload(),
                        "embedding_model": settings.embedding_model,
                        "index_version": INDEX_VERSION,
                    },
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            )

        # Embeddings are complete before replacing this document, so an API
        # failure cannot erase a previously working document from the index.
        qdrant_client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="filename",
                        match=models.MatchValue(value=filename),
                    )
                ]
            ),
            wait=True,
        )
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=embedded_points,
            wait=True,
        )
        total_chunks += len(document_chunks)

    return IndexSummary(
        documents=len(paths),
        chunks=total_chunks,
        collection=settings.qdrant_collection,
        embedding_model=settings.embedding_model,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index QuePlan policy PDFs into local Qdrant.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Replace the full collection (required after changing embedding dimensions).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        summary = index_policies(
            args.input_dir,
            settings=Settings.from_env(),
            batch_size=args.batch_size,
            recreate=args.recreate,
        )
    except AuthenticationError as exc:
        raise SystemExit("Indexing failed: OPENAI_API_KEY was rejected by OpenAI.") from exc
    except RateLimitError as exc:
        raise SystemExit(
            "Indexing failed: the OpenAI project has no available quota. "
            "Enable API billing or add credits, then retry."
        ) from exc
    except APIConnectionError as exc:
        raise SystemExit("Indexing failed: OpenAI could not be reached.") from exc
    print(
        f"Indexed {summary.chunks} chunks from {summary.documents} documents "
        f"into '{summary.collection}' using {summary.embedding_model}."
    )


if __name__ == "__main__":
    main()
