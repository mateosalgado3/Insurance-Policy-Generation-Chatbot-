"""Canonical, versioned chunking and Qdrant indexing pipeline."""

from __future__ import annotations

import argparse
import bisect
import json
import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import APIConnectionError, AuthenticationError, OpenAI, RateLimitError
from pypdf import PdfReader
from qdrant_client import QdrantClient, models

from insurance_chatbot import eda
from insurance_chatbot.settings import PROJECT_ROOT, Settings


DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "index" / "chunks.jsonl"
DEFAULT_CHUNK_SIZE_TOKENS = 1024
DEFAULT_CHUNK_OVERLAP_TOKENS = 154
CHARS_PER_TOKEN = 4.0
INDEX_VERSION = "article-v1-1024-154"
CHUNK_ID_NAMESPACE = uuid.UUID("2c9c9a0e-9f0a-4a9c-8f3e-8e2b6a1c9f2d")
ARTICLE_NUMBER_RE = re.compile(r"\d+")
ARTICLE_HEADING_LOOKAHEAD = 6
REQUIRED_FIELDS = (
    "chunk_id",
    "text",
    "policy_id",
    "filename",
    "article",
    "page",
    "document_hash",
    "embedding_model",
    "index_version",
)
KNOWN_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


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

    def payload(self, embedding_model: str) -> dict[str, str | int | None]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "policy_id": self.policy_id,
            "filename": self.filename,
            "article": self.article,
            "page": self.page,
            "document_hash": self.document_hash,
            "embedding_model": embedding_model,
            "index_version": INDEX_VERSION,
        }


@dataclass(frozen=True, slots=True)
class IndexSummary:
    documents: int
    chunks: int
    chunks_embedded: int
    chunks_reused: int
    collection: str
    embedding_model: str


def point_id_for(chunk_id: str) -> str:
    return str(uuid.uuid5(CHUNK_ID_NAMESPACE, chunk_id))


def is_heading_boundary(raw_text: str, match: re.Match[str]) -> bool:
    """Reject inline article references that are not actual headings."""
    return ":" in raw_text[match.end() : match.end() + ARTICLE_HEADING_LOOKAHEAD]


def policy_id_from_filename(filename: str) -> str:
    return Path(filename).stem


def page_offsets(page_texts: list[str]) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    for text in page_texts:
        offsets.append(cursor)
        cursor += len(text) + 1
    return offsets


def page_for_offset(offsets: list[int], position: int) -> int:
    index = bisect.bisect_right(offsets, position) - 1
    return max(index, 0) + 1


def clean_chunk_text(text: str) -> str:
    return " ".join(text.split())


def split_into_windows(text: str, chunk_chars: int, overlap_chars: int) -> list[tuple[int, str]]:
    if not text:
        return []
    step = chunk_chars - overlap_chars
    if chunk_chars <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap_chars < 0 or step <= 0:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")

    windows: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        windows.append((start, text[start:end]))
        if end == len(text):
            break
        start += step
    return windows


def _window_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Compatibility helper retained for callers of the first indexer."""
    return [
        clean_chunk_text(window)
        for _, window in split_into_windows(text, max_chars, overlap_chars)
        if clean_chunk_text(window)
    ]


def chunk_document(
    path: Path,
    chunk_chars: int,
    overlap_chars: int,
    *,
    embedding_model: str = "text-embedding-3-small",
) -> list[dict[str, Any]]:
    filename = path.name
    policy_id = policy_id_from_filename(filename)
    document_hash = eda.sha256_bytes(path)
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass

    page_texts = [page.extract_text() or "" for page in reader.pages]
    raw_text = "\n".join(page_texts)
    offsets = page_offsets(page_texts)
    matches = [
        match for match in eda.ARTICLE_RE.finditer(raw_text) if is_heading_boundary(raw_text, match)
    ]
    records: list[dict[str, Any]] = []

    def append_record(
        chunk_id: str,
        text: str,
        article: str | None,
        page: int,
    ) -> None:
        records.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "policy_id": policy_id,
                "filename": filename,
                "article": article,
                "page": page,
                "document_hash": document_hash,
                "embedding_model": embedding_model,
                "index_version": INDEX_VERSION,
            }
        )

    if not matches:
        for window_index, (start, raw_window) in enumerate(
            split_into_windows(raw_text, chunk_chars, overlap_chars), start=1
        ):
            text = clean_chunk_text(raw_window)
            if text:
                append_record(
                    f"{policy_id}-doc-{window_index:03d}",
                    text,
                    None,
                    page_for_offset(offsets, start),
                )
        return records

    bounds = [match.start() for match in matches] + [len(raw_text)]
    sequence_by_slug: dict[str, int] = {}
    for article_index, match in enumerate(matches):
        article_start = bounds[article_index]
        article_end = bounds[article_index + 1]
        article_label = match.group(0).strip()
        number_match = ARTICLE_NUMBER_RE.search(article_label)
        article_slug = number_match.group(0) if number_match else str(article_index + 1)
        article_text = raw_text[article_start:article_end]

        for relative_start, raw_window in split_into_windows(
            article_text, chunk_chars, overlap_chars
        ):
            text = clean_chunk_text(raw_window)
            if not text:
                continue
            sequence_by_slug[article_slug] = sequence_by_slug.get(article_slug, 0) + 1
            append_record(
                (f"{policy_id}-art{article_slug}-{sequence_by_slug[article_slug]:03d}"),
                text,
                article_label,
                page_for_offset(offsets, article_start + relative_start),
            )
    return records


def extract_policy_chunks(
    path: Path,
    *,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    embedding_model: str = "text-embedding-3-small",
) -> list[PolicyChunk]:
    records = chunk_document(
        path,
        round(chunk_size_tokens * CHARS_PER_TOKEN),
        round(chunk_overlap_tokens * CHARS_PER_TOKEN),
        embedding_model=embedding_model,
    )
    return [
        PolicyChunk(
            point_id=point_id_for(record["chunk_id"]),
            chunk_id=record["chunk_id"],
            text=record["text"],
            policy_id=record["policy_id"],
            filename=record["filename"],
            page=record["page"],
            article=record["article"],
            document_hash=record["document_hash"],
        )
        for record in records
    ]


def run_chunking(
    input_dir: Path,
    output_path: Path,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    embedding_model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    paths = eda.discover_pdfs(input_dir)
    if not paths:
        raise FileNotFoundError(f"No PDF files found under {input_dir}")
    chunk_chars = round(chunk_size_tokens * CHARS_PER_TOKEN)
    overlap_chars = round(chunk_overlap_tokens * CHARS_PER_TOKEN)

    records = [
        record
        for path in paths
        for record in chunk_document(
            path,
            chunk_chars,
            overlap_chars,
            embedding_model=embedding_model,
        )
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "documents": len(paths),
        "chunks": len(records),
        "chunk_size_tokens": chunk_size_tokens,
        "chunk_overlap_tokens": chunk_overlap_tokens,
        "embedding_model": embedding_model,
        "index_version": INDEX_VERSION,
        "output_path": str(output_path),
    }


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run the chunking command first")
    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            missing = [field for field in REQUIRED_FIELDS if field not in record]
            if missing:
                raise ValueError(f"{path}:{line_number} missing fields: {missing}")
            if record["chunk_id"] in seen_ids:
                raise ValueError(f"{path}:{line_number} duplicate chunk_id: {record['chunk_id']}")
            seen_ids.add(record["chunk_id"])
            chunks.append(record)
    return chunks


def batched(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    if size <= 0:
        raise ValueError("batch_size must be greater than zero")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def embed_texts(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in response.data]
    if len(vectors) != len(texts):
        raise RuntimeError("OpenAI returned an unexpected embedding count")
    return vectors


def resolve_vector_size(client: OpenAI, model: str, sample_text: str) -> int:
    known = KNOWN_EMBEDDING_DIMENSIONS.get(model)
    return known if known else len(embed_texts(client, model, [sample_text])[0])


def _vector_size(collection: object) -> int | None:
    vectors = collection.config.params.vectors  # type: ignore[attr-defined]
    if isinstance(vectors, models.VectorParams):
        return int(vectors.size)
    return None


def _all_points(
    client: QdrantClient, collection_name: str, *, with_vectors: bool = False
) -> list[Any]:
    points: list[Any] = []
    offset: Any = None
    while True:
        page, offset = client.scroll(
            collection_name=collection_name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=with_vectors,
        )
        points.extend(page)
        if offset is None:
            return points


def index_matches(
    client: QdrantClient,
    chunks: list[dict[str, Any]],
    *,
    collection_name: str,
    embedding_model: str,
) -> bool:
    if not client.collection_exists(collection_name):
        return False
    expected_size = KNOWN_EMBEDDING_DIMENSIONS.get(embedding_model)
    actual_size = _vector_size(client.get_collection(collection_name))
    if expected_size is not None and actual_size != expected_size:
        return False

    points = _all_points(client, collection_name)
    expected_ids = {chunk["chunk_id"] for chunk in chunks}
    if {point.payload.get("chunk_id") for point in points} != expected_ids:
        return False
    return all(
        point.payload.get("embedding_model") == embedding_model
        and point.payload.get("index_version") == INDEX_VERSION
        for point in points
    )


def annotate_existing_index(
    client: QdrantClient,
    chunks: list[dict[str, Any]],
    *,
    collection_name: str,
    embedding_model: str,
) -> dict[str, Any]:
    """Version a compatible prebuilt index without regenerating embeddings."""
    if not client.collection_exists(collection_name):
        raise RuntimeError(f"Collection '{collection_name}' does not exist")
    expected_size = KNOWN_EMBEDDING_DIMENSIONS.get(embedding_model)
    actual_size = _vector_size(client.get_collection(collection_name))
    if expected_size is not None and actual_size != expected_size:
        raise RuntimeError(f"Vector size mismatch: expected {expected_size}, found {actual_size}")

    points = _all_points(client, collection_name)
    expected_ids = {chunk["chunk_id"] for chunk in chunks}
    actual_ids = {point.payload.get("chunk_id") for point in points}
    if actual_ids != expected_ids:
        raise RuntimeError("Prebuilt Qdrant points do not match the canonical chunks file")
    client.set_payload(
        collection_name=collection_name,
        payload={
            "embedding_model": embedding_model,
            "index_version": INDEX_VERSION,
        },
        points=[point.id for point in points],
        wait=True,
    )
    return {
        "chunks_annotated": len(points),
        "collection": collection_name,
        "embedding_model": embedding_model,
        "index_version": INDEX_VERSION,
        "openai_calls": 0,
    }


def index_chunks(
    chunks: list[dict[str, Any]],
    *,
    openai_client: OpenAI,
    qdrant_client: QdrantClient,
    embedding_model: str,
    collection_name: str,
    batch_size: int = 64,
    force_reindex: bool = False,
) -> dict[str, Any]:
    if not chunks:
        return {
            "chunks_indexed": 0,
            "chunks_reused": 0,
            "batches": 0,
            "collection": collection_name,
        }
    if not force_reindex and index_matches(
        qdrant_client,
        chunks,
        collection_name=collection_name,
        embedding_model=embedding_model,
    ):
        return {
            "chunks_indexed": 0,
            "chunks_reused": len(chunks),
            "batches": 0,
            "collection": collection_name,
        }

    vector_size = resolve_vector_size(openai_client, embedding_model, chunks[0]["text"])
    points: list[models.PointStruct] = []
    batches = 0
    for batch in batched(chunks, batch_size):
        vectors = embed_texts(
            openai_client,
            embedding_model,
            [chunk["text"] for chunk in batch],
        )
        points.extend(
            models.PointStruct(
                id=point_id_for(chunk["chunk_id"]),
                vector=vector,
                payload={
                    **chunk,
                    "embedding_model": embedding_model,
                    "index_version": INDEX_VERSION,
                },
            )
            for chunk, vector in zip(batch, vectors, strict=True)
        )
        batches += 1

    if qdrant_client.collection_exists(collection_name):
        qdrant_client.delete_collection(collection_name)
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )
    for batch in batched(points, batch_size):
        qdrant_client.upsert(collection_name=collection_name, points=list(batch), wait=True)
    return {
        "chunks_indexed": len(points),
        "chunks_reused": 0,
        "batches": batches,
        "collection": collection_name,
    }


def index_policies(
    input_dir: Path,
    *,
    settings: Settings,
    openai_client: OpenAI | None = None,
    qdrant_client: QdrantClient | None = None,
    batch_size: int = 64,
    recreate: bool = False,
) -> IndexSummary:
    """Compatibility entrypoint backed by the canonical article chunker."""
    settings.require_openai()
    paths = sorted(input_dir.rglob("*.pdf"))
    if not paths:
        raise RuntimeError(f"No PDF files found under {input_dir}")
    chunks = [
        chunk
        for path in paths
        for chunk in extract_policy_chunks(path, embedding_model=settings.embedding_model)
    ]
    records = [chunk.payload(settings.embedding_model) for chunk in chunks]
    openai_client = openai_client or OpenAI(api_key=settings.openai_api_key)
    qdrant_client = qdrant_client or QdrantClient(path=str(settings.qdrant_path))
    result = index_chunks(
        records,
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model=settings.embedding_model,
        collection_name=settings.qdrant_collection,
        batch_size=batch_size,
        force_reindex=recreate,
    )
    return IndexSummary(
        documents=len(paths),
        chunks=len(records),
        chunks_embedded=result["chunks_indexed"],
        chunks_reused=result["chunks_reused"],
        collection=settings.qdrant_collection,
        embedding_model=settings.embedding_model,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate canonical chunks and maintain the Qdrant index."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Version an existing compatible index without calling OpenAI.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    run_chunking(
        args.input_dir,
        args.chunks_path,
        embedding_model=settings.embedding_model,
    )
    chunks = load_chunks(args.chunks_path)
    client = QdrantClient(path=str(settings.qdrant_path))
    try:
        if args.metadata_only:
            result = annotate_existing_index(
                client,
                chunks,
                collection_name=settings.qdrant_collection,
                embedding_model=settings.embedding_model,
            )
        else:
            settings.require_openai()
            result = index_chunks(
                chunks,
                openai_client=OpenAI(api_key=settings.openai_api_key),
                qdrant_client=client,
                embedding_model=settings.embedding_model,
                collection_name=settings.qdrant_collection,
                batch_size=args.batch_size,
            )
    except AuthenticationError as exc:
        raise SystemExit("Indexing failed: OPENAI_API_KEY was rejected by OpenAI.") from exc
    except RateLimitError as exc:
        raise SystemExit("Indexing failed: the OpenAI project has no available quota.") from exc
    except APIConnectionError as exc:
        raise SystemExit("Indexing failed: OpenAI could not be reached.") from exc
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
