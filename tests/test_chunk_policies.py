"""Tests for scripts/chunk_policies.py against synthetic PDFs.

Reuses the PDF-generation helpers from test_profile_dataset.py instead of
duplicating them.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chunk_policies  # noqa: E402

from test_profile_dataset import _write_blank_pdf, _write_pdf  # noqa: E402


@pytest.fixture
def synthetic_corpus(tmp_path: Path) -> Path:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()

    # Article 2 is long enough to force more than one chunk at a small
    # chunk_size, so overlap behavior gets exercised too.
    articles = ["palabra corta. " * 20, "cobertura extensa. " * 400, "exclusion breve. " * 15]
    _write_pdf(input_dir / "POL0001.pdf", articles)
    _write_blank_pdf(input_dir / "POL0002.pdf")

    return input_dir


def test_run_chunking_end_to_end(synthetic_corpus: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "index" / "chunks.jsonl"

    result = chunk_policies.run_chunking(
        input_dir=synthetic_corpus,
        output_path=output_path,
        chunk_size_tokens=32,  # tiny on purpose, to force article 2 to split
        chunk_overlap_tokens=8,
    )

    assert result["documents"] == 2
    assert output_path.exists()

    records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == result["chunks"]
    assert len(records) > 0

    # The blank PDF has no extractable text, so it must contribute zero chunks
    # rather than a chunk full of empty text.
    assert all(record["policy_id"] != "POL0002" for record in records)

    required_fields = {
        "chunk_id",
        "text",
        "policy_id",
        "filename",
        "article",
        "page",
        "document_hash",
    }
    for record in records:
        assert required_fields <= record.keys()
        assert record["text"].strip() == record["text"]
        assert record["text"] != ""
        assert record["page"] >= 1
        assert record["policy_id"] == "POL0001"
        assert record["filename"] == "POL0001.pdf"

    # Article 2 ("cobertura extensa...") is long, so it must have split into
    # more than one chunk, and those chunks must be numbered sequentially.
    article_2_ids = sorted(
        r["chunk_id"] for r in records if r["chunk_id"].startswith("POL0001-art2-")
    )
    assert len(article_2_ids) > 1
    assert article_2_ids == [f"POL0001-art2-{i:03d}" for i in range(1, len(article_2_ids) + 1)]

    # All chunks of the same document share the same document_hash.
    hashes = {record["document_hash"] for record in records}
    assert len(hashes) == 1


def test_split_into_windows_matches_manual_slicing() -> None:
    text = "0123456789" * 5  # 50 characters
    windows = chunk_policies.split_into_windows(text, chunk_chars=20, overlap_chars=5)

    assert [start for start, _ in windows] == [0, 15, 30]
    assert windows[0][1] == text[0:20]
    assert windows[-1][1] == text[30:50]
    # Consecutive windows must actually overlap by the requested amount.
    assert windows[0][1][-5:] == windows[1][1][:5]


def test_split_into_windows_rejects_overlap_not_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError):
        chunk_policies.split_into_windows("abcdef", chunk_chars=10, overlap_chars=10)


def test_page_for_offset_maps_to_the_right_page() -> None:
    page_texts = ["a" * 10, "b" * 10, "c" * 10]
    offsets = chunk_policies.page_offsets(page_texts)  # [0, 11, 22]

    assert chunk_policies.page_for_offset(offsets, 0) == 1
    assert chunk_policies.page_for_offset(offsets, 10) == 1
    assert chunk_policies.page_for_offset(offsets, 11) == 2
    assert chunk_policies.page_for_offset(offsets, 25) == 3


def test_chunk_document_disambiguates_repeated_article_numbers(tmp_path: Path) -> None:
    """Bundled policies restart numbering per rider ("Artículo 1, 2...each
    section"), so the printed number alone collides across sections — this
    must not produce duplicate chunk_ids that would overwrite each other
    once indexed into Qdrant."""
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    path = input_dir / "POLBUNDLE.pdf"
    _write_pdf_with_headings(
        path,
        [
            ("Articulo 1: Reglas generales", "contenido de reglas generales. " * 10),
            ("Articulo 2: Cobertura principal", "contenido de cobertura principal. " * 10),
            ("Articulo 1: Beneficiarios del anexo", "contenido de beneficiarios del anexo. " * 10),
            ("Articulo 2: Exclusiones del anexo", "contenido de exclusiones del anexo. " * 10),
        ],
    )

    records = chunk_policies.chunk_document(path, chunk_chars=2000, overlap_chars=100)
    ids = [record["chunk_id"] for record in records]

    assert len(records) == 4
    assert len(ids) == len(set(ids)), f"chunk_id collision: {ids}"
    assert ids == [
        "POLBUNDLE-art1-001",
        "POLBUNDLE-art2-001",
        "POLBUNDLE-art1-002",
        "POLBUNDLE-art2-002",
    ]


def test_chunk_document_without_articles_falls_back_to_whole_document(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    path = input_dir / "NOARTS.pdf"
    _write_pdf_no_headings(path, "contenido sin encabezados numerados. " * 50)

    records = chunk_policies.chunk_document(path, chunk_chars=200, overlap_chars=20)

    assert len(records) >= 1
    assert all(record["article"] is None for record in records)
    assert all(record["chunk_id"].startswith("NOARTS-doc-") for record in records)


def _write_pdf_no_headings(path: Path, text: str) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    wrapped = "\n".join(textwrap.wrap(text, width=90))
    with PdfPages(path) as pdf:
        figure, axis = plt.subplots(figsize=(8.5, 11))
        axis.axis("off")
        axis.text(0.02, 0.98, wrapped, va="top", fontsize=9, family="monospace")
        pdf.savefig(figure)
        plt.close(figure)


def _write_pdf_with_headings(path: Path, sections: list[tuple[str, str]]) -> None:
    """Like test_profile_dataset._write_pdf, but with explicit heading text
    instead of auto-numbered ones — needed to simulate repeated article
    numbers across bundled riders."""
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    lines: list[str] = []
    for heading, body in sections:
        lines.append(heading)
        lines.extend(textwrap.wrap(body, width=90))
    text = "\n".join(lines)

    with PdfPages(path) as pdf:
        figure, axis = plt.subplots(figsize=(8.5, 11))
        axis.axis("off")
        axis.text(0.02, 0.98, text, va="top", fontsize=9, family="monospace")
        pdf.savefig(figure)
        plt.close(figure)
