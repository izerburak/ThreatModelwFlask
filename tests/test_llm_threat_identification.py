import json
import unittest
from unittest.mock import patch

from app.services.llm_threat_identification import identify_threats
from app.services.ollama_client import OllamaError


DFD = {
    "nodes": [
        {"id": "llm_gateway", "data": {"label": "LLM Gateway", "nodeType": "llm"}},
        {"id": "entry_web_chat", "data": {"label": "Web Chat", "nodeType": "interface"}},
    ],
    "edges": [
        {"id": "edge_entry_web_chat_to_llm_gateway_llm_request", "source": "entry_web_chat", "target": "llm_gateway", "label": "LLM request"},
    ],
}

DETERMINISTIC = [
    {"code": "LLM01", "name": "Prompt Injection", "framework": "owasp_llm",
     "affected_assets": [], "missing_information": [],
     "evidence": [{"question": "Q2", "text": "Who can reach it", "answer": "Anonymous public internet users"}]},
    {"code": "LLM06", "name": "Excessive Agency", "framework": "owasp_llm",
     "affected_assets": [], "missing_information": [],
     "evidence": [{"question": "Q15", "text": "Actions", "answer": "Execute workflows or transactions"}]},
]


def _chat_return(payload):
    return {"model": "test-model", "message": {"role": "assistant", "content": json.dumps(payload)}}


class ThreatIdentificationTests(unittest.TestCase):
    @patch("app.services.llm_threat_identification.chat")
    def test_schema_constrains_codes_and_ids(self, chat_mock):
        chat_mock.return_value = _chat_return({"identified_threats": [], "suggested_secondary_findings": []})

        identify_threats("/tmp/app", {"Q2": ["Anonymous public internet users"]}, DETERMINISTIC, {}, DFD)

        schema = chat_mock.call_args.kwargs["response_format"]
        item = schema["properties"]["identified_threats"]["items"]["properties"]
        # PRIMARY codes are enum-constrained to the deterministic candidate codes.
        self.assertEqual(item["code"]["enum"], ["LLM01", "LLM06"])
        # affected_nodes / affected_edges are enum-constrained to real DFD ids.
        self.assertEqual(item["affected_nodes"]["items"]["enum"], ["llm_gateway", "entry_web_chat"])
        self.assertEqual(item["affected_edges"]["items"]["enum"], ["edge_entry_web_chat_to_llm_gateway_llm_request"])

    @patch("app.services.llm_threat_identification.chat")
    def test_payload_carries_allowed_codes_and_patterns(self, chat_mock):
        chat_mock.return_value = _chat_return({"identified_threats": [], "suggested_secondary_findings": []})

        identify_threats("/tmp/app", {"Q2": ["x"]}, DETERMINISTIC, {}, DFD)

        payload = json.loads(chat_mock.call_args.args[0][1]["content"])
        self.assertEqual(payload["instructions"]["primary_codes_allowed"], ["LLM01", "LLM06"])
        self.assertEqual(len(payload["threat_patterns"]), 10)
        self.assertEqual({n["id"] for n in payload["dfd"]["nodes"]}, {"llm_gateway", "entry_web_chat"})
        # Candidate-first: the deterministic candidate risks are the analysis spine the
        # LLM must inspect (the template guides HOW, the candidate set decides WHICH).
        self.assertEqual([r["code"] for r in payload["deterministic_risks"]], ["LLM01", "LLM06"])

    @patch("app.services.llm_threat_identification.chat")
    def test_completed_output_is_returned(self, chat_mock):
        chat_mock.return_value = _chat_return(
            {
                "identified_threats": [
                    {"code": "LLM01", "name": "Prompt Injection", "status": "confirmed",
                     "threat_pattern": "prompt_context_manipulation", "evidence": ["Q2: public"],
                     "affected_nodes": ["llm_gateway"], "affected_edges": [], "abuse_path": ["a"],
                     "control_gap": "no isolation", "confidence": "high", "missing_information": []}
                ],
                "suggested_secondary_findings": [],
            }
        )
        result = identify_threats("/tmp/app", {"Q2": ["x"]}, DETERMINISTIC, {}, DFD)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["identified_threats"]), 1)
        self.assertEqual(result["identified_threats"][0]["code"], "LLM01")

    @patch("app.services.llm_threat_identification.chat")
    def test_unavailable_when_ollama_down(self, chat_mock):
        chat_mock.side_effect = OllamaError("connection refused")
        result = identify_threats("/tmp/app", {"Q2": ["x"]}, DETERMINISTIC, {}, DFD)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["identified_threats"], [])

    @patch("app.services.llm_threat_identification.chat")
    def test_skipped_when_no_deterministic_candidates(self, chat_mock):
        result = identify_threats("/tmp/app", {"Q2": ["x"]}, [], {}, DFD)
        self.assertEqual(result["status"], "skipped")
        chat_mock.assert_not_called()

    @patch("app.services.llm_threat_identification.chat")
    def test_candidates_are_chunked_and_results_merged(self, chat_mock):
        # chunk_size=1 -> one call per candidate; each chunk's enum is its single code.
        def _per_chunk(messages, *args, **kwargs):
            allowed = json.loads(messages[1]["content"])["instructions"]["primary_codes_allowed"]
            code = allowed[0]
            return _chat_return({
                "identified_threats": [{
                    "code": code, "name": code, "status": "plausible",
                    "threat_pattern": "prompt_context_manipulation", "evidence": ["e"],
                    "affected_nodes": [], "affected_edges": [], "abuse_path": ["s"],
                    "control_gap": "gap", "confidence": "medium", "missing_information": [],
                }],
                "suggested_secondary_findings": [{"code": "API7:2023", "name": "SSRF", "status": "needs_more_info"}],
            })

        chat_mock.side_effect = _per_chunk
        result = identify_threats("/tmp/app", {"Q2": ["x"]}, DETERMINISTIC, {}, DFD,
                                  {"LLM_THREAT_ID_CHUNK_SIZE": 1})

        self.assertEqual(chat_mock.call_count, 2)  # LLM01 + LLM06 in separate calls
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["chunks_total"], 2)
        self.assertEqual({t["code"] for t in result["identified_threats"]}, {"LLM01", "LLM06"})
        # identical secondary finding from both chunks is de-duplicated.
        self.assertEqual(len(result["suggested_secondary_findings"]), 1)

    @patch("app.services.llm_threat_identification.chat")
    def test_partial_when_some_chunks_fail(self, chat_mock):
        calls = {"n": 0}

        def _flaky(messages, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OllamaError("boom")
            allowed = json.loads(messages[1]["content"])["instructions"]["primary_codes_allowed"]
            return _chat_return({"identified_threats": [{
                "code": allowed[0], "name": allowed[0], "status": "needs_more_info",
                "threat_pattern": "prompt_context_manipulation", "evidence": [],
                "affected_nodes": [], "affected_edges": [], "abuse_path": [],
                "control_gap": "", "confidence": "low", "missing_information": []}],
                "suggested_secondary_findings": []})

        chat_mock.side_effect = _flaky
        result = identify_threats("/tmp/app", {"Q2": ["x"]}, DETERMINISTIC, {}, DFD,
                                  {"LLM_THREAT_ID_CHUNK_SIZE": 1})
        # one chunk failed, one succeeded -> partial, not unavailable.
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["chunks_succeeded"], 1)
        self.assertEqual(len(result["identified_threats"]), 1)


if __name__ == "__main__":
    unittest.main()
