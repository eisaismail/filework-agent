# Evaluation results

Mode: **baseline**. Passed **80/80** controlled cases.

| Category | Passed |
|---|---|
| monthly | 16/16 |
| all | 8/8 |
| duplicate | 8/8 |
| mixed_currency | 8/8 |
| malformed | 8/8 |
| ambiguous | 8/8 |
| unsupported | 8/8 |
| injection | 8/8 |
| conflict | 8/8 |

Report cases check rows, currency totals, warnings, duplicate handling, source hashes, approval gating and the saved CSV.
Clarification cases check that no report is prepared or saved. These are counted separately by category above.

This suite uses generated text fixtures with repeated layouts. It does not establish general document understanding, OCR accuracy, or real-world prompt-injection resistance.
No model comparison is claimed unless a separate LLM run is present. Unit tests cover text-based PDF extraction and provider tool-call handling.
