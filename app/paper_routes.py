"""Manual selection and reproducible research extraction UI."""
import json
import re
from flask import Blueprint, current_app, render_template, request, flash, Response, abort
from app.services.sustainability.sustainability_service import SustainabilityService
from app.services.sustainability.paper_extraction import (
    ExtractionError, fetch_source, extract, run_directory, save_run, training_sample,
)

papers = Blueprint("papers", __name__)


@papers.route("/sustainability/extract", methods=["GET", "POST"])
def extraction():
    service = SustainabilityService(current_app.root_path, current_app.config.get("SUSTAINABILITY_STORAGE_PATH"))
    state = service.view_state()
    candidates = (state.get("last_scan") or {}).get("papers", [])
    results = []
    if request.method == "POST":
        mode = request.form.get("mode", "abstract")
        model = request.form.get("model", "").strip()
        selected = set(request.form.getlist("paper_id"))
        lookup = {p["arxiv_id"]: p for p in candidates}
        sources = []
        try:
            if not selected.issubset(lookup):
                raise ExtractionError("Selected paper no longer exists in the scan. Refresh the page.")
            urls = [lookup[k]["paper_url"] for k in lookup if k in selected]
            extra_url = request.form.get("url", "").strip()
            pasted = request.form.get("source_text", "").strip()
            if extra_url and not pasted:
                urls.append(extra_url)
            urls = list(dict.fromkeys(urls))
            if len(urls) + bool(pasted) > 10:
                raise ExtractionError("Select at most 10 papers per run.")
            if not urls and not pasted:
                raise ExtractionError("Select a paper, enter an arXiv URL, or paste source text.")
            # Configuration errors should be found before downloading selected papers.
            import os
            if not (current_app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
                raise ExtractionError("Set OPENAI_API_KEY on the server before extracting.")
            if not model or mode not in {"abstract", "full_text"}:
                raise ExtractionError("Enter a model ID and valid source mode.")
            if pasted:
                sources.append({"url": extra_url, "title": "Manually supplied text", "mode": "pasted_" + mode, "text": pasted})
            sources.extend(urls)
            for source in sources:
                try:
                    source = fetch_source(source, mode) if isinstance(source, str) else source
                    run = extract(source, model, current_app.config)
                    save_run(run_directory(current_app), run)
                    results.append(run)
                except (ExtractionError, OSError) as exc:
                    flash(str(exc) if isinstance(exc, ExtractionError) else "Could not save extraction locally.", "danger")
        except ExtractionError as exc:
            flash(str(exc), "danger")
        if not results:
            return render_template(
                "sustainability.html", active_tab="sustainability",
                selected_paper_count=(state.get("last_scan") or {}).get("requested_count", 50),
                **state,
            )
    directory = run_directory(current_app)
    history = []
    if directory.exists():
        for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            try:
                history.append(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
    return render_template("paper_extraction.html", active_tab="sustainability",
                           candidates=candidates, results=results, history=history)


@papers.get("/sustainability/extractions/<run_id>/<kind>")
def download(run_id, kind):
    if not re.fullmatch(r"[a-f0-9]{32}", run_id) or kind not in {"json", "jsonl"}:
        abort(404)
    path = run_directory(current_app) / (run_id + ".json")
    if not path.is_file():
        abort(404)
    run = json.loads(path.read_text(encoding="utf-8"))
    body = json.dumps(training_sample(run) if kind == "jsonl" else run, ensure_ascii=False) + "\n"
    return Response(body, mimetype="application/x-ndjson" if kind == "jsonl" else "application/json",
                    headers={"Content-Disposition": f'attachment; filename="paper-{run_id}.{kind}"'})
