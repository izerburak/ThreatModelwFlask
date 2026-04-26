import re
from typing import Any


ACTOR_TYPES = {
    "external_user",
    "authenticated_user",
    "admin",
    "internal_user",
    "third_party_actor",
}
INTERFACE_TYPES = {"web_app", "mobile_app", "api_service", "admin_panel"}
PROCESSING_TYPES = {"process", "backend_service", "llm", "rag_engine", "tool_executor"}
DATA_TYPES = {"database", "file_storage", "vector_db"}
BOUNDARY_TYPES = {"trust_boundary"}
NOTE_TYPES = {"text_note"}

CATEGORY_X = {
    "actors": 80,
    "interfaces": 350,
    "processing": 650,
    "data": 950,
    "boundaries": 1200,
    "notes": 1450,
}
START_Y = 100
Y_SPACING = 140

TYPE_KEYWORDS_BY_SECTION = {
    "actors": [
        ("authenticated_user", ["authenticated public users"]),
        ("external_user", ["anonymous public users", "public users"]),
        ("admin", ["admin", "administrator"]),
        ("internal_user", ["internal employee", "internal user"]),
        ("third_party_actor", ["third party system"]),
    ],
    "interfaces": [
        ("web_app", ["web based chat interface", "web interface", "frontend"]),
        ("mobile_app", ["mobile app"]),
        ("api_service", ["api response consumed by other systems", "api", "endpoint"]),
        ("admin_panel", ["admin panel"]),
    ],
    "processing": [
        ("backend_service", ["backend logic", "backend", "service"]),
        ("llm", ["third party cloud api", "llm", "model"]),
        ("rag_engine", ["search functionality", "retrieval", "rag"]),
        ("tool_executor", ["tool executor"]),
    ],
    "data": [
        ("database", ["database", "sql"]),
        ("file_storage", ["file storage", "object storage"]),
        ("vector_db", ["internal knowledge base", "documentation", "embeddings"]),
    ],
}


def extract_to_reactflow(extract: dict) -> dict:
    """Map an LLM extract payload to deterministic React Flow graph JSON."""
    if not isinstance(extract, dict):
        extract = {}

    builder = _GraphBuilder()
    architecture = _as_dict(extract.get("architecture"))

    for section in ("actors", "interfaces"):
        for label in _as_list(architecture.get(section)):
            builder.add_node(label, _map_type(str(label), section), f"Generated from architecture.{section}")

    for section in ("tools",):
        for label in _as_list(architecture.get(section)):
            builder.add_node(label, _map_type(str(label), "processing"), f"Generated from architecture.{section}")

    for section in ("data_sources", "storage"):
        for label in _as_list(architecture.get(section)):
            builder.add_node(label, _map_type(str(label), "data"), f"Generated from architecture.{section}")

    system_summary = _as_dict(extract.get("system_summary"))
    for label in _as_list(system_summary.get("trust_boundaries")):
        builder.add_node(label, "trust_boundary", "Generated from system_summary.trust_boundaries")

    purpose = _clean_string(system_summary.get("purpose")) or "Not specified"
    exposure = _clean_string(system_summary.get("exposure")) or "Not specified"
    builder.add_node("System Summary", "text_note", f"Purpose: {purpose}\nExposure: {exposure}")

    builder.apply_layout()
    builder.add_logical_edges()
    return {
        "nodes": builder.nodes,
        "edges": builder.edges,
        "viewport": {"x": 0, "y": 0, "zoom": 0.9},
    }


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []
        self._node_by_label: dict[str, dict[str, Any]] = {}
        self._edge_keys: set[tuple[str, str, str]] = set()

    def add_node(self, raw_label: Any, node_type: str, notes: str) -> dict[str, Any] | None:
        label = _clean_string(raw_label)
        if not label:
            return None

        normalized = _normalize_label(label)
        existing = self._node_by_label.get(normalized)
        if existing is not None:
            return existing

        node = {
            "id": f"node_{len(self.nodes) + 1}",
            "type": node_type or "process",
            "position": {"x": 0, "y": 0},
            "data": {
                "label": label,
                "notes": notes,
            },
        }
        self.nodes.append(node)
        self._node_by_label[normalized] = node
        return node

    def apply_layout(self) -> None:
        offsets = {category: 0 for category in CATEGORY_X}
        for node in self.nodes:
            category = _category_for_type(node["type"])
            node["position"] = {
                "x": CATEGORY_X[category],
                "y": START_Y + offsets[category] * Y_SPACING,
            }
            offsets[category] += 1

    def add_logical_edges(self) -> None:
        actors = self._nodes_with_types(ACTOR_TYPES)
        interfaces = self._nodes_with_types(INTERFACE_TYPES)
        web_apps = self._nodes_with_types({"web_app"})
        api_services = self._nodes_with_types({"api_service"})
        backends = self._nodes_with_types({"backend_service"})
        llms = self._nodes_with_types({"llm"})
        rag_engines = self._nodes_with_types({"rag_engine"})
        vector_dbs = self._nodes_with_types({"vector_db"})
        file_stores = self._nodes_with_types({"file_storage"})
        databases = self._nodes_with_types({"database"})

        self._connect_many(actors, interfaces, "Uses")
        self._connect_many(web_apps, api_services, "Uses")
        self._connect_many(interfaces, backends, "Uses")
        self._connect_many(interfaces, llms, "Uses")
        self._connect_many(backends, llms, "Uses")
        self._connect_many(llms, rag_engines, "Uses")
        self._connect_many(rag_engines, vector_dbs, "Uses")
        self._connect_many(llms, file_stores, "Uses")
        self._connect_many(llms, databases, "Uses")
        self._connect_many(backends, databases, "Uses")
        self._connect_many(api_services, databases, "Uses")

    def _nodes_with_types(self, node_types: set[str]) -> list[dict[str, Any]]:
        return [node for node in self.nodes if node["type"] in node_types]

    def _connect_many(self, sources: list[dict[str, Any]], targets: list[dict[str, Any]], label: str) -> None:
        for source in sources:
            for target in targets:
                if source["id"] != target["id"]:
                    self._add_edge(source["id"], target["id"], label)

    def _add_edge(self, source: str, target: str, label: str) -> None:
        key = (source, target, label)
        if key in self._edge_keys:
            return

        self.edges.append({
            "id": f"edge_{len(self.edges) + 1}",
            "source": source,
            "target": target,
            "label": label,
        })
        self._edge_keys.add(key)


def _map_type(label: str, section: str) -> str:
    normalized = _normalize_label(label)
    for node_type, keywords in TYPE_KEYWORDS_BY_SECTION.get(section, []):
        if any(keyword in normalized for keyword in keywords):
            return node_type
    return "process"


def _category_for_type(node_type: str) -> str:
    if node_type in ACTOR_TYPES:
        return "actors"
    if node_type in INTERFACE_TYPES:
        return "interfaces"
    if node_type in PROCESSING_TYPES:
        return "processing"
    if node_type in DATA_TYPES:
        return "data"
    if node_type in BOUNDARY_TYPES:
        return "boundaries"
    if node_type in NOTE_TYPES:
        return "notes"
    return "processing"


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_string(label).lower()).strip()
