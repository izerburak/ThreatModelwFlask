"""Local-LLM mitigation generation (stage 7 of the pipeline).

Runs only AFTER threats are identified, grounding-validated, and DREAD-scored. It
receives the validated + scored threats and asks a local LLM to propose concrete,
verifiable mitigations for them. It is constrained so the model cannot distort the
risk model:

  * ``mitigations[].risk_code`` is enum-constrained to the supplied scored codes -
    the model cannot add new risks.
  * It never changes risk codes, DREAD scores, or risk levels (read-only context).
  * Each mitigation must map to evidence or a control gap from its threat;
    mitigations that don't are backfilled from the threat's control_gap or dropped.

Best-effort: if the model is unavailable / unparseable, returns a result with an
empty ``mitigations`` list and a status note. A valid risks.json is still produced.
"""

import json
from pathlib import Path

from app.services.feature_flags import config_int
from app.services.ollama_client import OllamaError, chat

PROMPT_FILENAME = "Mitigation-Generation-prompt.txt"
PRIORITIES = ["Low", "Medium", "High", "Critical"]

_FALLBACK_PROMPT = (
    "You write concrete mitigations for already-validated, already-scored threats. "
    "mitigations[].risk_code MUST be one of the supplied threats' risk codes; never add "
    "new risks or codes. Do not change DREAD scores or risk levels. Every mitigation must "
    "map to evidence or a control_gap (put them in maps_to_evidence). Return JSON only "
    "matching the requested schema."
)


def generate_mitigations(app_root_path, scored_threats, answers_by_flow_id, dfd_graph, app_config=None, timeout=400):
    """Generate mitigations for the validated, DREAD-scored threats (best-effort).

    Threats are processed in small batches (``LLM_MITIGATION_BATCH_SIZE``, default 3)
    instead of one big call: a single all-threats request makes the local model emit
    a large schema-constrained payload that can exceed the request timeout. Batching
    keeps each call bounded and degrades gracefully - if one batch fails the others
    still yield mitigations (status ``partial``).
    """
    threats = [t for t in (scored_threats or []) if isinstance(t, dict) and str(t.get("code") or "").strip()]
    if not threats:
        return _empty("skipped")

    prompt = _load_prompt(app_root_path)
    slim_nodes = _slim_nodes(dfd_graph)
    batch_size = max(1, config_int(app_config, "LLM_MITIGATION_BATCH_SIZE", 3))

    mitigations = []
    quick_wins, assumptions, missing = [], [], []
    model = None
    batch_count = ok_count = 0
    last_error = None

    for batch in _chunk(threats, batch_size):
        batch_count += 1
        outcome = _run_batch(prompt, batch, slim_nodes, app_config, timeout)
        if outcome.get("error"):
            last_error = outcome["error"]
            continue
        ok_count += 1
        model = model or outcome.get("model")
        mitigations.extend(outcome.get("mitigations") or [])
        quick_wins.extend(outcome.get("quick_wins") or [])
        assumptions.extend(outcome.get("assumptions") or [])
        missing.extend(outcome.get("missing_information") or [])

    if ok_count == 0:
        result = _empty("unavailable")
        result["error"] = last_error or "Could not parse mitigation output."
        return result

    result = {
        "status": "completed" if ok_count == batch_count else "partial",
        "model": model,
        "mitigations": mitigations,
        "quick_wins": _dedupe(quick_wins),
        "assumptions": _dedupe(assumptions),
        "missing_information": _dedupe(missing),
    }
    if result["status"] == "partial":
        result["error"] = last_error
    return result


def _run_batch(prompt, batch_threats, slim_nodes, app_config, timeout):
    """Run one mitigation chat call for a small batch of threats (best-effort).

    Returns ``{"error": ...}`` on failure; otherwise the parsed, guardrailed
    mitigations and side lists for that batch.
    """
    codes = _unique([threat.get("code") for threat in batch_threats])
    user_payload = {
        "threats": _slim_threats(batch_threats),
        "dfd": {"nodes": slim_nodes},
    }
    schema = _mitigation_schema(codes)

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
        return {"error": str(exc)}

    parsed = _parse((response or {}).get("message", {}).get("content"))
    if parsed is None:
        return {"error": "Could not parse mitigation output."}

    control_gaps = {threat.get("code"): str(threat.get("control_gap") or "").strip() for threat in batch_threats if isinstance(threat, dict)}
    allowed = set(codes)
    mitigations = []
    for item in parsed.get("mitigations") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("risk_code") or "").strip().upper()
        # Closed-set guardrail: never let a mitigation introduce a new risk code.
        if code not in allowed:
            continue
        action = str(item.get("action") or "").strip()
        title = str(item.get("title") or "").strip()
        if not action and not title:
            continue
        maps_to = [str(value).strip() for value in (item.get("maps_to_evidence") or []) if str(value).strip()]
        # Rule: every mitigation must map to evidence or a control_gap.
        if not maps_to and control_gaps.get(code):
            maps_to = [control_gaps[code]]
        if not maps_to:
            continue
        mitigations.append(
            {
                "risk_code": code,
                "title": title or action[:60],
                "action": action,
                "priority": item.get("priority") if item.get("priority") in PRIORITIES else None,
                "target_component": str(item.get("target_component") or "").strip(),
                "validation_step": str(item.get("validation_step") or "").strip(),
                "maps_to_evidence": maps_to,
            }
        )

    return {
        "model": response.get("model"),
        "mitigations": mitigations,
        "quick_wins": _string_list(parsed.get("quick_wins")),
        "assumptions": _string_list(parsed.get("assumptions")),
        "missing_information": _string_list(parsed.get("missing_information")),
    }


def _mitigation_schema(codes):
    return {
        "type": "object",
        "properties": {
            "mitigations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "risk_code": {"type": "string", "enum": codes},
                        "title": {"type": "string"},
                        "action": {"type": "string"},
                        "priority": {"type": "string", "enum": PRIORITIES},
                        "target_component": {"type": "string"},
                        "validation_step": {"type": "string"},
                        "maps_to_evidence": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["risk_code", "title", "action"],
                },
            },
            "quick_wins": {"type": "array", "items": {"type": "string"}},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["mitigations"],
    }


def _slim_threats(scored_threats):
    slim = []
    for threat in scored_threats or []:
        if not isinstance(threat, dict):
            continue
        dread = threat.get("dread") if isinstance(threat.get("dread"), dict) else {}
        slim.append(
            {
                "risk_code": threat.get("code"),
                "name": threat.get("name"),
                "risk_level": threat.get("risk_level"),
                "status": threat.get("status"),
                "dread": {"total": dread.get("total"), "average": dread.get("average"), "band": dread.get("band")},
                "control_gap": threat.get("control_gap"),
                "affected_components": threat.get("affected_assets") or [],
                "affected_nodes": threat.get("affected_nodes") or [],
                "evidence": _evidence_lines(threat.get("evidence") or threat.get("llm_evidence")),
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
        slim.append({"id": node.get("id"), "label": data.get("label") or node.get("id")})
    return slim


def _unique(values):
    seen = set()
    result = []
    for value in values:
        text = str(value or "").strip().upper()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _chunk(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _dedupe(values):
    seen = set()
    result = []
    for value in _string_list(values):
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _empty(status):
    return {"status": status, "mitigations": [], "quick_wins": [], "assumptions": [], "missing_information": []}


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
