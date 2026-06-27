import unittest

from app.services.threat_template import THREAT_PATTERNS, pattern_ids, threat_patterns_prompt_block


EXPECTED_PATTERNS = {
    "prompt_context_manipulation",
    "untrusted_input_crossing_trust_boundary",
    "rag_or_memory_contamination",
    "sensitive_data_exposure",
    "excessive_tool_or_workflow_agency",
    "weak_authentication_authorization",
    "unsafe_output_handling",
    "vector_store_or_embedding_isolation",
    "secrets_logging_transport_exposure",
    "missing_monitoring_limits_incident_response",
}


class ThreatTemplateTests(unittest.TestCase):
    def test_ten_generic_patterns_present(self):
        ids = pattern_ids()
        self.assertEqual(len(ids), 10)
        self.assertEqual(set(ids), EXPECTED_PATTERNS)
        self.assertEqual(len(set(ids)), len(ids))  # unique

    def test_every_pattern_has_required_fields(self):
        for pattern in THREAT_PATTERNS:
            self.assertIn("id", pattern)
            self.assertIn("title", pattern)
            self.assertIn("description", pattern)
            self.assertIsInstance(pattern["typical_codes"], list)
            self.assertTrue(pattern["typical_codes"])

    def test_prompt_block_mentions_all_ids(self):
        block = threat_patterns_prompt_block()
        for pattern_id in pattern_ids():
            self.assertIn(pattern_id, block)


if __name__ == "__main__":
    unittest.main()
