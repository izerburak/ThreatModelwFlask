import json
import re
from functools import lru_cache
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - fallback for environments without PyYAML
    yaml = None


def load_questions(root_path):
    """Load the questionnaire catalog keyed by flow IDs."""
    return _load_questions_cached(str(Path(root_path)))


def clear_questionnaire_caches():
    _load_questions_cached.cache_clear()
    _load_qat_tree.cache_clear()
    _load_qat_flow.cache_clear()


@lru_cache(maxsize=4)
def _load_questions_cached(root_path_str):
    root_path = _normalize_root_path(root_path_str)
    primary_questions = _read_question_file(_resolve_primary_questions_path(root_path))

    qat_flow = _load_qat_flow(root_path)

    all_question_ids = _collect_qat_question_ids(qat_flow)

    flow_questions = {}
    for flow_id in all_question_ids:
        source_question = next(
            (
                q
                for q in primary_questions
                if q.get("id") == int(flow_id[1:]) or str(q.get("id")) == flow_id
            ),
            None,
        )

        if source_question:
            flow_questions[flow_id] = {
                "flow_id": flow_id,
                "id": str(source_question.get("id", flow_id)),
                "source_id": str(source_question.get("id", flow_id)),
                "layer": source_question.get("layer", 1),
                "text": source_question.get("text", flow_id),
                "type": source_question.get("type", "single"),
                "options": list(source_question.get("options", [])),
                "source_file": "questionsDb.json",
                "branch_text": source_question.get("text", flow_id),
            }

    return flow_questions


@lru_cache(maxsize=4)
def _load_qat_tree(root_path=None):
    root_path = _normalize_root_path(root_path)

    qat_path = root_path / "TM-Questions" / "QaT_new.txt"
    if not qat_path.exists():
        qat_path = root_path / "QaT_new.txt"
        
    try:
        text = qat_path.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(text)
            return data or {}
        return _parse_qat_without_yaml(text)
    except Exception as e:
        print(f"Error loading {qat_path}: {e}")
        return {}


@lru_cache(maxsize=4)
def _load_qat_flow(root_path=None):
    qat_data = _load_qat_tree(root_path)
    if "questions" in qat_data and "start" in qat_data:
        return _normalize_graph_qat(qat_data)

    return _normalize_legacy_qat(qat_data)


def get_next_question(current_question_id, answers, root_path=None):
    survey_state = build_survey_state(answers, root_path)
    pending_questions = survey_state["pending_question_queue"]

    if not pending_questions:
        return None

    if current_question_id is None:
        return pending_questions[0]

    current_question_id = _normalize_flow_id(current_question_id)
    if current_question_id not in pending_questions:
        return pending_questions[0]

    current_index = pending_questions.index(current_question_id)
    if current_index + 1 < len(pending_questions):
        return pending_questions[current_index + 1]

    return None


def get_follow_up_questions(current_question_id, answers, root_path=None):
    qat_flow = _load_qat_flow(root_path)
    current_question_id = _normalize_flow_id(current_question_id)
    if not current_question_id:
        return []

    node = (qat_flow.get("questions") or {}).get(current_question_id, {})
    if not node:
        return []

    answer = answers.get(current_question_id)
    return _get_node_follow_ups(node, answer)


def build_survey_state(answers, root_path=None):
    qat_flow = _load_qat_flow(root_path)
    return _build_survey_state(qat_flow, answers)


def _build_full_question_path(answers, root_path=None):
    survey_state = build_survey_state(answers, root_path)
    return list(survey_state["visited_question_ids"])


def get_question_path(answers, root_path=None):
    return _build_full_question_path(answers, root_path)


def _build_survey_state(qat_flow, answers):
    normalized_answers = {
        _normalize_flow_id(qid): value
        for qid, value in (answers or {}).items()
        if _normalize_flow_id(qid)
    }
    answered_question_ids = {
        qid for qid, value in normalized_answers.items() if _is_answered_value(value)
    }

    start_question_id = _normalize_flow_id(qat_flow.get("start"))
    if not start_question_id:
        return {
            "answers_so_far": normalized_answers,
            "visited_question_ids": [],
            "pending_question_queue": [],
        }

    processing_queue = [start_question_id]
    scheduled_question_ids = {start_question_id}
    visited_question_ids = []
    pending_question_queue = []

    while processing_queue:
        question_id = processing_queue.pop(0)
        visited_question_ids.append(question_id)

        if question_id not in answered_question_ids:
            pending_question_queue.append(question_id)
            continue

        node = (qat_flow.get("questions") or {}).get(question_id, {})
        answer = normalized_answers.get(question_id)

        follow_up_question_ids = _get_node_follow_ups(node, answer)
        for next_question_id in reversed(follow_up_question_ids):
            if next_question_id in processing_queue:
                processing_queue.remove(next_question_id)
            elif next_question_id in scheduled_question_ids:
                continue
            processing_queue.insert(0, next_question_id)
            scheduled_question_ids.add(next_question_id)

    return {
        "answers_so_far": normalized_answers,
        "visited_question_ids": visited_question_ids,
        "pending_question_queue": pending_question_queue,
    }


def get_question_by_id(root_path, question_id):
    return load_questions(root_path).get(question_id)


def evaluate_condition(condition_clause, answer):
    if not _is_answered_value(answer):
        return False, True

    ans = answer
    if not isinstance(ans, list):
        ans = [ans]

    ans_lower = [_normalize_text(a) for a in ans]

    if 'equals' in condition_clause:
        val = _normalize_text(condition_clause['equals'])
        return val in ans_lower, False

    if 'not_equals' in condition_clause:
        val = _normalize_text(condition_clause['not_equals'])
        return val not in ans_lower, False

    if 'any_of' in condition_clause:
        vals = [_normalize_text(v) for v in condition_clause['any_of']]
        return any(v in ans_lower for v in vals), False

    if 'not_any_of' in condition_clause:
        vals = [_normalize_text(v) for v in condition_clause['not_any_of']]
        return not any(v in ans_lower for v in vals), False

    if 'includes' in condition_clause:
        val = _normalize_text(condition_clause['includes'])
        return any(val in a for a in ans_lower), False

    if 'not_includes' in condition_clause:
        val = _normalize_text(condition_clause['not_includes'])
        return not any(val in a for a in ans_lower), False

    return True, False


def get_first_question_id():
    qat_flow = _load_qat_flow()
    return qat_flow.get("start")


def extract_answer(form_data, question):
    field_name = f"q_{question['flow_id']}"

    if question.get("options"):
        selected_values = [value.strip() for value in form_data.getlist(field_name) if value.strip()]
        other_value = form_data.get(f"{field_name}_other", "").strip()

        if question.get("type") == "single":
            if other_value:
                return other_value
            return selected_values[0] if selected_values else None

        if other_value:
            selected_values.append(other_value)

        if not selected_values:
            return None
        if len(selected_values) == 1:
            return selected_values[0]
        return selected_values

    free_text_value = form_data.get(field_name, "").strip()
    return free_text_value or None


def split_answer_for_display(question, answer):
    if answer is None:
        return [], ""

    options = set(question.get("options", []))
    values = answer if isinstance(answer, list) else [answer]

    selected_options = [value for value in values if value in options]
    other_values = [value for value in values if value not in options]

    return selected_options, "; ".join(other_values)


def _read_question_file(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    else:
        questions = data

    return questions if isinstance(questions, list) else []


def _normalize_text(value):
    if not value:
        return ""
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _normalize_root_path(root_path):
    if root_path is None:
        return Path(__file__).parent.parent.parent

    root_path = Path(root_path)
    if root_path.name == "app":
        return root_path.parent
    return root_path


def _resolve_primary_questions_path(root_path):
    preferred_path = root_path / "TM-Questions" / "questionsDb.json"
    if preferred_path.exists():
        return preferred_path

    fallback_path = root_path / "app" / "questions" / "questionsDb.json"
    if fallback_path.exists():
        return fallback_path

    return root_path / "questions" / "questionsDb.json"


def _parse_qat_without_yaml(text):
    if re.search(r"(?m)^start:\s*", text):
        return _parse_graph_qat_without_yaml(text)

    data = {"FLOW": [], "BRANCHES": []}
    current_section = None
    current_branch = None
    current_clause = None
    current_list_key = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            continue

        indent = len(line) - len(line.lstrip(" "))

        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            current_branch = None
            current_clause = None
            current_list_key = None
            continue

        if current_section == "FLOW" and stripped.startswith("- "):
            data["FLOW"].append(stripped[2:].strip())
            continue

        if current_section != "BRANCHES":
            continue

        if indent == 2 and stripped.startswith("- "):
            current_branch = {}
            data["BRANCHES"].append(current_branch)
            current_clause = None
            current_list_key = None

            header = stripped[2:].strip()
            if header.endswith(":"):
                key = header[:-1]
                if key in ("when", "ask", "else_ask"):
                    current_branch[key] = {} if key == "when" else []
                    current_clause = current_branch[key] if key == "when" else None
                    current_list_key = key if key != "when" else None
            continue

        if current_branch is None:
            continue

        if indent == 6 and stripped.endswith(":"):
            key = stripped[:-1]
            if key == "when":
                current_branch["when"] = {}
                current_clause = current_branch["when"]
                current_list_key = None
            elif key in ("ask", "else_ask"):
                current_branch[key] = []
                current_clause = None
                current_list_key = key
            continue

        if indent == 8 and current_clause is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                current_clause[key] = _strip_quotes(value)
                current_list_key = None
            else:
                current_clause[key] = []
                current_list_key = key
            continue

        if indent >= 8 and current_list_key in ("ask", "else_ask") and stripped.startswith("- "):
            current_branch[current_list_key].append(_strip_quotes(stripped[2:].strip()))
            continue

        if indent >= 10 and current_clause is not None and current_list_key and stripped.startswith("- "):
            current_clause[current_list_key].append(_strip_quotes(stripped[2:].strip()))

    return data


def _strip_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _normalize_graph_qat(qat_data):
    questions = {}

    for raw_question_id, raw_node in (qat_data.get("questions") or {}).items():
        question_id = _normalize_flow_id(raw_question_id)
        if not question_id:
            continue

        node = raw_node or {}
        normalized_node = {
            "next": _normalize_flow_target(node.get("next")),
            "conditions": [],
        }

        for raw_condition in node.get("conditions") or []:
            normalized_condition = {
                "if": _normalize_condition_clause(raw_condition.get("if")),
                "then": _normalize_question_list(raw_condition.get("then", [])),
                "else": _normalize_question_list(raw_condition.get("else", [])),
                "next_after": _normalize_flow_target(raw_condition.get("next_after")),
            }
            normalized_node["conditions"].append(normalized_condition)

        questions[question_id] = normalized_node

    return {
        "start": _normalize_flow_id(qat_data.get("start")),
        "questions": questions,
    }


def _normalize_legacy_qat(qat_data):
    start = None
    ordered_questions = []

    for qid in qat_data.get("FLOW", []):
        normalized_qid = _normalize_flow_id(qid)
        if not normalized_qid:
            continue
        if start is None:
            start = normalized_qid
        ordered_questions.append(normalized_qid)

    questions = {}
    for index, qid in enumerate(ordered_questions):
        next_qid = ordered_questions[index + 1] if index + 1 < len(ordered_questions) else None
        questions[qid] = {"next": next_qid, "conditions": []}

    for raw_branch in qat_data.get("BRANCHES", []):
        when_clause = _normalize_when_clause(raw_branch.get("when"))
        ask = _normalize_question_list(raw_branch.get("ask", []))
        else_ask = _normalize_question_list(raw_branch.get("else_ask", []))

        if when_clause and when_clause.get("question"):
            owner_qid = when_clause["question"]
            condition_clause = dict(when_clause)
            condition_clause.pop("question", None)
            node = questions.setdefault(owner_qid, {"next": None, "conditions": []})
            node["conditions"].append(
                {
                    "if": condition_clause,
                    "then": ask,
                    "else": else_ask,
                    "next_after": node.get("next"),
                }
            )
            continue

        if ordered_questions:
            tail_qid = ordered_questions[-1]
            node = questions.setdefault(tail_qid, {"next": None, "conditions": []})
            node["conditions"].append(
                {
                    "if": None,
                    "then": ask,
                    "else": else_ask,
                    "next_after": node.get("next"),
                }
            )

    return {"start": start, "questions": questions}


def _collect_qat_question_ids(qat_flow):
    question_ids = []

    def add_question_id(qid):
        normalized_qid = _normalize_flow_id(qid)
        if normalized_qid and normalized_qid != "END" and normalized_qid not in question_ids:
            question_ids.append(normalized_qid)

    add_question_id(qat_flow.get("start"))

    for qid, node in (qat_flow.get("questions") or {}).items():
        add_question_id(qid)
        add_question_id(node.get("next"))
        for condition in node.get("conditions") or []:
            for branch_qid in condition.get("then", []):
                add_question_id(branch_qid)
            for branch_qid in condition.get("else", []):
                add_question_id(branch_qid)
            add_question_id(condition.get("next_after"))

    return question_ids


def _resolve_condition_branch(conditions, answer):
    for condition in conditions or []:
        condition_clause = condition.get("if")
        if condition_clause is None:
            return {
                "ask": condition.get("else", []),
                "next_after": condition.get("next_after"),
            }

        matched, deferred = evaluate_condition(condition_clause, answer)
        if deferred:
            return None
        if matched:
            return {
                "ask": condition.get("then", []),
                "next_after": condition.get("next_after"),
            }

    return None


def _get_node_follow_ups(node, answer):
    follow_ups = []

    conditions = node.get("conditions") or []
    if conditions:
        branch = _resolve_condition_branch(conditions, answer)
        if branch is None:
            return []

        follow_ups.extend(branch.get("ask", []))
        next_after = branch.get("next_after")
        if next_after and next_after != "END":
            follow_ups.append(next_after)
        return _normalize_question_list(follow_ups)

    next_qid = node.get("next")
    if next_qid and next_qid != "END":
        follow_ups.append(next_qid)

    return _normalize_question_list(follow_ups)


def _normalize_condition_clause(condition_clause):
    if not condition_clause:
        return None

    normalized = {}
    for key, value in condition_clause.items():
        if isinstance(value, list):
            normalized[key] = [_parse_scalar(item) for item in value]
        else:
            normalized[key] = _parse_scalar(value)
    return normalized


def _normalize_flow_target(value):
    parsed_value = _parse_scalar(value)
    if parsed_value in (None, ""):
        return None
    if str(parsed_value).upper() == "END":
        return "END"
    return _normalize_flow_id(parsed_value)


def _parse_scalar(value):
    if value is None:
        return None
    if isinstance(value, list):
        return value

    text = _strip_quotes(str(value).strip())
    if not text:
        return None
    if text.lower() == "null":
        return None
    if text == "[]":
        return []
    return text


def _parse_inline_list_or_scalar(value, normalize_questions=False):
    parsed = _parse_scalar(value)
    if parsed is None:
        return None
    if parsed == []:
        return []
    if isinstance(parsed, list):
        values = parsed
    else:
        values = [parsed]

    if normalize_questions:
        normalized_values = []
        for item in values:
            qid = _normalize_flow_id(item)
            if qid:
                normalized_values.append(qid)
        return normalized_values

    return values


def _is_answered_value(value):
    return value not in (None, "", [])


def _parse_graph_qat_without_yaml(text):
    data = {"questions": {}}
    current_question_id = None
    current_condition = None
    current_list_target = None
    current_if_key = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            continue

        indent = len(line) - len(line.lstrip(" "))

        if indent == 0:
            if stripped.startswith("version:"):
                data["version"] = _parse_scalar(stripped.split(":", 1)[1].strip())
            elif stripped.startswith("start:"):
                data["start"] = _normalize_flow_id(_parse_scalar(stripped.split(":", 1)[1].strip()))
            elif stripped == "questions:":
                continue
            continue

        if indent == 2 and stripped.endswith(":"):
            current_question_id = stripped[:-1].strip()
            data["questions"][current_question_id] = {}
            current_condition = None
            current_list_target = None
            current_if_key = None
            continue

        if current_question_id is None:
            continue

        current_question = data["questions"][current_question_id]

        if indent == 4 and stripped.startswith("next:"):
            current_question["next"] = _parse_scalar(stripped.split(":", 1)[1].strip())
            continue

        if indent == 4 and stripped == "conditions:":
            current_question["conditions"] = []
            current_condition = None
            current_list_target = None
            current_if_key = None
            continue

        if indent == 6 and stripped.startswith("- "):
            current_condition = {}
            current_question.setdefault("conditions", []).append(current_condition)
            current_list_target = None
            current_if_key = None

            header = stripped[2:].strip()
            if header == "if:":
                current_condition["if"] = {}
            elif header.startswith("else:"):
                inline_value = header.split(":", 1)[1].strip()
                current_condition["else"] = _parse_inline_list_or_scalar(inline_value, normalize_questions=True)
                if current_condition["else"] is None:
                    current_condition["else"] = []
                    current_list_target = ("condition", "else")
            continue

        if current_condition is None:
            continue

        if indent == 8:
            if stripped.startswith("then:"):
                inline_value = stripped.split(":", 1)[1].strip()
                current_condition["then"] = _parse_inline_list_or_scalar(inline_value, normalize_questions=True)
                if current_condition["then"] is None:
                    current_condition["then"] = []
                    current_list_target = ("condition", "then")
                else:
                    current_list_target = None
                continue

            if stripped.startswith("next_after:"):
                current_condition["next_after"] = _normalize_flow_id(_parse_scalar(stripped.split(":", 1)[1].strip()))
                current_list_target = None
                continue

            if ":" in stripped and "if" in current_condition:
                key, raw_value = stripped.split(":", 1)
                key = key.strip()
                raw_value = raw_value.strip()
                if raw_value:
                    current_condition["if"][key] = _parse_scalar(raw_value)
                    current_list_target = None
                    current_if_key = None
                else:
                    current_condition["if"][key] = []
                    current_list_target = ("if", key)
                    current_if_key = key
                continue

        if indent >= 10 and stripped.startswith("- "):
            value = stripped[2:].strip()
            if current_list_target == ("condition", "then"):
                parsed_value = _normalize_flow_id(_parse_scalar(value))
                if parsed_value:
                    current_condition["then"].append(parsed_value)
            elif current_list_target == ("condition", "else"):
                parsed_value = _normalize_flow_id(_parse_scalar(value))
                if parsed_value:
                    current_condition["else"].append(parsed_value)
            elif current_list_target and current_list_target[0] == "if":
                current_condition["if"][current_if_key].append(_parse_scalar(value))

    return data


def _normalize_flow_id(value):
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        return None
    text = str(value).strip()
    if not text:
        return None
    if text in ("[]", "[ ]"):
        return None
    if text.upper() == "END":
        return "END"
    if re.fullmatch(r"Q\d+", text, flags=re.IGNORECASE):
        return f"Q{int(text[1:])}"
    if text.isdigit():
        return f"Q{int(text)}"
    return text


def _normalize_question_list(values):
    normalized = []
    for value in values or []:
        if isinstance(value, list):
            if not value:
                continue
            for nested_value in value:
                qid = _normalize_flow_id(nested_value)
                if qid and qid not in ("[END]", "END") and qid not in normalized:
                    normalized.append(qid)
            continue
        qid = _normalize_flow_id(value)
        if qid and qid not in ("[END]", "END") and qid not in normalized:
            normalized.append(qid)
    return normalized


def _normalize_when_clause(when_clause):
    if not when_clause:
        return None

    normalized = dict(when_clause)
    normalized["question"] = _normalize_flow_id(when_clause.get("question"))
    return normalized
