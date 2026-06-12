"""Optional, constrained local-LLM reasoning layer over the deterministic risk list.

The deterministic engine (`risk_analysis_service`) produces the canonical risk set, scores,
and baseline levels. This layer asks a local LLM to *review* those candidates only — it cannot
invent new risks because the output `code` field is constrained (via Ollama structured outputs)
to the closed set of deterministic candidate codes. Every assessment is grounded in the supplied
answers/evidence. The deterministic `risk_level` always remains the baseline; the LLM result is
attached as an advisory `llm_assessment` overlay. The layer is best-effort: if the model is
unavailable or returns nothing usable, the risk analysis is returned unchanged with a status note.
"""

import json

from app.services.ollama_client import OllamaError, chat


RISK_LEVELS = ["Low", "Medium", "High", "Critical"]

_SYSTEM_PROMPT = (
    "You are a security reviewer refining a deterministic threat-model risk list for an "
    "LLM-enabled application.\n"
    "You receive the questionnaire answers and a FIXED set of candidate risks that a deterministic "
    "engine already mapped from those answers (each with a baseline level and supporting evidence).\n"
    "For EACH candidate risk you must:\n"
    "- decide whether it genuinely applies given the answers (applies: true/false);\n"
    "- assign a calibrated assessed_level (Low/Medium/High/Critical) using impact x likelihood "
    "reasoning;\n"
    "- give a short rationale grounded ONLY in the provided answers/evidence;\n"
    "- optionally set priority (P1/P2/P3);\n"
    "- propose 1-3 CONTEXT-SPECIFIC mitigations grounded in the provided answers (not generic "
    "boilerplate): each with a short title, a concrete action that references the system's actual "
    "components/answers, and a priority (High/Medium/Low).\n"
    "Hard rules: do NOT invent new risks or codes — only assess the codes provided; do NOT add "
    "facts beyond the provided answers. Return JSON only, matching the requested schema."
)


def review_risk_analysis(risk_analysis, answers_by_flow_id, app_config=None, timeout=120):
    """Augment a deterministic risk-analysis dict with advisory LLM assessments (best-effort)."""
    if not isinstance(risk_analysis, dict):
        return risk_analysis

    candidates = _candidate_risks(risk_analysis)
    if not candidates:
        risk_analysis["llm_review"] = {
            "status": "skipped",
            "reason": "No deterministic candidate risks to review.",
        }
        return risk_analysis

    codes = [candidate["code"] for candidate in candidates]
    user_payload = {
        "answers_by_flow_id": answers_by_flow_id if isinstance(answers_by_flow_id, dict) else {},
        "candidate_risks": candidates,
    }

    try:
        response = chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
            ],
            app_config,
            timeout=timeout,
            response_format=_review_schema(codes),
            options={"temperature": 0},
        )
    except (OllamaError, ValueError) as exc:
        risk_analysis["llm_review"] = {"status": "unavailable", "error": str(exc)}
        return risk_analysis

    assessments = _parse_assessments((response or {}).get("message", {}).get("content"))
    if assessments is None:
        risk_analysis["llm_review"] = {
            "status": "unavailable",
            "error": "Could not parse LLM review output.",
        }
        return risk_analysis

    allowed = set(codes)
    by_code = {}
    for item in assessments:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().upper()
        # Closed-set guardrail: ignore anything outside the deterministic candidate codes.
        if code not in allowed or code in by_code:
            continue
        level = item.get("assessed_level")
        by_code[code] = {
            "applies": bool(item.get("applies", True)),
            "assessed_level": level if level in RISK_LEVELS else None,
            "rationale": str(item.get("rationale") or "").strip(),
            "priority": item.get("priority") if item.get("priority") in ("P1", "P2", "P3") else None,
            "mitigations": _clean_mitigations(item.get("mitigations")),
        }

    applied = 0
    for risk in risk_analysis.get("unified_risks", []):
        if not isinstance(risk, dict):
            continue
        assessment = by_code.get(str(risk.get("code") or "").strip().upper())
        if assessment:
            risk["llm_assessment"] = assessment
            applied += 1

    risk_analysis["llm_review"] = {
        "status": "completed",
        "model": response.get("model"),
        "candidates_reviewed": len(codes),
        "assessments_applied": applied,
        "note": "LLM assessments are advisory; the deterministic risk_level remains the baseline.",
    }
    return risk_analysis


def _candidate_risks(risk_analysis):
    unified = risk_analysis.get("unified_risks")
    source = unified if isinstance(unified, list) else risk_analysis.get("mapped_risks")
    candidates = []
    seen = set()
    for risk in source or []:
        if not isinstance(risk, dict):
            continue
        code = str(risk.get("code") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        candidates.append(
            {
                "code": code,
                "name": risk.get("name") or code,
                "baseline_level": risk.get("risk_level") or "Medium",
                "evidence": _evidence_summary(risk),
            }
        )
    return candidates


def _evidence_summary(risk):
    items = []
    evidence = risk.get("question_evidence") or risk.get("evidence") or []
    if isinstance(evidence, list):
        for entry in evidence[:6]:
            if isinstance(entry, dict):
                question = str(entry.get("question") or "").strip()
                answer = _answer_text(entry.get("answer"))
                line = f"{question}: {answer}".strip(": ").strip()
                if line:
                    items.append(line)
            elif isinstance(entry, str) and entry.strip():
                items.append(entry.strip())
    return items


def _answer_text(answer):
    if isinstance(answer, list):
        return ", ".join(str(value) for value in answer if str(value).strip())
    return str(answer or "").strip()


def _review_schema(codes):
    return {
        "type": "object",
        "properties": {
            "assessments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "enum": codes},
                        "applies": {"type": "boolean"},
                        "assessed_level": {"type": "string", "enum": RISK_LEVELS},
                        "rationale": {"type": "string"},
                        "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                        "mitigations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "action": {"type": "string"},
                                    "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
                                    "owner_hint": {"type": "string"},
                                    "verification": {"type": "string"},
                                },
                                "required": ["title", "action"],
                            },
                        },
                    },
                    "required": ["code", "applies", "assessed_level", "rationale", "mitigations"],
                },
            }
        },
        "required": ["assessments"],
    }


def _clean_mitigations(mitigations):
    if not isinstance(mitigations, list):
        return []
    cleaned = []
    for item in mitigations[:4]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        action = str(item.get("action") or "").strip()
        if not title and not action:
            continue
        cleaned.append(
            {
                "title": title or action[:60],
                "action": action,
                "priority": item.get("priority") if item.get("priority") in ("High", "Medium", "Low") else None,
                "owner_hint": str(item.get("owner_hint") or "").strip() or None,
                "verification": str(item.get("verification") or "").strip() or None,
            }
        )
    return cleaned


def _parse_assessments(content):
    if not isinstance(content, str):
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and isinstance(data.get("assessments"), list):
        return data["assessments"]
    if isinstance(data, list):
        return data
    return None
