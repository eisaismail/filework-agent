"""Read a bounded workspace and parse labelled invoices without guessing fields."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_BYTES = 2_000_000
MAX_FILES = 250
MAX_TEXT = 30_000
FIELDS = {
    "invoice_id": r"Invoice\s*(?:ID|Number|No\.?|#)",
    "supplier": r"Supplier",
    "date": r"(?:Invoice\s+)?Date",
    "currency": r"Currency",
    "total": r"(?:Grand\s+)?Total",
}


class DocumentError(ValueError):
    pass


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    supplier: str
    date: str
    currency: str
    total: str
    source: str
    sha256: str

    def row(self):
        return asdict(self)


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise DocumentError("Workspace must be a directory.")

    def resolve(self, name: str) -> Path:
        if not name or "\\" in name or ":" in name or ".." in Path(name).parts:
            raise DocumentError("Use a relative file path inside the workspace.")
        raw = self.root / name
        # Reject symlinks even when their current target happens to be inside the root.
        if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
               for p in [raw, *raw.parents] if p != self.root and self.root in p.parents):
            raise DocumentError("Linked paths are not supported.")
        path = raw.resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise DocumentError("File is not available in this workspace.")
        if path.suffix.lower() not in {".txt", ".md", ".pdf"}:
            raise DocumentError("Supported documents: TXT, Markdown and text-based PDF.")
        if path.stat().st_size > MAX_BYTES:
            raise DocumentError("File exceeds the 2 MB limit.")
        return path

    def files(self) -> list[str]:
        found = []
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".md", ".pdf"}:
                name = p.relative_to(self.root).as_posix()
                try:
                    self.resolve(name)
                except DocumentError:
                    continue
                found.append(name)
                if len(found) > MAX_FILES:
                    raise DocumentError("Workspace exceeds 250 supported files; use a smaller folder.")
        return found

    def digest(self, name: str) -> str:
        return hashlib.sha256(self.resolve(name).read_bytes()).hexdigest()

    def read(self, name: str) -> str:
        path = self.resolve(name)
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            try:
                reader = PdfReader(path)
                if reader.is_encrypted or len(reader.pages) > 20:
                    raise DocumentError("PDF must be unencrypted and at most 20 pages.")
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except DocumentError:
                raise
            except Exception as exc:
                raise DocumentError("Could not read this PDF.") from exc
        else:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeError as exc:
                raise DocumentError("Text document must use UTF-8 encoding.") from exc
        if not text.strip():
            raise DocumentError("No readable text; scanned PDFs need OCR, which is not included.")
        if len(text) > MAX_TEXT:
            raise DocumentError("Document exceeds the 30,000-character limit.")
        return text

    def invoice(self, name: str) -> Invoice | None:
        text = self.read(name)
        if not re.search(r"(?im)^\s*Invoice\s*(?:ID|Number|No\.?|#)\s*:", text):
            return None
        values = {}
        for key, label in FIELDS.items():
            matches = re.findall(rf"(?im)^\s*{label}\s*:\s*([^\r\n]+)", text)
            if len(matches) != 1:
                raise DocumentError(f"{name}: expected exactly one {key} field.")
            values[key] = matches[0].strip()
        try:
            values["date"] = date.fromisoformat(values["date"]).isoformat()
        except ValueError as exc:
            raise DocumentError(f"{name}: date must be YYYY-MM-DD.") from exc
        values["currency"] = values["currency"].upper()
        if not re.fullmatch(r"[A-Z]{3}", values["currency"]):
            raise DocumentError(f"{name}: currency must be a three-letter code.")
        # Explicit decimal-point format; never silently reinterpret decimal commas.
        raw = values["total"]
        if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?", raw):
            raise DocumentError(f"{name}: total must be a non-negative decimal, e.g. 1,200.50.")
        try:
            amount = Decimal(raw.replace(",", ""))
        except InvalidOperation as exc:
            raise DocumentError(f"{name}: invalid total.") from exc
        values["total"] = format(amount.quantize(Decimal("0.01")), ".2f")
        return Invoice(**values, source=name, sha256=self.digest(name))
