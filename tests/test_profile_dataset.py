"""Smoke test for scripts/profile_dataset.py against a tiny synthetic PDF corpus.

No real dataset is available in this environment (requires AWS credentials), so
this builds a handful of matplotlib-rendered PDFs that exercise the same paths
a real policy corpus would: numbered articles, an exact duplicate, a near
duplicate, and a page with no extractable text.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import profile_dataset  # noqa: E402


def _write_pdf(path: Path, articles: list[str]) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    lines: list[str] = []
    for index, body in enumerate(articles, start=1):
        lines.append(f"Articulo {index}: Titulo del articulo")
        lines.extend(textwrap.wrap(body, width=90))
    text = "\n".join(lines)

    with PdfPages(path) as pdf:
        figure, axis = plt.subplots(figsize=(8.5, 11))
        axis.axis("off")
        axis.text(0.02, 0.98, text, va="top", fontsize=9, family="monospace")
        pdf.savefig(figure)
        plt.close(figure)


def _write_blank_pdf(path: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(path) as pdf:
        figure, axis = plt.subplots(figsize=(8.5, 11))
        axis.axis("off")
        pdf.savefig(figure)
        plt.close(figure)


@pytest.fixture
def synthetic_corpus(tmp_path: Path) -> Path:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()

    articles_a = ["palabra " * 60, "cobertura " * 80, "exclusion " * 40]
    articles_b = ["palabra " * 60, "cobertura " * 80, "exclusion " * 41]  # near-duplicate of A
    articles_c = ["condicion " * 30, "prima " * 50, "vigencia " * 20, "renovacion " * 70]

    _write_pdf(input_dir / "policy_a.pdf", articles_a)
    _write_pdf(input_dir / "policy_a_copy.pdf", articles_a)  # exact text duplicate
    _write_pdf(input_dir / "policy_b.pdf", articles_b)
    _write_pdf(input_dir / "policy_c.pdf", articles_c)
    _write_blank_pdf(input_dir / "policy_scanned.pdf")  # no extractable text

    return input_dir


def test_run_profiling_end_to_end(synthetic_corpus: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "profiling"

    result = profile_dataset.run_profiling(
        input_dir=synthetic_corpus,
        output_dir=output_dir,
        test_ratio=0.2,
        seed=42,
    )

    assert result["summary"]["documents"] == 5
    assert result["nulls"]["documents_with_no_extractable_text_count"] == 1
    assert "policy_scanned.pdf" in result["nulls"]["documents_with_no_extractable_text"][0]

    for filename in (
        "document_metrics.csv",
        "article_lengths.csv",
        "train_test_split.csv",
        "chunk_estimates.csv",
        "summary.json",
        "report.md",
        "chunking_evidence.png",
    ):
        assert (output_dir / filename).exists(), f"missing {filename}"

    split = pd.read_csv(output_dir / "train_test_split.csv")
    assert set(split["split"]) <= {"train", "test"}
    assert len(split) == 5

    # policy_a and policy_a_copy are exact duplicates: same group, same split.
    groups = split.set_index("path")["duplicate_group_id"]
    assert groups["policy_a.pdf"] == groups["policy_a_copy.pdf"]
    splits = split.set_index("path")["split"]
    assert splits["policy_a.pdf"] == splits["policy_a_copy.pdf"]

    chunk_grid = pd.read_csv(output_dir / "chunk_estimates.csv")
    assert (chunk_grid["total_chunks"] > 0).all()

    proposal = result["chunk_proposal"]
    assert proposal["basis"] == "article_length_distribution"
    assert proposal["recommended_chunk_size_tokens"] in profile_dataset.DEFAULT_CHUNK_SIZE_CANDIDATES
    assert proposal["recommended_chunk_overlap_tokens"] < proposal["recommended_chunk_size_tokens"]


def test_estimate_chunks_matches_sliding_window_arithmetic() -> None:
    assert profile_dataset.estimate_chunks(0, 500, 50) == 0
    assert profile_dataset.estimate_chunks(400, 500, 50) == 1
    assert profile_dataset.estimate_chunks(500, 500, 50) == 1
    # 501 chars: one full chunk of 500, then 1 leftover char -> 2 chunks.
    assert profile_dataset.estimate_chunks(501, 500, 50) == 2


def test_estimate_chunks_rejects_overlap_not_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError):
        profile_dataset.estimate_chunks(1000, 500, 500)
