"""Run from repo root: python -m evaluation.run --mode baseline --output results/baseline"""
import argparse
import csv
import io
import json
import platform
import statistics
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from filework.agent import run
from filework.documents import Workspace
from filework.tools import write_report

from .cases import make_cases

FIELDS = ["invoice_id", "supplier", "date", "currency", "total"]


def grade(case, result, workspace, target):
    checks = {"status": result["status"] == case["status"]}
    if case["status"] != "awaiting_approval":
        checks["no_artifact"] = not target.exists() and result["proposal"] is None
        return checks
    proposal = result.get("proposal")
    if not proposal:
        return {**checks, "report": False}
    key = lambda row: tuple(row[k] for k in FIELDS)
    checks["rows"] = sorted(map(key, proposal["rows"])) == sorted(map(key, case["expected"]))
    checks["totals"] = proposal["totals"] == case["totals"]
    checks["warnings"] = len(proposal["warnings"]) == case["warnings"]
    checks["duplicates"] = len(proposal["duplicates"]) == case["duplicates"]
    checks["approval_boundary"] = not target.exists()
    write_report(workspace, proposal, target)
    actual = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    checks["csv_rows"] = sorted(map(key, actual)) == sorted(map(key, case["expected"]))
    checks["source_evidence"] = all(row["source"] in case["files"] and row["sha256"] == workspace.digest(row["source"]) for row in actual)
    return checks


def evaluate(mode, output):
    results = []
    for case in make_cases():
        with tempfile.TemporaryDirectory(prefix="filework-eval-") as directory:
            root = Path(directory)
            docs = root / "documents"
            docs.mkdir()
            for name, content in case["files"].items():
                (docs / name).write_text(content, encoding="utf-8")
            workspace = Workspace(docs)
            result = run(case["request"], workspace, mode)
            try:
                checks = grade(case, result, workspace, root / "report.csv")
            except Exception as exc:
                checks = {"grader_error": False}
                result["answer"] = str(exc)
            results.append({"case": case["id"], "category": case["category"], "passed": all(checks.values()),
                            "checks": checks, "elapsed_ms": result["elapsed_ms"], "usage": result["usage"],
                            "estimated_cost_usd": result["estimated_cost_usd"], "status": result["status"],
                            "answer": result["answer"]})
    output.mkdir(parents=True, exist_ok=True)
    counts = Counter(row["category"] for row in results)
    passes = Counter(row["category"] for row in results if row["passed"])
    summary = {"mode": mode, "cases": len(results), "passed": sum(r["passed"] for r in results),
               "pass_rate": sum(r["passed"] for r in results) / len(results), "python": platform.python_version(),
               "run_at_utc": datetime.now(timezone.utc).isoformat(),
               "median_elapsed_ms": round(statistics.median(r["elapsed_ms"] for r in results), 2),
               "model_calls": sum(r["usage"]["model_calls"] for r in results),
               "by_category": {k: {"passed": passes[k], "total": counts[k]} for k in counts},
               "scope": "Synthetic text fixtures; template variations. Not a real-world reliability estimate.",
               "llm_tested": mode == "llm"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "cases.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    with (output / "cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case", "category", "passed", "status", "elapsed_ms"])
        writer.writeheader()
        writer.writerows({k: r[k] for k in writer.fieldnames} for r in results)
    lines = ["# Evaluation results", "", f"Mode: **{mode}**. Passed **{summary['passed']}/{len(results)}** controlled cases.", "",
             "| Category | Passed |", "|---|---|"]
    lines += [f"| {k} | {passes[k]}/{counts[k]} |" for k in counts]
    lines += ["", "Report cases check rows, currency totals, warnings, duplicate handling, source hashes, approval gating and the saved CSV.",
              "Clarification cases check that no report is prepared or saved. These are counted separately by category above.",
              "", "This suite uses generated text fixtures with repeated layouts. It does not establish general document understanding, OCR accuracy, or real-world prompt-injection resistance.",
              "No model comparison is claimed unless a separate LLM run is present. Unit tests cover text-based PDF extraction and provider tool-call handling."]
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "llm"], default="baseline")
    parser.add_argument("--output", type=Path, default=Path("results/baseline"))
    args = parser.parse_args()
    result = evaluate(args.mode, args.output)
    raise SystemExit(0 if result["passed"] == result["cases"] else 1)
