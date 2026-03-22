import json
import re
from functools import lru_cache
from pathlib import Path


FLOW_ORDER = [
    "Q1",
    "Q2",
    "Q3",
    "Q31",
    "Q4",
    "Q5",
    "Q6",
    "Q7",
    "Q8",
    "Q9",
    "Q10",
    "Q11",
    "Q12",
    "Q13",
    "Q14",
    "Q15",
    "Q16",
    "Q17",
    "Q18",
    "Q19",
    "Q20",
    "Q21",
    "Q22",
    "Q23",
    "Q24",
    "Q25",
    "Q26",
    "Q27",
    "Q28",
    "Q29",
    "Q30",
    "Q32",
    "Q33",
]


FLOW_TEXT_ALIASES = {
    "Q15": ["Does the system use multiple LLM models for different tasks?"],
    "Q32": ["Which misuse scenarios are most plausible for this LLM deployment?"],
    "Q33": ["What operational weaknesses could increase LLM-related security risks?"],
}


def load_questions(root_path):
    """Load the adaptive questionnaire catalog keyed by QaT flow IDs.

    `questionsDb.json` remains the primary metadata source. When a QaT node is
    not present there, the legacy layer files are used as a backward-conscious
    fallback so the thesis flow remains complete and easy to evolve.
    """
    return _load_questions_cached(str(Path(root_path)))


@lru_cache(maxsize=4)
def _load_questions_cached(root_path_str):
    root_path = Path(root_path_str)
    branch_reference = _load_branch_reference(root_path)
    primary_questions = _read_question_file(root_path / "questions" / "questionsDb.json")
    legacy_questions = _read_question_file(root_path / "questions" / "layer1.json")
    legacy_questions.extend(_read_question_file(root_path / "questions" / "layer2.json"))

    primary_by_text = _index_questions_by_text(primary_questions)
    legacy_by_text = _index_questions_by_text(legacy_questions)

    flow_questions = {}

    for flow_id in FLOW_ORDER:
        reference_text = branch_reference.get(flow_id)
        candidates = [reference_text] if reference_text else []
        candidates.extend(FLOW_TEXT_ALIASES.get(flow_id, []))

        source_question = _find_question(primary_by_text, candidates)
        source_name = "questionsDb.json"

        if source_question is None:
            source_question = _find_question(legacy_by_text, candidates)
            source_name = "legacy layer fallback"

        if source_question is None:
            raise KeyError(f"Unable to resolve {flow_id} from QaT.txt into a question definition.")

        flow_questions[flow_id] = {
            "flow_id": flow_id,
            "id": str(source_question.get("id", flow_id)),
            "source_id": str(source_question.get("id", flow_id)),
            "layer": source_question.get("layer", _infer_layer(flow_id)),
            "text": source_question.get("text", reference_text or flow_id),
            "type": source_question.get("type", "single"),
            "options": list(source_question.get("options", [])),
            "source_file": source_name,
            "branch_text": reference_text or source_question.get("text", flow_id),
        }

    return flow_questions


def get_question_by_id(root_path, question_id):
    return load_questions(root_path).get(question_id)


def get_next_question(current_question_id, answers):
    if current_question_id not in FLOW_ORDER:
        return FLOW_ORDER[0]

    current_index = FLOW_ORDER.index(current_question_id)
    for next_question_id in FLOW_ORDER[current_index + 1:]:
        if not should_skip_question(next_question_id, answers):
            return next_question_id
    return None


def should_skip_question(question_id, answers):
    if question_id == "Q31":
        return not _has_public_or_external_users(answers)
    if question_id == "Q8":
        return not _has_untrusted_content(answers)
    if question_id in {"Q10", "Q11"}:
        return not _uses_rag(answers)
    if question_id == "Q13":
        return not _has_persistent_or_shared_memory(answers)
    if question_id == "Q15":
        return not _has_orchestration_layer(answers)
    if question_id in {"Q20", "Q21", "Q22", "Q23"}:
        return (not _has_tool_access(answers)) or (not _has_action_capability(answers))
    if question_id in {"Q17", "Q18", "Q19"}:
        return not _has_tool_access(answers)
    return False


def get_first_question_id():
    return FLOW_ORDER[0]


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


def _load_branch_reference(root_path):
    qat_path = Path(root_path) / "QaT.txt"
    reference = {}

    for line in qat_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.search(r"Q(\d+)\.\s*(.+)", line)
        if not match:
            continue
        question_id = f"Q{match.group(1)}"
        reference.setdefault(question_id, match.group(2).strip())

    return reference


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


def _index_questions_by_text(questions):
    index = {}
    for question in questions:
        text_key = _normalize_text(question.get("text", ""))
        if text_key:
            index[text_key] = question
    return index


def _find_question(index, candidate_texts):
    for text in candidate_texts:
        normalized_text = _normalize_text(text)
        if normalized_text in index:
            return index[normalized_text]
    return None


def _normalize_text(value):
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _infer_layer(flow_id):
    numeric_id = int(flow_id[1:])
    return 1 if numeric_id <= 16 else 2


def _answers_as_list(answers, question_id):
    value = answers.get(question_id)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _has_public_or_external_users(answers):
    selected = {_normalize_text(value) for value in _answers_as_list(answers, "Q2")}
    return bool(
        selected.intersection(
            {
                _normalize_text("Anonymous public internet users"),
                _normalize_text("Authenticated public users"),
            }
        )
    )


def _has_untrusted_content(answers):
    selected = {_normalize_text(value) for value in _answers_as_list(answers, "Q6")}
    return bool(selected) and _normalize_text("No untrusted external content") not in selected


def _uses_rag(answers):
    input_sources = {_normalize_text(value) for value in _answers_as_list(answers, "Q5")}
    rag_sources = {_normalize_text(value) for value in _answers_as_list(answers, "Q9")}

    if _normalize_text("Retrieved documents (RAG)") in input_sources:
        return True

    return bool(rag_sources) and _normalize_text("No retrieval or RAG is used") not in rag_sources


def _has_persistent_or_shared_memory(answers):
    selected = {_normalize_text(value) for value in _answers_as_list(answers, "Q12")}
    return bool(
        selected.intersection(
            {
                _normalize_text("Persistent user conversation history"),
                _normalize_text("Shared organizational knowledge memory"),
                _normalize_text("Vector memory storage"),
            }
        )
    )


def _has_orchestration_layer(answers):
    selected = {_normalize_text(value) for value in _answers_as_list(answers, "Q14")}
    return bool(
        selected.intersection(
            {
                _normalize_text("Prompt orchestration framework"),
                _normalize_text("Agent-based orchestration"),
                _normalize_text("Multi-model routing system"),
                _normalize_text("Prompt orchestration framework (LangChain, etc.)"),
            }
        )
    )


def _has_tool_access(answers):
    selected = {_normalize_text(value) for value in _answers_as_list(answers, "Q16")}
    if not selected:
        return False
    return _normalize_text("No system access") not in selected


def _has_action_capability(answers):
    selected = {_normalize_text(value) for value in _answers_as_list(answers, "Q19")}
    if not selected:
        return False
    return not selected.intersection(
        {
            _normalize_text("No actions (advisory only responses)"),
            _normalize_text("No direct actions (advisory only)"),
        }
    )
