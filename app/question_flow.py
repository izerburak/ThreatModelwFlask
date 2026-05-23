import json
import logging
import re
from functools import lru_cache
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


LOGGER = logging.getLogger(__name__)


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

        processing_queue = [_flow_step(start_question_id, allow_linear_next=True)]
        processed_answered_contexts = set()
        visited_question_ids = []
        pending_question_ids = []
        pending_question_id_set = set()
        max_steps = max(1000, len(self.flow_definition.get("questions") or {}) * 20)
        step_count = 0

        while processing_queue:
            step_count += 1
            if step_count > max_steps:
                LOGGER.warning("Question flow stopped after %s steps to avoid a loop.", max_steps)
                break

            flow_step = processing_queue.pop(0)
            question_id = flow_step["question_id"]
            allow_linear_next = flow_step["allow_linear_next"]

            if not question_id or question_id == "END":
                LOGGER.debug("Question flow reached END.")
                continue

            is_duplicate_visit = question_id in visited_question_ids
            if not is_duplicate_visit:
                visited_question_ids.append(question_id)

            if question_id not in answered_question_ids:
                if question_id not in pending_question_id_set:
                    pending_question_ids.append(question_id)
                    pending_question_id_set.add(question_id)
                    LOGGER.debug("Question flow pending question: %s", question_id)
                else:
                    LOGGER.debug("Question flow skipped duplicate pending question: %s", question_id)
                continue

            if is_duplicate_visit:
                LOGGER.debug("Question flow skipped already answered duplicate question: %s", question_id)

            context_key = (question_id, allow_linear_next)
            if context_key in processed_answered_contexts:
                LOGGER.debug(
                    "Question flow skipped already processed context: %s allow_linear_next=%s",
                    question_id,
                    allow_linear_next,
                )
                continue
            processed_answered_contexts.add(context_key)

            node = (self.flow_definition.get("questions") or {}).get(question_id, {})
            answer_value = normalized_answers.get(question_id)
            follow_up_steps = _get_follow_up_steps(node, answer_value, allow_linear_next, question_id)

            for follow_up_step in reversed(follow_up_steps):
                processing_queue.insert(0, follow_up_step)

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
    for source_question in all_questions:
        flow_question_id = _normalize_flow_id(source_question.get("id"))
        if not flow_question_id:
            continue
        question_catalog[flow_question_id] = _question_record(flow_question_id, source_question, questions_path)

    for flow_question_id in flow_question_ids:
        if flow_question_id in question_catalog:
            continue

        source_question = next(
            (
                question
                for question in all_questions
                if str(question.get("id")) == flow_question_id[1:] or str(question.get("id")) == flow_question_id
            ),
            None,
        )
        if source_question is not None:
            question_catalog[flow_question_id] = _question_record(flow_question_id, source_question, questions_path)

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
                    "if": _normalize_condition(_condition_value(raw_condition, "if")),
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


def _condition_value(raw_condition, key):
    if not isinstance(raw_condition, dict):
        return None
    if key in raw_condition:
        return raw_condition.get(key)
    if key == "if":
        return raw_condition.get(True)
    return None


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


def _question_record(flow_question_id, source_question, questions_path):
    record = {
        "flow_id": flow_question_id,
        "id": str(source_question.get("id", flow_question_id)),
        "source_id": str(source_question.get("id", flow_question_id)),
        "layer": source_question.get("layer", 1),
        "text": source_question.get("text", flow_question_id),
        "type": source_question.get("type", "single"),
        "options": list(source_question.get("options", [])),
        "source_file": questions_path.name,
    }
    for key, value in source_question.items():
        if key not in record:
            record[key] = value
    return record


def _get_follow_up_questions(node, answer_value):
    return [
        step["question_id"]
        for step in _get_follow_up_steps(node, answer_value, allow_linear_next=True)
    ]


def _get_follow_up_steps(node, answer_value, allow_linear_next=True, question_id=None):
    conditions = node.get("conditions") or []
    if conditions:
        branch = _resolve_condition_branch(conditions, answer_value, question_id)
        if branch is None:
            return []

        follow_up_steps = [
            _flow_step(branch_question_id, allow_linear_next=False)
            for branch_question_id in branch.get("ask", [])
        ]
        next_after = branch.get("next_after")
        if next_after and next_after != "END":
            follow_up_steps.append(_flow_step(next_after, allow_linear_next=True))
        elif next_after == "END":
            LOGGER.debug("Question flow selected next_after END for %s.", question_id or "unknown question")
        return _dedupe_steps(follow_up_steps)

    next_question_id = node.get("next")
    if allow_linear_next and next_question_id and next_question_id != "END":
        return [_flow_step(next_question_id, allow_linear_next=True)]
    if allow_linear_next and next_question_id == "END":
        LOGGER.debug("Question flow reached END after %s.", question_id or "unknown question")
    elif not allow_linear_next and next_question_id:
        LOGGER.debug(
            "Question flow suppressed branch item's linear next from %s to %s.",
            question_id or "unknown question",
            next_question_id,
        )

    return []


def _resolve_condition_branch(conditions, answer_value, question_id=None):
    for index, condition in enumerate(conditions):
        condition_clause = condition.get("if")
        if condition_clause is None:
            LOGGER.debug(
                "Question flow matched else for %s; queued then questions=%s; next_after=%s.",
                question_id or "unknown question",
                condition.get("else", []),
                condition.get("next_after"),
            )
            return {
                "ask": condition.get("else", []),
                "next_after": condition.get("next_after"),
            }

        matched, deferred = _evaluate_condition(condition_clause, answer_value)
        if deferred:
            return None
        if matched:
            LOGGER.debug(
                "Question flow matched condition %s for %s; queued then questions=%s; next_after=%s.",
                index,
                question_id or "unknown question",
                condition.get("then", []),
                condition.get("next_after"),
            )
            return {
                "ask": condition.get("then", []),
                "next_after": condition.get("next_after"),
            }

    return None


def _evaluate_condition(condition_clause, answer_value):
    if not _is_answered_value(answer_value):
        return False, True

    if "equals" in condition_clause:
        return _answers_equal(answer_value, condition_clause["equals"]), False

    if "not_equals" in condition_clause:
        return not _answers_equal(answer_value, condition_clause["not_equals"]), False

    if "any_of" in condition_clause:
        normalized_answers = [_normalize_text(value) for value in _answer_values(answer_value)]
        expected_values = [_normalize_text(value) for value in condition_clause["any_of"]]
        return any(value in normalized_answers for value in expected_values), False

    if "not_any_of" in condition_clause:
        normalized_answers = [_normalize_text(value) for value in _answer_values(answer_value)]
        expected_values = [_normalize_text(value) for value in condition_clause["not_any_of"]]
        return not any(value in normalized_answers for value in expected_values), False

    if "not_includes" in condition_clause:
        expected_value = _normalize_text(condition_clause["not_includes"])
        return not any(expected_value == answer or expected_value in answer for answer in _normalized_answer_values(answer_value)), False

    return True, False


def _flow_step(question_id, allow_linear_next=True):
    return {
        "question_id": _normalize_flow_target(question_id),
        "allow_linear_next": bool(allow_linear_next),
    }


def _dedupe_steps(steps):
    deduped_steps = []
    seen = set()
    for step in steps:
        key = (step.get("question_id"), step.get("allow_linear_next"))
        if step.get("question_id") and key not in seen:
            deduped_steps.append(step)
            seen.add(key)
    return deduped_steps


def _answer_values(answer_value):
    return answer_value if isinstance(answer_value, list) else [answer_value]


def _normalized_answer_values(answer_value):
    return [_normalize_text(value) for value in _answer_values(answer_value)]


def _answers_equal(answer_value, expected_value):
    if isinstance(answer_value, list) or isinstance(expected_value, list):
        if not isinstance(answer_value, list) or not isinstance(expected_value, list):
            return False
        return [_normalize_text(value) for value in answer_value] == [
            _normalize_text(value) for value in expected_value
        ]
    return _normalize_text(answer_value) == _normalize_text(expected_value)


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

        if indent >= 8:
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
