"""Generate the canonical article-aware chunks JSONL without API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from insurance_chatbot.indexing import (
    ARTICLE_HEADING_LOOKAHEAD as ARTICLE_HEADING_LOOKAHEAD,
    DEFAULT_CHUNKS_PATH,
    DEFAULT_CHUNK_OVERLAP_TOKENS,
    DEFAULT_CHUNK_SIZE_TOKENS,
    DEFAULT_INPUT_DIR,
    chunk_document as chunk_document,
    clean_chunk_text as clean_chunk_text,
    is_heading_boundary as is_heading_boundary,
    page_for_offset as page_for_offset,
    page_offsets as page_offsets,
    policy_id_from_filename as policy_id_from_filename,
    run_chunking,
    split_into_windows as split_into_windows,
)
from insurance_chatbot.settings import Settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--chunk-size-tokens", type=int, default=DEFAULT_CHUNK_SIZE_TOKENS)
    parser.add_argument(
        "--chunk-overlap-tokens",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP_TOKENS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_chunking(
        args.input_dir,
        args.output_path,
        args.chunk_size_tokens,
        args.chunk_overlap_tokens,
        embedding_model=Settings.from_env().embedding_model,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
