import unittest

from app.services.threat_grounding_validator import validate_threats


DFD = {
    "nodes": [
        {"id": "entry_web_chat", "data": {"label": "Web Chat"}},
        {"id": "llm_gateway", "data": {"label": "LLM Gateway"}},
    ],
    "edges": [
        {"id": "edge_entry_web_chat_to_llm_gateway_llm_request", "source": "entry_web_chat", "target": "llm_gateway", "label": "LLM request"},
    ],
}


def _det(code="LLM01", answer="Anonymous public internet users"):
    return [{
        "code": code,
        "name": code,
        "framework": "owasp_llm",
        "affected_assets": [],
        "missing_information": [],
        "evidence": [{"question": "Q2", "text": "Who", "answer": answer}],
    }]


def _threat(**overrides):
    threat = {
        "code": "LLM01",
        "name": "Prompt Injection",
        "status": "confirmed",
        "threat_pattern": "prompt_context_manipulation",
        "evidence": ["Q2: Anonymous public internet users"],
        "affected_nodes": [],
        "affected_edges": [],
        "abuse_path": [],
        "control_gap": "No prompt/content isolation",
        "confidence": "high",
        "missing_information": [],
    }
    threat.update(overrides)
    return threat


def _ident(threats, secondary=None):
    return {"identified_threats": threats, "suggested_secondary_findings": secondary or []}


class GroundingValidatorTests(unittest.TestCase):
    def test_strips_hallucinated_node_ids(self):
        result = validate_threats(_ident([_threat(affected_nodes=["llm_gateway", "entry_FAKE"])]), DFD, _det())
        threat = result["primary_threats"][0]
        self.assertEqual(threat["affected_nodes"], ["llm_gateway"])
        self.assertIn("entry_FAKE", result["report"]["stripped_node_ids"])

    def test_strips_hallucinated_edge_ids(self):
        result = validate_threats(_ident([_threat(affected_edges=["edge_entry_web_chat_to_llm_gateway_llm_request", "edge_FAKE"])]), DFD, _det())
        threat = result["primary_threats"][0]
        self.assertEqual(threat["affected_edges"], ["edge_entry_web_chat_to_llm_gateway_llm_request"])
        self.assertIn("edge_FAKE", result["report"]["stripped_edge_ids"])

    def test_non_deterministic_code_demoted_to_secondary(self):
        # API7 is not in the deterministic set (only LLM01) -> must not be primary.
        result = validate_threats(_ident([_threat(code="API7:2023")]), DFD, _det())
        self.assertEqual(result["primary_threats"], [])
        self.assertTrue(any(f["code"] == "API7:2023" for f in result["secondary_findings"]))
        self.assertEqual(result["secondary_findings"][0]["status"], "needs_more_info")
        self.assertIn("API7:2023", result["report"]["demoted_non_primary_codes"])

    def test_unknown_only_evidence_cannot_be_confirmed(self):
        result = validate_threats(_ident([_threat(status="confirmed")]), DFD, _det(answer="Unknown"))
        self.assertEqual(result["primary_threats"], [])
        downgraded = result["downgraded_threats"][0]
        self.assertEqual(downgraded["status"], "needs_more_info")

    def test_empty_evidence_and_no_control_gap_downgraded(self):
        result = validate_threats(_ident([_threat(evidence=[], control_gap="")]), DFD, _det(answer="Yes"))
        self.assertEqual(result["primary_threats"], [])
        self.assertEqual(result["downgraded_threats"][0]["status"], "needs_more_info")

    def test_confirmed_with_low_confidence_downgraded_to_plausible(self):
        result = validate_threats(_ident([_threat(status="confirmed", confidence="low")]), DFD, _det(answer="Yes"))
        self.assertEqual(len(result["primary_threats"]), 1)
        self.assertEqual(result["primary_threats"][0]["status"], "plausible")

    def test_strong_confirmed_stays_primary(self):
        result = validate_threats(_ident([_threat(affected_nodes=["llm_gateway"])]), DFD, _det(answer="Yes"))
        self.assertEqual(len(result["primary_threats"]), 1)
        self.assertEqual(result["primary_threats"][0]["status"], "confirmed")

    def test_only_confirmed_or_plausible_proceed(self):
        threats = [
            _threat(affected_nodes=["llm_gateway"]),                       # confirmed
            _threat(status="plausible"),                                   # plausible
            _threat(status="needs_more_info", evidence=[], control_gap=""),  # not validated
            _threat(status="not_applicable"),                              # not validated
        ]
        result = validate_threats(_ident(threats), DFD, _det(answer="Yes"))
        for threat in result["primary_threats"]:
            self.assertIn(threat["status"], ("confirmed", "plausible"))


if __name__ == "__main__":
    unittest.main()
