import json
from pathlib import Path
from flask import current_app


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
