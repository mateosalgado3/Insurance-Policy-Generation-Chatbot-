"""Embed chunks and upsert them into the Qdrant collection the API reads from.

Reads a JSONL file where each line matches the chunk schema produced by
scripts/chunk_policies.py, embeds each chunk's `text` with the OpenAI model
configured for the project, and upserts the vector + full record (as payload)
into the same Qdrant instance `insurance_chatbot.rag_service.RealRetrievalService`
queries at request time — same local path, same collection name, so nothing
else needs to change for retrieval to start finding these chunks.

Point IDs are derived deterministically from chunk_id (uuid5), so re-running
this script on the same chunks file re-indexes those chunks in place instead
of creating duplicates.

This makes real, billed calls to the OpenAI embeddings API — run it
deliberately, not as part of an automated test.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "index" / "chunks.jsonl"

# Deterministic namespace so the same chunk_id always maps to the same point,
# turning re-runs into upserts instead of duplicate inserts.
CHUNK_ID_NAMESPACE = uuid.UUID("2c9c9a0e-9f0a-4a9c-8f3e-8e2b6a1c9f2d")
REQUIRED_FIELDS = ("chunk_id", "text", "policy_id", "filename", "page", "document_hash")

# Avoids spending one embedding call just to learn the vector size for
# collection creation, for the models this project actually uses.
KNOWN_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run scripts/chunk_policies.py first")

    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            missing = [field for field in REQUIRED_FIELDS if field not in record]
            if missing:
                raise ValueError(f"{path}:{line_number} missing fields: {missing}")
            chunks.append(record)
    return chunks


def point_id_for(chunk_id: str) -> str:
    return str(uuid.uuid5(CHUNK_ID_NAMESPACE, chunk_id))


def batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def embed_texts(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def resolve_vector_size(client: OpenAI, model: str, sample_text: str) -> int:
    known = KNOWN_EMBEDDING_DIMENSIONS.get(model)
    if known:
        return known
    return len(embed_texts(client, model, [sample_text])[0])


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    if client.collection_exists(collection_name):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )


def index_chunks(
    chunks: list[dict[str, Any]],
    *,
    openai_client: OpenAI,
    qdrant_client: QdrantClient,
    embedding_model: str,
    collection_name: str,
    batch_size: int = 64,
) -> dict[str, Any]:
    if not chunks:
        return {"chunks_indexed": 0, "batches": 0, "collection": collection_name}

    vector_size = resolve_vector_size(openai_client, embedding_model, chunks[0]["text"])
    ensure_collection(qdrant_client, collection_name, vector_size)

    indexed = 0
    batches = 0
    for batch in batched(chunks, batch_size):
        vectors = embed_texts(openai_client, embedding_model, [chunk["text"] for chunk in batch])
        points = [
            models.PointStruct(id=point_id_for(chunk["chunk_id"]), vector=vector, payload=chunk)
            for chunk, vector in zip(batch, vectors, strict=True)
        ]
        qdrant_client.upsert(collection_name=collection_name, points=points)
        indexed += len(points)
        batches += 1
        print(f"  indexed batch {batches}: {indexed}/{len(chunks)} chunks")

    return {"chunks_indexed": indexed, "batches": batches, "collection": collection_name}


def build_clients(qdrant_path: str) -> tuple[OpenAI, QdrantClient]:
    load_dotenv(PROJECT_ROOT / ".env")
    return OpenAI(), QdrantClient(path=qdrant_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--collection", default=None, help="Defaults to $QDRANT_COLLECTION or queplan_policies.")
    parser.add_argument("--embedding-model", default=None, help="Defaults to $OPENAI_EMBEDDING_MODEL.")
    parser.add_argument("--qdrant-path", default=None, help="Defaults to $QDRANT_PATH or data/index/qdrant.")
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    chunks = load_chunks(args.chunks_path)

    # Same defaults as insurance_chatbot.rag_service.RealRetrievalService, so
    # this always writes to the same place the API reads from.
    qdrant_path = args.qdrant_path or os.getenv("QDRANT_PATH", "data/index/qdrant")
    openai_client, qdrant_client = build_clients(qdrant_path)
    embedding_model = args.embedding_model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    collection_name = args.collection or os.getenv("QDRANT_COLLECTION", "queplan_policies")

    print(f"Indexing {len(chunks)} chunks into '{collection_name}' at {qdrant_path} ({embedding_model})")
    result = index_chunks(
        chunks,
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model=embedding_model,
        collection_name=collection_name,
        batch_size=args.batch_size,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
