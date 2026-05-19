import json
from pathlib import Path
from flask import current_app


def append_question_to_catalog(question_text: str, options: list):
    qpath = Path(current_app.root_path) / "questions" / "questionsDb.json"
    questions = json.loads(qpath.read_text(encoding="utf-8")) if qpath.exists() else []
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
    new_question = {
        "id": max_id + 1,
        "text": question_text,
        "type": "multi" if len(clean_options) > 1 else "single",
        "options": clean_options,
        "owasp_llm": [],
        "severity_weight": 1,
        "confidence_weight": 1,
    }
    questions.append(new_question)
    qpath.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(qpath), new_question



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

    Only the compact `answers_by_flow_id` payload is written for survey answers.
    The `question_catalog` argument is kept for compatibility with existing call sites.
    """
    from datetime import datetime, timezone

    record = {
        "schema_version": "llmsec.adaptive.v1",
        "project_id": "DEFAULT_PROJECT",
        "system_id": "DEFAULT_SYSTEM",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "answers_by_flow_id": answer_map,
    }

    responses_dir = Path(current_app.root_path).parent / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"llmsec_{timestamp_str}.json"
    filepath = responses_dir / filename

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return str(filepath)
