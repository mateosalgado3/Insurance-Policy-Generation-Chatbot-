"""Cut indexable chunks out of the policy PDFs in data/raw.

Reuses `insurance_chatbot.eda` for PDF discovery, hashing and article
detection, then slices each article into overlapping windows sized by the
chunk_size/chunk_overlap that scripts/profile_dataset.py proposed from real
article-length evidence (see outputs/profiling/report.md):
chunk_size=1024 tokens, chunk_overlap=154 tokens.

Output: one JSON object per line (JSONL) at data/index/chunks.jsonl, ready
for scripts/index_chunks.py to embed and upload to Qdrant:

    {
      "chunk_id": "POL320190074-art12-001",
      "text": "...",
      "policy_id": "POL320190074",
      "filename": "POL320190074.pdf",
      "article": "Articulo 12",
      "page": 20,
      "document_hash": "..."
    }
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from insurance_chatbot import eda

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "index" / "chunks.jsonl"

# Matches the evidence-based proposal in outputs/profiling/report.md.
CHARS_PER_TOKEN = 4.0
DEFAULT_CHUNK_SIZE_TOKENS = 1024
DEFAULT_CHUNK_OVERLAP_TOKENS = 154

ARTICLE_NUMBER_RE = re.compile(r"\d+")

# eda.ARTICLE_RE also matches inline cross-references ("...ver Artículo 12 de
# estas Condiciones...") which are not real heading boundaries. Real headings
# in this corpus are formatted "ARTÍCULO N°: Título", so requiring a colon
# shortly after the match tells genuine headings apart from running text —
# without this, two "article 12" boundaries collide into the same chunk_id
# and the second silently overwrites the first once indexed into Qdrant.
ARTICLE_HEADING_LOOKAHEAD = 6


def is_heading_boundary(raw_text: str, match: re.Match[str]) -> bool:
    return ":" in raw_text[match.end() : match.end() + ARTICLE_HEADING_LOOKAHEAD]


def policy_id_from_filename(filename: str) -> str:
    return Path(filename).stem


def page_offsets(page_texts: list[str]) -> list[int]:
    """Start offset of each page inside "\\n".join(page_texts)."""
    offsets = []
    cursor = 0
    for text in page_texts:
        offsets.append(cursor)
        cursor += len(text) + 1  # account for the "\n" used to join pages
    return offsets


def page_for_offset(offsets: list[int], position: int) -> int:
    index = bisect.bisect_right(offsets, position) - 1
    return max(index, 0) + 1


def clean_chunk_text(text: str) -> str:
    """Collapse whitespace for storage without touching case or accents."""
    return " ".join(text.split())


def split_into_windows(text: str, chunk_chars: int, overlap_chars: int) -> list[tuple[int, str]]:
    """Sliding window over `text`; returns (start_offset, window_text) pairs."""
    if not text:
        return []
    step = chunk_chars - overlap_chars
    if step <= 0:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    windows: list[tuple[int, str]] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_chars, length)
        windows.append((start, text[start:end]))
        if end == length:
            break
        start += step
    return windows


def chunk_document(path: Path, chunk_chars: int, overlap_chars: int) -> list[dict[str, Any]]:
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

    if not matches:
        for window_index, (start, window_text) in enumerate(
            split_into_windows(raw_text, chunk_chars, overlap_chars), start=1
        ):
            text = clean_chunk_text(window_text)
            if not text:
                continue
            records.append(
                {
                    "chunk_id": f"{policy_id}-doc-{window_index:03d}",
                    "text": text,
                    "policy_id": policy_id,
                    "filename": filename,
                    "article": None,
                    "page": page_for_offset(offsets, start),
                    "document_hash": document_hash,
                }
            )
        return records

    bounds = [match.start() for match in matches] + [len(raw_text)]
    # Some policies bundle several "Cláusulas Adicionales" in one PDF, each
    # restarting its own "Artículo 1, 2, 3..." numbering, so the printed
    # number alone is not unique within the document. Counting occurrences
    # per number keeps the chunk_id shape (policy-artN-NNN) while guaranteeing
    # every id is unique — the `page` field tells apart which physical
    # occurrence of "Artículo N" a given chunk came from.
    sequence_by_slug: dict[str, int] = {}
    for article_index, match in enumerate(matches):
        article_start, article_end = bounds[article_index], bounds[article_index + 1]
        article_label = match.group(0).strip()
        number_match = ARTICLE_NUMBER_RE.search(article_label)
        article_slug = number_match.group(0) if number_match else str(article_index + 1)
        article_text = raw_text[article_start:article_end]

        for relative_start, window_text in split_into_windows(article_text, chunk_chars, overlap_chars):
            text = clean_chunk_text(window_text)
            if not text:
                continue
            sequence_by_slug[article_slug] = sequence_by_slug.get(article_slug, 0) + 1
            records.append(
                {
                    "chunk_id": f"{policy_id}-art{article_slug}-{sequence_by_slug[article_slug]:03d}",
                    "text": text,
                    "policy_id": policy_id,
                    "filename": filename,
                    "article": article_label,
                    "page": page_for_offset(offsets, article_start + relative_start),
                    "document_hash": document_hash,
                }
            )
    return records


def run_chunking(
    input_dir: Path,
    output_path: Path,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> dict[str, Any]:
    paths = eda.discover_pdfs(input_dir)
    if not paths:
        raise FileNotFoundError(f"No PDF files found under {input_dir}")

    chunk_chars = round(chunk_size_tokens * CHARS_PER_TOKEN)
    overlap_chars = round(chunk_overlap_tokens * CHARS_PER_TOKEN)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    with output_path.open("w", encoding="utf-8") as stream:
        for path in paths:
            for record in chunk_document(path, chunk_chars, overlap_chars):
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    return {
        "documents": len(paths),
        "chunks": total_chunks,
        "chunk_size_tokens": chunk_size_tokens,
        "chunk_overlap_tokens": chunk_overlap_tokens,
        "output_path": str(output_path),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--chunk-size-tokens", type=int, default=DEFAULT_CHUNK_SIZE_TOKENS)
    parser.add_argument("--chunk-overlap-tokens", type=int, default=DEFAULT_CHUNK_OVERLAP_TOKENS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_chunking(
        args.input_dir,
        args.output_path,
        args.chunk_size_tokens,
        args.chunk_overlap_tokens,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
