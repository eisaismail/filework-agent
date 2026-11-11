"""A deliberately small, offline baseline; it is not an LLM."""
import calendar
import re
from datetime import date


class Clarification(ValueError):
    pass


def plan_request(request: str) -> dict:
    text = request.lower()
    if any(re.search(rf"\b{verb}\b", text) for verb in
           ["delete", "remove", "send", "email", "upload", "execute", "install"]):
        raise Clarification("This assistant only reads documents and prepares local CSV reports.")
    if not re.search(r"\binvoices?\b", text):
        raise Clarification("Try an invoice report, for example: 'Total invoices for March 2026'.")
    if re.search(r"\b(?:except|excluding|not|before|after|between|supplier|over|under)\b", text):
        raise Clarification("The baseline supports one month and year, or 'all invoices'. Use LLM mode for other filters.")
    months = [(i, name) for i, name in enumerate(calendar.month_name) if name]
    # Refuse unfamiliar qualifiers rather than silently dropping a supplier, currency,
    # amount threshold, or other constraint that this small baseline cannot handle.
    vocabulary = {"total", "the", "invoice", "invoices", "for", "and", "prepare", "a", "csv",
                  "report", "create", "of", "all", "find", "show", "me", "please", "generate",
                  "an", "in", "from", "export", "make", "sum", "up"}
    vocabulary.update(name.lower() for _, name in months)
    words = re.findall(r"[a-z]+|\d+", text)
    if any(word not in vocabulary and not re.fullmatch(r"20\d{2}", word) for word in words):
        raise Clarification("The baseline supports a month and year, or all invoices. For supplier, currency or other filters, use LLM mode.")
    picked = [i for i, name in months if re.search(rf"\b{name.lower()}\b", text)]
    years = re.findall(r"\b(20\d{2})\b", text)
    if len(set(picked)) > 1 or len(set(years)) > 1:
        raise Clarification("Which single month and year should the report cover?")
    if picked and len(set(years)) == 1:
        year, month = int(years[0]), picked[0]
        return {"start_date": date(year, month, 1).isoformat(),
                "end_date": date(year, month, calendar.monthrange(year, month)[1]).isoformat()}
    if re.search(r"\ball\s+invoices\b", text) and not picked and not years:
        return {}
    raise Clarification("Which month and year? For example, March 2026, or 'all invoices'.")
