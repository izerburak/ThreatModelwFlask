import unittest

from app.services.extract_to_reactflow import extract_to_reactflow, has_recognized_dfd_content


class ExtractToReactFlowTests(unittest.TestCase):
    def test_new_dfd_schema_produces_architecture_nodes_and_flows(self):
        extract = {
            "system_summary": {
                "purpose": "Developer documentation assistant",
                "exposure": "Internal employees only",
            },
            "dfd": {
                "actors": [
                    {
                        "id": "actor_1",
                        "name": "Internal Employee",
                        "type": "human",
                        "trust_zone": "internal",
                        "evidence": ["Q2"],
                    }
                ],
                "interfaces": [
                    {
                        "id": "interface_1",
                        "name": "REST API",
                        "type": "api",
                        "evidence": ["Q3"],
                    }
                ],
                "processes": [
                    {
                        "id": "process_1",
                        "name": "Backend API",
                        "type": "backend_api",
                        "description": "Internal service caller",
                        "evidence": ["Q9"],
                    },
                    {
                        "id": "process_2",
                        "name": "Model Service",
                        "type": "model_service",
                        "evidence": ["Q17"],
                    },
                ],
                "data_stores": [
                    {
                        "id": "store_1",
                        "name": "Knowledge Base",
                        "type": "knowledge_base",
                        "contains_sensitive_data": "Unknown",
                        "evidence": ["Q8"],
                    }
                ],
                "data_flows": [
                    {
                        "source": "actor_1",
                        "target": "interface_1",
                        "data": "Documentation query",
                        "evidence": ["Q2", "Q3"],
                    },
                    {
                        "source": "process_1",
                        "target": "process_2",
                        "data": "Prompt",
                        "evidence": ["Q17"],
                    },
                ],
            },
        }

        graph = extract_to_reactflow(extract)
        labels = {node["data"]["label"] for node in graph["nodes"]}
        edges = {(edge["source"], edge["target"], edge["label"]) for edge in graph["edges"]}

        self.assertTrue(has_recognized_dfd_content(extract))
        self.assertIn("Internal Employee", labels)
        self.assertIn("REST API", labels)
        self.assertIn("Backend API", labels)
        self.assertIn("Model Service", labels)
        self.assertIn("Knowledge Base", labels)
        self.assertTrue(any(edge[2] == "Documentation query" for edge in edges))
        self.assertGreater(len(graph["nodes"]), 1)

    def test_unrecognized_compliance_report_is_not_treated_as_dfd_content(self):
        extract = {
            "metadata": {"project_name": "LLM Security & Compliance Review"},
            "questions": [{"id": "Q1", "answer": "Reviewed"}],
            "compliance_status": {"security": "Compliant"},
        }

        graph = extract_to_reactflow(extract)

        self.assertFalse(has_recognized_dfd_content(extract))
        self.assertEqual(len(graph["nodes"]), 1)
        self.assertEqual(graph["nodes"][0]["data"]["label"], "System Summary")

    def test_legacy_raw_system_extract_is_treated_as_dfd_content(self):
        extract = {
            "system": {
                "name": "DocsAI",
                "description": "Documentation and knowledge management assistant",
                "features": {
                    "document_generation": "Generates documentation from technical content.",
                },
                "security": {
                    "access_control": "RBAC is enforced.",
                    "audit_logs": "Access and changes are logged.",
                },
            },
            "llm_components": {
                "model": "Large Language Model for technical documentation tasks.",
                "prompt_engineering": "Custom prompts guide structured output.",
            },
        }

        graph = extract_to_reactflow(extract)
        labels_by_type = {node["data"]["label"]: node["type"] for node in graph["nodes"]}

        self.assertTrue(has_recognized_dfd_content(extract))
        self.assertEqual(labels_by_type["DocsAI"], "backend_service")
        self.assertEqual(labels_by_type["Document Generation"], "backend_service")
        self.assertEqual(labels_by_type["Access Control"], "auth_service")
        self.assertEqual(labels_by_type["Logging / SIEM"], "logging")
        self.assertEqual(labels_by_type["LLM / Model Service"], "llm")
        self.assertGreater(len(graph["nodes"]), 1)

    def test_arch_extract_v1_schema_produces_architecture_nodes(self):
        extract = {
            "schema_version": "llmsec.arch_extract.v1",
            "system_summary": {
                "purpose": "Developer documentation assistant",
                "exposure": "internal",
                "llm_role": "assistant",
                "deployment": "third_party_cloud",
                "confidence": "High",
            },
            "architecture_signals": {
                "actors": [
                    {
                        "name": "Internal Employee",
                        "actor_type": "human",
                        "trust_zone": "internal",
                        "evidence": ["Q2"],
                    }
                ],
                "entry_points": [
                    {
                        "name": "Web Chat Interface",
                        "interface_type": "web_chat",
                        "exposure": "internal",
                        "initiates_llm_workflow": "Yes",
                        "evidence": ["Q3"],
                    }
                ],
                "runtime_components": [
                    {
                        "name": "LLM Orchestrator",
                        "component_type": "orchestrator",
                        "role": "Routes prompts to the model.",
                        "evidence": ["Q9"],
                    }
                ],
                "data_stores": [
                    {
                        "name": "Internal Knowledge Base",
                        "store_type": "knowledge_base",
                        "sensitive_data": "Unknown",
                        "shared_across_users_or_tenants": "No",
                        "evidence": ["Q8"],
                    }
                ],
                "external_systems": [
                    {
                        "name": "Third-party LLM Provider",
                        "system_type": "llm_provider",
                        "trust_zone": "vendor",
                        "evidence": ["Q17"],
                    }
                ],
                "tools_actions": [
                    {
                        "name": "Internal API Call",
                        "action_type": "external_call",
                        "triggered_by": "orchestrator",
                        "requires_human_approval": "Unknown",
                        "state_changing": "No",
                        "evidence": ["Q12"],
                    }
                ],
                "trust_boundary_hints": [
                    {
                        "name": "Backend to model provider",
                        "from_zone": "backend",
                        "to_zone": "vendor",
                        "reason": "Model hosted by third-party provider.",
                        "evidence": ["Q17"],
                    }
                ],
            },
        }

        graph = extract_to_reactflow(extract)
        labels_by_type = {node["data"]["label"]: node["type"] for node in graph["nodes"]}

        self.assertTrue(has_recognized_dfd_content(extract))
        self.assertEqual(labels_by_type["Internal Employee"], "internal_user")
        self.assertEqual(labels_by_type["Web Chat Interface"], "web_app")
        self.assertEqual(labels_by_type["LLM Orchestrator"], "backend_service")
        self.assertEqual(labels_by_type["Internal Knowledge Base"], "vector_db")
        self.assertEqual(labels_by_type["Third-party LLM Provider"], "llm")
        self.assertEqual(labels_by_type["Internal API Call"], "tool_executor")
        self.assertEqual(labels_by_type["Backend to model provider"], "trust_boundary")

    def test_answer_derived_web_and_api_security_entities_are_added(self):
        answers = {
            "Q2": ["Authenticated public users", "Administrators only"],
            "Q48": ["Authenticated user dashboard", "Webhook or callback endpoint"],
            "Q49": "Partially separated",
            "Q50": "Yes, revalidated on every sensitive request",
            "Q51": "Yes, CSRF/origin protections are enforced",
            "Q52": "Strict allowlist with credentials handled safely",
            "Q58": "Yes, complete inventory and classification",
            "Q60": "Validated, normalized, and treated as untrusted data",
            "Q62": "Arbitrary URLs or internal addresses may be reachable",
            "Q63": "Partially restricted",
            "Q72": "Dedicated secret manager with least privilege",
            "Q74": "Yes, with security alerts and privacy controls",
            "Q77": "Yes, per user/tenant/client with anomaly detection",
        }

        graph = extract_to_reactflow({}, answers_by_flow_id=answers)
        labels_by_type = {node["data"]["label"]: node["type"] for node in graph["nodes"]}

        self.assertEqual(labels_by_type["Authenticated User"], "authenticated_user")
        self.assertEqual(labels_by_type["Administrator"], "admin")
        self.assertEqual(labels_by_type["Authenticated User Dashboard"], "web_app")
        self.assertEqual(labels_by_type["Webhook / Callback Endpoint"], "api_service")
        self.assertEqual(labels_by_type["API Gateway / Authorization Layer"], "gateway")
        self.assertEqual(labels_by_type["Auth / Session Service"], "auth_service")
        self.assertEqual(labels_by_type["CSRF / Origin Protection"], "waf")
        self.assertEqual(labels_by_type["CORS Policy"], "gateway")
        self.assertEqual(labels_by_type["API Inventory"], "database")
        self.assertEqual(labels_by_type["External API"], "external_api")
        self.assertEqual(labels_by_type["URL Fetch / Browser Tool"], "tool_executor")
        self.assertEqual(labels_by_type["Egress Control"], "gateway")
        self.assertEqual(labels_by_type["Secrets Vault"], "secrets_vault")
        self.assertEqual(labels_by_type["Logging / SIEM"], "logging")
        self.assertEqual(labels_by_type["Rate Limiter"], "gateway")
        self.assertGreater(len(graph["edges"]), 0)


if __name__ == "__main__":
    unittest.main()
