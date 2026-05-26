import re
from typing import Any


MAPPER_VERSION = "static-dfd-v2"
GRAPH_MODES = {"compact", "detailed"}

LANE_X = {
    "actor": 0,
    "entry": 260,
    "backend": 540,
    "llm": 820,
    "data": 1100,
    "external": 1380,
    "boundary": 540,
    "lower": 820,
}

LANE_START_Y = {
    "actor": 100,
    "entry": 100,
    "backend": 100,
    "llm": 140,
    "data": 100,
    "external": 100,
    "boundary": 680,
    "lower": 560,
}

LANE_SPACING = 145


def build_static_dfd_from_answers(raw_answers: dict, graph_mode: str = "compact") -> dict:
    """Build a deterministic React Flow DFD from questionnaire answers only."""
    mode = graph_mode if graph_mode in GRAPH_MODES else "compact"
    normalized_answers = normalize_answers(raw_answers)
    signals = extract_architecture_signals(normalized_answers)
    graph = {
        "nodes": build_nodes(signals),
        "edges": [],
    }
    _clean_boundary_contains(graph["nodes"])
    graph["edges"] = build_edges(signals, graph["nodes"], mode)
    graph = prune_edges(graph, signals, mode)
    graph = layout_graph(graph)
    controls, unresolved_control_targets = _finalize_metadata_controls(signals["controls"], graph["nodes"])
    orphan_nodes = _graph_orphan_nodes(graph)
    graph["metadata"] = {
        "mapper_version": MAPPER_VERSION,
        "graph_mode": mode,
        "normalized_answer_count": len(normalized_answers),
        "warnings": signals["warnings"],
        "assumptions": signals["assumptions"],
        "controls": controls,
        "unresolved_control_targets": unresolved_control_targets,
        "orphan_nodes": orphan_nodes,
        "signals_summary": {
            "actors": len(signals["actors"]),
            "entry_points": len(signals["entry_points"]),
            "data_stores": len(signals["data_stores"]),
            "tools": len(signals["tools"]),
            "trust_boundaries": len(signals["trust_boundaries"]),
        },
    }
    return graph


def _graph_orphan_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    incident_ids = {
        node_id
        for edge in graph.get("edges", [])
        for node_id in (edge.get("source"), edge.get("target"))
        if node_id
    }
    orphan_nodes = []
    for node in graph.get("nodes", []):
        data = node.get("data") or {}
        if data.get("nodeType") == "trust_boundary" or node.get("id") in incident_ids:
            continue
        orphan_nodes.append(
            {
                "id": node.get("id"),
                "label": data.get("label") or node.get("id"),
                "nodeType": data.get("nodeType"),
                "role": data.get("role"),
                "kind": data.get("kind"),
            }
        )
    return orphan_nodes


def normalize_answers(raw_answers: dict) -> dict[str, Any]:
    """Normalize supported response payloads to Q-id keyed answers."""
    if not isinstance(raw_answers, dict):
        raise ValueError("Static DFD mapper expects a JSON object.")

    payload = raw_answers.get("raw") if isinstance(raw_answers.get("raw"), dict) else raw_answers

    # Endpoint wrapper: {"answers": {"Q1": "..."}}
    if isinstance(payload.get("answers"), dict):
        return _normalize_answer_keys(payload["answers"])

    if isinstance(payload.get("answers_by_flow_id"), dict):
        return _normalize_answer_keys(payload["answers_by_flow_id"])

    # Saved app response format: {"answers": [{"flow_id": "Q1", "answer": "..."}]}
    if isinstance(payload.get("answers"), list):
        normalized = {}
        for record in payload["answers"]:
            if not isinstance(record, dict):
                continue
            question_id = record.get("flow_id") or record.get("question_id") or record.get("id")
            answer = record.get("answer")
            if question_id is not None and answer not in (None, "", []):
                normalized[_normalize_question_id(question_id)] = answer
        if normalized:
            return normalized

    flat_answers = {
        key: value
        for key, value in payload.items()
        if _looks_like_question_id(key) and value not in (None, "", [])
    }
    if flat_answers:
        return _normalize_answer_keys(flat_answers)

    raise ValueError(
        "Unsupported input shape. Provide flat Q-id answers, answers_by_flow_id, or the saved app response format."
    )


def extract_architecture_signals(normalized_answers: dict[str, Any]) -> dict[str, Any]:
    """Extract generic architecture signals from normalized questionnaire answers."""
    signals = {
        "actors": [],
        "entry_points": [],
        "preprocessing": [],
        "rag": {"enabled": False, "evidence": []},
        "processes": [],
        "data_stores": [],
        "tools": [],
        "business_actions": [],
        "external_services": [],
        "trust_boundaries": [],
        "controls": [],
        "logging": {"enabled": False, "evidence": []},
        "model": {"has_llm": bool(normalized_answers), "hosting": None, "evidence": []},
        "warnings": [],
        "assumptions": [],
    }

    _extract_actors(signals, normalized_answers)
    _extract_entry_points(signals, normalized_answers)
    _extract_core_processes(signals, normalized_answers)
    _extract_model(signals, normalized_answers)
    _extract_data_stores(signals, normalized_answers)
    _extract_tools_and_actions(signals, normalized_answers)
    _extract_external_services(signals, normalized_answers)
    _extract_trust_boundaries(signals, normalized_answers)
    _extract_controls(signals, normalized_answers)
    _extract_warnings_and_assumptions(signals, normalized_answers)
    return signals


def build_nodes(signals: dict[str, Any]) -> list[dict[str, Any]]:
    """Create React Flow nodes from structural architecture signals."""
    builder = _NodeBuilder()

    for signal in signals["actors"]:
        builder.add_signal_node(signal, "actor", "actor")
    for signal in signals["entry_points"]:
        builder.add_signal_node(signal, "process", "interface")

    for signal in signals["preprocessing"]:
        builder.add_signal_node(signal, "process", "process")
    for signal in signals["processes"]:
        builder.add_signal_node(signal, "process", signal.get("role", "process"))

    if signals["rag"]["enabled"]:
        builder.add_node(
            "process_rag_orchestrator",
            "RAG Orchestrator",
            "process",
            "process",
            signals["rag"]["evidence"],
        )

    if signals["model"]["has_llm"]:
        builder.add_node(
            "llm_gateway",
            "LLM Gateway / Model Adapter",
            "llm",
            "llm",
            signals["model"].get("evidence") or ["static_mapper: LLM questionnaire response"],
        )

    hosting = signals["model"].get("hosting")
    if hosting == "external":
        builder.add_node(
            "external_model_provider",
            signals["model"].get("provider_label") or "Third-party LLM Provider",
            "llm",
            "external",
            signals["model"].get("evidence") or [],
        )
    elif hosting == "self_hosted":
        builder.add_node(
            "llm_runtime",
            "Self-hosted Model Runtime",
            "llm",
            "llm",
            signals["model"].get("evidence") or [],
        )

    for signal in signals["data_stores"]:
        builder.add_signal_node(signal, "database", "data_store")
    for signal in signals["tools"]:
        builder.add_signal_node(signal, "process", "tool")
    for signal in signals["business_actions"]:
        builder.add_signal_node(signal, "external_api", "action")
    for signal in signals["external_services"]:
        node_type = signal.get("nodeType") or "external_api"
        builder.add_signal_node(signal, node_type, "external")

    if signals["logging"]["enabled"]:
        builder.add_node(
            "process_logging_monitoring",
            "Logging and Monitoring",
            "process",
            "process",
            signals["logging"]["evidence"],
        )

    for signal in signals["trust_boundaries"]:
        builder.add_signal_node(signal, "trust_boundary", "process")

    _attach_controls(builder.nodes, signals)
    return builder.nodes


def build_edges(signals: dict[str, Any], nodes: list[dict[str, Any]], graph_mode: str) -> list[dict[str, Any]]:
    """Create semantically valid DFD edges from architecture signals and nodes."""
    builder = _EdgeBuilder(nodes)
    request_pairs = _valid_request_pairs(signals)

    for actor_id, entry_id in request_pairs:
        builder.add(actor_id, entry_id, _request_label(actor_id), _evidence_for(nodes, actor_id, entry_id))

    entries_to_backend = [entry_id for _, entry_id in request_pairs] or [signal["id"] for signal in signals["entry_points"]]
    first_process = _first_existing(
        builder,
        ["process_preprocessor", "process_orchestrator", "process_rag_orchestrator", "llm_gateway"],
    )
    for entry_id in sorted(set(entries_to_backend)):
        if first_process:
            builder.add(entry_id, first_process, "LLM request", _evidence_for(nodes, entry_id, first_process))

    _add_core_processing_edges(builder, signals, nodes)
    _add_model_edges(builder, signals, nodes)
    _add_rag_edges(builder, signals, nodes)
    _add_tool_edges(builder, signals, nodes)
    _add_external_api_edges(builder, signals, nodes)
    _add_output_edges(builder, signals, nodes, request_pairs, graph_mode)
    _add_logging_edges(builder, signals, graph_mode)
    _add_boundary_edges(builder, signals, graph_mode)
    _add_orphan_node_edges(builder, signals, nodes)
    return builder.edges


def prune_edges(graph: dict[str, Any], signals: dict[str, Any], graph_mode: str) -> dict[str, Any]:
    """Remove duplicated or semantically invalid edges."""
    valid_request_pairs = set(_valid_request_pairs(signals))
    valid_response_pairs = {(entry_id, actor_id) for actor_id, entry_id in valid_request_pairs}
    node_ids = {node["id"] for node in graph["nodes"]}
    seen = set()
    pruned = []

    for edge in graph["edges"]:
        key = (edge.get("source"), edge.get("target"), edge.get("label"))
        if key in seen:
            continue
        seen.add(key)
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            continue
        if edge.get("source", "").startswith("actor_") and edge.get("target", "").startswith("entry_"):
            if (edge["source"], edge["target"]) not in valid_request_pairs:
                continue
        if edge.get("label") in {"Response", "Validated response"} and edge.get("target", "").startswith("actor_"):
            if (edge["source"], edge["target"]) not in valid_response_pairs:
                continue
        if graph_mode == "compact" and edge.get("label") == "Telemetry / audit event":
            compact_telemetry_sources = {"llm_gateway", "process_tool_layer"}
            if edge.get("source") not in compact_telemetry_sources:
                continue
        pruned.append(edge)

    graph["edges"] = pruned
    return graph


def layout_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Apply stable deterministic node positions."""
    offsets = {lane: 0 for lane in LANE_X}
    for node in sorted(graph["nodes"], key=lambda item: (_lane_for_node(item), item["id"])):
        lane = _lane_for_node(node)
        node["position"] = {
            "x": LANE_X[lane],
            "y": LANE_START_Y[lane] + offsets[lane] * LANE_SPACING,
        }
        offsets[lane] += 1
    return graph


def _extract_actors(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    mappings = [
        ("anonymous public internet users", "actor_public_user", "Public Internet User", "human"),
        ("authenticated public users", "actor_authenticated_user", "Authenticated User", "human"),
        ("internal employees only", "actor_internal_employee", "Internal Employee", "human"),
        ("administrators only", "actor_admin", "Administrator", "human"),
        ("local system processes only", "actor_local_process", "Local System Process", "system"),
    ]
    for value in _answer_values(answers, "Q2"):
        normalized = _normalize_text(value)
        for keyword, actor_id, label, kind in mappings:
            if keyword in normalized:
                _add_signal(signals["actors"], actor_id, label, kind, [_evidence("Q2", value)])

    if _answers_contain(answers, "Q3", ("third party integration",)):
        _add_signal(signals["actors"], "actor_third_party_system", "Third-party System", "system", _matching_evidence(answers, "Q3", ("third party integration",)))
    if _answers_contain(answers, "Q48", ("webhook or callback endpoint",)):
        _add_signal(signals["actors"], "actor_external_service", "External Service", "system", _matching_evidence(answers, "Q48", ("webhook or callback endpoint",)))


def _extract_entry_points(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    mappings = [
        (("web based chat interface", "public chat page"), "entry_web_chat", "Web Chat Interface", "web"),
        (("rest api endpoint",), "entry_rest_api", "REST API Endpoint", "api"),
        (("internal service to service calls",), "entry_internal_service", "Internal Service Call", "internal_api"),
        (("cli or local scripts",), "entry_cli", "CLI or Local Script", "cli"),
        (("third party integration",), "entry_third_party_integration", "Third-party Integration", "integration"),
        (("authenticated user dashboard",), "entry_user_dashboard", "User Dashboard", "web"),
        (("admin operator panel",), "entry_admin_panel", "Admin / Operator Panel", "admin"),
        (("webhook or callback endpoint",), "entry_webhook", "Webhook / Callback Endpoint", "webhook"),
        (("embedded widget or iframe",), "entry_embedded_widget", "Embedded Widget", "web"),
    ]
    for question_id in ("Q3", "Q48"):
        for value in _answer_values(answers, question_id):
            normalized = _normalize_text(value)
            for keywords, entry_id, label, kind in mappings:
                if any(keyword in normalized for keyword in keywords):
                    _add_signal(signals["entry_points"], entry_id, label, kind, [_evidence(question_id, value)])


def _extract_core_processes(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    q7_evidence = _matching_evidence(answers, "Q7", ("input filtering", "prompt templating", "routing classification"))
    if q7_evidence:
        _add_signal(signals["preprocessing"], "process_preprocessor", "Input Processing Layer", "preprocessor", q7_evidence)

    rag_evidence = []
    rag_evidence.extend(_matching_evidence(answers, "Q7", ("rag augmentation",)))
    rag_evidence.extend(_matching_evidence(answers, "Q5", ("retrieved internal documents",)))
    rag_evidence.extend(
        _evidence("Q8", value)
        for value in _answer_values(answers, "Q8")
        if not _is_negative_answer(value) and not _contains_any(value, ("no rag",))
    )
    if rag_evidence:
        signals["rag"]["enabled"] = True
        signals["rag"]["evidence"] = list(dict.fromkeys(rag_evidence))

    q11_evidence = [
        _evidence("Q11", value)
        for value in _answer_values(answers, "Q11")
        if not _is_negative_answer(value)
    ]
    q18_evidence = _matching_evidence(answers, "Q18", ("different models", "fallback", "routing"))
    if q11_evidence or q18_evidence:
        _add_signal(signals["processes"], "process_orchestrator", "Orchestration Layer", "orchestrator", q11_evidence + q18_evidence)

    tool_layer_evidence = []
    tool_layer_evidence.extend(_evidence("Q12", value) for value in _answer_values(answers, "Q12") if not _is_negative_answer(value))
    tool_layer_evidence.extend(_evidence("Q15", value) for value in _answer_values(answers, "Q15") if not _contains_any(value, ("generate text responses only",)))
    tool_layer_evidence.extend(_evidence("Q79", value) for value in _answer_values(answers, "Q79") if not _contains_any(value, ("no sensitive business flows",)))
    if tool_layer_evidence:
        _add_signal(signals["processes"], "process_tool_layer", "Tool / Action Layer", "tool_layer", tool_layer_evidence, role="tool")

    if _answers_contain(answers, "Q14", ("directly", "via backend")) or any(
        _answer_has_external_api_content(answers, question_id) for question_id in ("Q60", "Q61", "Q62", "Q63")
    ):
        evidence = _matching_evidence(answers, "Q14", ("directly", "via backend"))
        for question_id in ("Q60", "Q61", "Q62", "Q63"):
            evidence.extend(
                _evidence(question_id, value)
                for value in _answer_values(answers, question_id)
                if _answer_has_external_api_value(value)
            )
        _add_signal(signals["processes"], "process_api_connector", "API Connector", "api_connector", evidence)

    validator_evidence = []
    validator_evidence.extend(_matching_evidence(answers, "Q31", ("rule based", "schema validation", "human in the loop", "technical validation")))
    validator_evidence.extend(_matching_evidence(answers, "Q65", ("strict schema", "allowlists")))
    validator_evidence.extend(_matching_evidence(answers, "Q66", ("strict blocking", "allowlisting")))
    if validator_evidence:
        _add_signal(signals["processes"], "process_output_validator", "Output Validation Layer", "output_validator", validator_evidence)

    logging_evidence = []
    logging_evidence.extend(_evidence("Q33", value) for value in _answer_values(answers, "Q33") if not _contains_any(value, ("no logging", "none", "unknown")))
    logging_evidence.extend(_evidence("Q74", value) for value in _answer_values(answers, "Q74") if not _contains_any(value, ("not logged", "none", "unknown")))
    if logging_evidence:
        signals["logging"]["enabled"] = True
        signals["logging"]["evidence"] = list(dict.fromkeys(logging_evidence))


def _extract_model(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    q17_values = _answer_values(answers, "Q17")
    signals["model"]["evidence"].extend(_evidence("Q17", value) for value in q17_values)
    if _answers_contain(answers, "Q17", ("third party cloud api",)):
        signals["model"]["hosting"] = "external"
        signals["model"]["provider_label"] = "Third-party LLM Provider"
    elif _answers_contain(answers, "Q17", ("hosted by external vendor",)):
        signals["model"]["hosting"] = "external"
        signals["model"]["provider_label"] = "External Private Model Provider"
    elif _answers_contain(answers, "Q17", ("hybrid deployment",)):
        signals["model"]["hosting"] = "external"
        signals["model"]["provider_label"] = "Hybrid / External Model Provider"
    elif _answers_contain(answers, "Q17", ("self hosted on internal infrastructure",)):
        signals["model"]["hosting"] = "self_hosted"


def _extract_data_stores(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    data_mappings = [
        ("Q8", "internal knowledge base", "store_knowledge_base", "Internal Knowledge Base", "knowledge_base"),
        ("Q8", "documentation", "store_documentation", "Documentation Store", "documentation"),
        ("Q8", "customer data", "store_customer_data", "Customer Data Store", "customer_data"),
        ("Q8", "source code", "store_source_code", "Source Code Repository", "source_code"),
        ("Q13", "vector db", "store_vector_db", "Vector Database", "vector_db"),
        ("Q13", "sql nosql", "store_database", "Application Database", "application_database"),
        ("Q13", "file storage", "store_file_storage", "File Storage", "file_storage"),
        ("Q13", "cloud storage", "store_cloud_storage", "Cloud Storage", "cloud_storage"),
    ]
    for question_id, keyword, node_id, label, kind in data_mappings:
        evidence = _matching_evidence(answers, question_id, (keyword,))
        if evidence:
            _add_signal(signals["data_stores"], node_id, label, kind, evidence)

    q10_evidence = [
        _evidence("Q10", value)
        for value in _answer_values(answers, "Q10")
        if not _is_negative_answer(value)
    ]
    if q10_evidence:
        _add_signal(signals["data_stores"], "store_conversation_history", "Conversation History Store", "conversation_history", q10_evidence)

    sensitive_evidence = [
        _evidence("Q24", value)
        for value in _answer_values(answers, "Q24")
        if not _contains_any(value, ("no sensitive data",))
    ]
    if sensitive_evidence:
        target_stores = _classification_targets(signals["data_stores"])
        if target_stores:
            for store in target_stores:
                store.setdefault("data_classification", [])
                store["data_classification"].extend(sensitive_evidence)
        else:
            _add_signal(signals["data_stores"], "store_sensitive_data", "Sensitive Data Store", "sensitive_data", sensitive_evidence)

    q43_values = _answer_values(answers, "Q43")
    if _answers_contain(answers, "Q43", ("indexing only",)):
        for store in signals["data_stores"]:
            if store["id"] in {"store_vector_db", "store_knowledge_base", "store_documentation", "store_customer_data"}:
                store.setdefault("metadata", {})["indexing"] = _matching_evidence(answers, "Q43", ("indexing only",))
    elif _answers_contain(answers, "Q43", ("training", "both indexing and training")):
        _add_signal(signals["data_stores"], "store_index_training_data", "Indexing / Training Data Store", "index_training", [_evidence("Q43", value) for value in q43_values])

    if _answers_contain(answers, "Q47", ("logs contain full prompts and responses",)):
        _add_signal(signals["data_stores"], "store_llm_logs", "LLM Logs", "logs", _matching_evidence(answers, "Q47", ("logs contain full prompts and responses",)))


def _extract_tools_and_actions(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    tool_mappings = [
        ("search", "tool_search", "Search Tool", "search"),
        ("database", "tool_database", "Database Tool", "database"),
        ("internal apis", "tool_internal_api", "Internal API Tool", "internal_api"),
        ("admin tools", "tool_admin", "Admin Tool", "admin"),
    ]
    for keyword, node_id, label, kind in tool_mappings:
        evidence = _matching_evidence(answers, "Q12", (keyword,))
        if evidence:
            _add_signal(signals["tools"], node_id, label, kind, evidence)

    action_specs = [
        ("Q15", "create or update tickets records", "business_ticketing", "Ticketing System", "ticketing"),
        ("Q15", "send emails or notifications", "business_notifications", "Notification System", "notifications"),
        ("Q15", "execute workflows or transactions", "business_workflow", "Workflow Engine", "workflow"),
        ("Q15", "modify system configurations", "business_configuration", "Configuration Management", "configuration"),
        ("Q79", "ticket escalation or priority changes", "business_ticketing", "Ticketing System", "ticketing"),
        ("Q79", "notifications or external messages", "business_notifications", "Notification System", "notifications"),
        ("Q79", "refunds or payments", "business_payments", "Payments or Refunds", "payments"),
        ("Q79", "account profile changes", "business_accounts", "Account Management", "accounts"),
        ("Q79", "approvals or entitlement changes", "business_approvals", "Approvals / Entitlements", "approvals"),
    ]
    for question_id, keyword, node_id, label, kind in action_specs:
        evidence = _matching_evidence(answers, question_id, (keyword,))
        if evidence:
            _add_signal(signals["business_actions"], node_id, label, kind, evidence)

    q39_evidence = [
        _evidence("Q39", value)
        for value in _answer_values(answers, "Q39")
        if not _contains_any(value, ("no informational use only", "unknown"))
    ]
    if q39_evidence:
        _add_signal(signals["business_actions"], "business_decisioning", "Automated Decision Flow", "decisioning", q39_evidence)


def _extract_external_services(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    if _answers_contain(answers, "Q5", ("external web content",)) or _answers_contain(answers, "Q6", ("web urls",)):
        evidence = _matching_evidence(answers, "Q5", ("external web content",))
        evidence.extend(_matching_evidence(answers, "Q6", ("web urls",)))
        _add_signal(signals["external_services"], "external_web", "External Web Content", "web_content", evidence)

    if _answers_contain(answers, "Q14", ("directly", "via backend")):
        _add_signal(signals["external_services"], "external_api", "External API", "external_api", _matching_evidence(answers, "Q14", ("directly", "via backend")))

    if _answers_contain(answers, "Q62", ("arbitrary urls or internal addresses may be reachable",)):
        _add_signal(signals["external_services"], "external_network", "External Network Destinations", "network", _matching_evidence(answers, "Q62", ("arbitrary urls or internal addresses may be reachable",)))


def _extract_trust_boundaries(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    boundary_specs = [
        (
            "boundary_public_internet",
            "Public Internet Boundary",
            "public_internet",
            _matching_evidence(answers, "Q2", ("anonymous public internet users", "authenticated public users"))
            + _matching_evidence(answers, "Q23", ("public internet to web application",)),
            ["actor_public_user", "actor_authenticated_user", "entry_web_chat", "entry_embedded_widget", "entry_rest_api"],
        ),
        (
            "boundary_web_to_internal_api",
            "Web to Internal API Boundary",
            "web_to_internal_api",
            _matching_evidence(answers, "Q23", ("web application to internal api",)),
            ["entry_web_chat", "entry_user_dashboard", "entry_rest_api", "process_orchestrator", "process_preprocessor"],
        ),
        (
            "boundary_internal_api_to_model",
            "Internal API to Model Service Boundary",
            "internal_api_to_model",
            _matching_evidence(answers, "Q23", ("internal api to model service",)),
            ["process_orchestrator", "process_preprocessor", "llm_gateway", "llm_runtime", "external_model_provider"],
        ),
        (
            "boundary_tenant",
            "Tenant Isolation Boundary",
            "tenant",
            _matching_evidence(answers, "Q40", ("multi tenant",))
            + _matching_evidence(answers, "Q23", ("cross tenant", "cross user")),
            ["actor_authenticated_user", "store_conversation_history", "store_customer_data", "store_vector_db"],
        ),
        (
            "boundary_external_provider",
            "External Provider Boundary",
            "external_provider",
            _matching_evidence(answers, "Q17", ("third party", "external vendor", "hybrid deployment")),
            ["llm_gateway", "external_model_provider"],
        ),
        (
            "boundary_external_api",
            "External API Boundary",
            "external_api",
            _matching_evidence(answers, "Q14", ("directly", "via backend"))
            + [
                _evidence(question_id, value)
                for question_id in ("Q60", "Q61", "Q62", "Q63")
                for value in _answer_values(answers, question_id)
                if _answer_has_external_api_value(value)
            ],
            ["process_api_connector", "external_api", "external_network", "external_web"],
        ),
    ]

    for node_id, label, boundary_type, evidence, contains in boundary_specs:
        if evidence:
            _add_signal(
                signals["trust_boundaries"],
                node_id,
                label,
                "trust_boundary",
                evidence,
                boundaryType=boundary_type,
                contains=contains,
            )


def _extract_controls(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    control_targets = {
        "Q25": ["entry_web_chat", "entry_rest_api", "entry_user_dashboard"],
        "Q26": ["entry_web_chat", "entry_rest_api", "process_orchestrator"],
        "Q27": ["process_rag_orchestrator"],
        "Q28": ["llm_gateway", "process_tool_layer"],
        "Q29": ["llm_gateway", "process_tool_layer", "process_rag_orchestrator"],
        "Q30": ["process_preprocessor"],
        "Q32": ["store_customer_data", "store_knowledge_base", "store_vector_db"],
        "Q34": ["entry_web_chat", "entry_rest_api"],
        "Q35": ["external_model_provider", "llm_runtime"],
        "Q36": ["store_vector_db"],
        "Q37": ["llm_gateway", "process_tool_layer"],
        "Q38": ["process_logging_monitoring"],
        "Q41": ["process_tool_layer", "tool_internal_api"],
        "Q42": ["entry_admin_panel", "business_configuration"],
        "Q44": ["process_tool_layer"],
        "Q45": ["process_tool_layer", "process_api_connector"],
        "Q46": ["store_conversation_history", "boundary_tenant"],
        "Q49": ["entry_web_chat", "entry_rest_api", "entry_user_dashboard"],
        "Q50": ["entry_web_chat", "entry_user_dashboard", "entry_rest_api"],
        "Q51": ["entry_web_chat", "entry_user_dashboard"],
        "Q52": ["entry_rest_api"],
        "Q53": ["tool_database", "tool_internal_api"],
        "Q54": ["tool_database", "tool_internal_api"],
        "Q55": ["tool_internal_api", "tool_admin"],
        "Q56": ["tool_internal_api", "process_tool_layer"],
        "Q57": ["process_tool_layer"],
        "Q58": ["tool_internal_api", "process_api_connector"],
        "Q59": ["tool_internal_api", "process_api_connector"],
        "Q75": ["process_tool_layer", "process_api_connector"],
        "Q76": ["process_output_validator"],
        "Q77": ["entry_rest_api", "process_tool_layer"],
        "Q78": ["process_tool_layer"],
        "Q80": ["process_tool_layer", "business_approvals"],
    }

    for question_id, targets in control_targets.items():
        for value in _answer_values(answers, question_id):
            control = {
                "question_id": question_id,
                "answer": value,
                "meaning": _control_meaning(question_id),
                "target_node_ids": targets,
            }
            signals["controls"].append(control)


def _extract_warnings_and_assumptions(signals: dict[str, Any], answers: dict[str, Any]) -> None:
    if not signals["actors"]:
        signals["warnings"].append("No actor could be inferred from Q2.")
    if not signals["entry_points"]:
        signals["warnings"].append("No entry point could be inferred from Q3 or Q48.")
    if not _answer_values(answers, "Q17"):
        signals["warnings"].append("No model hosting answer is available in Q17.")
    if signals["rag"]["enabled"] and not _rag_store_ids(signals):
        signals["warnings"].append("RAG is inferred but no RAG data source/store is present.")
    if _has_signal(signals["processes"], "process_tool_layer") and not (signals["tools"] or signals["business_actions"]):
        signals["warnings"].append("Tool layer exists but no specific tool target exists.")
    if _answers_contain(answers, "Q14", ("directly",)):
        signals["warnings"].append("Direct external API access by the LLM or tool environment is inferred.")
    for question_id in ("Q2", "Q3", "Q8", "Q11", "Q12", "Q14", "Q17", "Q31", "Q33", "Q40", "Q47"):
        if _answers_contain(answers, question_id, ("unknown",)):
            signals["warnings"].append(f"{question_id} is Unknown; static mapping may be incomplete.")

    if signals["model"]["has_llm"]:
        signals["assumptions"].append("LLM Gateway / Model Adapter represents the logical model integration point.")
    if signals["model"].get("hosting") == "external":
        signals["assumptions"].append("External model provider is separated from the logical LLM gateway.")
    if any(control["question_id"] == "Q30" for control in signals["controls"]) and not _has_signal(signals["preprocessing"], "process_preprocessor"):
        signals["assumptions"].append("Q30 is retained as control metadata and does not create a preprocessing node by itself.")


def _add_core_processing_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    if builder.has("process_preprocessor"):
        next_node = _first_existing(builder, ["process_orchestrator", "process_rag_orchestrator", "llm_gateway"])
        if next_node:
            builder.add("process_preprocessor", next_node, "Prepared prompt", _evidence_for(nodes, "process_preprocessor", next_node))

    if builder.has("process_orchestrator"):
        next_node = _first_existing(builder, ["process_rag_orchestrator", "llm_gateway"])
        if next_node:
            builder.add("process_orchestrator", next_node, "Orchestrated request", _evidence_for(nodes, "process_orchestrator", next_node))

    if not builder.has("process_preprocessor") and not builder.has("process_orchestrator") and builder.has("process_rag_orchestrator"):
        builder.add("process_rag_orchestrator", "llm_gateway", "Prompt + retrieved context", _evidence_for(nodes, "process_rag_orchestrator", "llm_gateway"))


def _add_model_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    if not builder.has("llm_gateway"):
        return
    if builder.has("external_model_provider"):
        builder.add("llm_gateway", "external_model_provider", "Model API request", _evidence_for(nodes, "llm_gateway", "external_model_provider"))
        builder.add("external_model_provider", "llm_gateway", "Model response", _evidence_for(nodes, "external_model_provider", "llm_gateway"))
    elif builder.has("llm_runtime"):
        builder.add("llm_gateway", "llm_runtime", "Model invocation", _evidence_for(nodes, "llm_gateway", "llm_runtime"))
        builder.add("llm_runtime", "llm_gateway", "Model response", _evidence_for(nodes, "llm_runtime", "llm_gateway"))


def _add_rag_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    if not builder.has("process_rag_orchestrator"):
        return
    for store_id in sorted(_rag_store_ids(signals)):
        if builder.has(store_id):
            builder.add("process_rag_orchestrator", store_id, "Retrieval query", _evidence_for(nodes, "process_rag_orchestrator", store_id))
            builder.add(store_id, "process_rag_orchestrator", "Retrieved context", _evidence_for(nodes, store_id, "process_rag_orchestrator"))
    if builder.has("llm_gateway"):
        builder.add("process_rag_orchestrator", "llm_gateway", "Prompt + retrieved context", _evidence_for(nodes, "process_rag_orchestrator", "llm_gateway"))


def _add_tool_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    if not builder.has("process_tool_layer"):
        return
    if builder.has("llm_gateway"):
        builder.add("llm_gateway", "process_tool_layer", "Tool request", _evidence_for(nodes, "llm_gateway", "process_tool_layer"))

    for tool_id in ("tool_search", "tool_database", "tool_internal_api", "tool_admin"):
        if builder.has(tool_id):
            builder.add("process_tool_layer", tool_id, "Invoke tool", _evidence_for(nodes, "process_tool_layer", tool_id))

    for target_id in ("store_knowledge_base", "store_documentation", "store_source_code", "store_vector_db", "store_file_storage", "store_cloud_storage"):
        if builder.has("tool_search") and builder.has(target_id):
            builder.add("tool_search", target_id, "Search query", _evidence_for(nodes, "tool_search", target_id))

    for target_id in ("store_database", "store_customer_data", "store_file_storage", "store_cloud_storage"):
        if builder.has("tool_database") and builder.has(target_id):
            label = "Storage operation" if target_id in {"store_file_storage", "store_cloud_storage"} else "Database operation"
            builder.add("tool_database", target_id, label, _evidence_for(nodes, "tool_database", target_id))

    for business_id in ("business_ticketing", "business_notifications", "business_workflow", "business_accounts", "business_payments", "business_approvals", "business_decisioning"):
        if builder.has("tool_internal_api") and builder.has(business_id):
            builder.add("tool_internal_api", business_id, "Business API call", _evidence_for(nodes, "tool_internal_api", business_id))

    if builder.has("tool_admin") and builder.has("business_configuration"):
        builder.add("tool_admin", "business_configuration", "Admin configuration change", _evidence_for(nodes, "tool_admin", "business_configuration"))

    if builder.has("llm_gateway"):
        builder.add("process_tool_layer", "llm_gateway", "Tool result", _evidence_for(nodes, "process_tool_layer", "llm_gateway"))


def _add_external_api_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    if builder.has("external_web"):
        target = "process_rag_orchestrator" if builder.has("process_rag_orchestrator") else "llm_gateway"
        if builder.has(target):
            builder.add("external_web", target, "Untrusted retrieved content", _evidence_for(nodes, "external_web", target))

    if not builder.has("external_api"):
        return

    via_backend = any("Via backend" in item for signal in signals["external_services"] if signal["id"] == "external_api" for item in signal.get("evidence", []))
    direct = any("Directly" in item for signal in signals["external_services"] if signal["id"] == "external_api" for item in signal.get("evidence", []))

    if via_backend and builder.has("process_api_connector"):
        source = _first_existing(builder, ["process_tool_layer", "process_orchestrator", "llm_gateway"])
        if source:
            builder.add(source, "process_api_connector", "API call request", _evidence_for(nodes, source, "process_api_connector"))
        builder.add("process_api_connector", "external_api", "Outbound API call", _evidence_for(nodes, "process_api_connector", "external_api"))
    elif direct:
        source = "process_tool_layer" if builder.has("process_tool_layer") else "llm_gateway"
        if builder.has(source):
            builder.add(source, "external_api", "Direct external API call", _evidence_for(nodes, source, "external_api"))

    if builder.has("external_network") and builder.has("process_api_connector"):
        builder.add("process_api_connector", "external_network", "Network fetch", _evidence_for(nodes, "process_api_connector", "external_network"))


def _add_output_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]], request_pairs: list[tuple[str, str]], graph_mode: str) -> None:
    if not builder.has("llm_gateway"):
        return
    response_pairs = request_pairs
    if graph_mode == "compact":
        response_pairs = [
            (actor_id, entry_id)
            for actor_id, entry_id in request_pairs
            if actor_id not in {"actor_third_party_system", "actor_external_service"}
        ]
    output_node = "process_output_validator" if builder.has("process_output_validator") else None
    if output_node:
        builder.add("llm_gateway", output_node, "Model output", _evidence_for(nodes, "llm_gateway", output_node))
        for _, entry_id in sorted(set(response_pairs)):
            builder.add(output_node, entry_id, "Validated response", _evidence_for(nodes, output_node, entry_id))
    else:
        for _, entry_id in sorted(set(response_pairs)):
            builder.add("llm_gateway", entry_id, "Model output", _evidence_for(nodes, "llm_gateway", entry_id))

    for actor_id, entry_id in response_pairs:
        builder.add(entry_id, actor_id, "Response", _evidence_for(nodes, entry_id, actor_id))


def _add_logging_edges(builder: "_EdgeBuilder", signals: dict[str, Any], graph_mode: str) -> None:
    if not builder.has("process_logging_monitoring"):
        return
    logging_evidence = signals.get("logging", {}).get("evidence") or []
    sources = ["llm_gateway"]
    if graph_mode == "detailed":
        sources = ["process_preprocessor", "process_orchestrator", "process_rag_orchestrator", "llm_gateway", "process_tool_layer", "process_api_connector", "process_output_validator"]
    for source in sources:
        if builder.has(source):
            builder.add(source, "process_logging_monitoring", "Telemetry / audit event", logging_evidence)
    if builder.has("store_llm_logs"):
        log_store_evidence = logging_evidence + _node_evidence(builder.nodes, "store_llm_logs")
        builder.add("process_logging_monitoring", "store_llm_logs", "Prompt/response logs", log_store_evidence)


def _add_boundary_edges(builder: "_EdgeBuilder", signals: dict[str, Any], graph_mode: str) -> None:
    if graph_mode != "detailed":
        return
    for boundary in signals["trust_boundaries"]:
        boundary_id = boundary["id"]
        for contained_id in boundary.get("contains", []):
            if builder.has(boundary_id) and builder.has(contained_id):
                builder.add(boundary_id, contained_id, "Contains", boundary.get("evidence") or [])


def _add_orphan_node_edges(builder: "_EdgeBuilder", signals: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    """Attach otherwise isolated architecture nodes without inventing dense cross-products."""
    for node in nodes:
        node_id = node["id"]
        data = node.get("data") or {}
        if data.get("nodeType") == "trust_boundary" or _has_incident_edge(builder, node_id):
            continue

        anchor = _orphan_anchor(builder, node)
        if not anchor:
            continue
        source, target, label = anchor
        builder.add(source, target, label, _evidence_for(nodes, source, target))


def _has_incident_edge(builder: "_EdgeBuilder", node_id: str) -> bool:
    return any(edge.get("source") == node_id or edge.get("target") == node_id for edge in builder.edges)


def _orphan_anchor(builder: "_EdgeBuilder", node: dict[str, Any]) -> tuple[str, str, str] | None:
    node_id = node["id"]
    data = node.get("data") or {}
    role = data.get("role")
    node_type = data.get("nodeType")
    kind = data.get("kind")

    if role == "actor":
        entry = _first_existing(builder, ["entry_web_chat", "entry_user_dashboard", "entry_rest_api", "entry_internal_service", "entry_cli", "entry_webhook"])
        return (node_id, entry, _request_label(node_id)) if entry else None

    if node_id.startswith("entry_"):
        backend = _first_existing(builder, ["process_preprocessor", "process_orchestrator", "process_rag_orchestrator", "llm_gateway"])
        return (node_id, backend, "LLM request") if backend else None

    if node_type == "database":
        if kind in {"file_storage", "cloud_storage"} and builder.has("process_tool_layer"):
            return ("process_tool_layer", node_id, "Storage operation")
        source = _first_existing(builder, ["process_rag_orchestrator", "tool_database", "process_orchestrator", "process_preprocessor", "process_api_connector", "llm_gateway"])
        if not source:
            return None
        label = "Retrieval query" if source == "process_rag_orchestrator" else "Data operation"
        return (source, node_id, label)

    if role == "tool":
        source = _first_existing(builder, ["process_tool_layer", "llm_gateway"])
        return (source, node_id, "Invoke tool") if source else None

    if role == "action" or node_type == "external_api":
        source = _first_existing(builder, ["tool_internal_api", "process_api_connector", "process_tool_layer", "llm_gateway"])
        return (source, node_id, "Outbound API call") if source else None

    if node_type == "llm":
        source = _first_existing(builder, ["llm_gateway", "process_orchestrator", "process_preprocessor"])
        if source and source != node_id:
            return (source, node_id, "Model invocation")
        return None

    source = _first_existing(builder, ["process_preprocessor", "process_orchestrator", "llm_gateway"])
    if source and source != node_id:
        return (source, node_id, "Internal data flow")
    target = _first_existing(builder, ["llm_gateway", "process_output_validator"])
    if target and target != node_id:
        return (node_id, target, "Internal data flow")
    return None


class _NodeBuilder:
    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def add_signal_node(self, signal: dict[str, Any], node_type: str, role: str) -> dict[str, Any]:
        return self.add_node(
            signal["id"],
            signal["label"],
            signal.get("nodeType") or node_type,
            signal.get("role") or role,
            signal.get("evidence") or [],
            signal,
        )

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        role: str,
        evidence: list[str],
        signal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = next((node for node in self.nodes if node["id"] == node_id), None)
        if existing:
            _merge_data(existing["data"], evidence, signal)
            return existing

        data = {
            "label": label,
            "nodeType": node_type,
            "role": role,
            "source": "static_mapper",
            "evidence": list(dict.fromkeys(evidence)),
        }
        if signal:
            for key in ("kind", "boundaryType", "contains", "metadata", "data_classification"):
                if key in signal:
                    data[key] = signal[key]

        node = {"id": node_id, "type": "custom", "position": {"x": 0, "y": 0}, "data": data}
        self.nodes.append(node)
        self._ids.add(node_id)
        return node


class _EdgeBuilder:
    def __init__(self, nodes: list[dict[str, Any]]) -> None:
        self.nodes = nodes
        self.node_ids = {node["id"] for node in nodes}
        self.edges: list[dict[str, Any]] = []
        self._keys: set[tuple[str, str, str]] = set()

    def has(self, node_id: str) -> bool:
        return node_id in self.node_ids

    def add(self, source: str, target: str, label: str, evidence: list[str]) -> None:
        if source == target or source not in self.node_ids or target not in self.node_ids:
            return
        key = (source, target, label)
        if key in self._keys:
            return
        self.edges.append(
            {
                "id": f"edge_{_slug(source)}_to_{_slug(target)}_{_slug(label)}",
                "source": source,
                "target": target,
                "label": label,
                "data": {
                    "source": "static_mapper",
                    "evidence": list(dict.fromkeys([item for item in evidence if item])),
                },
            }
        )
        self._keys.add(key)


def _valid_request_pairs(signals: dict[str, Any]) -> list[tuple[str, str]]:
    actors = {signal["id"] for signal in signals["actors"]}
    entries = {signal["id"] for signal in signals["entry_points"]}
    pairs = []

    def add(actor_id: str, entry_id: str) -> None:
        if actor_id in actors and entry_id in entries and (actor_id, entry_id) not in pairs:
            pairs.append((actor_id, entry_id))

    for entry_id in ("entry_web_chat", "entry_embedded_widget"):
        add("actor_public_user", entry_id)
        add("actor_authenticated_user", entry_id)

    if "entry_rest_api" in entries:
        if "actor_authenticated_user" in actors:
            add("actor_authenticated_user", "entry_rest_api")
        if _no_auth_or_public_api(signals):
            add("actor_public_user", "entry_rest_api")

    add("actor_authenticated_user", "entry_user_dashboard")
    add("actor_admin", "entry_admin_panel")
    add("actor_internal_employee", "entry_user_dashboard")
    add("actor_internal_employee", "entry_internal_service")
    add("actor_internal_employee", "entry_cli")
    add("actor_local_process", "entry_internal_service")
    add("actor_local_process", "entry_cli")
    add("actor_third_party_system", "entry_third_party_integration")
    add("actor_third_party_system", "entry_webhook")
    add("actor_external_service", "entry_webhook")

    if "actor_admin" in actors and "entry_admin_panel" not in entries and entries == {"entry_web_chat"}:
        add("actor_admin", "entry_web_chat")

    return sorted(pairs)


def _no_auth_or_public_api(signals: dict[str, Any]) -> bool:
    for control in signals["controls"]:
        if control["question_id"] == "Q25" and _contains_any(control["answer"], ("no authentication required",)):
            return True
    return False


def _request_label(actor_id: str) -> str:
    if actor_id == "actor_authenticated_user":
        return "Authenticated request"
    if actor_id == "actor_admin":
        return "Admin operation"
    if actor_id in {"actor_third_party_system", "actor_external_service"}:
        return "Integration request"
    return "User prompt / request"


def _first_existing(builder: _EdgeBuilder, node_ids: list[str]) -> str | None:
    return next((node_id for node_id in node_ids if builder.has(node_id)), None)


def _evidence_for(nodes: list[dict[str, Any]], *node_ids: str) -> list[str]:
    by_id = {node["id"]: node for node in nodes}
    evidence: list[str] = []
    for node_id in node_ids:
        evidence.extend((by_id.get(node_id, {}).get("data") or {}).get("evidence") or [])
    return list(dict.fromkeys(evidence))


def _node_evidence(nodes: list[dict[str, Any]], node_id: str) -> list[str]:
    return _evidence_for(nodes, node_id)


def _clean_boundary_contains(nodes: list[dict[str, Any]]) -> None:
    node_ids = {node["id"] for node in nodes}
    for node in nodes:
        data = node.get("data") or {}
        contains = data.get("contains")
        if isinstance(contains, list):
            data["contains"] = [node_id for node_id in contains if node_id in node_ids]


def _finalize_metadata_controls(controls: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    node_ids = {node["id"] for node in nodes}
    resolved = []
    unresolved = []

    for control in controls:
        target_ids = control.get("target_node_ids") or []
        existing_targets = [node_id for node_id in target_ids if node_id in node_ids]
        missing_targets = [node_id for node_id in target_ids if node_id not in node_ids]

        if existing_targets:
            resolved.append({**control, "target_node_ids": existing_targets})
        else:
            resolved.append({**control, "target_node_ids": []})

        if missing_targets:
            unresolved.append(
                {
                    "question_id": control.get("question_id"),
                    "answer": control.get("answer"),
                    "missing_target_node_ids": missing_targets,
                }
            )

    return resolved, unresolved


def _attach_controls(nodes: list[dict[str, Any]], signals: dict[str, Any]) -> None:
    by_id = {node["id"]: node for node in nodes}
    for control in signals["controls"]:
        for target_id in control.get("target_node_ids", []):
            node = by_id.get(target_id)
            if not node:
                continue
            node["data"].setdefault("controls", []).append(
                {
                    "question_id": control["question_id"],
                    "answer": control["answer"],
                    "meaning": control["meaning"],
                }
            )


def _merge_data(data: dict[str, Any], evidence: list[str], signal: dict[str, Any] | None) -> None:
    data["evidence"] = list(dict.fromkeys((data.get("evidence") or []) + evidence))
    if not signal:
        return
    for key in ("metadata", "data_classification"):
        if key in signal:
            if isinstance(signal[key], dict):
                data.setdefault(key, {}).update(signal[key])
            elif isinstance(signal[key], list):
                data.setdefault(key, [])
                data[key].extend(item for item in signal[key] if item not in data[key])


def _classification_targets(data_stores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"store_customer_data", "store_database", "store_knowledge_base", "store_documentation", "store_conversation_history"}
    targets = [store for store in data_stores if store["id"] in priority]
    return targets or data_stores


def _rag_store_ids(signals: dict[str, Any]) -> set[str]:
    rag_ids = {
        "store_knowledge_base",
        "store_documentation",
        "store_customer_data",
        "store_source_code",
        "store_vector_db",
        "store_file_storage",
        "store_cloud_storage",
    }
    return {signal["id"] for signal in signals["data_stores"] if signal["id"] in rag_ids}


def _has_signal(signals: list[dict[str, Any]], signal_id: str) -> bool:
    return any(signal["id"] == signal_id for signal in signals)


def _add_signal(target: list[dict[str, Any]], signal_id: str, label: str, kind: str, evidence: list[str], **extra: Any) -> None:
    existing = next((item for item in target if item["id"] == signal_id), None)
    clean_evidence = list(dict.fromkeys([item for item in evidence if item]))
    if existing:
        existing["evidence"] = list(dict.fromkeys(existing.get("evidence", []) + clean_evidence))
        for key, value in extra.items():
            if value:
                existing[key] = value
        return
    target.append({"id": signal_id, "label": label, "kind": kind, "evidence": clean_evidence, **extra})


def _control_meaning(question_id: str) -> str:
    meanings = {
        "Q30": "Prompt injection safeguard evidence; do not create standalone DFD node.",
        "Q40": "Tenant architecture evidence; tenant boundary may be created separately.",
        "Q80": "Approval or confirmation control for sensitive actions.",
    }
    return meanings.get(question_id, "Control/risk evidence attached to existing architecture nodes.")


def _answer_has_external_api_content(answers: dict[str, Any], question_id: str) -> bool:
    return any(_answer_has_external_api_value(value) for value in _answer_values(answers, question_id))


def _answer_has_external_api_value(value: Any) -> bool:
    return not _contains_any(
        value,
        (
            "no third party api data used",
            "no external api content enters prompt context",
            "no arbitrary url fetching is possible",
            "no outbound network access",
            "not applicable",
        ),
    )


def _answers_contain(answers: dict[str, Any], question_id: str, needles: tuple[str, ...]) -> bool:
    return any(_contains_any(value, needles) for value in _answer_values(answers, question_id))


def _matching_evidence(answers: dict[str, Any], question_id: str, needles: tuple[str, ...]) -> list[str]:
    return [
        _evidence(question_id, value)
        for value in _answer_values(answers, question_id)
        if _contains_any(value, needles)
    ]


def _answer_values(answers: dict[str, Any], question_id: str) -> list[Any]:
    value = answers.get(question_id)
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _normalize_answer_keys(answers: dict[Any, Any]) -> dict[str, Any]:
    return {
        _normalize_question_id(key): value
        for key, value in answers.items()
        if _looks_like_question_id(key) and value not in (None, "", [])
    }


def _normalize_question_id(value: Any) -> str:
    match = re.fullmatch(r"\s*[Qq]?(\d+)\s*", str(value or ""))
    if match:
        return f"Q{int(match.group(1))}"
    return str(value or "").strip().upper()


def _looks_like_question_id(value: Any) -> bool:
    return bool(re.fullmatch(r"\s*[Qq]?\d+\s*", str(value or "")))


def _contains_any(value: Any, needles: tuple[str, ...]) -> bool:
    normalized = _normalize_text(value)
    return any(needle in normalized for needle in needles)


def _is_negative_answer(value: Any) -> bool:
    normalized = _normalize_text(value)
    return (
        normalized in {"none", "no", "no rag", "not applicable", "unknown"}
        or normalized.startswith("no ")
        or normalized.startswith("not applicable")
    )


def _normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _evidence(question_id: str, value: Any) -> str:
    return f"{question_id}: {value}"


def _lane_for_node(node: dict[str, Any]) -> str:
    node_id = node["id"]
    node_type = node.get("data", {}).get("nodeType")
    role = node.get("data", {}).get("role")
    if role == "actor":
        return "actor"
    if node_id.startswith("entry_"):
        return "entry"
    if node_type == "trust_boundary":
        return "boundary"
    if node_id in {"llm_gateway", "llm_runtime", "external_model_provider"}:
        return "llm"
    if node_type == "database":
        return "data"
    if node_id in {"process_logging_monitoring", "store_llm_logs"}:
        return "lower"
    if role in {"external", "action"} or node_type == "external_api":
        return "external"
    return "backend"


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
