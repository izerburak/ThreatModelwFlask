import json
import re
from datetime import datetime, timezone
from pathlib import Path


def list_response_files(app_root_path):
    responses_dir = Path(app_root_path).parent / "responses"
    if not responses_dir.exists():
        return []
    return sorted(file_path.name for file_path in responses_dir.glob("*.json"))


def load_response_payload(app_root_path, filename):
    response_path = _safe_json_path(Path(app_root_path).parent / "responses", filename)
    return json.loads(response_path.read_text(encoding="utf-8"))


def archive_dfd_graph(app_root_path, graph, source_name=None, metadata=None):
    archive_dir = _ensure_dfd_archive_dir(app_root_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_source = _safe_slug(Path(str(source_name or "dfd")).stem)
    archive_id = f"{timestamp}-{safe_source}"
    archive_path = archive_dir / f"{archive_id}.json"
    suffix = 2
    while archive_path.exists():
        archive_path = archive_dir / f"{archive_id}-{suffix}.json"
        suffix += 1

    payload = dict(graph) if isinstance(graph, dict) else {}
    payload["metadata"] = {
        **(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
        **(metadata if isinstance(metadata, dict) else {}),
        "archive_id": archive_path.stem,
        "source_name": source_name,
        "archived_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    archive_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return archive_path


def list_dfd_archives(app_root_path):
    archive_dir = _ensure_dfd_archive_dir(app_root_path)
    archives = []
    for archive_path in archive_dir.glob("*.json"):
        try:
            payload = json.loads(archive_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        metadata = payload.get("metadata") if isinstance(payload, dict) else {}
        if not isinstance(metadata, dict):
            metadata = {}
        archives.append(
            {
                "filename": archive_path.name,
                "archive_id": archive_path.stem,
                "label": metadata.get("display_name") or metadata.get("pipeline_id") or archive_path.stem,
                "source_name": metadata.get("source_name"),
                "pipeline_id": metadata.get("pipeline_id"),
                "archived_at": metadata.get("archived_at"),
                "node_count": len(payload.get("nodes") or []) if isinstance(payload, dict) else 0,
                "edge_count": len(payload.get("edges") or []) if isinstance(payload, dict) else 0,
            }
        )
    return sorted(archives, key=lambda item: item.get("archived_at") or item["filename"], reverse=True)


def load_dfd_archive(app_root_path, filename):
    archive_path = _safe_json_path(_ensure_dfd_archive_dir(app_root_path), filename)
    return json.loads(archive_path.read_text(encoding="utf-8"))


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


def _ensure_dfd_archive_dir(app_root_path):
    archive_dir = _ensure_generated_models_dir(app_root_path) / "dfd_runs"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


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


def _safe_slug(value):
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "")).strip("-._")
    return slug or "dfd"


def _escape_label(value):
    return str(value).replace('"', '\\"')


def _diagram_alias(node_id, prefix):
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", str(node_id))
    return f"{prefix}_{sanitized}"
