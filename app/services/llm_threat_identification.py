"""Template-guided local-LLM threat identification (stage 4 of the pipeline).

The deterministic engine discovers candidate risk families; this stage asks a
local LLM to decide which of those families are concrete, grounded threats for
*this* system and to describe them (status, threat pattern, evidence, affected
DFD nodes/edges, abuse path, control gap, confidence). It is deliberately
constrained:

  * PRIMARY ``identified_threats[].code`` is enum-constrained to the deterministic
    candidate codes - the model cannot invent primary risks.
  * ``affected_nodes`` / ``affected_edges`` are enum-constrained to real DFD ids.
  * It NEVER computes DREAD, assigns a final risk_level, or writes mitigations.

Anything the model wants to add beyond the deterministic set goes under
``suggested_secondary_findings`` (status ``needs_more_info``). The call is
best-effort: if the model is unavailable / unparseable the result carries
``status="unavailable"`` and the caller falls back to the deterministic baseline.
"""

import json
from pathlib import Path

from app.services.ollama_client import OllamaError, chat
from app.services.risk_catalog import all_catalog_codes
from app.services.threat_template import pattern_ids

PROMPT_FILENAME = "Threat-Identification-prompt.txt"

STATUS_VALUES = ["confirmed", "plausible", "needs_more_info", "not_applicable"]
CONFIDENCE_VALUES = ["low", "medium", "high"]

_FALLBACK_PROMPT = (
    "You identify grounded security threats for an LLM-enabled application by analyzing ONLY the "
    "candidate risks in deterministic_risks (a static mapper already chose them; you do not decide "
    "the risk universe or search freely). For each candidate risk, use the generic threat_patterns "
    "as investigation lenses, grounded in evidence, DFD nodes/edges, abuse paths, and control gaps. "
    "PRIMARY identified_threats[].code MUST be one of instructions.primary_codes_allowed; put any "
    "other idea under suggested_secondary_findings with status needs_more_info. affected_nodes/"
    "affected_edges must use ids from dfd. Do NOT compute DREAD, assign risk levels, or write "
    "mitigations. Return JSON only matching the requested schema."
)


def identify_threats(app_root_path, answers_by_flow_id, deterministic_risks, extraction_payload, dfd_graph, app_config=None, timeout=400):
    """Run template-guided threat identification. Returns a result dict (never raises)."""
    primary_codes = _unique([risk.get("code") for risk in (deterministic_risks or []) if isinstance(risk, dict)])
    if not primary_codes:
        return {
            "status": "skipped",
            "reason": "No deterministic candidate risks to identify threats for.",
            "identified_threats": [],
            "suggested_secondary_findings": [],
        }

    node_ids = _node_ids(dfd_graph)
    edge_ids = _edge_ids(dfd_graph)
    prompt = _load_prompt(app_root_path)

    user_payload = {
        "questionnaire_answers": answers_by_flow_id if isinstance(answers_by_flow_id, dict) else {},
        "deterministic_risks": _slim_risks(deterministic_risks),
        "extraction_payload": extraction_payload if isinstance(extraction_payload, dict) else {},
        "dfd": {"nodes": _slim_nodes(dfd_graph), "edges": _slim_edges(dfd_graph)},
        "threat_patterns": pattern_ids(),
        "instructions": {
            "primary_codes_allowed": primary_codes,
            "rules": [
                "identified_threats[].code MUST be one of primary_codes_allowed.",
                "Put any other risk idea under suggested_secondary_findings with status needs_more_info.",
                "affected_nodes/affected_edges MUST use ids from dfd; never invent ids.",
                "Do not compute DREAD, do not assign risk levels, do not write mitigations.",
                "Unknown-only evidence cannot be confirmed; use plausible or needs_more_info.",
            ],
        },
    }

    schema = _identification_schema(primary_codes, all_catalog_codes(), pattern_ids(), node_ids, edge_ids)

    try:
        response = chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
            ],
            app_config,
            timeout=timeout,
            response_format=schema,
            options={"temperature": 0},
        )
    except (OllamaError, ValueError) as exc:
        return {
            "status": "unavailable",
            "error": str(exc),
            "identified_threats": [],
            "suggested_secondary_findings": [],
        }

    parsed = _parse((response or {}).get("message", {}).get("content"))
    if parsed is None:
        return {
            "status": "unavailable",
            "error": "Could not parse threat-identification output.",
            "identified_threats": [],
            "suggested_secondary_findings": [],
        }

    return {
        "status": "completed",
        "model": response.get("model"),
        "identified_threats": parsed.get("identified_threats") if isinstance(parsed.get("identified_threats"), list) else [],
        "suggested_secondary_findings": parsed.get("suggested_secondary_findings") if isinstance(parsed.get("suggested_secondary_findings"), list) else [],
    }


def _identification_schema(primary_codes, secondary_codes, patterns, node_ids, edge_ids):
    node_item = {"type": "string", "enum": node_ids} if node_ids else {"type": "string"}
    edge_item = {"type": "string", "enum": edge_ids} if edge_ids else {"type": "string"}
    secondary_code = {"type": "string", "enum": secondary_codes} if secondary_codes else {"type": "string"}
    threat_item = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "enum": primary_codes},
            "name": {"type": "string"},
            "status": {"type": "string", "enum": STATUS_VALUES},
            "threat_pattern": {"type": "string", "enum": patterns},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "affected_nodes": {"type": "array", "items": node_item},
            "affected_edges": {"type": "array", "items": edge_item},
            "abuse_path": {"type": "array", "items": {"type": "string"}},
            "control_gap": {"type": "string"},
            "confidence": {"type": "string", "enum": CONFIDENCE_VALUES},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["code", "name", "status", "threat_pattern", "confidence", "evidence"],
    }
    secondary_item = {
        "type": "object",
        "properties": {
            "code": secondary_code,
            "name": {"type": "string"},
            "threat_pattern": {"type": "string", "enum": patterns},
            "status": {"type": "string", "enum": ["needs_more_info"]},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "status"],
    }
    return {
        "type": "object",
        "properties": {
            "identified_threats": {"type": "array", "items": threat_item},
            "suggested_secondary_findings": {"type": "array", "items": secondary_item},
        },
        "required": ["identified_threats"],
    }


def _slim_risks(deterministic_risks):
    slim = []
    for risk in deterministic_risks or []:
        if not isinstance(risk, dict):
            continue
        slim.append(
            {
                "code": risk.get("code"),
                "name": risk.get("name"),
                "framework": risk.get("framework"),
                "affected_assets": risk.get("affected_assets") or [],
                "missing_information": risk.get("missing_information") or [],
                "evidence": _evidence_lines(risk.get("evidence")),
            }
        )
    return slim


def _evidence_lines(evidence):
    lines = []
    if isinstance(evidence, list):
        for entry in evidence[:6]:
            if isinstance(entry, dict):
                question = str(entry.get("question") or "").strip()
                answer = entry.get("answer")
                answer_text = ", ".join(str(v) for v in answer) if isinstance(answer, list) else str(answer or "")
                line = f"{question}: {answer_text}".strip(": ").strip()
                if line:
                    lines.append(line)
            elif isinstance(entry, str) and entry.strip():
                lines.append(entry.strip())
    return lines


def _slim_nodes(dfd_graph):
    nodes = (dfd_graph or {}).get("nodes") if isinstance(dfd_graph, dict) else None
    slim = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        data = node.get("data") or {}
        slim.append({"id": node.get("id"), "label": data.get("label") or node.get("id"), "nodeType": data.get("nodeType")})
    return slim


def _slim_edges(dfd_graph):
    edges = (dfd_graph or {}).get("edges") if isinstance(dfd_graph, dict) else None
    slim = []
    for edge in edges or []:
        if not isinstance(edge, dict):
            continue
        slim.append({"id": edge.get("id"), "source": edge.get("source"), "target": edge.get("target"), "label": edge.get("label")})
    return slim


def _node_ids(dfd_graph):
    return [node["id"] for node in _slim_nodes(dfd_graph) if node.get("id")]


def _edge_ids(dfd_graph):
    return [edge["id"] for edge in _slim_edges(dfd_graph) if edge.get("id")]


def _unique(values):
    seen = set()
    result = []
    for value in values:
        text = str(value or "").strip().upper()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _load_prompt(app_root_path):
    try:
        prompt_path = Path(app_root_path).parent / "LLM-Prompts" / PROMPT_FILENAME
        text = prompt_path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except (OSError, ValueError):
        pass
    return _FALLBACK_PROMPT


def _parse(content):
    if not isinstance(content, str):
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
