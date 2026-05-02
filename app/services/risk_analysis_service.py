import json
import re
from collections import defaultdict
from pathlib import Path


OWASP_LLM_2025 = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM03": "Supply Chain",
    "LLM04": "Data and Model Poisoning",
    "LLM05": "Improper Output Handling",
    "LLM06": "Excessive Agency",
    "LLM07": "System Prompt Leakage",
    "LLM08": "Vector and Embedding Weaknesses",
    "LLM09": "Misinformation",
    "LLM10": "Unbounded Consumption",
}

RISK_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}


def build_risk_analysis(app_root_path, response_payload, extract_payload=None):
    questions = _load_questions(app_root_path)
    answers = _answers_by_flow_id(response_payload)
    extract_payload = extract_payload if isinstance(extract_payload, dict) else {}

    mapped_risks = _mapped_question_risks(questions, answers)
    extract_risks = _extract_risks(extract_payload)
    status = _overall_status(extract_payload, mapped_risks, extract_risks)

    return {
        "overall_status": status,
        "status_source": "LLM extract" if _normalize_level(extract_payload.get("overall_posture")) else "Question mapping",
        "mapped_risks": mapped_risks,
        "extract_risks": extract_risks,
        "quick_wins": _string_list(extract_payload.get("quick_wins")),
        "answers_analyzed": len(answers),
    }


def suggested_extract_filename(response_file):
    stem = Path(str(response_file)).stem
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", stem).strip("-._")
    return f"{safe_stem}-extract.json" if safe_stem else ""


def _mapped_question_risks(questions, answers):
    grouped = defaultdict(lambda: {"score": 0, "severity": 0, "confidence": 0, "evidence": []})

    for flow_id, answer in answers.items():
        question = questions.get(_question_number(flow_id))
        if not question:
            continue

        codes = question.get("owasp_llm") or []
        if not codes:
            continue

        severity = _int_value(question.get("severity_weight"))
        confidence = _int_value(question.get("confidence_weight"))
        score = severity * confidence
        evidence = {
            "question": _question_label(flow_id),
            "text": question.get("text", ""),
            "answer": answer,
            "severity_weight": severity,
            "confidence_weight": confidence,
        }

        for code in codes:
            if code not in OWASP_LLM_2025:
                continue
            bucket = grouped[code]
            bucket["score"] += score
            bucket["severity"] = max(bucket["severity"], severity)
            bucket["confidence"] = max(bucket["confidence"], confidence)
            bucket["evidence"].append(evidence)

    risks = []
    for code, bucket in grouped.items():
        risks.append(
            {
                "code": code,
                "name": OWASP_LLM_2025[code],
                "risk_level": _level_from_weights(bucket["severity"], bucket["score"]),
                "score": bucket["score"],
                "evidence": bucket["evidence"],
            }
        )

    return sorted(risks, key=lambda item: (-RISK_RANK.get(item["risk_level"], 0), -item["score"], item["code"]))


def _extract_risks(extract_payload):
    top_risks = extract_payload.get("top_risks")
    if not isinstance(top_risks, list):
        return []

    risks = []
    for risk in top_risks:
        if not isinstance(risk, dict):
            continue

        code = str(risk.get("code") or "").strip().upper()
        if code not in OWASP_LLM_2025:
            continue

        risks.append(
            {
                "code": code,
                "name": str(risk.get("name") or OWASP_LLM_2025[code]).strip(),
                "risk_level": _normalize_level(risk.get("risk_level")) or "Medium",
                "why": str(risk.get("why") or "").strip(),
                "evidence": _string_list(risk.get("evidence")),
                "mitigation": str(risk.get("mitigation") or "").strip(),
            }
        )

    return sorted(risks, key=lambda item: (-RISK_RANK.get(item["risk_level"], 0), item["code"]))


def _overall_status(extract_payload, mapped_risks, extract_risks):
    extract_status = _normalize_level(extract_payload.get("overall_posture"))
    if extract_status:
        return extract_status

    levels = [risk.get("risk_level") for risk in mapped_risks + extract_risks]
    ranked = [level for level in levels if level in RISK_RANK]
    if not ranked:
        return "Low"
    return max(ranked, key=lambda level: RISK_RANK[level])


def _level_from_weights(severity, score):
    if severity >= 5 and score >= 50:
        return "Critical"
    if severity >= 5 or score >= 35:
        return "High"
    if severity >= 3 or score >= 15:
        return "Medium"
    return "Low"


def _load_questions(app_root_path):
    questions_path = Path(app_root_path) / "questions" / "questionsDb.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    return {
        int(question["id"]): question
        for question in questions
        if isinstance(question, dict) and str(question.get("id", "")).isdigit()
    }


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


def _question_number(flow_id):
    match = re.search(r"(\d+)", str(flow_id))
    return int(match.group(1)) if match else None


def _question_label(flow_id):
    number = _question_number(flow_id)
    return f"Q{number}" if number is not None else str(flow_id)


def _normalize_level(value):
    text = str(value or "").strip().lower()
    levels = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "med": "Medium",
        "low": "Low",
    }
    return levels.get(text)


def _string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _int_value(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
