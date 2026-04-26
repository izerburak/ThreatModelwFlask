from datetime import datetime, timezone
import re


def build_mock_dfd_payload(setup_payload, response_payload, response_file):
    """
    Temporary mock DFD generator.

    TODO:
    Replace this function with a real local LLM-backed generator that returns
    the same diagram schema:
    {
      "nodes": [...],
      "edges": [...]
    }
    """
    model_title = (setup_payload.get("model_title") or "Threat Model").strip()
    project_name = (setup_payload.get("project_name") or "Unnamed Project").strip()
    owner = (setup_payload.get("owner") or "").strip()
    reviewer = (setup_payload.get("reviewer") or "").strip()
    description = (setup_payload.get("description") or "").strip()
    environment = (setup_payload.get("environment") or "Development").strip()
    generation_mode = (setup_payload.get("generation_mode") or "Fast").strip()

    options = {
        "include_trust_boundaries": bool(setup_payload.get("include_trust_boundaries")),
        "include_risk_tags": bool(setup_payload.get("include_risk_tags")),
        "auto_layout": bool(setup_payload.get("auto_layout")),
        "editable_canvas": bool(setup_payload.get("editable_canvas")),
    }

    answers = response_payload.get("answers") or {}
    model_id = _build_model_id(model_title, project_name)

    user_label = _derive_user_label(answers)
    process_label = _derive_process_label(project_name, answers)
    external_label = _derive_external_label(answers)
    note_text = (
        f"Mode: {generation_mode}. Env: {environment}. "
        f"Source: {response_file}."
    )

    nodes = [
        {"id": "1", "type": "user", "label": user_label, "notes": owner, "position": {"x": 100, "y": 120}},
        {"id": "2", "type": "process", "label": process_label, "notes": description, "position": {"x": 420, "y": 120}},
        {"id": "3", "type": "llm", "label": "Future LLM Engine", "notes": "Reserved for future local model integration.", "position": {"x": 760, "y": 120}},
        {"id": "4", "type": "external_api", "label": external_label, "notes": reviewer, "position": {"x": 420, "y": 320}},
    ]

    edges = [
        {"id": "e1", "source": "1", "target": "2", "label": "Request"},
        {"id": "e2", "source": "2", "target": "3", "label": "Prompt"},
        {"id": "e3", "source": "2", "target": "4", "label": "Integration"},
    ]

    if options["include_trust_boundaries"]:
        nodes.append(
            {
                "id": "5",
                "type": "trust_boundary",
                "label": f"{environment} Boundary",
                "notes": "Logical trust boundary placeholder.",
                "position": {"x": 60, "y": 40},
                "width": 860,
                "height": 390,
            }
        )

    if options["include_risk_tags"]:
        nodes.append(
            {
                "id": "6",
                "type": "text_note",
                "label": "Risk Tags",
                "notes": note_text,
                "position": {"x": 760, "y": 320},
            }
        )

    return {
        "model_id": model_id,
        "title": model_title,
        "project_name": project_name,
        "owner": owner,
        "reviewer": reviewer,
        "description": description,
        "environment": environment,
        "generation_mode": generation_mode,
        "options": options,
        "source_response_file": response_file,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "response_summary": {
            "layer": response_payload.get("layer"),
            "question_count": len(answers),
        },
        "diagram": {
            "nodes": nodes,
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


def _build_model_id(model_title, project_name):
    base = f"{project_name}-{model_title}".strip("-")
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "threat-model"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{slug}-{timestamp}"


def _derive_user_label(answers):
    user_scope = answers.get("q_2")
    if isinstance(user_scope, list) and user_scope:
        return user_scope[0]
    if isinstance(user_scope, str) and user_scope.strip():
        return user_scope.strip()
    return "Public User"


def _derive_process_label(project_name, answers):
    system_type = answers.get("q_1")
    if isinstance(system_type, list) and system_type:
        return system_type[0]
    if isinstance(system_type, str) and system_type.strip():
        return system_type.strip()
    return project_name or "Web App"


def _derive_external_label(answers):
    external_dependency = answers.get("q_8") or answers.get("q_4")
    if isinstance(external_dependency, list) and external_dependency:
        return external_dependency[0]
    if isinstance(external_dependency, str) and external_dependency.strip():
        return external_dependency.strip()
    return "External API"
