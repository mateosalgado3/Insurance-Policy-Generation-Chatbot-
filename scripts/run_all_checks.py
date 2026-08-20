"""Run the complete project verification suite and replace one Markdown report.

The default run includes paid OpenAI evaluations. Use ``--skip-paid`` to run
only deterministic local checks while developing the report itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "evaluation-results.md"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluation"


@dataclass
class CheckResult:
    name: str
    command: list[str]
    status: str
    duration_seconds: float
    output: str = ""
    report_path: Path | None = None


def run_command(
    name: str,
    command: list[str],
    *,
    report_path: Path | None = None,
) -> CheckResult:
    """Execute one check without preventing the remaining checks from running."""
    started = time.perf_counter()
    environment = {**os.environ, "PYTHONUTF8": "1"}
    if report_path is not None:
        report_path.unlink(missing_ok=True)
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        status = "passed" if completed.returncode == 0 else "failed"
    except OSError as exc:
        output = f"Could not start command: {exc}"
        status = "failed"
    return CheckResult(
        name=name,
        command=command,
        status=status,
        duration_seconds=round(time.perf_counter() - started, 2),
        output=output,
        report_path=report_path,
    )


def skipped_result(name: str, reason: str) -> CheckResult:
    return CheckResult(
        name=name,
        command=[],
        status="skipped",
        duration_seconds=0.0,
        output=reason,
    )


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def number(value: Any, digits: int = 4) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    return f"{value:.{digits}f}"


def status_label(status: str) -> str:
    return {"passed": "PASS", "failed": "FAIL", "skipped": "SKIPPED"}[status]


def command_text(command: list[str]) -> str:
    if not command:
        return "—"
    rendered = ["python" if item == sys.executable else item for item in command]
    return " ".join(rendered)


def git_value(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def pytest_summary(output: str) -> str:
    matches = re.findall(
        r"(\d+\s+(?:passed|failed|skipped|xfailed|xpassed|error|errors))",
        output,
        flags=re.IGNORECASE,
    )
    return ", ".join(matches[-6:]) if matches else "See execution details"


def render_retrieval(title: str, report: dict[str, Any]) -> list[str]:
    metrics = report.get("metrics", {})
    lines = [
        f"### {title}",
        "",
        f"Provider: `{markdown_escape(report.get('provider', 'unknown'))}` · "
        f"Embedding: `{markdown_escape(report.get('embedding_model', 'unknown'))}` · "
        f"Top-k: `{metrics.get('top_k', '—')}`",
        "",
        "| Cases | Labeled | Unlabeled | Hit Rate@k | Recall@k | MRR |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            f"| {metrics.get('total_questions', metrics.get('questions', '—'))} "
            f"| {metrics.get('labeled_questions', metrics.get('questions', '—'))} "
            f"| {metrics.get('unlabeled_questions', 0)} "
            f"| {number(metrics.get('hit_rate_at_k'))} "
            f"| {number(metrics.get('recall_at_k'))} "
            f"| {number(metrics.get('mrr'))} |"
        ),
    ]
    by_type = metrics.get("by_type")
    if isinstance(by_type, dict) and by_type:
        lines.extend(
            [
                "",
                "| Type | Cases | Labeled | Hit Rate@k | Recall@k | MRR |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for case_type, values in by_type.items():
            lines.append(
                f"| {markdown_escape(case_type)} | {values.get('total_cases', '—')} "
                f"| {values.get('labeled_questions', '—')} "
                f"| {number(values.get('hit_rate_at_k'))} "
                f"| {number(values.get('recall_at_k'))} "
                f"| {number(values.get('mrr'))} |"
            )
    threshold = report.get("exploratory_threshold")
    if isinstance(threshold, dict):
        lines.extend(
            [
                "",
                "Exploratory score threshold: "
                f"`{number(threshold.get('score_threshold'))}`; labeled precision "
                f"`{number(threshold.get('labeled_precision'))}`, recall "
                f"`{number(threshold.get('labeled_recall'))}`, F1 "
                f"`{number(threshold.get('labeled_f1'))}`.",
            ]
        )
    return lines


def render_ragas(report: dict[str, Any]) -> list[str]:
    summary = report.get("summary", {})
    answer = summary.get("answer_relevancy", {})
    context = summary.get("context_relevance", {})
    threshold = summary.get("health_threshold", 0.6)
    lines = [
        "## RAGAS",
        "",
        f"Generator: `{markdown_escape(report.get('generator_model', 'unknown'))}` · "
        f"Evaluator: `{markdown_escape(report.get('evaluator_model', 'unknown'))}` · "
        f"Embedding: `{markdown_escape(report.get('embedding_model', 'unknown'))}` · "
        f"Top-k: `{report.get('top_k', '—')}`",
        "",
        f"Cases: `{summary.get('cases', '—')}` · Health threshold: `{number(threshold, 2)}` "
        f"· Overall: `{'HEALTHY' if summary.get('healthy') else 'REVIEW'}`",
        "",
        "| Metric | Mean | Minimum | Passing cases | Healthy |",
        "|---|---:|---:|---:|---|",
        f"| Answer Relevancy | {number(answer.get('mean'))} | {number(answer.get('minimum'))} "
        f"| {answer.get('passing_cases', '—')}/{summary.get('cases', '—')} "
        f"| {'yes' if answer.get('healthy') else 'no'} |",
        f"| Context Relevance | {number(context.get('mean'))} | {number(context.get('minimum'))} "
        f"| {context.get('passing_cases', '—')}/{summary.get('cases', '—')} "
        f"| {'yes' if context.get('healthy') else 'no'} |",
        f"| Combined mean | {number(summary.get('overall_mean'))} | — | — | "
        f"{'yes' if summary.get('healthy') else 'no'} |",
    ]
    by_type = summary.get("by_type")
    if isinstance(by_type, dict) and by_type:
        lines.extend(
            [
                "",
                "| Type | Cases | Answer Relevancy | Context Relevance |",
                "|---|---:|---:|---:|",
            ]
        )
        for case_type, values in by_type.items():
            lines.append(
                f"| {markdown_escape(case_type)} | {values.get('cases', '—')} "
                f"| {number(values.get('answer_relevancy_mean'))} "
                f"| {number(values.get('context_relevance_mean'))} |"
            )
    comparison = report.get("baseline_comparison")
    if isinstance(comparison, dict):
        lines.extend(["", f"Baseline matched cases: `{comparison.get('matched_cases', 0)}`."])
        for key, label in (
            ("answer_relevancy", "Answer Relevancy"),
            ("context_relevance", "Context Relevance"),
        ):
            values = comparison.get(key)
            if isinstance(values, dict):
                lines.append(
                    f"- {label}: current `{number(values.get('current_mean'))}`, baseline "
                    f"`{number(values.get('baseline_mean'))}`, delta `{number(values.get('delta'))}`."
                )
    return lines


def render_latency(report: dict[str, Any]) -> list[str]:
    summary = report.get("summary", {})
    labels = {
        "time_to_model_ms": "Up to model",
        "model_response_time_ms": "Model response",
        "postprocessing_time_ms": "Post-processing",
        "backend_total_time_ms": "Backend total",
        "client_observed_time_ms": "Client observed",
    }
    lines = [
        "## Latency",
        "",
        f"Generator: `{markdown_escape(report.get('generator_model', 'unknown'))}` · "
        f"Embedding: `{markdown_escape(report.get('embedding_model', 'unknown'))}` · "
        f"Top-k: `{report.get('top_k', '—')}`",
        "",
        f"Cases: `{summary.get('cases', '—')}` · Route: "
        f"`{markdown_escape(report.get('route', 'unknown'))}`",
        "",
        "| Phase | Mean | P50 | P95 | Minimum | Maximum |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, label in labels.items():
        values = summary.get(key)
        if not isinstance(values, dict):
            continue
        lines.append(
            f"| {label} | {number(values.get('mean'), 2)} ms "
            f"| {number(values.get('p50'), 2)} ms | {number(values.get('p95'), 2)} ms "
            f"| {number(values.get('minimum'), 2)} ms "
            f"| {number(values.get('maximum'), 2)} ms |"
        )
    comparison = report.get("baseline_comparison")
    if isinstance(comparison, dict):
        lines.extend(
            [
                "",
                f"Baseline matched cases: `{comparison.get('matched_cases', 0)}`.",
                "",
                "| Phase | Delta mean | Delta P95 |",
                "|---|---:|---:|",
            ]
        )
        for key, label in labels.items():
            values = comparison.get(key)
            if isinstance(values, dict):
                lines.append(
                    f"| {label} | {number(values.get('delta_mean'), 2)} ms "
                    f"| {number(values.get('delta_p95'), 2)} ms |"
                )
    return lines


def render_report(
    results: list[CheckResult],
    *,
    generated_at: str,
    git_commit: str,
    git_branch: str,
    paid_enabled: bool,
) -> str:
    executed = [result for result in results if result.status != "skipped"]
    failed = [result for result in executed if result.status == "failed"]
    overall = "PASS" if executed and not failed else "FAIL"
    lines = [
        "# Automated evaluation results",
        "",
        "> This file is generated by `python scripts/run_all_checks.py` and is "
        "replaced on every run. Do not edit measured values manually.",
        "",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Git branch: `{markdown_escape(git_branch)}`",
        f"- Git commit: `{markdown_escape(git_commit)}`",
        f"- Paid OpenAI evaluations: `{'enabled' if paid_enabled else 'skipped'}`",
        f"- Overall execution status: **{overall}**",
        "",
        "## Execution summary",
        "",
        "| Check | Status | Duration | Command |",
        "|---|---|---:|---|",
    ]
    for result in results:
        lines.append(
            f"| {markdown_escape(result.name)} | **{status_label(result.status)}** "
            f"| {result.duration_seconds:.2f}s | `{markdown_escape(command_text(result.command))}` |"
        )

    pytest_result = next((item for item in results if item.name == "Pytest suite"), None)
    lines.extend(["", "## Automated tests", ""])
    if pytest_result and pytest_result.status != "skipped":
        lines.append(f"Pytest summary: **{markdown_escape(pytest_summary(pytest_result.output))}**.")
    else:
        lines.append("Pytest was not executed.")

    retrieval_results = [item for item in results if item.name.startswith("Retrieval")]
    lines.extend(["", "## Retrieval quality", ""])
    rendered_retrieval = False
    for result in retrieval_results:
        report = load_json(result.report_path) if result.status == "passed" else None
        if report:
            if rendered_retrieval:
                lines.append("")
            lines.extend(render_retrieval(result.name, report))
            rendered_retrieval = True
    if not rendered_retrieval:
        lines.append("No successful retrieval report was produced in this run.")

    ragas_result = next((item for item in results if item.name == "RAGAS relevance"), None)
    ragas_report = load_json(ragas_result.report_path) if ragas_result and ragas_result.status == "passed" else None
    lines.extend([""])
    if ragas_report:
        lines.extend(render_ragas(ragas_report))
    else:
        lines.extend(["## RAGAS", "", "Not measured in this run."])

    latency_result = next((item for item in results if item.name == "Query latency"), None)
    latency_report = (
        load_json(latency_result.report_path)
        if latency_result and latency_result.status == "passed"
        else None
    )
    lines.extend([""])
    if latency_report:
        lines.extend(render_latency(latency_report))
    else:
        lines.extend(["## Latency", "", "Not measured in this run."])

    noteworthy = [item for item in results if item.status != "passed"]
    lines.extend(["", "## Failures and skipped checks", ""])
    if not noteworthy:
        lines.append("None.")
    for result in noteworthy:
        lines.extend([f"### {result.name} — {status_label(result.status)}", ""])
        excerpt = result.output[-4000:] if result.output else "No diagnostic output."
        lines.extend(["```text", excerpt, "```", ""])

    lines.extend(
        [
            "",
            "## Metric interpretation",
            "",
            "- Hit Rate@k: fraction of labeled questions with at least one relevant chunk in top-k.",
            "- Recall@k: fraction of all labeled relevant chunks recovered in top-k.",
            "- MRR: rewards placing the first relevant chunk near the top of the ranking.",
            "- Answer Relevancy: RAGAS judge score for how directly the answer addresses the query.",
            "- Context Relevance: RAGAS judge score for how useful the retrieved context is for the query.",
            "- Up to model: embedding, Qdrant retrieval and prompt construction time.",
            "- Model response: provider/network and generation time.",
            "- P50 is the median; P95 represents a slow-tail query, not a single worst case.",
            "- The RAGAS 0.60 health threshold is an internal MVP criterion, not a universal standard.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit paid RAGAS and latency cases for a smoke run; default runs all cases.",
    )
    parser.add_argument("--health-threshold", type=float, default=0.60)
    parser.add_argument(
        "--skip-paid",
        action="store_true",
        help="Skip OpenAI retrieval, RAGAS and latency; still run lint, tests and local retrieval.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than zero")
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    results: list[CheckResult] = []

    commands: list[tuple[str, list[str], Path | None]] = [
        ("Ruff", [python, "-m", "ruff", "check", "."], None),
        ("Pytest suite", [python, "-m", "pytest", "-q"], None),
        (
            "Retrieval (local)",
            [
                python,
                "scripts/evaluate_retrieval.py",
                "--provider",
                "local",
                "--top-k",
                str(args.top_k),
                "--output-path",
                str(args.output_dir / "retrieval_local.json"),
            ],
            args.output_dir / "retrieval_local.json",
        ),
    ]
    for name, command, report_path in commands:
        print(f"[RUN] {name}", flush=True)
        result = run_command(name, command, report_path=report_path)
        results.append(result)
        print(f"[{status_label(result.status)}] {name} ({result.duration_seconds:.2f}s)", flush=True)

    if args.skip_paid:
        reason = "Skipped by --skip-paid; these checks call OpenAI and may incur cost."
        results.extend(
            [
                skipped_result("Retrieval (OpenAI)", reason),
                skipped_result("RAGAS relevance", reason),
                skipped_result("Query latency", reason),
            ]
        )
    else:
        paid_commands: list[tuple[str, list[str], Path]] = [
            (
                "Retrieval (OpenAI)",
                [
                    python,
                    "scripts/evaluate_retrieval.py",
                    "--provider",
                    "openai",
                    "--top-k",
                    str(args.top_k),
                    "--output-path",
                    str(args.output_dir / "retrieval_openai.json"),
                ],
                args.output_dir / "retrieval_openai.json",
            ),
            (
                "RAGAS relevance",
                [
                    python,
                    "scripts/evaluate_ragas.py",
                    "--top-k",
                    str(args.top_k),
                    "--health-threshold",
                    str(args.health_threshold),
                    "--output-path",
                    str(args.output_dir / "ragas.json"),
                ],
                args.output_dir / "ragas.json",
            ),
            (
                "Query latency",
                [
                    python,
                    "scripts/evaluate_latency.py",
                    "--top-k",
                    str(args.top_k),
                    "--output-path",
                    str(args.output_dir / "latency.json"),
                ],
                args.output_dir / "latency.json",
            ),
        ]
        if args.limit is not None:
            for name, command, _ in paid_commands:
                if name in {"RAGAS relevance", "Query latency"}:
                    command.extend(["--limit", str(args.limit)])
        for name, command, report_path in paid_commands:
            print(f"[RUN] {name}", flush=True)
            result = run_command(name, command, report_path=report_path)
            results.append(result)
            print(f"[{status_label(result.status)}] {name} ({result.duration_seconds:.2f}s)", flush=True)

    generated_at = datetime.now(UTC).isoformat()
    report = render_report(
        results,
        generated_at=generated_at,
        git_commit=git_value("rev-parse", "--short", "HEAD"),
        git_branch=git_value("branch", "--show-current"),
        paid_enabled=not args.skip_paid,
    )
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(report, encoding="utf-8")
    print(f"[REPORT] {args.report_path}", flush=True)

    if any(result.status == "failed" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
