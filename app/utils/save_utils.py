import json
import re
from pathlib import Path
from flask import current_app


def append_question_to_catalog(question_text: str, options: list):
    root = Path(current_app.root_path)
    app_db = root / "questions" / "questionsDb.json"
    tm_db = root.parent / "TM-Questions" / "questionsDb.json"

    # Load from whichever canonical copy exists (prefer the app copy).
    source = app_db if app_db.exists() else (tm_db if tm_db.exists() else app_db)
    questions = json.loads(source.read_text(encoding="utf-8")) if source.exists() else []
    if not isinstance(questions, list):
        questions = []

    max_id = 0
    for question in questions:
        if not isinstance(question, dict):
            continue
        try:
            max_id = max(max_id, int(question.get("id", 0)))
        except (TypeError, ValueError):
            continue

    clean_options = [str(option).strip() for option in options or [] if str(option).strip()]
    new_id = max_id + 1
    new_question = {
        "id": new_id,
        "text": question_text,
        "type": "multi" if len(clean_options) > 1 else "single",
        "options": clean_options,
        "category": "",
        "scope": [],
        "owasp_llm": [],
        "owasp_web": [],
        "owasp_api": [],
        "severity_weight": 1,
        "confidence_weight": 1,
    }
    questions.append(new_question)

    serialized = json.dumps(questions, ensure_ascii=False, indent=2)
    # Keep BOTH copies in sync: the questionnaire flow (question_flow) and the risk
    # engine (risk_analysis_service) resolve questionsDb.json with different precedence,
    # so writing only one copy would silently desync them.
    app_db.parent.mkdir(parents=True, exist_ok=True)
    app_db.write_text(serialized, encoding="utf-8")
    if tm_db.parent.exists():
        tm_db.write_text(serialized, encoding="utf-8")

    # Make the new question reachable instead of orphaned: append it to the QaT flow.
    _append_question_to_flow(root.parent / "TM-Questions" / "QaT.txt", new_id)

    return str(app_db), new_question


def _append_question_to_flow(qat_path, question_id):
    """Append a new question as a linear step before END in the QaT flow graph.

    Re-points the current terminal ``next: END`` to the new node so the question is
    actually asked, then defines the new node as the new terminal. Safe no-op if
    QaT.txt is missing, the question already exists, or no terminal can be found.
    """
    flow_id = f"Q{int(question_id)}"
    if not qat_path.exists():
        return False

    text = qat_path.read_text(encoding="utf-8")
    if re.search(rf"^\s*{re.escape(flow_id)}\s*:", text, flags=re.MULTILINE):
        return False  # already wired in

    terminals = list(re.finditer(r"^(?P<indent>[ \t]*)next:[ \t]*END[ \t]*$", text, flags=re.MULTILINE))
    if not terminals:
        return False

    last = terminals[-1]
    indent = last.group("indent")
    text = text[: last.start()] + f"{indent}next: {flow_id}" + text[last.end():]
    if not text.endswith("\n"):
        text += "\n"
    text += f"\n  {flow_id}:\n    next: END\n"
    qat_path.write_text(text, encoding="utf-8")
    return True



def append_question_to_layer(layer_name: str, question_text: str, options: list):
    import json
    from pathlib import Path
    from flask import current_app

    qdir = Path(current_app.root_path) / "questions"
    qdir.mkdir(parents=True, exist_ok=True)
    qpath = qdir / f"{layer_name}.json"

    # Load or create default structure
    if qpath.exists():
        with qpath.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # ensure it's dict with "questions"
                if isinstance(data, list):
                    data = {"questions": data}
                elif not isinstance(data, dict) or "questions" not in data:
                    data = {"questions": []}
            except Exception:
                data = {"questions": []}
    else:
        data = {"questions": []}

    # Normalize questions list
    questions = data.get("questions", [])
    if not isinstance(questions, list):
        questions = []

    # Determine next numeric ID
    max_id = 0
    for q in questions:
        try:
            qid = int(q.get("id", 0))
            if qid > max_id:
                max_id = qid
        except Exception:
            continue
    new_id = str(max_id + 1)

    # Create and append new question
    new_question = {"id": new_id, "text": question_text, "options": options}
    questions.append(new_question)
    data["questions"] = questions

    # Write back in consistent format
    with qpath.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(qpath), new_question





def save_adaptive_llm_sec_answers(answer_map, question_catalog):
    """Save the adaptive LLM security questionnaire.

    The compact `answers_by_flow_id` map remains the canonical payload for
    downstream compatibility. The detailed `answers` list keeps the old answer
    record shape without exposing extra question metadata.
    """
    from datetime import datetime, timezone

    compact_answers = {
        str(flow_id): answer
        for flow_id, answer in (answer_map or {}).items()
        if answer not in (None, "", [])
    }

    record = {
        "schema_version": "llmsec.adaptive.v1",
        "project_id": "DEFAULT_PROJECT",
        "system_id": "DEFAULT_SYSTEM",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "answers_by_flow_id": compact_answers,
        "answers": _detailed_answer_records(compact_answers, question_catalog),
    }

    responses_dir = Path(current_app.root_path).parent / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"llmsec_{timestamp_str}.json"
    filepath = responses_dir / filename

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return str(filepath)


def _detailed_answer_records(answer_map, question_catalog):
    records = []
    question_catalog = question_catalog if isinstance(question_catalog, dict) else {}

    for flow_id, answer in answer_map.items():
        question = question_catalog.get(flow_id) or {}
        source_question_id = str(question.get("source_id") or question.get("id") or _flow_id_number(flow_id) or flow_id)
        question_id = str(question.get("id") or source_question_id)
        records.append(
            {
                "flow_id": str(flow_id),
                "question_id": question_id,
                "source_question_id": source_question_id,
                "text": str(question.get("text") or flow_id),
                "answer": answer,
            }
        )

    return records


def _flow_id_number(flow_id):
    text = str(flow_id or "").strip()
    return text[1:] if len(text) > 1 and text[0].upper() == "Q" and text[1:].isdigit() else None
