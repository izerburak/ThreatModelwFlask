import json
import re
from functools import lru_cache
from pathlib import Path


def load_questions(root_path):
    """Load the questionnaire catalog from questionsDb.json keyed by flow IDs."""
    return _load_questions_cached(str(Path(root_path)))


@lru_cache(maxsize=4)
def _load_questions_cached(root_path_str):
    root_path = Path(root_path_str)
    primary_questions = _read_question_file(root_path / "questions" / "questionsDb.json")
    
    # We will also parse QaT.txt to get the flow order
    qat_tree = _load_qat_tree(root_path)

    flow_questions = {}
    for node in qat_tree:
        if node['type'] == 'question':
            flow_id = node['id']
            source_question = next((q for q in primary_questions if q.get("id") == int(flow_id[1:]) or q.get("id") == flow_id), None)
            
            if source_question is None:
                # Fallback matching by text if ID doesn't directly map (though in this dataset they do)
                pass

            if source_question:
                flow_questions[flow_id] = {
                    "flow_id": flow_id,
                    "id": str(source_question.get("id", flow_id)),
                    "source_id": str(source_question.get("id", flow_id)),
                    "layer": source_question.get("layer", 1),
                    "text": source_question.get("text", node.get("content", flow_id)),
                    "type": source_question.get("type", "single"),
                    "options": list(source_question.get("options", [])),
                    "source_file": "questionsDb.json",
                    "branch_text": node.get("content", flow_id),
                }

    return flow_questions


@lru_cache(maxsize=4)
def _load_qat_tree(root_path=None):
    if root_path is None:
        # Fallback to relative path if not provided
        root_path = Path(__file__).parent.parent.parent
    else:
        root_path = Path(root_path)
        # Handle case where root_path is 'app'
        if root_path.name == "app":
            root_path = root_path.parent

    qat_path = root_path / "TM-Questions" / "QaT.txt"
    if not qat_path.exists():
        qat_path = root_path / "QaT.txt"
        
    lines = qat_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    tree = []
    
    current_condition = None  # None, or {'cond': str, 'is_else': bool}
    
    for line in lines:
        if not line.strip() or '[START]' in line or '[END]' in line:
            if not line.strip():
                # Empty line means we converge and exit any if/else block
                current_condition = None
            continue
        
        text = line.strip().lstrip('├─└│ ')

        if text.startswith('Q') and '. ' in text:
            qid = text.split('. ')[0]
            node = {'type': 'question', 'id': qid, 'content': text.split('. ', 1)[1]}
            if current_condition:
                node['condition'] = current_condition['cond']
                node['is_else'] = current_condition['is_else']
            tree.append(node)
            
        elif text.startswith('If '):
            cond = text[3:].strip(':')
            current_condition = {'cond': cond, 'is_else': False}
            tree.append({'type': 'condition_def', 'condition': cond})
            
        elif text.startswith('Else:'):
            if current_condition is not None:
                current_condition = {'cond': current_condition['cond'], 'is_else': True}
            else:
                current_condition = {'cond': 'Unknown', 'is_else': True}

    return tree

def get_next_question(current_question_id, answers, root_path=None):
    qat_tree = _load_qat_tree(root_path)
    
    if current_question_id is None:
        for node in qat_tree:
            if node['type'] == 'question':
                return node['id']
        return None
        
    last_unconditional_qid = None
    last_if_result = False
    last_node_seen = None
    
    # Simulate traversal from the start to find what logically comes AFTER current_question_id
    # We must traverse the tree and ONLY yield nodes that evaluate to TRUE.
    # We record all TRUE nodes in a list, then find current_question_id, and return the one after it.
    
    valid_path = []
    
    for node in qat_tree:
        if node['type'] == 'question':
            if 'condition' not in node:
                last_unconditional_qid = node['id']
                valid_path.append(node['id'])
            else:
                if node['is_else']:
                    res = not last_if_result
                else:
                    res = evaluate_condition(node['condition'], last_unconditional_qid, answers)
                
                if res:
                    valid_path.append(node['id'])
                    
        elif node['type'] == 'condition_def':
            last_if_result = evaluate_condition(node['condition'], last_unconditional_qid, answers)

    # Now valid_path contains the exact sequence of questions the user SHOULD see
    # given their current answers.
    try:
        idx = valid_path.index(current_question_id)
        if idx + 1 < len(valid_path):
            return valid_path[idx + 1]
    except ValueError:
        pass
        
    return None


def get_question_by_id(root_path, question_id):
    return load_questions(root_path).get(question_id)


def evaluate_condition(condition_text, qid, answers):
    ans = answers.get(qid)
    if not ans:
        ans = []
    elif not isinstance(ans, list):
        ans = [ans]
    ans_lower = [_normalize_text(a) for a in ans]
    cond = condition_text.lower()
    
    if qid == "Q2":
        if "anonymous" in cond or "authenticated" in cond:
            return any("anonymous" in a or "authenticated" in a for a in ans_lower)
    elif qid == "Q4":
        if "yes" in cond: return "yes" in ans_lower
        if "no" in cond or "unknown" in cond: return "no" in ans_lower or "unknown" in ans_lower
    elif qid == "Q6":
        if "untrusted" in cond:
            return bool(ans_lower) and not all("no untrusted" in a or "none" in a for a in ans_lower)
    elif qid == "Q8":
        if "rag/retrieval" in cond:
            return bool(ans_lower) and not all("no rag" in a for a in ans_lower)
        if "no retrieval" in cond:
            return not ans_lower or any("no rag" in a for a in ans_lower)
    elif qid == "Q10":
        if "session" in cond:
            return any("session" in a or "per user" in a or "global" in a for a in ans_lower)
        if "no persistent" in cond:
            return not ans_lower or any("no" in a or "unknown" in a for a in ans_lower)
    elif qid == "Q11":
        if "orchestration" in cond:
            return bool(ans_lower) and not all("none" in a or "unknown" in a for a in ans_lower)
    elif qid == "Q12":
        if "no tool access" in cond:
            return "none" in ans_lower
    elif qid == "Q15":
        if "generate text responses only" in cond:
            return "generate text responses only" in ans_lower and len(ans_lower) == 1
        if "action beyond text" in cond:
            return bool(ans_lower) and not ("generate text responses only" in ans_lower and len(ans_lower) == 1)
    elif qid == "Q22":
        if "shown to users" in cond:
            return any("user facing" in a or "downstream" in a or "api response" in a for a in ans_lower)
            
    return True 





def get_first_question_id():
    qat_tree = _load_qat_tree()
    for node in qat_tree:
        if node['type'] == 'question':
            return node['id']
    return None


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
