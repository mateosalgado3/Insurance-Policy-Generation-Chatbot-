"""Dataset profiling for chunking decisions on the QuePlan insurance corpus.

Builds on `insurance_chatbot.eda` (per-PDF extraction and quality audit) and adds
what that module does not cover:

- a leakage-safe train/test split of the corpus, where exact- and near-duplicate
  policies are kept together so the same (or near-identical) text never appears
  on both sides of the split,
- article-level length statistics, used as evidence for a chunk_size decision,
- a chunk-count estimate for a grid of chunk_size / chunk_overlap candidates,
- a written recommendation for chunk_size and chunk_overlap.

Assumption (undocumented in the project brief): this corpus is a set of policy
PDFs, not a labeled dataset, so "train/test" here means a document-level split
for retrieval evaluation later on (train = indexed corpus, test = holdout used
to build evaluation questions), grouped so duplicate/near-duplicate policies
don't leak across the split. See report.md's "Supuestos" section.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from random import Random
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from pypdf import PdfReader

from insurance_chatbot import eda

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "profiling"

# Rough chars-per-token ratio for GPT-style tokenizers on English/Spanish legal
# text. Avoids a tokenizer dependency that needs a network call on first use.
CHARS_PER_TOKEN = 4.0
DEFAULT_CHUNK_SIZE_CANDIDATES = [128, 256, 384, 512, 768, 1024]
DEFAULT_OVERLAP_RATIOS = [0.0, 0.1, 0.15, 0.2]


def extract_raw_text(path: Path) -> str:
    """Re-extract page text for article segmentation.

    `eda.audit_pdf` only keeps a normalized, whitespace-collapsed copy of the
    text (for TF-IDF similarity), which destroys the line starts that
    `eda.ARTICLE_RE` needs. Re-reading is wasteful but keeps eda.py untouched.
    """
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def split_into_articles(raw_text: str) -> list[str]:
    """Split a document's raw text at each detected article/clause heading."""
    matches = list(eda.ARTICLE_RE.finditer(raw_text))
    if not matches:
        return []
    bounds = [match.start() for match in matches] + [len(raw_text)]
    return [raw_text[bounds[i] : bounds[i + 1]].strip() for i in range(len(matches))]


def build_article_lengths(paths: list[Path], input_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        raw_text = extract_raw_text(path)
        for index, article in enumerate(split_into_articles(raw_text), start=1):
            normalized = eda.normalize_text(article)
            words = len(eda.WORD_RE.findall(normalized))
            rows.append(
                {
                    "path": str(path.relative_to(input_dir)).replace("\\", "/"),
                    "article_index": index,
                    "characters": len(normalized),
                    "words": words,
                    "estimated_tokens": round(len(normalized) / CHARS_PER_TOKEN, 1),
                }
            )
    return pd.DataFrame(rows, columns=["path", "article_index", "characters", "words", "estimated_tokens"])


def report_nulls(frame: pd.DataFrame) -> dict[str, Any]:
    missing_by_column = {
        column: int(frame[column].isna().sum())
        for column in frame.columns
        if int(frame[column].isna().sum()) > 0
    }
    empty_text = frame.loc[frame["words"].eq(0) | frame["pages_with_text"].eq(0), "path"].tolist()
    return {
        "missing_values_by_column": missing_by_column,
        "documents_with_no_extractable_text": empty_text,
        "documents_with_no_extractable_text_count": len(empty_text),
    }


def union_find_groups(paths: list[str], pairs: list[tuple[str, str]]) -> dict[str, str]:
    parent = {path: path for path in paths}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    for left, right in pairs:
        union(left, right)
    return {path: find(path) for path in paths}


def build_duplicate_groups(frame: pd.DataFrame, near_duplicates: pd.DataFrame) -> dict[str, str]:
    pairs: list[tuple[str, str]] = []
    for _, group in frame[frame["text_sha256"].ne("")].groupby("text_sha256"):
        paths = group["path"].tolist()
        pairs.extend(zip(paths, paths[1:]))
    pairs.extend(zip(near_duplicates["document"], near_duplicates["nearest_document"]))
    return union_find_groups(frame["path"].tolist(), pairs)


def train_test_split_groups(
    frame: pd.DataFrame, groups: dict[str, str], test_ratio: float, seed: int
) -> pd.DataFrame:
    """Split by duplicate group so near-identical policies stay on one side."""
    group_to_paths: dict[str, list[str]] = defaultdict(list)
    for path, group_id in groups.items():
        group_to_paths[group_id].append(path)

    group_ids = sorted(group_to_paths)
    Random(seed).shuffle(group_ids)

    target_test = round(len(frame) * test_ratio)
    test_paths: set[str] = set()
    for group_id in group_ids:
        if len(test_paths) >= target_test:
            break
        test_paths.update(group_to_paths[group_id])

    split = pd.DataFrame({"path": list(groups.keys())})
    split["duplicate_group_id"] = split["path"].map(groups)
    split["split"] = split["path"].apply(lambda path: "test" if path in test_paths else "train")
    return split.sort_values("path").reset_index(drop=True)


def estimate_chunks(length_chars: int, chunk_chars: int, overlap_chars: int) -> int:
    if length_chars <= 0:
        return 0
    step = chunk_chars - overlap_chars
    if step <= 0:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if length_chars <= chunk_chars:
        return 1
    return 1 + math.ceil((length_chars - chunk_chars) / step)


def build_chunk_grid(
    frame: pd.DataFrame,
    chunk_size_candidates: list[int],
    overlap_ratios: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for chunk_size_tokens in chunk_size_candidates:
        chunk_chars = round(chunk_size_tokens * CHARS_PER_TOKEN)
        for overlap_ratio in overlap_ratios:
            overlap_chars = round(chunk_chars * overlap_ratio)
            chunk_counts = frame["characters"].apply(
                lambda length: estimate_chunks(length, chunk_chars, overlap_chars)
            )
            rows.append(
                {
                    "chunk_size_tokens": chunk_size_tokens,
                    "chunk_overlap_ratio": overlap_ratio,
                    "chunk_overlap_tokens": round(overlap_chars / CHARS_PER_TOKEN, 1),
                    "total_chunks": int(chunk_counts.sum()),
                    "mean_chunks_per_document": round(float(chunk_counts.mean()), 2) if len(frame) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def propose_chunk_params(
    article_lengths: pd.DataFrame,
    chunk_size_candidates: list[int],
    target_coverage: float,
    overlap_ratio: float,
) -> dict[str, Any]:
    """Pick chunk_size as the smallest candidate whose *actual measured*
    coverage (share of articles that fit without being split) reaches
    `target_coverage`, using the article length distribution as evidence.

    Insurance clause lengths are heavily right-skewed (a handful of very long
    "Coberturas"/"Exclusiones" articles next to many short ones), so no small
    chunk_size will cover every percentile. If no candidate reaches the
    target, this reports the best achievable coverage instead of silently
    claiming a target it didn't hit — the long tail is expected to split
    across overlapping chunks, which is normal for RAG chunking.
    """
    if article_lengths.empty:
        return {
            "basis": "no_articles_detected",
            "recommended_chunk_size_tokens": None,
            "recommended_chunk_overlap_tokens": None,
            "evidence": {},
        }

    tokens = article_lengths["estimated_tokens"]
    coverage_by_candidate = {size: float((tokens <= size).mean()) for size in chunk_size_candidates}
    meeting_target = [size for size, coverage in coverage_by_candidate.items() if coverage >= target_coverage]
    candidate = min(meeting_target) if meeting_target else max(chunk_size_candidates)
    overlap_tokens = round(candidate * overlap_ratio)
    return {
        "basis": "article_length_distribution",
        "target_coverage": target_coverage,
        "met_target_coverage": bool(meeting_target),
        "achieved_coverage_at_recommended_size": round(coverage_by_candidate[candidate], 4),
        "coverage_by_candidate": {str(size): round(cov, 4) for size, cov in coverage_by_candidate.items()},
        "article_tokens_p50": round(float(tokens.quantile(0.5)), 1),
        "article_tokens_p75": round(float(tokens.quantile(0.75)), 1),
        "article_tokens_p90": round(float(tokens.quantile(0.9)), 1),
        "article_tokens_max": round(float(tokens.max()), 1),
        "recommended_chunk_size_tokens": candidate,
        "recommended_chunk_overlap_tokens": overlap_tokens,
        "recommended_chunk_overlap_ratio": overlap_ratio,
    }


def save_evidence_plot(article_lengths: pd.DataFrame, proposal: dict[str, Any], output_path: Path) -> None:
    if article_lengths.empty:
        return
    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.hist(
        article_lengths["estimated_tokens"],
        bins=min(40, max(5, len(article_lengths) // 3)),
        color="#0f766e",
        edgecolor="white",
    )
    chunk_size = proposal.get("recommended_chunk_size_tokens")
    if chunk_size:
        axis.axvline(chunk_size, color="#dc2626", linestyle="--", linewidth=2, label=f"chunk_size propuesto = {chunk_size} tokens")
        axis.legend()
    axis.set(
        title="Distribución de longitud de artículos/cláusulas (tokens estimados)",
        xlabel="Tokens estimados por artículo",
        ylabel="Artículos",
    )
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def write_markdown_report(
    summary: dict[str, Any],
    nulls: dict[str, Any],
    split: pd.DataFrame,
    chunk_grid: pd.DataFrame,
    proposal: dict[str, Any],
    output_path: Path,
) -> None:
    split_counts = split["split"].value_counts().to_dict()
    grid_rows = "\n".join(
        f"| {row.chunk_size_tokens} | {row.chunk_overlap_ratio:.0%} | {row.total_chunks} | {row.mean_chunks_per_document} |"
        for row in chunk_grid.itertuples()
    )
    if proposal["basis"] == "article_length_distribution":
        achieved = proposal["achieved_coverage_at_recommended_size"]
        if proposal["met_target_coverage"]:
            fit_line = (
                f"- `chunk_size` propuesto: **{proposal['recommended_chunk_size_tokens']} tokens** "
                f"(el candidato más chico de la grilla cuya cobertura medida alcanza el objetivo de "
                f"{proposal['target_coverage']:.0%}; cobertura real: **{achieved:.0%}** de los artículos "
                "caben en un solo chunk sin truncarse)."
            )
        else:
            fit_line = (
                f"- `chunk_size` propuesto: **{proposal['recommended_chunk_size_tokens']} tokens** "
                f"(el candidato más grande disponible; **ningún candidato de la grilla alcanza** el objetivo "
                f"de {proposal['target_coverage']:.0%} — la distribución de artículos tiene una cola larga "
                f"de cláusulas extensas. Cobertura real lograda: **{achieved:.0%}**. Forzar un chunk_size que "
                "cubra ese percentil requeriría varios miles de tokens, lo que degradaría la precisión de "
                "recuperación; se prioriza un chunk_size razonable y se acepta que el "
                f"{1 - achieved:.0%} de artículos más largos se divida en varios chunks solapados)."
            )
        proposal_lines = (
            f"- Longitud de artículo: mediana **{proposal['article_tokens_p50']} tokens**, "
            f"p75 **{proposal['article_tokens_p75']}**, p90 **{proposal['article_tokens_p90']}**, "
            f"máximo **{proposal['article_tokens_max']}**.\n"
            f"{fit_line}\n"
            f"- `chunk_overlap` propuesto: **{proposal['recommended_chunk_overlap_tokens']} tokens** "
            f"(~{proposal['recommended_chunk_overlap_ratio']:.0%} del chunk_size, para preservar contexto "
            "en los artículos que sí quedan divididos)."
        )
    else:
        proposal_lines = (
            "- No se detectaron artículos/cláusulas numeradas; no hay evidencia suficiente para proponer "
            "chunk_size/chunk_overlap todavía. Revisar manualmente el formato de estos documentos."
        )

    content = f"""# Perfilado del dataset — train/test, nulos, duplicados y chunking

Generated: {summary['generated_at_utc']}


## Resumen del corpus

- Documentos: **{summary['documents']:,}**
- Tamaño: **{summary['total_size_mb']:,} MB**
- Páginas: **{summary['total_pages']:,}**
- Palabras extraídas: **{summary['total_words']:,}**

## Nulos y calidad de extracción

- Documentos sin texto extraíble: **{nulls['documents_with_no_extractable_text_count']}**
  {', '.join(nulls['documents_with_no_extractable_text']) or '(ninguno)'}
- Columnas con valores nulos en `document_metrics.csv`: **{nulls['missing_values_by_column'] or 'ninguna'}**
- PDFs posiblemente escaneados (candidatos a OCR): **{summary['suspected_image_only_documents']:,}**
- Documentos con errores de extracción: **{summary['documents_with_extraction_errors']:,}**

## Duplicados

- Duplicados exactos por archivo: **{summary['exact_file_duplicate_documents']:,}**
- Duplicados exactos por texto normalizado: **{summary['exact_text_duplicate_documents']:,}**
- Pares casi duplicados (coseno ≥ 0.90): **{summary['near_duplicate_pairs']:,}**
- Grupos de duplicados usados para evitar leakage en el split: **{split['duplicate_group_id'].nunique()}**

## Split train/test

- Train: **{split_counts.get('train', 0)}** documentos
- Test: **{split_counts.get('test', 0)}** documentos
- Split reproducible (semilla fija), agrupado por duplicado/casi-duplicado — ver `train_test_split.csv`.
{f"- **Corpus chico ({summary['documents']} documentos):** los percentiles y el split train/test son ilustrativos, no estadísticamente robustos. Cuando el bucket S3 tenga más pólizas, re-ejecutar este script y revisar si la propuesta de chunk_size cambia." if summary['documents'] < 30 else ""}

## Chunks estimados por combinación chunk_size / chunk_overlap

| chunk_size (tokens) | overlap | chunks totales | chunks/documento (media) |
|---|---|---|---|
{grid_rows}

Ver `chunk_estimates.csv` para la grilla completa.

## Propuesta de chunk_size y chunk_overlap, con evidencia

*Los "tokens" de esta sección son una estimación (~{CHARS_PER_TOKEN:.0f} caracteres/token), no un conteo
exacto de un tokenizer de OpenAI — se evitó esa dependencia porque requiere descargar el vocabulario BPE
por red. Suficiente para comparar candidatos de chunk_size entre sí; antes de fijar el valor en producción,
validar el conteo real con `tiktoken` contra el modelo de embeddings elegido.*

{proposal_lines}

## Artefactos

- `document_metrics.csv`: métricas y banderas de calidad por PDF (nulos, duplicados, longitudes).
- `article_lengths.csv`: longitud por artículo/cláusula detectado (evidencia del chunk_size).
- `train_test_split.csv`: asignación train/test por documento y grupo de duplicados.
- `chunk_estimates.csv`: grilla completa de chunks estimados por chunk_size/overlap.
- `chunking_evidence.png`: histograma de longitud de artículos con el chunk_size propuesto marcado.
- `summary.json`: todo lo anterior en formato máquina.
"""
    output_path.write_text(content, encoding="utf-8")


def run_profiling(
    input_dir: Path,
    output_dir: Path,
    test_ratio: float = 0.2,
    seed: int = 42,
    target_coverage: float = 0.9,
    overlap_ratio: float = 0.15,
    chunk_size_candidates: list[int] | None = None,
    overlap_ratios: list[float] | None = None,
    plots: bool = True,
) -> dict[str, Any]:
    chunk_size_candidates = sorted(chunk_size_candidates or DEFAULT_CHUNK_SIZE_CANDIDATES)
    overlap_ratios = overlap_ratios or DEFAULT_OVERLAP_RATIOS

    paths = eda.discover_pdfs(input_dir)
    if not paths:
        raise FileNotFoundError(f"No PDF files found under {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    audits = [eda.audit_pdf(path, input_dir) for path in paths]
    frame = pd.DataFrame(asdict(audit) for audit in audits)
    frame = eda.add_duplicate_flags(frame)
    near_duplicates = eda.find_near_duplicates(frame)
    summary = eda.build_summary(frame, near_duplicates)

    nulls = report_nulls(frame)
    groups = build_duplicate_groups(frame, near_duplicates)
    split = train_test_split_groups(frame, groups, test_ratio, seed)

    article_lengths = build_article_lengths(paths, input_dir)
    chunk_grid = build_chunk_grid(frame, chunk_size_candidates, overlap_ratios)
    proposal = propose_chunk_params(article_lengths, chunk_size_candidates, target_coverage, overlap_ratio)

    frame.drop(columns=["text_for_similarity"]).to_csv(output_dir / "document_metrics.csv", index=False)
    article_lengths.to_csv(output_dir / "article_lengths.csv", index=False)
    split.to_csv(output_dir / "train_test_split.csv", index=False)
    chunk_grid.to_csv(output_dir / "chunk_estimates.csv", index=False)

    result = {
        "summary": summary,
        "nulls": nulls,
        "split_counts": split["split"].value_counts().to_dict(),
        "duplicate_groups": int(split["duplicate_group_id"].nunique()),
        "chunk_proposal": proposal,
    }
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(summary, nulls, split, chunk_grid, proposal, output_dir / "report.md")
    if plots:
        save_evidence_plot(article_lengths, proposal, output_dir / "chunking_evidence.png")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-coverage", type=float, default=0.9, help="Percentile of article length that must fit in one chunk.")
    parser.add_argument("--overlap-ratio", type=float, default=0.15, help="Proposed chunk_overlap as a ratio of the proposed chunk_size.")
    parser.add_argument("--chunk-size-candidates", type=int, nargs="+", default=None)
    parser.add_argument("--overlap-ratios", type=float, nargs="+", default=None)
    parser.add_argument("--skip-plots", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_profiling(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        test_ratio=args.test_ratio,
        seed=args.seed,
        target_coverage=args.target_coverage,
        overlap_ratio=args.overlap_ratio,
        chunk_size_candidates=args.chunk_size_candidates,
        overlap_ratios=args.overlap_ratios,
        plots=not args.skip_plots,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Artifacts written to: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
