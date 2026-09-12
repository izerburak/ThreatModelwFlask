# Paper extraction

Open Sustainability → Select papers & extract. All checkboxes start unchecked.
Only selected papers and an explicitly supplied additional URL are retrieved.
Set `OPENAI_API_KEY` in the server environment before starting Flask; enter a model
ID supported by your API account in the page. No additional Python dependency is
needed. API calls are billable and use the Responses API with `store: false`.

Abstract mode retrieves arXiv abstract metadata; full-text mode requires arXiv HTML.
arXiv PDF URLs are normalized to abstract/HTML, not parsed as PDFs. Other publishers
and inaccessible HTML are supported by manually pasting text with its source URL.
No automatic fallback, silent truncation, or automatic selection is performed.
At most ten papers are processed sequentially per submission. Failed papers show
an error; successful papers remain saved. Resubmission creates new paid runs.

Runs are saved under `sustainability/extractions` (override `PAPER_EXTRACTION_DIR`).
JSON contains source text, SHA-256, scope, prompt/version, model, usage, latency,
findings and unreviewed status. Evidence quotes and mitigation references are
validated locally. Quote occurrence does not establish semantic correctness.
JSONL is a messages-format candidate dataset for **paper extraction**, not a
drop-in replacement for the DFD-grounded threat/mitigation datasets in `training`.
Review labels and keep all versions of the same paper in the same dataset split.

For benchmark runs, reuse exactly the same source text/scope and prompt version.
The provider registry in `paper_extraction.py` accepts adapters returning
`(extraction, metadata)`; only OpenAI is implemented in this version. Quality
metrics, automated multi-model benchmark execution, and fine-tuning are not included.
OpenAI models are API-hosted proprietary models, not open-weight models.

Verification: `.\.venv-win\Scripts\python.exe -m unittest discover -s tests -p test_paper_extraction.py`
Live API access must be verified separately with your configured account.

API reference: https://developers.openai.com/api/docs/guides/structured-outputs
