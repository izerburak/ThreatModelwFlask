import unittest

from app.services.arch_extract_cleaner import clean_arch_extract_v4


class ArchExtractCleanerTests(unittest.TestCase):
    def test_required_schema_shape(self):
        cleaned = clean_arch_extract_v4({})

        self.assertEqual(cleaned["schema_version"], "llmsec.arch_extract.cleaned.v1")
        self.assertEqual(
            set(cleaned["system_summary"]),
            {"purpose", "llm_role", "deployment", "exposure", "confidence"},
        )
        self.assertEqual(
            set(cleaned["architecture"]),
            {
                "actors",
                "entry_points",
                "components",
                "data_stores",
                "external_services",
                "trust_boundaries",
                "data_flows",
            },
        )
        self.assertEqual(
            set(cleaned["security_controls"]),
            {
                "authentication",
                "authorization",
                "input_validation",
                "output_validation",
                "logging_monitoring",
                "rate_limiting",
                "secrets_management",
                "encryption",
            },
        )
        self.assertEqual(
            set(cleaned["risk_signals"]),
            {"misuse_scenarios", "operational_weaknesses", "owasp_llm_candidates"},
        )

    def test_risk_like_security_control_moves_to_risk_signals(self):
        cleaned = clean_arch_extract_v4(
            {
                "security_controls": {
                    "authorization": [
                        "RBAC",
                        "Prompt injection to override instructions",
                    ]
                }
            }
        )

        self.assertEqual(cleaned["security_controls"]["authorization"], ["RBAC"])
        self.assertIn("Prompt injection to override instructions", cleaned["risk_signals"]["misuse_scenarios"])

    def test_duplicate_items_are_removed(self):
        cleaned = clean_arch_extract_v4(
            {
                "architecture": {
                    "components": [
                        {"name": "Backend API", "type": "api"},
                        {"name": "Backend API", "type": "api"},
                    ]
                },
                "security_controls": {
                    "rate_limiting": ["Rate limiting", "Rate limiting"],
                },
            }
        )

        self.assertEqual(cleaned["architecture"]["components"], [{"name": "Backend API", "type": "api"}])
        self.assertEqual(cleaned["security_controls"]["rate_limiting"], ["Rate limiting"])

    def test_system_purpose_is_not_actor(self):
        cleaned = clean_arch_extract_v4(
            {
                "system_summary": {"purpose": "Customer support assistant"},
                "architecture": {
                    "actors": [
                        "Customer support assistant",
                        "Authenticated customer",
                    ]
                },
            }
        )

        self.assertEqual(cleaned["architecture"]["actors"], ["Authenticated customer"])

    def test_non_storage_data_stores_move_to_components(self):
        cleaned = clean_arch_extract_v4(
            {
                "architecture": {
                    "data_stores": [
                        "Internal API",
                        "Model service",
                        "Conversation history store",
                    ]
                }
            }
        )

        self.assertEqual(cleaned["architecture"]["data_stores"], ["Conversation history store"])
        self.assertIn("Internal API", cleaned["architecture"]["components"])
        self.assertIn("Model service", cleaned["architecture"]["components"])


if __name__ == "__main__":
    unittest.main()
