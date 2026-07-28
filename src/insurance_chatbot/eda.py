"""Reproducible exploratory analysis for the QuePlan insurance-policy PDFs.

The module deliberately performs no LLM calls. It audits the raw corpus before
chunking or embedding so retrieval failures can be separated from source-data
and PDF-extraction failures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import boto3
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = Path(os.getenv("DATA_INPUT_DIR", PROJECT_ROOT / "data" / "raw"))
DEFAULT_OUTPUT_DIR = Path(os.getenv("DATA_OUTPUT_DIR", PROJECT_ROOT / "outputs" / "eda")) 

# DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
# DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "eda"

WORD_RE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
ARTICLE_RE = re.compile(r"(?im)^\s*(?:art(?:í|i)culo|article)\s+(?:n[°ºo]\s*)?\d+[\w.-]*")
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b"
)
CURRENCY_RE = re.compile(r"(?i)(?:\b(?:USD|CLP|UF|UTM)\b|\$\s*\d)")
POLICY_ID_RE = re.compile(r"(?i)\b(?:POL|P[ÓO]LIZA\s*(?:N[°ºO])?)[-_: ]*\d{5,}\b")


@dataclass(slots=True)
class DocumentAudit:
    path: str
    filename: str
    extension: str
    size_bytes: int
    file_sha256: str
    text_sha256: str
    pages: int
    pages_with_text: int
    extraction_coverage: float
    characters: int
    words: int
    unique_words: int
    lexical_diversity: float
    sentences: int
    mean_words_per_sentence: float
    articles_detected: int
    dates_detected: int
    currency_mentions: int
    policy_ids_detected: int
    image_only_suspected: bool
    encrypted: bool
    extraction_error: str
    text_for_similarity: str


def sha256_bytes(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def discover_pdfs(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")


def safe_destination(root: Path, key: str, prefix: str) -> Path:
    relative = key[len(prefix) :] if key.startswith(prefix) else key
    destination = (root / relative.lstrip("/\\")).resolve()
    if root.resolve() not in destination.parents and destination != root.resolve():
        raise ValueError(f"Unsafe S3 object key: {key!r}")
    return destination


def download_dataset(destination: Path, limit: int | None = None) -> dict[str, int]:
    """Download the configured S3 prefix, skipping files already present at the same size."""
    load_dotenv(PROJECT_ROOT / ".env")
    bucket = os.getenv("S3_BUCKET", "anyoneai-datasets")
    prefix = os.getenv("S3_PREFIX", "queplan_insurance/")
    required = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    client = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    objects: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects.extend(item for item in page.get("Contents", []) if not item["Key"].endswith("/"))
    objects.sort(key=lambda item: item["Key"])
    if limit is not None:
        objects = objects[:limit]

    downloaded = skipped = 0
    for item in objects:
        target = safe_destination(destination, item["Key"], prefix)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size == item["Size"]:
            skipped += 1
            continue
        client.download_file(bucket, item["Key"], str(target))
        downloaded += 1
    return {"objects": len(objects), "downloaded": downloaded, "skipped": skipped}


def audit_pdf(path: Path, root: Path) -> DocumentAudit:
    error = ""
    encrypted = False
    page_texts: list[str] = []
    pages = 0
    try:
        reader = PdfReader(path, strict=False)
        encrypted = bool(reader.is_encrypted)
        if encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
        pages = len(reader.pages)
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_texts.append(page.extract_text() or "")
            except Exception as exc:
                page_texts.append("")
                error += f"page {page_number}: {type(exc).__name__}; "
    except Exception as exc:
        error = f"document: {type(exc).__name__}: {exc}"

    raw_text = "\n".join(page_texts)
    normalized = normalize_text(raw_text)
    words = WORD_RE.findall(normalized)
    word_count = len(words)
    unique_words = len(set(words))
    sentences = [sentence for sentence in SENTENCE_RE.split(normalized) if sentence.strip()]
    pages_with_text = sum(len(normalize_text(text)) >= 50 for text in page_texts)
    coverage = pages_with_text / pages if pages else 0.0

    return DocumentAudit(
        path=str(path.relative_to(root)).replace("\\", "/"),
        filename=path.name,
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        file_sha256=sha256_bytes(path),
        text_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else "",
        pages=pages,
        pages_with_text=pages_with_text,
        extraction_coverage=round(coverage, 4),
        characters=len(normalized),
        words=word_count,
        unique_words=unique_words,
        lexical_diversity=round(unique_words / word_count, 4) if word_count else 0.0,
        sentences=len(sentences),
        mean_words_per_sentence=round(word_count / len(sentences), 2) if sentences else 0.0,
        articles_detected=len(ARTICLE_RE.findall(raw_text)),
        dates_detected=len(DATE_RE.findall(raw_text)),
        currency_mentions=len(CURRENCY_RE.findall(raw_text)),
        policy_ids_detected=len(POLICY_ID_RE.findall(raw_text)),
        image_only_suspected=bool(pages and coverage < 0.25),
        encrypted=encrypted,
        extraction_error=error.strip(),
        text_for_similarity=normalized[:100_000],
    )


def add_duplicate_flags(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["exact_file_duplicate"] = frame["file_sha256"].duplicated(keep=False)
    nonempty = frame["text_sha256"].ne("")
    frame["exact_text_duplicate"] = False
    frame.loc[nonempty, "exact_text_duplicate"] = frame.loc[nonempty, "text_sha256"].duplicated(keep=False)
    return frame


def find_near_duplicates(frame: pd.DataFrame, threshold: float = 0.90) -> pd.DataFrame:
    usable = frame.loc[frame["text_for_similarity"].str.len() >= 100, ["path", "text_for_similarity"]]
    if len(usable) < 2:
        return pd.DataFrame(columns=["document", "nearest_document", "cosine_similarity"])

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        # Keep terms that occur in every document: tiny corpora and duplicate
        # audits commonly have no vocabulary left when max_df is below 1.0.
        max_df=1.0,
        max_features=30_000,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(usable["text_for_similarity"])
    neighbors = NearestNeighbors(n_neighbors=min(2, len(usable)), metric="cosine", algorithm="brute")
    neighbors.fit(matrix)
    distances, indices = neighbors.kneighbors(matrix)
    rows: list[dict[str, Any]] = []
    paths = usable["path"].tolist()
    for position, (distance_row, index_row) in enumerate(zip(distances, indices, strict=True)):
        candidates = [(distance, index) for distance, index in zip(distance_row, index_row, strict=True) if index != position]
        if not candidates:
            continue
        distance, nearest = min(candidates)
        similarity = float(1 - distance)
        if similarity >= threshold:
            rows.append(
                {
                    "document": paths[position],
                    "nearest_document": paths[nearest],
                    "cosine_similarity": round(similarity, 4),
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=["document", "nearest_document", "cosine_similarity"])
    result["_pair"] = result.apply(
        lambda row: "|".join(sorted((row["document"], row["nearest_document"]))), axis=1
    )
    return (
        result.sort_values("cosine_similarity", ascending=False)
        .drop_duplicates("_pair")
        .drop(columns="_pair")
        .reset_index(drop=True)
    )


def corpus_vocabulary(audits: Iterable[DocumentAudit], top_n: int = 30) -> list[dict[str, Any]]:
    stopwords = {
        "a", "al", "cada", "como", "con", "cualquier", "cuando", "de", "deberá", "del", "donde", "el",
        "en", "entre", "es", "esta", "estas", "este", "estos", "la", "las", "lo", "los", "más", "no",
        "o", "para", "podrá", "por", "que", "se", "será", "serán", "si", "sin", "sobre", "su", "sus",
        "un", "una", "y", "the", "of", "to", "and", "in", "is", "for",
    }
    counts: Counter[str] = Counter()
    for audit in audits:
        counts.update(word for word in WORD_RE.findall(audit.text_for_similarity) if len(word) > 2 and word not in stopwords)
    return [{"term": term, "count": count} for term, count in counts.most_common(top_n)]


def build_summary(frame: pd.DataFrame, near_duplicates: pd.DataFrame) -> dict[str, Any]:
    total_pages = int(frame["pages"].sum()) if not frame.empty else 0
    total_words = int(frame["words"].sum()) if not frame.empty else 0
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "documents": int(len(frame)),
        "total_size_mb": round(float(frame["size_bytes"].sum()) / 1_048_576, 2) if not frame.empty else 0.0,
        "total_pages": total_pages,
        "total_words": total_words,
        "median_pages_per_document": round(float(frame["pages"].median()), 2) if not frame.empty else 0.0,
        "mean_words_per_page": round(total_words / total_pages, 2) if total_pages else 0.0,
        "documents_with_extraction_errors": int(frame["extraction_error"].ne("").sum()) if not frame.empty else 0,
        "suspected_image_only_documents": int(frame["image_only_suspected"].sum()) if not frame.empty else 0,
        "encrypted_documents": int(frame["encrypted"].sum()) if not frame.empty else 0,
        "exact_file_duplicate_documents": int(frame["exact_file_duplicate"].sum()) if not frame.empty else 0,
        "exact_text_duplicate_documents": int(frame["exact_text_duplicate"].sum()) if not frame.empty else 0,
        "near_duplicate_pairs": int(len(near_duplicates)),
        "documents_without_detected_articles": int(frame["articles_detected"].eq(0).sum()) if not frame.empty else 0,
        "total_articles_detected": int(frame["articles_detected"].sum()) if not frame.empty else 0,
        "total_policy_ids_detected": int(frame["policy_ids_detected"].sum()) if not frame.empty else 0,
    }


def save_plots(frame: pd.DataFrame, output_path: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    axes[0, 0].hist(frame["pages"], bins=min(30, max(5, len(frame))), color="#0f766e", edgecolor="white")
    axes[0, 0].set(title="Páginas por documento", xlabel="Páginas", ylabel="Documentos")

    positive_words = frame.loc[frame["words"] > 0, "words"]
    axes[0, 1].hist(positive_words, bins=min(30, max(5, len(positive_words))), color="#2563eb", edgecolor="white")
    axes[0, 1].set(title="Palabras extraídas por documento", xlabel="Palabras", ylabel="Documentos")

    axes[1, 0].scatter(frame["pages"], frame["words"], alpha=0.65, color="#7c3aed")
    axes[1, 0].set(title="Longitud y extracción", xlabel="Páginas", ylabel="Palabras extraídas")

    quality = pd.Series(
        {
            "Extracción saludable": int((~frame["image_only_suspected"] & frame["extraction_error"].eq("")).sum()),
            "Posible PDF escaneado": int(frame["image_only_suspected"].sum()),
            "Error de extracción": int(frame["extraction_error"].ne("").sum()),
            "Texto duplicado": int(frame["exact_text_duplicate"].sum()),
        }
    )
    axes[1, 1].barh(quality.index, quality.values, color=["#16a34a", "#f59e0b", "#dc2626", "#64748b"])
    axes[1, 1].set(title="Señales de calidad", xlabel="Documentos")
    figure.suptitle("Corpus de seguros QuePlan — resumen EDA", fontsize=16, fontweight="bold")
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def write_markdown_report(summary: dict[str, Any], vocabulary: list[dict[str, Any]], output_path: Path) -> None:
    top_terms = ", ".join(f"`{item['term']}` ({item['count']})" for item in vocabulary[:15]) or "No text extracted"
    risk_lines = []
    if summary["suspected_image_only_documents"]:
        risk_lines.append("- Ejecutar OCR antes de indexar los documentos marcados como posibles escaneos.")
    if summary["exact_text_duplicate_documents"]:
        risk_lines.append("- Deduplicar por hash del texto normalizado antes de crear embeddings.")
    if summary["documents_with_extraction_errors"]:
        risk_lines.append("- Aislar y revisar manualmente los errores de extracción antes de la ingestión.")
    if not risk_lines:
        risk_lines.append("- No se detectaron bloqueos de extracción ni duplicados exactos.")

    content = f"""# Análisis Exploratorio de Datos — pólizas QuePlan

Generated: {summary['generated_at_utc']}

## Resumen ejecutivo

- Documentos: **{summary['documents']:,}**
- Tamaño del corpus: **{summary['total_size_mb']:,} MB**
- Páginas: **{summary['total_pages']:,}**
- Palabras extraídas: **{summary['total_words']:,}**
- Mediana de páginas/documento: **{summary['median_pages_per_document']:,}**
- Media de palabras extraídas/página: **{summary['mean_words_per_page']:,}**
- Artículos detectados: **{summary['total_articles_detected']:,}**
- PDFs posiblemente escaneados: **{summary['suspected_image_only_documents']:,}**
- PDFs con errores de extracción: **{summary['documents_with_extraction_errors']:,}**
- Documentos con texto exactamente duplicado: **{summary['exact_text_duplicate_documents']:,}**
- Pares casi duplicados (coseno ≥ 0.90): **{summary['near_duplicate_pairs']:,}**

## Términos informativos más frecuentes

{top_terms}

## Recomendaciones de ciencia de datos

{chr(10).join(risk_lines)}
- Preservar póliza, página y artículo en cada chunk para producir citas verificables.
- Comparar chunking por artículo contra ventanas fijas usando Recall@k, MRR y nDCG.
- Construir un conjunto de evaluación revisado por humanos antes de cambiar embeddings o reranking.
- No interpretar similitud léxica como equivalencia legal; toda cláusula generada requiere revisión humana.

## Artefactos

- `document_metrics.csv`: una fila por PDF con métricas y banderas de calidad.
- `near_duplicates.csv`: pares de alta similitud para validación manual.
- `top_terms.csv`: perfil de vocabulario del corpus.
- `summary.json`: estadísticas agregadas legibles por máquina.
- `eda_overview.png`: resumen visual compacto.
"""
    output_path.write_text(content, encoding="utf-8")


def run_eda(input_dir: Path, output_dir: Path, limit: int | None = None, plots: bool = True) -> dict[str, Any]:
    paths = discover_pdfs(input_dir)
    if limit is not None:
        paths = paths[:limit]
    if not paths:
        raise FileNotFoundError(f"No PDF files found under {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    audits = [audit_pdf(path, input_dir) for path in paths]
    frame = pd.DataFrame(asdict(audit) for audit in audits)
    frame = add_duplicate_flags(frame)
    near_duplicates = find_near_duplicates(frame)
    vocabulary = corpus_vocabulary(audits)
    summary = build_summary(frame, near_duplicates)

    frame.drop(columns=["text_for_similarity"]).to_csv(output_dir / "document_metrics.csv", index=False, encoding="utf-8")
    near_duplicates.to_csv(output_dir / "near_duplicates.csv", index=False, encoding="utf-8")
    pd.DataFrame(vocabulary).to_csv(output_dir / "top_terms.csv", index=False, encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(summary, vocabulary, output_dir / "report.md")
    if plots:
        save_plots(frame, output_dir / "eda_overview.png")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--download", action="store_true", help="Download the configured S3 prefix first.")
    parser.add_argument("--limit", type=int, default=None, help="Limit files for a fast smoke test.")
    parser.add_argument("--skip-plots", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env")
    try:
        if args.download:
            result = download_dataset(args.input_dir, args.limit)
            print(f"S3 sync: {result}")
        summary = run_eda(args.input_dir, args.output_dir, args.limit, plots=not args.skip_plots)
    except Exception as exc:
        print(f"EDA failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Artifacts written to: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
