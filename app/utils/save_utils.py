import os
import json
from datetime import datetime
from flask import current_app



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

    os.makedirs("responses", exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"llmsec_{timestamp_str}.json"
    filepath = os.path.join("responses", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return filepath
