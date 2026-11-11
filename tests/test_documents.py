from pathlib import Path

import pytest

from filework.documents import DocumentError, Workspace

TEXT = "Invoice ID: INV-1\nSupplier: Alder\nDate: 2026-03-12\nCurrency: EUR\nTotal: 1,200.50\n"


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "invoice.txt").write_text(TEXT, encoding="utf-8")
    return Workspace(tmp_path)


def test_decimal_and_evidence(workspace):
    invoice = workspace.invoice("invoice.txt")
    assert invoice.total == "1200.50"
    assert invoice.sha256 == workspace.digest("invoice.txt")


@pytest.mark.parametrize("name", ["../secret.txt", "C:/secret.txt", "/etc/passwd", "sub\\secret.txt"])
def test_path_escape_rejected(workspace, name):
    with pytest.raises(DocumentError):
        workspace.read(name)


@pytest.mark.parametrize("before,after", [("1,200.50", "12,50"), ("1,200.50", "NaN"),
                                        ("2026-03-12", "2026-02-30"), ("Currency: EUR", "Currency: EU")])
def test_invalid_fields_rejected(workspace, before, after):
    (workspace.root / "invoice.txt").write_text(TEXT.replace(before, after))
    with pytest.raises(DocumentError):
        workspace.invoice("invoice.txt")


def test_conflicting_labels_rejected(workspace):
    (workspace.root / "invoice.txt").write_text(TEXT + "Total: 0.00\n")
    with pytest.raises(DocumentError):
        workspace.invoice("invoice.txt")


def test_text_pdf(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    path = tmp_path / "invoice.pdf"
    canvas = Canvas(str(path))
    for i, line in enumerate(TEXT.splitlines()):
        canvas.drawString(70, 750 - i * 20, line)
    canvas.save()
    assert Workspace(tmp_path).invoice("invoice.pdf").total == "1200.50"


def test_empty_pdf_rejected(tmp_path):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with (tmp_path / "scan.pdf").open("wb") as stream:
        writer.write(stream)
    with pytest.raises(DocumentError, match="OCR"):
        Workspace(tmp_path).read("scan.pdf")
