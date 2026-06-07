import unittest

from app.services.static_dfd_mapper import build_static_dfd_from_answers


def _node_ids(graph):
    return {node["id"] for node in graph["nodes"]}


def _node(graph, node_id):
    return next(node for node in graph["nodes"] if node["id"] == node_id)


def _edges(graph):
    return {(edge["source"], edge["target"], edge["label"]) for edge in graph["edges"]}


def _edge(graph, source, target, label):
    return next(edge for edge in graph["edges"] if edge["source"] == source and edge["target"] == target and edge["label"] == label)


def _orphan_node_ids(graph):
    incident = {
        node_id
        for edge in graph["edges"]
        for node_id in (edge["source"], edge["target"])
    }
    return {
        node["id"]
        for node in graph["nodes"]
        if node["data"].get("nodeType") != "trust_boundary" and node["id"] not in incident
    }


def _consistency_answers():
    return {
        "Q2": ["Anonymous public internet users", "Authenticated public users"],
        "Q3": ["Web-based chat interface", "REST API endpoint", "Third-party integration"],
        "Q5": ["Retrieved internal documents", "External web content"],
        "Q6": ["Web URLs"],
        "Q7": ["Input filtering", "RAG augmentation"],
        "Q8": ["Internal knowledge base", "Customer data"],
        "Q10": "Per user",
        "Q11": "Framework",
        "Q12": ["Search", "Database", "Internal APIs"],
        "Q13": ["Vector DB", "SQL/NoSQL"],
        "Q14": "Via backend",
        "Q15": ["Create or update tickets/records"],
        "Q17": "Third-party cloud API",
        "Q23": [
            "Public internet to web application",
            "Web application to internal API",
            "Internal API to model service",
            "Cross-tenant or cross-user context boundary",
        ],
        "Q31": "Rule-based or schema validation",
        "Q33": "Prompt/response logging with monitoring",
        "Q40": "Multi-tenant with strong isolation",
        "Q47": "Logs contain full prompts and responses",
        "Q48": ["Authenticated user dashboard", "Webhook or callback endpoint"],
        "Q74": "Yes, with security alerts and privacy controls",
        "Q80": "Only high-risk actions require approval",
    }


class StaticDfdMapperTests(unittest.TestCase):
    def test_public_chatbot_graph_pairs_actors_to_valid_entries(self):
        graph = build_static_dfd_from_answers(
            {
                "Q2": ["Anonymous public internet users", "Authenticated public users", "Administrators only"],
                "Q3": ["Web-based chat interface", "REST API endpoint", "Third-party integration"],
                "Q48": [
                    "Public chat page",
                    "Authenticated user dashboard",
                    "Admin/operator panel",
                    "Webhook or callback endpoint",
                ],
            }
        )
        node_ids = _node_ids(graph)
        edges = _edges(graph)

        self.assertIn("actor_public_user", node_ids)
        self.assertIn("actor_authenticated_user", node_ids)
        self.assertIn("actor_admin", node_ids)
        self.assertTrue({"actor_third_party_system", "actor_external_service"} & node_ids)
        self.assertIn(("actor_public_user", "entry_web_chat", "User prompt / request"), edges)
        self.assertNotIn(("actor_public_user", "entry_admin_panel", "User prompt / request"), edges)
        self.assertNotIn(("actor_public_user", "entry_user_dashboard", "User prompt / request"), edges)
        self.assertNotIn(("actor_public_user", "entry_webhook", "User prompt / request"), edges)
        self.assertIn(("actor_admin", "entry_admin_panel", "Admin operation"), edges)
        self.assertNotIn(("entry_admin_panel", "actor_public_user", "Response"), edges)
        self.assertNotIn(("entry_user_dashboard", "actor_public_user", "Response"), edges)

    def test_rag_graph_routes_retrieval_through_rag_orchestrator(self):
        graph = build_static_dfd_from_answers(
            {
                "Q5": ["Retrieved internal documents"],
                "Q7": ["RAG augmentation"],
                "Q8": ["Internal knowledge base", "Customer data"],
                "Q13": ["Vector DB"],
            }
        )
        node_ids = _node_ids(graph)
        edges = _edges(graph)

        self.assertIn("process_rag_orchestrator", node_ids)
        self.assertIn("store_knowledge_base", node_ids)
        self.assertIn("store_customer_data", node_ids)
        self.assertIn("store_vector_db", node_ids)
        self.assertIn(("process_rag_orchestrator", "store_knowledge_base", "Retrieval query"), edges)
        self.assertIn(("store_knowledge_base", "process_rag_orchestrator", "Retrieved context"), edges)
        self.assertIn(("process_rag_orchestrator", "llm_gateway", "Prompt + retrieved context"), edges)

    def test_file_and_cloud_storage_are_connected_when_present(self):
        graph = build_static_dfd_from_answers(
            {
                "Q5": ["Retrieved internal documents"],
                "Q7": ["RAG augmentation"],
                "Q13": ["File storage", "Cloud storage"],
            }
        )
        node_ids = _node_ids(graph)
        edges = _edges(graph)

        self.assertIn("store_file_storage", node_ids)
        self.assertIn("store_cloud_storage", node_ids)
        self.assertIn(("process_rag_orchestrator", "store_file_storage", "Retrieval query"), edges)
        self.assertIn(("store_file_storage", "process_rag_orchestrator", "Retrieved context"), edges)
        self.assertIn(("process_rag_orchestrator", "store_cloud_storage", "Retrieval query"), edges)
        self.assertIn(("store_cloud_storage", "process_rag_orchestrator", "Retrieved context"), edges)
        self.assertNotIn("store_file_storage", _orphan_node_ids(graph))
        self.assertNotIn("store_cloud_storage", _orphan_node_ids(graph))

    def test_tool_routing_graph_avoids_tool_layer_to_every_store(self):
        graph = build_static_dfd_from_answers(
            {
                "Q12": ["Search", "Database", "Internal APIs"],
                "Q13": ["Vector DB", "SQL/NoSQL"],
                "Q15": ["Create or update tickets/records", "Send emails or notifications"],
                "Q79": ["Ticket escalation or priority changes", "Notifications or external messages"],
            }
        )
        node_ids = _node_ids(graph)
        edges = _edges(graph)

        self.assertIn("process_tool_layer", node_ids)
        self.assertIn("tool_search", node_ids)
        self.assertIn("tool_database", node_ids)
        self.assertIn("tool_internal_api", node_ids)
        self.assertIn("business_ticketing", node_ids)
        self.assertIn("business_notifications", node_ids)
        self.assertIn(("process_tool_layer", "tool_search", "Invoke tool"), edges)
        self.assertIn(("process_tool_layer", "tool_database", "Invoke tool"), edges)
        self.assertIn(("process_tool_layer", "tool_internal_api", "Invoke tool"), edges)
        self.assertIn(("tool_database", "store_database", "Database operation"), edges)
        self.assertIn(("tool_internal_api", "business_ticketing", "Business API call"), edges)
        self.assertNotIn(("process_tool_layer", "store_vector_db", "Tool/API action"), edges)
        self.assertNotIn(("process_tool_layer", "store_llm_logs", "Tool/API action"), edges)

    def test_external_model_provider_graph(self):
        graph = build_static_dfd_from_answers({"Q17": "Third-party cloud API"})
        node_ids = _node_ids(graph)
        edges = _edges(graph)

        self.assertIn("llm_gateway", node_ids)
        self.assertIn("external_model_provider", node_ids)
        self.assertIn("boundary_external_provider", node_ids)
        self.assertIn(("llm_gateway", "external_model_provider", "Model API request"), edges)
        self.assertIn(("external_model_provider", "llm_gateway", "Model response"), edges)

    def test_self_hosted_model_graph(self):
        graph = build_static_dfd_from_answers({"Q17": "Self-hosted on internal infrastructure"})
        node_ids = _node_ids(graph)

        self.assertIn("llm_gateway", node_ids)
        self.assertIn("llm_runtime", node_ids)
        self.assertNotIn("external_model_provider", node_ids)
        self.assertNotIn("boundary_external_provider", node_ids)

    def test_q30_control_metadata_attaches_to_existing_preprocessor(self):
        graph = build_static_dfd_from_answers({"Q7": ["Input filtering"], "Q30": "Basic input filtering only"})
        node_ids = _node_ids(graph)
        preprocessor = _node(graph, "process_preprocessor")
        controls = preprocessor["data"].get("controls") or []

        self.assertIn("process_preprocessor", node_ids)
        self.assertTrue(any(control["question_id"] == "Q30" for control in controls))
        self.assertFalse(any("prompt_injection" in node_id for node_id in node_ids))

    def test_q30_without_q7_does_not_create_preprocessor(self):
        graph = build_static_dfd_from_answers({"Q30": "Basic input filtering only"})
        node_ids = _node_ids(graph)

        self.assertNotIn("process_preprocessor", node_ids)
        self.assertTrue(any(control["question_id"] == "Q30" for control in graph["metadata"]["controls"]))

    def test_q40_tenant_boundary(self):
        graph = build_static_dfd_from_answers({"Q40": "Multi-tenant with strong isolation"})
        node_ids = _node_ids(graph)
        boundary = _node(graph, "boundary_tenant")

        self.assertIn("boundary_tenant", node_ids)
        self.assertEqual(boundary["data"]["boundaryType"], "tenant")

    def test_wrapped_answers_by_flow_id_matches_flat_q_id_input(self):
        flat = {
            "Q2": ["Anonymous public internet users"],
            "Q3": ["Web-based chat interface"],
        }
        wrapped = {
            "schema_version": "llmsec.adaptive.v1",
            "scenario_name": "Do not use this for graph structure",
            "answers_by_flow_id": flat,
        }

        self.assertEqual(build_static_dfd_from_answers(flat), build_static_dfd_from_answers(wrapped))

    def test_mapper_returns_one_canonical_graph(self):
        answers = {
            "Q1": "Customer support assistant",
            "Q2": ["Anonymous public internet users", "Authenticated public users", "Administrators only"],
            "Q3": ["Web-based chat interface", "REST API endpoint", "Third-party integration"],
            "Q5": ["Direct user prompts", "Retrieved internal documents", "API or database records"],
            "Q6": ["User text input only", "Web URLs", "Email or ticket data"],
            "Q7": ["Input filtering", "Prompt templating", "RAG augmentation"],
            "Q8": ["Internal knowledge base", "Documentation", "Customer data"],
            "Q10": "Per user",
            "Q11": "Framework",
            "Q12": ["Search", "Database", "Internal APIs"],
            "Q13": ["Vector DB", "SQL/NoSQL", "Cloud storage"],
            "Q14": "Via backend",
            "Q15": ["Generate text responses only", "Create or update tickets/records", "Send emails or notifications"],
            "Q17": "Third-party cloud API",
            "Q23": ["Public internet to web application", "Web application to internal API", "Internal API to model service"],
            "Q31": "Rule-based or schema validation",
            "Q33": "Prompt/response logging with monitoring",
            "Q47": "Logs contain full prompts and responses",
            "Q48": ["Public chat page", "Authenticated user dashboard", "Admin/operator panel", "Webhook or callback endpoint"],
        }

        graph = build_static_dfd_from_answers(answers)
        legacy_arg_graph = build_static_dfd_from_answers(answers, graph_mode="unused")
        edges = _edges(graph)

        self.assertEqual(graph, legacy_arg_graph)
        self.assertEqual(graph["metadata"]["graph_mode"], "canonical")
        self.assertTrue(graph["metadata"]["canonical_graph"])
        self.assertNotIn("compact", graph)
        self.assertNotIn("detailed", graph)
        self.assertNotIn(("actor_public_user", "entry_admin_panel", "User prompt / request"), edges)
        self.assertNotIn(("actor_public_user", "entry_user_dashboard", "User prompt / request"), edges)
        self.assertNotIn(("actor_admin", "entry_webhook", "Admin operation"), edges)
        self.assertFalse(any(edge["label"] == "Contains" for edge in graph["edges"]))
        self.assertLess(len(graph["edges"]), 65)

    def test_numeric_question_ids_and_saved_answer_records_are_supported(self):
        numeric = build_static_dfd_from_answers({"1": "Customer support assistant", "2": ["Authenticated public users"], "3": ["REST API endpoint"]})
        saved = build_static_dfd_from_answers(
            {
                "answers": [
                    {"flow_id": "Q1", "answer": "Customer support assistant"},
                    {"flow_id": "Q2", "answer": ["Administrators only"]},
                    {"flow_id": "Q48", "answer": ["Admin/operator panel"]},
                ]
            }
        )

        self.assertIn("actor_authenticated_user", _node_ids(numeric))
        self.assertIn("entry_rest_api", _node_ids(numeric))
        self.assertIn("actor_admin", _node_ids(saved))
        self.assertIn("entry_admin_panel", _node_ids(saved))

    def test_unsupported_shape_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported input shape"):
            build_static_dfd_from_answers({"project": "demo"})

    def test_all_edges_have_evidence(self):
        graph = build_static_dfd_from_answers(_consistency_answers())
        empty_edges = [
            edge
            for edge in graph["edges"]
            if not (edge.get("data") or {}).get("evidence")
            and not (edge.get("data") or {}).get("technical")
        ]

        self.assertEqual(empty_edges, [])

    def test_consistency_graph_has_no_non_boundary_orphans(self):
        answers = {
            **_consistency_answers(),
            "Q13": ["Vector DB", "SQL/NoSQL", "File storage", "Cloud storage"],
        }
        graph = build_static_dfd_from_answers(answers)

        self.assertEqual(_orphan_node_ids(graph), set())
        self.assertEqual(graph["metadata"]["orphan_nodes"], [])

    def test_trust_boundary_contains_only_existing_nodes(self):
        graph = build_static_dfd_from_answers(_consistency_answers())
        node_ids = _node_ids(graph)
        self.assertIn("boundary_public_internet", node_ids)
        self.assertIn("boundary_internal_api_to_model", node_ids)
        for node in graph["nodes"]:
            if node["data"].get("nodeType") != "trust_boundary":
                continue
            for contained_id in node["data"].get("contains") or []:
                self.assertIn(contained_id, node_ids)

    def test_edges_target_existing_nodes(self):
        graph = build_static_dfd_from_answers(_consistency_answers())
        node_ids = _node_ids(graph)

        for edge in graph["edges"]:
            self.assertIn(edge["source"], node_ids)
            self.assertIn(edge["target"], node_ids)

    def test_metadata_controls_reference_existing_nodes_only(self):
        graph = build_static_dfd_from_answers(_consistency_answers())
        node_ids = _node_ids(graph)

        for control in graph["metadata"]["controls"]:
            for target_id in control.get("target_node_ids") or []:
                self.assertIn(target_id, node_ids)

    def test_missing_control_targets_move_to_unresolved_metadata(self):
        graph = build_static_dfd_from_answers({"Q80": "Only high-risk actions require approval"})
        unresolved = graph["metadata"]["unresolved_control_targets"]

        self.assertTrue(
            any(
                item["question_id"] == "Q80"
                and "business_approvals" in item["missing_target_node_ids"]
                for item in unresolved
            )
        )

    def test_q81_q82_enrich_existing_edge_metadata_without_new_nodes(self):
        base_answers = {
            "Q2": ["Authenticated public users"],
            "Q3": ["REST API endpoint"],
            "Q11": "Framework",
            "Q33": "Prompt/response logging with monitoring",
            "Q74": "Yes, with security alerts and privacy controls",
        }
        base_graph = build_static_dfd_from_answers(base_answers)
        enriched_graph = build_static_dfd_from_answers(
            {
                **base_answers,
                "Q81": ["Web application to backend/API"],
                "Q82": ["Browser to web application", "Logging or monitoring pipeline"],
            }
        )

        self.assertEqual(_node_ids(base_graph), _node_ids(enriched_graph))
        self.assertEqual(_edges(base_graph), _edges(enriched_graph))

        request_edge = _edge(enriched_graph, "actor_authenticated_user", "entry_rest_api", "Authenticated request")
        backend_edge = _edge(enriched_graph, "entry_rest_api", "process_orchestrator", "LLM request")
        logging_edge = _edge(enriched_graph, "llm_gateway", "process_logging_monitoring", "Audit log event")

        self.assertIn("Sensitive data", request_edge["data"]["badges"])
        self.assertTrue(request_edge["data"]["trust_boundary_crossed"])
        self.assertTrue(request_edge["data"]["crosses_trust_boundary"])
        self.assertEqual(request_edge["data"]["direction"], "request")
        self.assertEqual(request_edge["data"]["display_badges"], [])
        self.assertEqual(request_edge["data"]["visual_badges"], [])
        self.assertEqual(backend_edge["data"]["transport_security"], "unclear")
        self.assertEqual(backend_edge["data"]["transport_state"], "unclear")
        self.assertEqual(backend_edge["data"]["required_control"], "TLS")
        self.assertNotIn("TLS required", backend_edge["data"]["badges"])
        self.assertEqual(backend_edge["data"]["contains_sensitive_data"], "unknown")
        self.assertEqual(backend_edge["data"]["display_badges"], [])
        self.assertEqual(backend_edge["data"]["visual_badges"], [])
        self.assertIn("Sensitive logs", logging_edge["data"]["badges"])
        self.assertEqual(logging_edge["data"]["display_badges"], [])
        self.assertIn("Q82", request_edge["data"]["source_questions"])
        self.assertEqual(logging_edge["data"]["data_categories"], ["prompt", "response", "PII"])

    def test_q81_q82_combined_risk_on_same_edge(self):
        graph = build_static_dfd_from_answers(
            {
                "Q2": ["Authenticated public users"],
                "Q3": ["REST API endpoint"],
                "Q11": "Framework",
                "Q81": ["Web application to backend/API"],
                "Q82": ["Web application to backend/API"],
            }
        )
        edge = _edge(graph, "entry_rest_api", "process_orchestrator", "LLM request")

        self.assertEqual(edge["data"]["transport_security"], "unclear")
        self.assertEqual(edge["data"]["transport_state"], "unclear")
        self.assertEqual(edge["data"]["sensitive_data"], "sensitive")
        self.assertTrue(edge["data"]["contains_sensitive_data"])
        self.assertEqual(edge["data"]["required_control"], "TLS")
        self.assertEqual(edge["data"]["combined_risk"], "sensitive_data_over_unclear_transport")
        self.assertNotIn("TLS required", edge["data"]["badges"])
        self.assertEqual(edge["data"]["display_badges"], [])
        self.assertEqual(edge["data"]["visual_badges"], [])

    def test_response_and_trust_boundary_are_metadata_not_display_badges(self):
        graph = build_static_dfd_from_answers(
            {
                "Q2": ["Authenticated public users"],
                "Q3": ["REST API endpoint"],
                "Q11": "Framework",
            }
        )
        response_edge = _edge(graph, "entry_rest_api", "actor_authenticated_user", "Response")
        request_edge = _edge(graph, "actor_authenticated_user", "entry_rest_api", "Authenticated request")

        self.assertEqual(response_edge["data"]["direction"], "response")
        self.assertTrue(request_edge["data"]["trust_boundary_crossed"])
        self.assertIn("Trust boundary", request_edge["data"]["badges"])
        self.assertEqual(request_edge["data"]["display_badges"], [])
        self.assertEqual(response_edge["data"]["display_badges"], [])

    def test_q73_sets_transport_state_without_treating_tls_required_as_enforced(self):
        enforced = build_static_dfd_from_answers(
            {
                "Q2": ["Authenticated public users"],
                "Q3": ["REST API endpoint"],
                "Q11": "Framework",
                "Q73": "Yes, encryption is enforced end-to-end where applicable",
                "Q82": ["Web application to backend/API"],
            }
        )
        enforced_edge = _edge(enforced, "entry_rest_api", "process_orchestrator", "LLM request")
        self.assertEqual(enforced_edge["data"]["transport_state"], "enforced")
        self.assertEqual(enforced_edge["data"]["required_control"], "TLS")
        self.assertNotIn("TLS required", enforced_edge["data"]["badges"])

        unclear = build_static_dfd_from_answers(
            {
                "Q2": ["Authenticated public users"],
                "Q3": ["REST API endpoint"],
                "Q11": "Framework",
                "Q73": "Yes, encryption is enforced end-to-end where applicable",
                "Q81": ["Web application to backend/API"],
                "Q82": ["Web application to backend/API"],
            }
        )
        unclear_edge = _edge(unclear, "entry_rest_api", "process_orchestrator", "LLM request")
        self.assertEqual(unclear_edge["data"]["transport_state"], "unclear")
        self.assertEqual(unclear_edge["data"]["combined_risk"], "sensitive_data_over_unclear_transport")

    def test_no_default_telemetry_label_for_logging(self):
        graph = build_static_dfd_from_answers(
            {
                "Q17": "Third-party cloud API",
                "Q33": "Prompt/response logging with monitoring",
                "Q74": "Yes, with security alerts and privacy controls",
            }
        )

        self.assertIn(("llm_gateway", "process_logging_monitoring", "Audit log event"), _edges(graph))
        self.assertFalse(any("Telemetry" in edge["label"] for edge in graph["edges"]))


if __name__ == "__main__":
    unittest.main()
