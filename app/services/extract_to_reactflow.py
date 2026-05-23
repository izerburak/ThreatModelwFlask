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
PROCESSING_TYPES = {
    "process",
    "backend_service",
    "llm",
    "rag_engine",
    "tool_executor",
    "auth_service",
    "waf",
    "gateway",
    "secrets_vault",
    "logging",
}
DATA_TYPES = {"database", "file_storage", "vector_db"}
EXTERNAL_TYPES = {"external_api"}
BOUNDARY_TYPES = {"trust_boundary"}
NOTE_TYPES = {"text_note"}

CATEGORY_X = {
    "actors": 80,
    "interfaces": 350,
    "processing": 650,
    "data": 950,
    "external": 1200,
    "boundaries": 1450,
    "notes": 1700,
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
        ("auth_service", ["auth service", "identity provider", "session"]),
        ("waf", ["waf", "csrf", "origin protection", "web application firewall"]),
        ("gateway", ["api gateway", "cors", "egress", "rate limiter", "quota"]),
        ("secrets_vault", ["secrets vault", "secret manager"]),
        ("logging", ["logging", "siem", "monitoring"]),
    ],
    "data": [
        ("database", ["database", "sql"]),
        ("file_storage", ["file storage", "object storage"]),
        ("vector_db", ["internal knowledge base", "documentation", "embeddings"]),
    ],
}


def extract_to_reactflow(extract: dict, answers_by_flow_id: dict | None = None) -> dict:
    """Map an LLM extract payload to deterministic React Flow graph JSON."""
    if not isinstance(extract, dict):
        extract = {}

    builder = _GraphBuilder()
    _add_answer_derived_nodes(builder, answers_by_flow_id if isinstance(answers_by_flow_id, dict) else {})
    _add_dfd_schema_nodes(builder, _as_dict(extract.get("dfd")))
    _add_architecture_signal_nodes(builder, _as_dict(extract.get("architecture_signals")))
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

    _add_legacy_system_nodes(builder, extract)

    system_summary = _as_dict(extract.get("system_summary"))
    for label in _as_list(system_summary.get("trust_boundaries")):
        builder.add_node(label, "trust_boundary", "Generated from system_summary.trust_boundaries")

    purpose = _clean_string(system_summary.get("purpose")) or _legacy_system_purpose(extract) or "Not specified"
    exposure = _clean_string(system_summary.get("exposure")) or _legacy_system_exposure(extract) or "Not specified"
    builder.add_node("System Summary", "text_note", f"Purpose: {purpose}\nExposure: {exposure}")

    builder.apply_layout()
    builder.add_logical_edges()
    return {
        "nodes": builder.nodes,
        "edges": builder.edges,
        "viewport": {"x": 0, "y": 0, "zoom": 0.9},
    }


def has_recognized_dfd_content(extract: dict) -> bool:
    """Return true when an extract contains old or new architecture fields."""
    if not isinstance(extract, dict):
        return False

    dfd = _as_dict(extract.get("dfd"))
    if any(_as_list(dfd.get(section)) for section in _DFD_NODE_SECTIONS):
        return True
    if _as_list(dfd.get("data_flows")):
        return True

    architecture_signals = _as_dict(extract.get("architecture_signals"))
    if any(_as_list(architecture_signals.get(section)) for section in _ARCH_SIGNAL_NODE_SECTIONS):
        return True
    if _as_list(architecture_signals.get("data_movement_hints")):
        return True

    architecture = _as_dict(extract.get("architecture"))
    if any(_as_list(architecture.get(section)) for section in ("actors", "interfaces", "tools", "data_sources", "storage")):
        return True

    summary = _as_dict(extract.get("system_summary"))
    if _clean_string(summary.get("purpose")) or _clean_string(summary.get("exposure")):
        return True

    legacy_system = _as_dict(extract.get("system"))
    if legacy_system and any(
        legacy_system.get(key)
        for key in ("name", "description", "purpose", "features", "security", "deployment")
    ):
        return True

    return any(_as_dict(extract.get(key)) for key in ("llm_components", "use_cases", "deployment"))


_DFD_NODE_SECTIONS = (
    "actors",
    "interfaces",
    "processes",
    "data_stores",
    "external_systems",
    "tools",
    "trust_boundaries",
)


_ARCH_SIGNAL_NODE_SECTIONS = (
    "actors",
    "entry_points",
    "runtime_components",
    "data_stores",
    "external_systems",
    "tools_actions",
    "trust_boundary_hints",
)


def _add_dfd_schema_nodes(builder: "_GraphBuilder", dfd: dict) -> None:
    if not dfd:
        return

    section_type_mappers = {
        "actors": _map_dfd_actor_type,
        "interfaces": _map_dfd_interface_type,
        "processes": _map_dfd_process_type,
        "data_stores": _map_dfd_store_type,
        "external_systems": _map_dfd_external_type,
        "tools": _map_dfd_tool_type,
        "trust_boundaries": lambda item: "trust_boundary",
    }

    for section, type_mapper in section_type_mappers.items():
        for item in _as_list(dfd.get(section)):
            item_dict = _as_dict(item)
            label = item_dict.get("name") if item_dict else item
            source_id = _clean_string(item_dict.get("id")) if item_dict else ""
            node_type = type_mapper(item_dict) if item_dict else "process"
            notes = _dfd_item_notes(section, item_dict) if item_dict else f"Generated from dfd.{section}"
            builder.add_node(label, node_type, notes, source_entity_id=source_id)

    for flow in _as_list(dfd.get("data_flows")):
        flow_dict = _as_dict(flow)
        source = _clean_string(flow_dict.get("source"))
        target = _clean_string(flow_dict.get("target"))
        if not source or not target:
            continue
        label = _clean_string(flow_dict.get("data")) or _clean_string(flow_dict.get("trigger")) or "Data flow"
        builder.add_edge_by_source_id(source, target, label)


def _add_architecture_signal_nodes(builder: "_GraphBuilder", signals: dict) -> None:
    if not signals:
        return

    section_mappers = {
        "actors": _map_signal_actor_type,
        "entry_points": _map_signal_entry_point_type,
        "runtime_components": _map_signal_runtime_type,
        "data_stores": _map_signal_store_type,
        "external_systems": _map_signal_external_type,
        "tools_actions": lambda item: "tool_executor",
        "trust_boundary_hints": lambda item: "trust_boundary",
    }

    for section, type_mapper in section_mappers.items():
        for item in _as_list(signals.get(section)):
            item_dict = _as_dict(item)
            label = item_dict.get("name") if item_dict else item
            if not label:
                continue
            builder.add_node(label, type_mapper(item_dict), _signal_item_notes(section, item_dict))


def _add_legacy_system_nodes(builder: "_GraphBuilder", extract: dict) -> None:
    system = _as_dict(extract.get("system"))
    llm_components = _as_dict(extract.get("llm_components"))
    deployment = _as_dict(extract.get("deployment")) or _as_dict(system.get("deployment"))

    system_name = _clean_string(system.get("name"))
    if system_name:
        description = _clean_string(system.get("description")) or _clean_string(system.get("purpose"))
        builder.add_node(system_name, "backend_service", _join_notes("Generated from system.name", description))

    for feature_name, feature_description in _as_dict(system.get("features")).items():
        label = _title_from_key(feature_name)
        if label:
            builder.add_node(label, "backend_service", _join_notes("Generated from system.features", feature_description))

    security = _as_dict(system.get("security"))
    if security.get("access_control"):
        builder.add_node("Access Control", "auth_service", _join_notes("Generated from system.security.access_control", security.get("access_control")))
    if security.get("data_encryption"):
        builder.add_node("Encryption Boundary", "trust_boundary", _join_notes("Generated from system.security.data_encryption", security.get("data_encryption")))
    if security.get("audit_logs"):
        builder.add_node("Logging / SIEM", "logging", _join_notes("Generated from system.security.audit_logs", security.get("audit_logs")))

    if llm_components.get("model"):
        builder.add_node("LLM / Model Service", "llm", _join_notes("Generated from llm_components.model", llm_components.get("model")))
    if llm_components.get("training_data"):
        builder.add_node("Training / Knowledge Data", "vector_db", _join_notes("Generated from llm_components.training_data", llm_components.get("training_data")))
    if llm_components.get("prompt_engineering"):
        builder.add_node("Prompt Management", "backend_service", _join_notes("Generated from llm_components.prompt_engineering", llm_components.get("prompt_engineering")))

    if deployment:
        builder.add_node("Deployment Environment", "backend_service", "Generated from deployment")


def _add_answer_derived_nodes(builder: "_GraphBuilder", answers: dict) -> None:
    if not answers:
        return

    for flow_id, answer in answers.items():
        question_id = _normalize_question_id(flow_id)
        for value in _as_list(answer):
            label = _clean_string(value)
            normalized = _normalize_label(label)
            if not normalized or normalized in {"none", "unknown", "not applicable", "no"}:
                continue
            _add_answer_value_node(builder, question_id, label, normalized)


def _add_answer_value_node(builder: "_GraphBuilder", question_id: str, label: str, normalized: str) -> None:
    source = f"answers.{question_id}"

    if question_id == "Q2":
        if "authenticated" in normalized:
            builder.add_node("Authenticated User", "authenticated_user", source, source_entity_id="answer_actor_authenticated")
        elif "anonymous" in normalized or "public" in normalized:
            builder.add_node("Anonymous User", "external_user", source, source_entity_id="answer_actor_public")
        elif "internal" in normalized or "employee" in normalized:
            builder.add_node("Internal Employee", "internal_user", source, source_entity_id="answer_actor_internal")
        elif "admin" in normalized:
            builder.add_node("Administrator", "admin", source, source_entity_id="answer_actor_admin")
        elif "local system" in normalized:
            builder.add_node("Local System Process", "backend_service", source)
        return

    if question_id in {"Q3", "Q48"}:
        if "chat" in normalized or "dashboard" in normalized or "public chat" in normalized:
            builder.add_node(_web_entry_label(label), "web_app", source)
        elif "admin" in normalized:
            builder.add_node("Admin Panel", "admin_panel", source)
        elif "rest api" in normalized or "webhook" in normalized or "callback" in normalized:
            builder.add_node(_api_entry_label(label), "api_service", source)
        elif "cli" in normalized:
            builder.add_node("CLI Script", "api_service", source)
        elif "third party" in normalized:
            builder.add_node("Third-party Integration", "external_api", source)
        elif "iframe" in normalized or "widget" in normalized:
            builder.add_node("Embedded Web Widget", "web_app", source)
        return

    if question_id in {"Q49", "Q52", "Q53", "Q54", "Q55", "Q57", "Q58", "Q59", "Q63", "Q77", "Q78"}:
        _add_api_security_node(builder, question_id, label, normalized, source)
        return

    if question_id in {"Q50", "Q56"}:
        builder.add_node("Auth / Session Service", "auth_service", source)
        if "service account" in normalized:
            builder.add_node("Service Account Identity", "auth_service", source)
        return

    if question_id == "Q51":
        builder.add_node("CSRF / Origin Protection", "waf", source)
        return

    if question_id in {"Q60", "Q61", "Q62"}:
        builder.add_node("External API", "external_api", source)
        if question_id == "Q62":
            builder.add_node("URL Fetch / Browser Tool", "tool_executor", source)
        return

    if question_id == "Q64":
        builder.add_node("Web Output Renderer", "web_app", source)
        return

    if question_id == "Q65":
        builder.add_node("Structured Output Processor", "tool_executor", source)
        return

    if question_id == "Q66":
        builder.add_node("Output Safety Filter", "waf", source)
        return

    if question_id == "Q67":
        builder.add_node("File Upload Interface", "web_app", source)
        builder.add_node("Uploaded File Storage", "file_storage", source)
        return

    if question_id == "Q68":
        builder.add_node("Shared Retrieval Index", "vector_db", source)
        return

    if question_id == "Q69":
        builder.add_node("RAG Source Administration API", "api_service", source)
        return

    if question_id == "Q70":
        builder.add_node("Admin Panel", "admin_panel", source)
        return

    if question_id == "Q71":
        builder.add_node("Configuration Audit Log", "logging", source)
        return

    if question_id == "Q72":
        builder.add_node("Secrets Vault", "secrets_vault", source)
        return

    if question_id == "Q73":
        builder.add_node("Encrypted Transport Boundary", "trust_boundary", source)
        return

    if question_id == "Q74":
        builder.add_node("Logging / SIEM", "logging", source)
        return

    if question_id == "Q75":
        builder.add_node("Failure Handling Controller", "backend_service", source)
        return

    if question_id == "Q76":
        builder.add_node("Error Sanitizer", "waf", source)
        return

    if question_id == "Q79":
        builder.add_node("Sensitive Business Workflow", "backend_service", source)
        return

    if question_id == "Q80":
        builder.add_node("Approval / Step-up Control", "auth_service", source)


def _add_api_security_node(builder: "_GraphBuilder", question_id: str, label: str, normalized: str, source: str) -> None:
    if question_id in {"Q49", "Q52", "Q53", "Q54", "Q55", "Q57"}:
        builder.add_node("API Gateway / Authorization Layer", "gateway", source)
    if question_id == "Q52":
        builder.add_node("CORS Policy", "gateway", source)
    if question_id == "Q58":
        builder.add_node("API Inventory", "database", source)
    if question_id == "Q59" and any(term in normalized for term in ("debug", "deprecated", "staging", "undocumented", "possibly")):
        builder.add_node("Non-production / Undocumented APIs", "external_api", source)
    if question_id == "Q63":
        builder.add_node("Egress Control", "gateway", source)
    if question_id == "Q77":
        builder.add_node("Rate Limiter", "gateway", source)
    if question_id == "Q78":
        builder.add_node("Quota / Timeout Controller", "gateway", source)


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []
        self._node_by_label: dict[str, dict[str, Any]] = {}
        self._node_by_source_id: dict[str, dict[str, Any]] = {}
        self._edge_keys: set[tuple[str, str, str]] = set()

    def add_node(
        self,
        raw_label: Any,
        node_type: str,
        notes: str,
        source_entity_id: str | None = None,
    ) -> dict[str, Any] | None:
        label = _clean_string(raw_label)
        if not label:
            return None

        normalized = _normalize_label(label)
        existing = self._node_by_label.get(normalized)
        if existing is not None:
            if source_entity_id:
                self._node_by_source_id[source_entity_id] = existing
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
        if source_entity_id:
            self._node_by_source_id[source_entity_id] = node
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
        auth_services = self._nodes_with_types({"auth_service"})
        gateways = self._nodes_with_types({"gateway"})
        wafs = self._nodes_with_types({"waf"})
        loggers = self._nodes_with_types({"logging"})
        secret_vaults = self._nodes_with_types({"secrets_vault"})
        external_apis = self._nodes_with_types({"external_api"})

        self._connect_many(actors, interfaces, "Uses")
        self._connect_many(interfaces, wafs, "Protected by")
        self._connect_many(wafs, gateways, "Forwards")
        self._connect_many(interfaces, gateways, "Routes through")
        self._connect_many(gateways, auth_services, "Validates identity")
        self._connect_many(gateways, backends, "Forwards")
        self._connect_many(auth_services, backends, "Authorizes")
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
        self._connect_many(backends, external_apis, "Calls")
        self._connect_many(self._nodes_with_types({"tool_executor"}), external_apis, "Calls")
        self._connect_many(backends, loggers, "Logs to")
        self._connect_many(gateways, loggers, "Logs to")
        self._connect_many(self._nodes_with_types({"tool_executor"}), secret_vaults, "Reads secrets")

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

    def add_edge_by_source_id(self, source_entity_id: str, target_entity_id: str, label: str) -> None:
        source = self._node_by_source_id.get(source_entity_id)
        target = self._node_by_source_id.get(target_entity_id)
        if not source or not target:
            return
        self._add_edge(source["id"], target["id"], label)


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
    if node_type in EXTERNAL_TYPES:
        return "external"
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


def _join_notes(source: str, detail: Any = "") -> str:
    detail_text = _clean_string(detail)
    return f"{source}\n{detail_text}" if detail_text else source


def _title_from_key(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", " ", str(value or "")).strip()
    return text.title() if text else ""


def _legacy_system_purpose(extract: dict) -> str:
    system = _as_dict(extract.get("system"))
    return _clean_string(system.get("purpose")) or _clean_string(system.get("description"))


def _legacy_system_exposure(extract: dict) -> str:
    deployment = _as_dict(extract.get("deployment")) or _as_dict(_as_dict(extract.get("system")).get("deployment"))
    if not deployment:
        return ""
    return ", ".join(_title_from_key(key) for key, value in deployment.items() if value)


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_string(label).lower()).strip()


def _normalize_enum(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", _clean_string(value).lower()).strip("_")


def _map_dfd_actor_type(item: dict) -> str:
    trust_zone = _normalize_enum(item.get("trust_zone"))
    name = _normalize_label(item.get("name"))
    if trust_zone == "admin" or "admin" in name:
        return "admin"
    if trust_zone == "internal" or "employee" in name:
        return "internal_user"
    if "authenticated" in name:
        return "authenticated_user"
    if item.get("type") == "system":
        return "third_party_actor"
    return "external_user"


def _map_dfd_interface_type(item: dict) -> str:
    interface_type = _normalize_label(item.get("type"))
    name = _normalize_label(item.get("name"))
    if interface_type == "web" or "web" in name or "chat" in name:
        return "web_app"
    if interface_type == "api" or "api" in name:
        return "api_service"
    if "admin" in name:
        return "admin_panel"
    return "api_service"


def _map_dfd_process_type(item: dict) -> str:
    process_type = _normalize_enum(item.get("type"))
    name = _normalize_label(item.get("name"))
    process_map = {
        "backend_api": "backend_service",
        "orchestrator": "backend_service",
        "rag_retriever": "rag_engine",
        "model_service": "llm",
        "tool_layer": "tool_executor",
        "auth_service": "auth_service",
        "monitoring": "logging",
        "web_app": "web_app",
        "gateway": "gateway",
        "api_gateway": "gateway",
        "waf": "waf",
        "secrets_vault": "secrets_vault",
        "logging": "logging",
    }
    if process_type in process_map:
        return process_map[process_type]
    if "gateway" in name or "cors" in name or "egress" in name:
        return "gateway"
    if "waf" in name or "csrf" in name or "origin" in name:
        return "waf"
    if "auth" in name or "identity" in name or "session" in name:
        return "auth_service"
    if "secret" in name:
        return "secrets_vault"
    if "log" in name or "siem" in name or "monitor" in name:
        return "logging"
    return "process"


def _map_dfd_store_type(item: dict) -> str:
    store_type = _normalize_enum(item.get("type"))
    store_map = {
        "vector_db": "vector_db",
        "sql_nosql": "database",
        "file_storage": "file_storage",
        "conversation_memory": "database",
        "logs": "database",
        "knowledge_base": "vector_db",
        "cloud_storage": "file_storage",
    }
    return store_map.get(store_type, "database")


def _map_dfd_external_type(item: dict) -> str:
    external_type = _normalize_enum(item.get("type"))
    if external_type == "llm_provider":
        return "llm"
    if external_type in {"external_api", "third_party_integration", "email_service", "web_content", "cloud_service"}:
        return "external_api"
    return "external_api"


def _map_dfd_tool_type(item: dict) -> str:
    action_type = _normalize_enum(item.get("action_type"))
    if action_type in {"read", "write", "admin", "external_call", "notification", "workflow"}:
        return "tool_executor"
    return "tool_executor"


def _map_signal_actor_type(item: dict) -> str:
    trust_zone = _normalize_enum(item.get("trust_zone"))
    name = _normalize_label(item.get("name"))
    actor_type = _normalize_enum(item.get("actor_type"))
    if trust_zone == "admin" or "admin" in name:
        return "admin"
    if trust_zone == "internal" or "employee" in name:
        return "internal_user"
    if trust_zone == "local":
        return "backend_service"
    if actor_type == "system":
        return "third_party_actor"
    if "authenticated" in name:
        return "authenticated_user"
    return "external_user"


def _map_signal_entry_point_type(item: dict) -> str:
    interface_type = _normalize_enum(item.get("interface_type"))
    name = _normalize_label(item.get("name"))
    entry_map = {
        "web_chat": "web_app",
        "rest_api": "api_service",
        "internal_call": "api_service",
        "cli": "api_service",
        "webhook": "api_service",
        "admin_panel": "admin_panel",
        "third_party_integration": "external_api",
    }
    if interface_type in entry_map:
        return entry_map[interface_type]
    if "admin" in name:
        return "admin_panel"
    if "web" in name or "chat" in name:
        return "web_app"
    if "api" in name or "webhook" in name:
        return "api_service"
    return "api_service"


def _map_signal_runtime_type(item: dict) -> str:
    component_type = _normalize_enum(item.get("component_type"))
    runtime_map = {
        "web_app": "web_app",
        "backend_api": "backend_service",
        "orchestrator": "backend_service",
        "rag_retriever": "rag_engine",
        "model_service": "llm",
        "tool_execution_layer": "tool_executor",
        "auth_service": "auth_service",
        "monitoring": "logging",
    }
    return runtime_map.get(component_type, "process")


def _map_signal_store_type(item: dict) -> str:
    store_type = _normalize_enum(item.get("store_type"))
    store_map = {
        "vector_db": "vector_db",
        "sql_nosql": "database",
        "file_storage": "file_storage",
        "cloud_storage": "file_storage",
        "conversation_history": "database",
        "logs": "database",
        "knowledge_base": "vector_db",
        "documentation": "vector_db",
        "source_code_repo": "database",
    }
    return store_map.get(store_type, "database")


def _map_signal_external_type(item: dict) -> str:
    system_type = _normalize_enum(item.get("system_type"))
    if system_type == "llm_provider":
        return "llm"
    return "external_api"


def _signal_item_notes(section: str, item: dict) -> str:
    parts = [f"Generated from architecture_signals.{section}"]
    evidence = _as_list(item.get("evidence"))
    if evidence:
        parts.append(f"Evidence: {', '.join(str(value) for value in evidence)}")
    role = _clean_string(item.get("role"))
    if role:
        parts.append(role)
    reason = _clean_string(item.get("reason"))
    if reason:
        parts.append(reason)
    return "\n".join(parts)


def _dfd_item_notes(section: str, item: dict) -> str:
    parts = [f"Generated from dfd.{section}"]
    evidence = _as_list(item.get("evidence"))
    if evidence:
        parts.append(f"Evidence: {', '.join(str(value) for value in evidence)}")
    description = _clean_string(item.get("description"))
    if description:
        parts.append(description)
    return "\n".join(parts)


def _normalize_question_id(value: Any) -> str:
    match = re.search(r"(\d+)", str(value or ""))
    return f"Q{int(match.group(1))}" if match else str(value or "").upper()


def _web_entry_label(label: str) -> str:
    normalized = _normalize_label(label)
    if "authenticated" in normalized or "dashboard" in normalized:
        return "Authenticated User Dashboard"
    if "admin" in normalized:
        return "Admin Panel"
    if "widget" in normalized or "iframe" in normalized:
        return "Embedded Web Widget"
    return "Web Chat UI"


def _api_entry_label(label: str) -> str:
    normalized = _normalize_label(label)
    if "webhook" in normalized or "callback" in normalized:
        return "Webhook / Callback Endpoint"
    if "internal service" in normalized:
        return "Internal Service API"
    return "REST API"
