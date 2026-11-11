"""Audit unchanged public PDFs, independently from the controlled text benchmark.

Downloads stay in a local cache. Do not commit third-party PDFs or extracted text.
Run from the repo root: python -m evaluation.public_audit --cache .runtime/public-documents
"""
import argparse
import hashlib
import json
from pathlib import Path

import httpx
from pypdf import PdfReader, PdfWriter

from filework.agent import run
from filework.documents import DocumentError, Workspace


def audit(cache: Path, output: Path):
    manifest = json.loads(Path(__file__).with_name("public_documents.json").read_text())
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in manifest:
        key = hashlib.sha256(case["url"].encode()).hexdigest()[:16]
        original = cache / (key + ".pdf")
        if not original.exists():
            with httpx.stream("GET", case["url"], follow_redirects=True, timeout=60) as response:
                response.raise_for_status()
                with original.open("wb") as stream:
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 20_000_000:
                            raise ValueError("Public source exceeds 20 MB download limit.")
                        stream.write(chunk)
        reader = PdfReader(original)
        folder = cache / case["id"]
        folder.mkdir(exist_ok=True)
        path = folder / "document.pdf"
        writer = PdfWriter()
        for page in case["pages"]:
            writer.add_page(reader.pages[page - 1])
        with path.open("wb") as stream:
            writer.write(stream)
        workspace = Workspace(folder)
        try:
            invoice = workspace.invoice("document.pdf")
            outcome = "extracted" if invoice else "silently_unrecognised"
            detail = "" if invoice else "Parser returned no invoice."
        except DocumentError as exc:
            invoice, outcome, detail = None, "requires_review", str(exc)
        task = run("Create a report of all invoices.", workspace)
        proposal = task.get("proposal")
        warning_count = len(proposal["warnings"]) if proposal else 0
        visible_review = outcome == "requires_review" and (
            task["status"] in {"needs_clarification", "failed"} or warning_count > 0)
        actual = invoice.row() if invoice else None
        checkable = {k: v for k, v in case["reviewed_fields"].items() if v is not None}
        field_matches = {k: bool(actual and actual.get(k) == v) for k, v in checkable.items()}
        rows.append({**case, "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                     "selected_pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "original_page_count": len(reader.pages), "outcome": outcome, "detail": detail,
                     "field_matches": field_matches, "extracted": actual, "task_status": task["status"],
                     "task_answer": task["answer"], "report_rows": len(proposal["rows"]) if proposal else 0,
                     "visible_review": visible_review, "warning_count": warning_count})
    genuine = [r for r in rows if r["kind"].startswith("publicly_released")]
    summary = {"documents": len(rows), "genuine_billing_documents": len(genuine),
               "publisher_samples": len(rows) - len(genuine),
               "genuine_documents_extracted": sum(r["outcome"] == "extracted" for r in genuine),
               "genuine_documents_with_visible_review": sum(r["visible_review"] for r in genuine),
               "genuine_documents_silently_unrecognised": sum(r["outcome"] == "silently_unrecognised" for r in genuine),
               "scope": "Convenience sample, not representative. Three genuine bills share a supplier; some fields are redacted. Source PDFs are not redistributed."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(json.dumps({"summary": summary, "documents": rows}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path(".runtime/public-documents"))
    parser.add_argument("--output", type=Path, default=Path("results/public-documents"))
    args = parser.parse_args()
    audit(args.cache, args.output)
