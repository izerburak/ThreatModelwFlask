import json
import re
from pathlib import Path


def list_response_files(app_root_path):
    responses_dir = Path(app_root_path).parent / "responses"
    if not responses_dir.exists():
        return []
    return sorted(file_path.name for file_path in responses_dir.glob("*.json"))


def load_response_payload(app_root_path, filename):
    response_path = _safe_json_path(Path(app_root_path).parent / "responses", filename)
    return json.loads(response_path.read_text(encoding="utf-8"))


def save_model_record(app_root_path, model_id, record):
    generated_dir = _ensure_generated_models_dir(app_root_path)
    model_path = _model_record_path(app_root_path, model_id)
    model_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return model_path


def load_model_record(app_root_path, model_id):
    try:
        model_path = _model_record_path(app_root_path, model_id)
    except ValueError:
        return None
    if not model_path.exists():
        return None
    return json.loads(model_path.read_text(encoding="utf-8"))


def export_diagram_as_mermaid(diagram):
    nodes = diagram.get("nodes", [])
    edges = diagram.get("edges", [])
    alias_map = {node["id"]: _diagram_alias(node["id"], "n") for node in nodes}

    lines = ["flowchart LR"]
    for node in nodes:
        lines.append(f'    {alias_map[node["id"]]}["{_escape_label(node.get("label", node["id"]))}"]')
    for edge in edges:
        edge_label = edge.get("label", "").strip()
        if edge_label:
            lines.append(
                f'    {alias_map.get(edge["source"], _diagram_alias(edge["source"], "n"))} -->|"{_escape_label(edge_label)}"| {alias_map.get(edge["target"], _diagram_alias(edge["target"], "n"))}'
            )
        else:
            lines.append(
                f'    {alias_map.get(edge["source"], _diagram_alias(edge["source"], "n"))} --> {alias_map.get(edge["target"], _diagram_alias(edge["target"], "n"))}'
            )
    return "\n".join(lines) + "\n"


def export_diagram_as_plantuml(diagram):
    nodes = diagram.get("nodes", [])
    edges = diagram.get("edges", [])
    alias_map = {node["id"]: _diagram_alias(node["id"], "node") for node in nodes}

    lines = ["@startuml", "left to right direction", "skinparam shadowing false"]
    for node in nodes:
        alias = alias_map[node["id"]]
        label = _escape_label(node.get("label", node["id"]))
        lines.append(f'rectangle "{label}" as {alias}')
    for edge in edges:
        source = alias_map.get(edge["source"], _diagram_alias(edge["source"], "node"))
        target = alias_map.get(edge["target"], _diagram_alias(edge["target"], "node"))
        label = edge.get("label", "").strip()
        if label:
            lines.append(f'{source} --> {target} : {_escape_label(label)}')
        else:
            lines.append(f"{source} --> {target}")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def _ensure_generated_models_dir(app_root_path):
    generated_dir = Path(app_root_path).parent / "generated_models"
    generated_dir.mkdir(parents=True, exist_ok=True)
    return generated_dir


def _model_record_path(app_root_path, model_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", model_id):
        raise ValueError("Invalid model id.")
    return _ensure_generated_models_dir(app_root_path) / f"{model_id}.json"


def _safe_json_path(base_dir, filename):
    candidate = (base_dir / filename).resolve()
    if candidate.parent != base_dir.resolve() or candidate.suffix.lower() != ".json":
        raise ValueError("Invalid JSON file selection.")
    if not candidate.exists():
        raise FileNotFoundError(filename)
    return candidate


def _escape_label(value):
    return str(value).replace('"', '\\"')


def _diagram_alias(node_id, prefix):
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", str(node_id))
    return f"{prefix}_{sanitized}"
