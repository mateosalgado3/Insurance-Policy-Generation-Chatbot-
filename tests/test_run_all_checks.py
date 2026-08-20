from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_all_checks.py"
SPEC = importlib.util.spec_from_file_location("run_all_checks", SCRIPT_PATH)
assert SPEC and SPEC.loader
run_all_checks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_all_checks
SPEC.loader.exec_module(run_all_checks)


def test_pytest_summary_extracts_counts() -> None:
    output = "........ [100%]\n112 passed, 2 skipped in 3.10s"
    assert run_all_checks.pytest_summary(output) == "112 passed, 2 skipped"


def test_render_report_does_not_reuse_skipped_paid_results(tmp_path: Path) -> None:
    results = [
        run_all_checks.CheckResult("Ruff", [], "passed", 0.1, "All checks passed!"),
        run_all_checks.CheckResult("Pytest suite", [], "passed", 0.2, "3 passed in 0.2s"),
        run_all_checks.skipped_result("Retrieval (OpenAI)", "paid check skipped"),
        run_all_checks.skipped_result("RAGAS relevance", "paid check skipped"),
        run_all_checks.skipped_result("Query latency", "paid check skipped"),
    ]

    markdown = run_all_checks.render_report(
        results,
        generated_at="2026-08-18T12:00:00+00:00",
        git_commit="abc123",
        git_branch="main",
        paid_enabled=False,
    )

    assert "Overall execution status: **PASS**" in markdown
    assert "RAGAS\n\nNot measured in this run." in markdown
    assert "paid check skipped" in markdown


def test_render_retrieval_includes_core_metrics() -> None:
    report = {
        "provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "metrics": {
            "top_k": 5,
            "total_questions": 52,
            "labeled_questions": 43,
            "unlabeled_questions": 9,
            "hit_rate_at_k": 1.0,
            "recall_at_k": 0.9341,
            "mrr": 0.8078,
        },
    }

    markdown = "\n".join(run_all_checks.render_retrieval("Retrieval (OpenAI)", report))

    assert "| 52 | 43 | 9 | 1.0000 | 0.9341 | 0.8078 |" in markdown
