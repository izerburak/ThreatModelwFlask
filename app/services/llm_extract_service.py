import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.services.ollama_client import chat


PROMPT_FILENAME = "Response-Extractor-prompt.txt"


def generate_llm_extract(app_root_path, metadata, response_file, app_config=None):
    response_payload = _load_response_payload(app_root_path, response_file)
    prompt_text = _load_prompt(app_root_path)
    answers_by_flow_id = _answers_by_flow_id(response_payload)

    user_payload = {
        "metadata": _clean_metadata(metadata),
        "response_file": response_file,
        "answers_by_flow_id": answers_by_flow_id,
        "response": response_payload,
    }

    llm_response = chat(
        [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": json.dumps(user_payload, indent=2, ensure_ascii=False)},
        ],
        app_config,
    )
    raw_content = llm_response["message"]["content"]
    parsed_extract = parse_extract_json(raw_content)
    if parsed_extract is None:
        raise ValueError("LLM returned a response that could not be parsed as JSON.")

    extract_filename = build_extract_filename(response_file)
    saved_path = save_extract_payload(app_root_path, extract_filename, parsed_extract)

    return {
        "filename": extract_filename,
        "raw": json.dumps(parsed_extract, indent=2, ensure_ascii=False),
        "parsed": parsed_extract,
        "saved_path": str(saved_path),
        "model": llm_response.get("model"),
    }


def build_extract_filename(response_file):
    response_name = Path(str(response_file)).name
    stem = Path(response_name).stem
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", stem).strip("-._")
    if not safe_stem:
        safe_stem = f"response-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return f"{safe_stem}-extract.json"


def save_extract_payload(app_root_path, filename, payload):
    extract_dir = Path(app_root_path).parent / "LLM_Extracts"
    extract_dir.mkdir(parents=True, exist_ok=True)
    extract_path = _safe_extract_path(extract_dir, filename)
    extract_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return extract_path


def parse_extract_json(raw):
    if not isinstance(raw, str):
        return None

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _load_prompt(app_root_path):
    prompt_path = Path(app_root_path).parent / "LLM-Prompts" / PROMPT_FILENAME
    return prompt_path.read_text(encoding="utf-8")


def _load_response_payload(app_root_path, filename):
    response_path = _safe_json_path(Path(app_root_path).parent / "responses", filename)
    return json.loads(response_path.read_text(encoding="utf-8"))


def _answers_by_flow_id(response_payload):
    if not isinstance(response_payload, dict):
        return {}

    compact_answers = response_payload.get("answers_by_flow_id")
    if isinstance(compact_answers, dict):
        return compact_answers

    answers = response_payload.get("answers")
    if not isinstance(answers, list):
        return {}

    normalized = {}
    for answer_record in answers:
        if not isinstance(answer_record, dict):
            continue

        flow_id = answer_record.get("flow_id")
        answer = answer_record.get("answer")
        if isinstance(flow_id, str) and flow_id.strip() and answer not in (None, "", []):
            normalized[flow_id.strip()] = answer

    return normalized


def _clean_metadata(metadata):
    if not isinstance(metadata, dict):
        return {}

    allowed_keys = {
        "model_title",
        "project_name",
        "owner",
        "reviewer",
        "description",
        "environment",
    }
    return {
        key: str(metadata.get(key) or "").strip()
        for key in allowed_keys
        if str(metadata.get(key) or "").strip()
    }


def _safe_json_path(base_dir, filename):
    candidate = (base_dir / str(filename)).resolve()
    if candidate.parent != base_dir.resolve() or candidate.suffix.lower() != ".json":
        raise ValueError("Invalid JSON file selection.")
    if not candidate.exists():
        raise FileNotFoundError(filename)
    return candidate


def _safe_extract_path(base_dir, filename):
    candidate = (base_dir / str(filename)).resolve()
    if candidate.parent != base_dir.resolve() or candidate.suffix.lower() != ".json":
        raise ValueError("Invalid extract filename.")
    return candidate
