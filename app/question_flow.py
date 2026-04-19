import json
import re
from functools import lru_cache
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class QuestionFlowEngine:
    """Resolve questionnaire order and branching from QaT and questionsDb."""

    def __init__(self, root_path):
        self.root_path = _normalize_root_path(root_path)
        self.flow_definition = _load_flow_definition(str(self.root_path))
        self.question_catalog = _load_question_catalog(str(self.root_path))

    def get_start_question(self):
        return self.flow_definition.get("start")

    def get_next_question(self, current_qid, answers):
        survey_state = self._build_survey_state(answers)
        pending_question_ids = survey_state["pending_question_ids"]

        if not pending_question_ids:
            return None

        normalized_current_qid = _normalize_flow_id(current_qid)
        if not normalized_current_qid:
            return pending_question_ids[0]

        if normalized_current_qid not in pending_question_ids:
            return pending_question_ids[0]

        current_index = pending_question_ids.index(normalized_current_qid)
        if current_index + 1 < len(pending_question_ids):
            return pending_question_ids[current_index + 1]

        return None

    def get_current_or_next_unanswered(self, answers):
        survey_state = self._build_survey_state(answers)
        pending_question_ids = survey_state["pending_question_ids"]
        return pending_question_ids[0] if pending_question_ids else None

    def get_question_path(self, answers):
        return list(self._build_survey_state(answers)["visited_question_ids"])

    def get_question(self, question_id):
        normalized_question_id = _normalize_flow_id(question_id)
        if not normalized_question_id:
            return None
        return self.question_catalog.get(normalized_question_id)

    def normalize_answers(self, answers):
        normalized_answers = {}
        for question_id, answer_value in (answers or {}).items():
            normalized_question_id = _normalize_flow_id(question_id)
            if not normalized_question_id:
                continue
            normalized_answers[normalized_question_id] = answer_value
        return normalized_answers

    def trim_answers_to_active_path(self, answers):
        normalized_answers = self.normalize_answers(answers)
        active_path = set(self.get_question_path(normalized_answers))
        return {
            question_id: answer_value
            for question_id, answer_value in normalized_answers.items()
            if question_id in active_path
        }

    def extract_answer(self, form_data, question):
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

    def split_answer_for_display(self, question, answer):
        if answer is None:
            return [], ""

        options = set(question.get("options", []))
        answer_values = answer if isinstance(answer, list) else [answer]

        selected_options = [value for value in answer_values if value in options]
        other_values = [value for value in answer_values if value not in options]
        return selected_options, "; ".join(other_values)

    def _build_survey_state(self, answers):
        normalized_answers = self.normalize_answers(answers)
        answered_question_ids = {
            question_id
            for question_id, answer_value in normalized_answers.items()
            if _is_answered_value(answer_value)
        }

        start_question_id = self.get_start_question()
        if not start_question_id:
            return {
                "visited_question_ids": [],
                "pending_question_ids": [],
            }

        processing_queue = [start_question_id]
        scheduled_question_ids = {start_question_id}
        visited_question_ids = []
        pending_question_ids = []

        while processing_queue:
            question_id = processing_queue.pop(0)
            visited_question_ids.append(question_id)

            if question_id not in answered_question_ids:
                pending_question_ids.append(question_id)
                continue

            node = (self.flow_definition.get("questions") or {}).get(question_id, {})
            answer_value = normalized_answers.get(question_id)
            follow_up_question_ids = _get_follow_up_questions(node, answer_value)

            for next_question_id in reversed(follow_up_question_ids):
                if next_question_id in processing_queue:
                    processing_queue.remove(next_question_id)
                elif next_question_id in scheduled_question_ids:
                    continue

                processing_queue.insert(0, next_question_id)
                scheduled_question_ids.add(next_question_id)

        return {
            "visited_question_ids": visited_question_ids,
            "pending_question_ids": pending_question_ids,
        }


def get_question_flow_engine(root_path):
    return QuestionFlowEngine(root_path)


def clear_question_flow_caches():
    _load_flow_definition.cache_clear()
    _load_question_catalog.cache_clear()


@lru_cache(maxsize=4)
def _load_flow_definition(root_path_str):
    root_path = _normalize_root_path(root_path_str)
    qat_path = _resolve_qat_path(root_path)
    raw_flow = _read_qat_yaml(qat_path)
    return _normalize_flow_definition(raw_flow)


@lru_cache(maxsize=4)
def _load_question_catalog(root_path_str):
    root_path = _normalize_root_path(root_path_str)
    questions_path = _resolve_questions_path(root_path)
    all_questions = _read_questions(questions_path)
    flow_definition = _load_flow_definition(str(root_path))
    flow_question_ids = _collect_question_ids(flow_definition)

    question_catalog = {}
    for flow_question_id in flow_question_ids:
        source_question = next(
            (
                question
                for question in all_questions
                if str(question.get("id")) == flow_question_id[1:] or str(question.get("id")) == flow_question_id
            ),
            None,
        )
        if source_question is None:
            continue

        question_catalog[flow_question_id] = {
            "flow_id": flow_question_id,
            "id": str(source_question.get("id", flow_question_id)),
            "source_id": str(source_question.get("id", flow_question_id)),
            "layer": source_question.get("layer", 1),
            "text": source_question.get("text", flow_question_id),
            "type": source_question.get("type", "single"),
            "options": list(source_question.get("options", [])),
            "source_file": questions_path.name,
        }

    return question_catalog


def _resolve_qat_path(root_path):
    candidate_paths = [
        root_path / "TM-Questions" / "QaT.txt",
        root_path / "QaT.txt",
        root_path / "TM-Questions" / "QaT_new.txt",
        root_path / "QaT_new.txt",
    ]
    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return candidate_path
    raise FileNotFoundError("Unable to find QaT.txt.")


def _resolve_questions_path(root_path):
    candidate_paths = [
        root_path / "TM-Questions" / "questionsDb.json",
        root_path / "app" / "questions" / "questionsDb.json",
        root_path / "questions" / "questionsDb.json",
    ]
    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return candidate_path
    raise FileNotFoundError("Unable to find questionsDb.json.")


def _read_qat_yaml(path):
    text = path.read_text(encoding="utf-8")

    if yaml is not None:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} must contain a YAML mapping.")
        return data

    return _parse_graph_qat_without_yaml(text)


def _read_questions(path):
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]

    return data if isinstance(data, list) else []


def _normalize_flow_definition(raw_flow):
    questions = {}

    for raw_question_id, raw_node in (raw_flow.get("questions") or {}).items():
        question_id = _normalize_flow_id(raw_question_id)
        if not question_id:
            continue

        node = raw_node or {}
        normalized_node = {
            "next": _normalize_flow_target(node.get("next")),
            "conditions": [],
        }

        for raw_condition in node.get("conditions") or []:
            normalized_node["conditions"].append(
                {
                    "if": _normalize_condition(raw_condition.get("if")),
                    "then": _normalize_question_list(raw_condition.get("then", [])),
                    "else": _normalize_question_list(raw_condition.get("else", [])),
                    "next_after": _normalize_flow_target(raw_condition.get("next_after")),
                }
            )

        questions[question_id] = normalized_node

    return {
        "start": _normalize_flow_id(raw_flow.get("start")),
        "questions": questions,
    }


def _normalize_condition(condition):
    if not condition:
        return None

    normalized_condition = {}
    for key, value in condition.items():
        if isinstance(value, list):
            normalized_condition[key] = [_parse_scalar(item) for item in value]
        else:
            normalized_condition[key] = _parse_scalar(value)
    return normalized_condition


def _collect_question_ids(flow_definition):
    question_ids = []

    def append_question_id(raw_question_id):
        question_id = _normalize_flow_id(raw_question_id)
        if question_id and question_id != "END" and question_id not in question_ids:
            question_ids.append(question_id)

    append_question_id(flow_definition.get("start"))

    for question_id, node in (flow_definition.get("questions") or {}).items():
        append_question_id(question_id)
        append_question_id(node.get("next"))

        for condition in node.get("conditions") or []:
            for branch_question_id in condition.get("then", []):
                append_question_id(branch_question_id)
            for branch_question_id in condition.get("else", []):
                append_question_id(branch_question_id)
            append_question_id(condition.get("next_after"))

    return question_ids


def _get_follow_up_questions(node, answer_value):
    conditions = node.get("conditions") or []
    if conditions:
        branch = _resolve_condition_branch(conditions, answer_value)
        if branch is None:
            return []

        follow_up_question_ids = list(branch.get("ask", []))
        next_after = branch.get("next_after")
        if next_after and next_after != "END":
            follow_up_question_ids.append(next_after)
        return _normalize_question_list(follow_up_question_ids)

    next_question_id = node.get("next")
    if next_question_id and next_question_id != "END":
        return [next_question_id]

    return []


def _resolve_condition_branch(conditions, answer_value):
    for condition in conditions:
        condition_clause = condition.get("if")
        if condition_clause is None:
            return {
                "ask": condition.get("else", []),
                "next_after": condition.get("next_after"),
            }

        matched, deferred = _evaluate_condition(condition_clause, answer_value)
        if deferred:
            return None
        if matched:
            return {
                "ask": condition.get("then", []),
                "next_after": condition.get("next_after"),
            }

    return None


def _evaluate_condition(condition_clause, answer_value):
    if not _is_answered_value(answer_value):
        return False, True

    answer_values = answer_value if isinstance(answer_value, list) else [answer_value]
    normalized_answers = [_normalize_text(value) for value in answer_values]

    if "equals" in condition_clause:
        expected_value = _normalize_text(condition_clause["equals"])
        return expected_value in normalized_answers, False

    if "not_equals" in condition_clause:
        expected_value = _normalize_text(condition_clause["not_equals"])
        return expected_value not in normalized_answers, False

    if "any_of" in condition_clause:
        expected_values = [_normalize_text(value) for value in condition_clause["any_of"]]
        return any(value in normalized_answers for value in expected_values), False

    if "not_any_of" in condition_clause:
        expected_values = [_normalize_text(value) for value in condition_clause["not_any_of"]]
        return not any(value in normalized_answers for value in expected_values), False

    if "not_includes" in condition_clause:
        expected_value = _normalize_text(condition_clause["not_includes"])
        return not any(expected_value in answer for answer in normalized_answers), False

    return True, False


def _normalize_root_path(root_path):
    root_path = Path(root_path)
    if root_path.name == "app":
        return root_path.parent
    return root_path


def _normalize_flow_target(value):
    parsed_value = _parse_scalar(value)
    if parsed_value in (None, ""):
        return None
    if str(parsed_value).upper() == "END":
        return "END"
    return _normalize_flow_id(parsed_value)


def _normalize_flow_id(value):
    if value is None or isinstance(value, list):
        return None

    text = str(value).strip()
    if not text or text in ("[]", "[ ]"):
        return None
    if text.upper() == "END":
        return "END"
    if re.fullmatch(r"Q\d+", text, flags=re.IGNORECASE):
        return f"Q{int(text[1:])}"
    if text.isdigit():
        return f"Q{int(text)}"
    return text


def _normalize_question_list(values):
    normalized_values = []
    for value in values or []:
        if isinstance(value, list):
            nested_values = value
        else:
            nested_values = [value]

        for nested_value in nested_values:
            question_id = _normalize_flow_id(nested_value)
            if question_id and question_id not in ("END", "[END]") and question_id not in normalized_values:
                normalized_values.append(question_id)

    return normalized_values


def _normalize_text(value):
    if value is None:
        return ""
    text = str(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_scalar(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.lower() == "null":
        return None
    if text == "[]":
        return []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


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
                current_condition["else"] = []
                current_list_target = ("condition", "else")
            continue

        if current_condition is None:
            continue

        if indent == 8:
            if stripped.startswith("then:"):
                current_condition["then"] = []
                current_list_target = ("condition", "then")
                continue

            if stripped.startswith("next_after:"):
                current_condition["next_after"] = _parse_scalar(stripped.split(":", 1)[1].strip())
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
            value = _parse_scalar(stripped[2:].strip())
            if current_list_target == ("condition", "then"):
                current_condition["then"].append(value)
            elif current_list_target == ("condition", "else"):
                current_condition["else"].append(value)
            elif current_list_target and current_list_target[0] == "if":
                current_condition["if"][current_if_key].append(value)

    return data
