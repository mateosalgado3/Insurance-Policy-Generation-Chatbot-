"""Compatibility CLI for the canonical versioned Qdrant indexer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openai import OpenAI
from qdrant_client import QdrantClient

from insurance_chatbot.indexing import (
    CHUNK_ID_NAMESPACE as CHUNK_ID_NAMESPACE,
    DEFAULT_CHUNKS_PATH,
    KNOWN_EMBEDDING_DIMENSIONS as KNOWN_EMBEDDING_DIMENSIONS,
    REQUIRED_FIELDS as REQUIRED_FIELDS,
    annotate_existing_index,
    batched as batched,
    embed_texts as embed_texts,
    index_chunks,
    load_chunks,
    point_id_for as point_id_for,
    resolve_vector_size as resolve_vector_size,
)
from insurance_chatbot.settings import Settings


def build_clients(qdrant_path: str) -> tuple[OpenAI, QdrantClient]:
    settings = Settings.from_env()
    settings.require_openai()
    return (
        OpenAI(api_key=settings.openai_api_key),
        QdrantClient(path=qdrant_path),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--collection")
    parser.add_argument("--embedding-model")
    parser.add_argument("--qdrant-path")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Version the shared index without calling OpenAI.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    chunks = load_chunks(args.chunks_path)
    collection = args.collection or settings.qdrant_collection
    model = args.embedding_model or settings.embedding_model
    path = args.qdrant_path or str(settings.qdrant_path)
    qdrant = QdrantClient(path=path)
    try:
        if args.metadata_only:
            result = annotate_existing_index(
                qdrant,
                chunks,
                collection_name=collection,
                embedding_model=model,
            )
        else:
            settings.require_openai()
            result = index_chunks(
                chunks,
                openai_client=OpenAI(api_key=settings.openai_api_key),
                qdrant_client=qdrant,
                embedding_model=model,
                collection_name=collection,
                batch_size=args.batch_size,
            )
    finally:
        qdrant.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
