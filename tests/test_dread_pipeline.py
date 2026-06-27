"""Tests for the DREAD-centered pipeline (91-question questionnaire).

Covers questionsDb integrity, the new questions Q83-Q91 and their DREAD effects,
Q85-driven DFD generation, and that the old OWASP-tag / severity-weight scoring
path has been removed.
"""
import json
import unittest
from pathlib import Path

from app.services import dread_scoring, risk_analysis_service
from app.services.dread_scoring import index_answers, level_from_average, score_code
from app.services.dread_signals import extract_dread_signals
from app.services.risk_catalog import all_catalog_codes, candidate_codes
from app.services.static_dfd_mapper import build_static_dfd_from_answers

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_DB = ROOT / "app" / "questions" / "questionsDb.json"


def _idx(answers):
    return index_answers(answers)


class QuestionsDbTests(unittest.TestCase):
    def test_questionsdb_loads_and_has_91_unique_ids(self):
        data = json.loads(QUESTIONS_DB.read_text(encoding="utf-8"))
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 91)
        ids = [q["id"] for q in data]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sorted(ids), list(range(1, 92)))

    def test_every_question_has_dread_schema(self):
        data = json.loads(QUESTIONS_DB.read_text(encoding="utf-8"))
        for question in data:
            self.assertIn("category", question)
            self.assertIn("scope", question)
            self.assertIn("dread_dimensions", question)
            self.assertIn("dread_weights", question)
            for dim in dread_scoring.DREAD_DIMENSIONS:
                self.assertIn(dim, question["dread_weights"])

    def test_no_question_level_owasp_or_weight_tags_remain(self):
        text = QUESTIONS_DB.read_text(encoding="utf-8")
        for legacy in ("owasp_llm", "owasp_web", "owasp_api", "severity_weight", "confidence_weight"):
            self.assertNotIn(f'"{legacy}"', text)


class DreadAverageBandTests(unittest.TestCase):
    def test_average_thresholds(self):
        self.assertEqual(level_from_average(1.4), "Low")
        self.assertEqual(level_from_average(1.5), "Medium")
        self.assertEqual(level_from_average(2.1), "Medium")
        self.assertEqual(level_from_average(2.2), "High")
        self.assertEqual(level_from_average(2.6), "High")
        self.assertEqual(level_from_average(2.7), "Critical")

    def test_score_block_exposes_total_average_and_level(self):
        block = score_code("LLM01", _idx({"Q2": ["Anonymous public internet users"]}))
        self.assertEqual(block["average"], round(block["total"] / 5.0, 2))
        self.assertEqual(block["risk_level"], level_from_average(block["average"]))
        self.assertIn(block["band"], {"Low", "Medium", "High", "Critical"})


class InputHandlingTests(unittest.TestCase):
    def test_q83_q84_increase_exploitability(self):
        base = {"Q2": ["Authenticated public users"]}
        risky = {**base, "Q83": ["HTML or rendered content", "Code or scripts"], "Q84": "Yes, parsed and inserted with minimal validation"}
        base_e = score_code("LLM01", _idx(base))["exploitability"]
        risky_e = score_code("LLM01", _idx(risky))["exploitability"]
        self.assertGreater(risky_e, base_e)

    def test_strict_parsing_lowers_exploitability(self):
        base = {"Q2": ["Authenticated public users"]}
        strict = {**base, "Q84": "Yes, parsed with strict validation and normalization"}
        self.assertLess(
            score_code("LLM01", _idx(strict))["exploitability"],
            score_code("LLM01", _idx(base))["exploitability"],
        )

    def test_q83_q84_show_up_as_exploitability_signals(self):
        signals = extract_dread_signals({"Q83": ["HTML or rendered content"], "Q84": "No parsing or transformation is performed"})
        questions = {s["question"] for s in signals["exploitability_signals"]}
        self.assertIn("Q83", questions)
        self.assertIn("Q84", questions)


class ArchitectureInventoryTests(unittest.TestCase):
    def test_q85_drives_dfd_nodes(self):
        graph = build_static_dfd_from_answers(
            {
                "Q85": [
                    "Web frontend",
                    "Backend API",
                    "RAG retriever",
                    "Vector database",
                    "Tool execution runtime",
                    "External model provider API",
                    "Logging or monitoring pipeline",
                ]
            }
        )
        node_ids = {node["id"] for node in graph["nodes"]}
        for expected in (
            "entry_web_chat",
            "process_orchestrator",
            "process_rag_orchestrator",
            "store_vector_db",
            "process_tool_layer",
            "external_model_provider",
            "process_logging_monitoring",
        ):
            self.assertIn(expected, node_ids)

    def test_q85_absent_falls_back_to_inference(self):
        # Without Q85 the old inference still produces nodes (fallback path).
        graph = build_static_dfd_from_answers({"Q2": ["Anonymous public internet users"], "Q3": ["Web-based chat interface"]})
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertIn("entry_web_chat", node_ids)
        self.assertTrue(any(w.startswith("Q85 component inventory was not provided") for w in graph["metadata"]["warnings"]))


class ImpactAndScaleTests(unittest.TestCase):
    def test_q86_raises_affected_users_for_public_scale(self):
        low = score_code("LLM01", _idx({"Q86": "Single user or local-only use"}))["affected_users"]
        high = score_code("LLM01", _idx({"Q86": "Public internet-scale user base"}))["affected_users"]
        self.assertLess(low, high)
        self.assertEqual(high, 3)

    def test_q87_raises_damage_floor(self):
        base = score_code("LLM01", _idx({}))["damage"]
        severe = score_code("LLM01", _idx({"Q87": "Severe impact such as large-scale data breach, fraud, or critical service disruption"}))["damage"]
        self.assertGreater(severe, base)
        self.assertEqual(severe, 3)

    def test_q88_long_retention_raises_data_damage(self):
        base = score_code("LLM02", _idx({"Q4": "No", "Q24": ["No sensitive data"]}))["damage"]
        retained = score_code("LLM02", _idx({"Q4": "No", "Q24": ["No sensitive data"], "Q88": "Long-term retention without clear deletion controls"}))["damage"]
        self.assertGreater(retained, base)

    def test_q89_mature_incident_response_reduces_damage(self):
        base = score_code("LLM01", _idx({}))["damage"]
        mature = score_code("LLM01", _idx({"Q89": "Documented and periodically tested process"}))["damage"]
        self.assertLess(mature, base)


class ReproducibilityTests(unittest.TestCase):
    def test_q91_replay_raises_reproducibility(self):
        blocked = score_code("LLM01", _idx({"Q91": "No, replay is blocked or requires fresh authorization"}))["reproducibility"]
        open_replay = score_code("LLM01", _idx({"Q91": "State-changing or sensitive actions can be replayed without strong controls"}))["reproducibility"]
        self.assertGreater(open_replay, blocked)

    def test_q90_affects_reproducibility_and_discoverability(self):
        none = score_code("LLM01", _idx({"Q90": "No testing performed"}))
        mature = score_code("LLM01", _idx({"Q90": "Continuous adversarial testing or regression tests are in place"}))
        self.assertGreater(none["reproducibility"], mature["reproducibility"])
        self.assertGreater(none["discoverability"], mature["discoverability"])

    def test_q90_is_signal_for_three_dimensions(self):
        signals = extract_dread_signals({"Q90": "No testing performed"})
        for key in ("reproducibility_signals", "exploitability_signals", "discoverability_signals"):
            self.assertTrue(any(s["question"] == "Q90" for s in signals[key]), key)


class CatalogAndLegacyTests(unittest.TestCase):
    def test_catalog_codes_are_known_owasp_codes(self):
        known = set(risk_analysis_service.OWASP_LLM_2025) | set(risk_analysis_service.OWASP_WEB_2025) | set(risk_analysis_service.OWASP_API_2023)
        for code in all_catalog_codes():
            self.assertIn(code, known)

    def test_candidate_evidence_only_cites_present_questions(self):
        answers = {"Q2": ["Anonymous public internet users"], "Q4": "Yes"}
        present = {2, 4}
        for candidate in candidate_codes(answers):
            for number in candidate["evidence_questions"]:
                self.assertIn(number, present)

    def test_empty_answers_produce_no_ungrounded_risks(self):
        # Empty answers => no grounded evidence => no risks (no hallucinated risks).
        result = risk_analysis_service.build_risk_analysis(str(ROOT / "app"), {"answers_by_flow_id": {}})
        self.assertEqual(result["unified_risks"], [])


class RemovedOldDependenciesTests(unittest.TestCase):
    def test_scoring_service_has_no_weight_or_question_tag_dependency(self):
        text = (ROOT / "app" / "services" / "risk_analysis_service.py").read_text(encoding="utf-8")
        self.assertNotIn("severity_weight", text)
        self.assertNotIn("confidence_weight", text)
        self.assertNotIn("LEGACY_RISK_CONTEXT_TO_OWASP_LLM", text)
        # The framework grouping keys (owasp_llm/web/api) remain as output keys, but
        # the per-question tag reader (_question_codes / question.get("owasp_llm")) is gone.
        self.assertNotIn("_question_codes", text)
        self.assertNotIn('question.get("owasp_llm")', text)


if __name__ == "__main__":
    unittest.main()
