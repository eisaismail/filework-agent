import csv
import json

import pytest

from filework.agent import run
from filework.documents import DocumentError, Workspace
from filework.tools import Tools, write_report

TEXT = "Invoice ID: INV-1\nSupplier: Alder\nDate: 2026-03-12\nCurrency: EUR\nTotal: 10.25\n"


@pytest.fixture
def workspace(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text(TEXT)
    return Workspace(docs)


def test_approval_and_actual_csv(workspace, tmp_path):
    task = run("Total invoices for March 2026", workspace)
    target = tmp_path / "result.csv"
    assert task["status"] == "awaiting_approval" and not target.exists()
    write_report(workspace, task["proposal"], target)
    with target.open() as stream:
        assert list(csv.DictReader(stream))[0]["total"] == "10.25"
    with pytest.raises(FileExistsError):
        write_report(workspace, task["proposal"], target)


def test_changed_source_invalidates_approval(workspace, tmp_path):
    task = run("Total invoices for March 2026", workspace)
    (workspace.root / "a.txt").write_text(TEXT.replace("10.25", "99.00"))
    with pytest.raises(DocumentError, match="changed"):
        write_report(workspace, task["proposal"], tmp_path / "result.csv")


def test_added_source_invalidates_approval(workspace, tmp_path):
    task = run("Total invoices for March 2026", workspace)
    (workspace.root / "new.txt").write_text(TEXT.replace("INV-1", "INV-2"))
    with pytest.raises(DocumentError):
        write_report(workspace, task["proposal"], tmp_path / "result.csv")


def test_conflicting_duplicate_stops_task(workspace):
    (workspace.root / "copy.txt").write_text(TEXT.replace("10.25", "99.00"))
    task = run("Total invoices for March 2026", workspace)
    assert task["status"] == "needs_clarification"
    assert task["proposal"] is None


def test_mixed_currency_not_added_together(workspace):
    (workspace.root / "usd.txt").write_text(TEXT.replace("INV-1", "INV-2").replace("EUR", "USD"))
    task = run("all invoices", workspace)
    assert task["proposal"]["totals"] == {"EUR": "10.25", "USD": "10.25"}


def test_formula_escaped_at_csv_boundary(workspace, tmp_path):
    (workspace.root / "a.txt").write_text(TEXT.replace("Alder", "=1+1"))
    task = run("all invoices", workspace)
    target = tmp_path / "result.csv"
    write_report(workspace, task["proposal"], target)
    assert "'=1+1" in target.read_text()


@pytest.mark.parametrize("prompt", ["March invoices", "invoices for last month", "delete all invoices", "all invoices except March", "invoices before March 2026", "March 2026 invoices for Alder", "March 2026 invoices in USD"])
def test_unclear_or_unsupported_baseline_requests_do_not_write(workspace, prompt):
    task = run(prompt, workspace)
    assert task["status"] == "needs_clarification" and task["proposal"] is None


class ScriptedProvider:
    def __init__(self, messages):
        self.messages = iter(messages)

    def complete(self, history):
        return next(self.messages), {"prompt_tokens": 10, "completion_tokens": 5}


def call(name, args):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}]}


def test_llm_tool_loop_and_usage(workspace):
    provider = ScriptedProvider([call("list_documents", {}), call("read_document", {"path": "a.txt"}),
                                 call("prepare_report", {"start_date": "2026-03-01", "end_date": "2026-03-31"})])
    task = run("March 2026 invoices", workspace, "llm", provider)
    assert task["status"] == "awaiting_approval"
    assert task["usage"] == {"prompt_tokens": 30, "completion_tokens": 15, "model_calls": 3}


def test_llm_cannot_use_unknown_tool(workspace):
    provider = ScriptedProvider([call("run_shell", {"command": "delete everything"}),
                                 {"role": "assistant", "content": "Please clarify."}])
    task = run("Make a report", workspace, "llm", provider)
    assert task["proposal"] is None
    assert any(e["summary"] == "Tool request rejected" for e in task["events"])


def test_llm_has_turn_limit(workspace):
    provider = ScriptedProvider([call("list_documents", {})] * 10)
    task = run("Make a report", workspace, "llm", provider)
    assert task["status"] == "failed" and task["usage"]["model_calls"] == 10
