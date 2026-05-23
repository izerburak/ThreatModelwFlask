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
        "answers": _answer_records_for_prompt(response_payload, answers_by_flow_id),
    }

    llm_response = chat(
        [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": json.dumps(user_payload, indent=2, ensure_ascii=False)},
        ],
        app_config,
        json_mode=True,
    )
    raw_content = llm_response["message"]["content"]
    parsed_extract = parse_extract_json(raw_content)
    if parsed_extract is None:
        raw_path = save_raw_extract_text(app_root_path, build_raw_extract_filename(response_file), raw_content)
        parsed_extract = build_fallback_extract(
            metadata,
            response_file,
            answers_by_flow_id,
            "LLM returned a response that could not be parsed as JSON.",
            raw_path.name,
        )

    extract_filename = build_extract_filename(response_file)
    saved_path = save_extract_payload(app_root_path, extract_filename, parsed_extract)

    return {
        "filename": extract_filename,
        "raw": json.dumps(parsed_extract, indent=2, ensure_ascii=False),
        "parsed": parsed_extract,
        "saved_path": str(saved_path),
        "model": llm_response.get("model"),
        "parse_warning": parsed_extract.get("llm_parse_error") if isinstance(parsed_extract, dict) else None,
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


def build_raw_extract_filename(response_file):
    extract_name = build_extract_filename(response_file)
    return f"{Path(extract_name).stem}.raw.txt"


def save_raw_extract_text(app_root_path, filename, raw_text):
    extract_dir = Path(app_root_path).parent / "LLM_Extracts"
    extract_dir.mkdir(parents=True, exist_ok=True)
    raw_path = _safe_extract_text_path(extract_dir, filename)
    raw_path.write_text(str(raw_text or ""), encoding="utf-8")
    return raw_path


def parse_extract_json(raw):
    if not isinstance(raw, str):
        return None

    raw = raw.strip().lstrip("\ufeff")
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    for fenced in re.findall(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL):
        parsed = _parse_json_object_candidate(fenced)
        if isinstance(parsed, dict):
            return parsed

    for candidate in _json_object_candidates(raw):
        parsed = _parse_json_object_candidate(candidate)
        if isinstance(parsed, dict):
            return parsed

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


def build_fallback_extract(metadata, response_file, answers_by_flow_id, reason, raw_extract_file=None):
    answers = answers_by_flow_id if isinstance(answers_by_flow_id, dict) else {}
    purpose = _answer_as_text(answers.get("Q1")) or "Unknown"
    exposure = _answer_as_text(answers.get("Q2")) or "Unknown"
    interfaces = _answer_as_text(answers.get("Q3")) or "Unknown"

    notes = [
        f"{reason} This fallback extract was generated from questionnaire answers.",
        "The React Flow DFD mapper can still derive architecture nodes from answers_by_flow_id.",
    ]
    if raw_extract_file:
        notes.append(f"Original raw LLM output saved as {raw_extract_file}.")

    return {
        "system_summary": {
            "purpose": purpose,
            "exposure": exposure,
            "architecture_style": interfaces,
            "overall_dfd_confidence": "Low",
        },
        "dfd": {
            "actors": [],
            "interfaces": [],
            "processes": [],
            "data_stores": [],
            "external_systems": [],
            "tools": [],
            "trust_boundaries": [],
            "data_flows": [],
        },
        "applicable_owasp_llm_risks": [],
        "dfd_notes": notes,
        "missing_information": ["Review the raw LLM output or regenerate extraction for a model-authored DFD summary."],
        "llm_parse_error": reason,
        "response_file": Path(str(response_file or "")).name,
        "metadata": _clean_metadata(metadata),
    }


def _has_extraction_content(parsed):
    if not isinstance(parsed, dict) or not parsed:
        return False
    if isinstance(parsed.get("system_summary"), dict) and parsed["system_summary"]:
        return True
    if isinstance(parsed.get("architecture"), dict) and parsed["architecture"]:
        return True
    dfd = parsed.get("dfd")
    if isinstance(dfd, dict):
        return any(isinstance(dfd.get(key), list) and dfd.get(key) for key in (
            "actors",
            "interfaces",
            "processes",
            "data_stores",
            "external_systems",
            "tools",
            "trust_boundaries",
            "data_flows",
        ))
    return any(parsed.get(key) for key in ("applicable_owasp_llm_risks", "top_risks", "extract_risks"))


def _parse_json_object_candidate(candidate):
    if not isinstance(candidate, str):
        return None

    variants = [candidate.strip(), _repair_json_text(candidate)]
    for variant in variants:
        if not variant:
            continue
        try:
            parsed = json.loads(variant)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _repair_json_text(text):
    repaired = str(text or "").strip().lstrip("\ufeff")
    repaired = (
        repaired.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    return repaired


def _json_object_candidates(text):
    candidates = []
    stack = []
    start = None
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if not stack:
                start = index
            stack.append(char)
            continue
        if char == "}" and stack:
            stack.pop()
            if not stack and start is not None:
                candidates.append(text[start : index + 1])
                start = None

    return candidates


def _answer_as_text(answer):
    if answer in (None, "", []):
        return ""
    if isinstance(answer, list):
        return ", ".join(str(item) for item in answer if str(item).strip())
    return str(answer).strip()


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


def _answer_records_for_prompt(response_payload, answers_by_flow_id):
    records = []
    detailed_answers = response_payload.get("answers") if isinstance(response_payload, dict) else None

    if isinstance(detailed_answers, list):
        for answer_record in detailed_answers:
            if not isinstance(answer_record, dict):
                continue
            flow_id = str(answer_record.get("flow_id") or "").strip()
            answer = answer_record.get("answer")
            if not flow_id or answer in (None, "", []):
                continue
            records.append(
                {
                    "flow_id": flow_id,
                    "text": str(answer_record.get("text") or "").strip(),
                    "answer": answer,
                }
            )

    seen = {record["flow_id"] for record in records}
    for flow_id, answer in (answers_by_flow_id or {}).items():
        if flow_id in seen or answer in (None, "", []):
            continue
        records.append(
            {
                "flow_id": str(flow_id),
                "text": "",
                "answer": answer,
            }
        )

    return records


def _clean_metadata(metadata):
    if not isinstance(metadata, dict):
        return {}

    allowed_keys = {
        "model_title",
        "project_name",
        "dfd_name",
        "auditor_name",
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


def _safe_extract_text_path(base_dir, filename):
    candidate = (base_dir / str(filename)).resolve()
    if candidate.parent != base_dir.resolve() or candidate.suffix.lower() != ".txt":
        raise ValueError("Invalid raw extract filename.")
    return candidate
