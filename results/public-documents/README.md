# Public-document audit

The original 80-case benchmark only checks generated text templates. It does not establish performance on issued invoices. This audit was added separately after the first release, without modifying the original source documents or tuning an extraction parser to these examples.

## Documents and manual checks

Four genuine public billing documents were selected from government disclosures. Three are bills from the same electricity supplier, so this is a small convenience sample with limited layout diversity. Two additional supplier/publisher examples are listed separately and are not described as real transactions.

| Document | Source pages | Visually checked information | Limitation |
|---|---|---|---|
| Jersey Electricity, December 2024 | [Disclosure PDF](https://www.gov.je/Freedom%20of%20Information%20library/ID%20FOI%208261%20JE%20Invoice%20for%20JGH%20-%20Dec%202024_Redacted%2020250303.pdf), p. 1 | 27 December 2024; amount due 86,173.74 | Invoice identifier is redacted; no explicit three-letter currency code |
| Jersey Electricity, January 2024 | [Disclosure bundle](https://www.gov.je/Freedom%20of%20Information%20library/ID%20FOI%208405%20JE%20Invoices%20redacted%2020250404.pdf), p. 1 | 31 January 2024; amount due 86,271.75 | Identifier redacted; currency not explicit |
| Jersey Electricity, February 2024 | Same bundle, p. 3 | 28 February 2024; amount due 86,280.01 | Identifier redacted; currency not explicit |
| Pitney Bowes invoice/statement | [Electoral Commission disclosure](https://www.electoralcommission.org.uk/sites/default/files/pdf_file/Labour-Party-invoices-2-of-2.pdf), p. 3 | Statement 10610077; 2 March 2011; printed total GBP 2,007.20 | Image scan. Total includes account funding, not only service charges |

The two extra documents are an [annotated Lloyds supplier example](https://www.lloydsbankinggroup.com/assets/pdfs/who-we-are/working-with-suppliers/getting-paid/what-to-include-on-invoice-example.pdf), p. 1, and a [watermarked Payex sample](https://payex.io/wp-content/uploads/2024/01/sample-invoice.pdf), p. 1. They are examples of unfamiliar layouts, not evidence of actual transactions.

Gold fields were transcribed from rendered pages. Redacted or unspecified values are left null; they are not guessed from context or reconstructed. The extraction result is compared only with visible checked fields. Complete-record extraction and visible review are reported separately.

## Results

| Genuine billing documents | Before warning fix | After warning fix |
|---|---:|---:|
| Complete records extracted | 0/4 | 0/4 |
| Explicitly flagged for review | 2/4 | 4/4 |
| Silently unrecognised | 2/4 | 0/4 |

These are failures of extraction coverage, not successful extractions. The change prevents an unsupported invoice from disappearing silently and prevents saving an empty report when every candidate document needs review. It does not add OCR or infer redacted identifiers. The current LLM mode uses the same extraction tools, so connecting a model alone does not remove these limitations.

Detailed observed outcomes, source URLs, selected page numbers and SHA-256 checksums are in [before/audit.json](before/audit.json) and [after/audit.json](after/audit.json).

## Reproduce

```powershell
python -m evaluation.public_audit --cache .runtime/public-documents --output .runtime/public-audit
```

This makes network requests. Downloads and selected PDF pages stay in the ignored local cache. The public repo contains the audit code, small field annotations and results, not the source PDFs, bank details, customer addresses or full extracted text. The script selects complete document faces by page number without OCR, retyping, or converting them to the parser's preferred template.

For a broader test, obtain permitted invoices from several suppliers, include both complete and redacted documents, label fields independently, and hold out unseen layouts before improving extraction. A review warning is useful, but it must not be reported as invoice-reading accuracy.
