import os
import json
from datetime import datetime
from flask import current_app

def save_answers(form_data, layer_name="layer1"):
    import os, json
    from datetime import datetime

    answers = {}
    for key in form_data.keys():
        vals = form_data.getlist(key)
        if len(vals) == 0:
            answers[key] = None
        elif len(vals) == 1:
            answers[key] = vals[0]
        else:
            answers[key] = vals

    result = {
        "timestamp": datetime.now().isoformat(),
        "layer": layer_name,
        "answers": answers,
    }

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("responses", exist_ok=True)
    filename = f"{layer_name}_answers_{timestamp_str}.json"
    filepath = os.path.join("responses", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

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
