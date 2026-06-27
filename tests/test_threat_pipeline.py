"""Integration tests for the target-order pipeline (template-guided LLM threat
identification -> grounding validation -> deterministic DREAD -> mitigation)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import risk_analysis_service as ras
from app.services.dread_scoring import index_answers, score_code
from app.services.ollama_client import OllamaError
from app.services.static_dfd_mapper import build_static_dfd_from_answers

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app")

ANSWERS = {
    "Q2": ["Anonymous public internet users"],
    "Q3": ["Web-based chat interface", "REST API endpoint"],
    "Q4": "Yes",
    "Q15": ["Execute workflows or transactions"],
    "Q24": ["Personally identifiable information (PII)"],
    "Q85": ["Web frontend", "Backend API", "Tool execution runtime"],
}


def _chat_return(payload):
    return {"model": "test-model", "message": {"role": "assistant", "content": json.dumps(payload)}}


def _dfd():
    return build_static_dfd_from_answers({"answers_by_flow_id": ANSWERS})


def _deterministic_codes(dfd):
    questions = ras._load_questions(APP)
    norm, _ = ras.normalize_answers(ANSWERS)
    return [risk["code"] for risk in ras.discover_candidate_risks(questions, norm, dfd)]


class ThreatPipelineIntegrationTests(unittest.TestCase):
    def _run(self, identified, mitigations):
        dfd = _dfd()
        codes = _deterministic_codes(dfd)
        self.assertTrue(codes, "expected deterministic candidates for the sample answers")
        ident_payload = _chat_return({"identified_threats": identified, "suggested_secondary_findings": []})
        mit_payload = _chat_return(mitigations)
        with patch("app.services.llm_threat_identification.chat", return_value=ident_payload), patch(
            "app.services.llm_mitigation_service.chat", return_value=mit_payload
        ):
            return ras.build_threat_analysis(APP, {"answers_by_flow_id": ANSWERS}, dfd), dfd, codes

    def test_dread_is_deterministic_and_set_after_identification(self):
        dfd = _dfd()
        codes = _deterministic_codes(dfd)
        code = codes[0]
        node_id = dfd["nodes"][0]["id"]
        identified = [{
            "code": code, "name": "X", "status": "confirmed",
            "threat_pattern": "prompt_context_manipulation",
            "evidence": ["Q2: Anonymous public internet users"],
            "affected_nodes": [node_id, "entry_FAKE"], "affected_edges": [],
            "abuse_path": ["x"], "control_gap": "no auth", "confidence": "high", "missing_information": [],
        }]
        result, _, _ = self._run(identified, {"mitigations": [], "quick_wins": [], "assumptions": [], "missing_information": []})

        scored = {r["code"]: r for r in result["unified_risks"]}
        self.assertIn(code, scored)
        expected_band = score_code(code, index_answers(ras.normalize_answers(ANSWERS)[0]))["band"]
        # risk_level comes from DREAD, never from the LLM.
        self.assertEqual(scored[code]["risk_level"], expected_band)
        self.assertIsInstance(scored[code]["dread"], dict)
        self.assertEqual(scored[code]["status"], "confirmed")
        # Hallucinated node id was stripped before scoring.
        self.assertNotIn("entry_FAKE", scored[code]["affected_nodes"])
        self.assertEqual(result["pipeline_mode"], "llm_threat_identification_v1")

    def test_only_validated_threats_are_scored(self):
        dfd = _dfd()
        codes = _deterministic_codes(dfd)
        # One confirmed (validated) + one not_applicable (must NOT be scored).
        identified = [
            {"code": codes[0], "name": "A", "status": "confirmed", "threat_pattern": "prompt_context_manipulation",
             "evidence": ["Q2"], "affected_nodes": [], "affected_edges": [], "abuse_path": [],
             "control_gap": "gap", "confidence": "high", "missing_information": []},
            {"code": codes[1], "name": "B", "status": "not_applicable", "threat_pattern": "sensitive_data_exposure",
             "evidence": ["Q2"], "affected_nodes": [], "affected_edges": [], "abuse_path": [],
             "control_gap": "gap", "confidence": "high", "missing_information": []},
        ]
        result, _, _ = self._run(identified, {"mitigations": []})
        scored_codes = {r["code"] for r in result["unified_risks"]}
        self.assertIn(codes[0], scored_codes)
        self.assertNotIn(codes[1], scored_codes)

    def test_mitigation_cannot_add_new_risks(self):
        dfd = _dfd()
        codes = _deterministic_codes(dfd)
        code = codes[0]
        identified = [{
            "code": code, "name": "X", "status": "confirmed", "threat_pattern": "prompt_context_manipulation",
            "evidence": ["Q2"], "affected_nodes": [], "affected_edges": [], "abuse_path": [],
            "control_gap": "no auth", "confidence": "high", "missing_information": [],
        }]
        mitigations = {"mitigations": [
            {"risk_code": code, "title": "Real", "action": "Do X", "priority": "High",
             "target_component": "LLM Gateway", "validation_step": "verify", "maps_to_evidence": ["Q2"]},
            {"risk_code": "ZZZ99", "title": "Bogus", "action": "Invent risk", "priority": "Low", "maps_to_evidence": ["e"]},
        ], "quick_wins": [], "assumptions": [], "missing_information": []}
        result, _, _ = self._run(identified, mitigations)

        mit_codes = {m["risk_code"] for m in result["mitigations"]}
        self.assertEqual(mit_codes, {code})  # bogus code filtered out
        # No new risk family appeared in unified_risks from the mitigation stage.
        self.assertNotIn("ZZZ99", {r["code"] for r in result["unified_risks"]})

    def test_backward_compatible_keys_present(self):
        dfd = _dfd()
        codes = _deterministic_codes(dfd)
        identified = [{
            "code": codes[0], "name": "X", "status": "confirmed", "threat_pattern": "prompt_context_manipulation",
            "evidence": ["Q2"], "affected_nodes": [], "affected_edges": [], "abuse_path": [],
            "control_gap": "gap", "confidence": "high", "missing_information": [],
        }]
        result, _, _ = self._run(identified, {"mitigations": []})
        for key in ("overall_status", "status_source", "unified_risks", "quick_wins",
                    "missing_information", "assumptions", "answers_analyzed", "risk_summary",
                    "identified_threats", "deterministic_risks", "threat_validation_report"):
            self.assertIn(key, result)
        for risk in result["unified_risks"]:
            self.assertIn(risk["risk_level"], {"Low", "Medium", "High", "Critical"})
            self.assertTrue(risk["question_evidence"])

    def test_identification_unavailable_raises(self):
        dfd = _dfd()
        with patch("app.services.llm_threat_identification.chat", side_effect=OllamaError("down")):
            with self.assertRaises(ras.ThreatIdentificationUnavailable):
                ras.build_threat_analysis(APP, {"answers_by_flow_id": ANSWERS}, dfd)


class OrchestratorFallbackTests(unittest.TestCase):
    def setUp(self):
        try:
            from app.services.pipeline_orchestrator import PipelineOrchestrator
        except ModuleNotFoundError as exc:
            if exc.name == "flask":
                self.skipTest("Flask not installed")
            raise
        self.PipelineOrchestrator = PipelineOrchestrator
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        (self.app_dir / "questions").mkdir(parents=True)
        (self.root / "responses").mkdir()
        # Real questions DB so the deterministic baseline can score.
        shutil.copyfile(ROOT / "app" / "questions" / "questionsDb.json", self.app_dir / "questions" / "questionsDb.json")
        (self.root / "responses" / "llmsec_test.json").write_text(
            json.dumps({"answers_by_flow_id": ANSWERS}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fallback_to_deterministic_when_llm_unavailable(self):
        orchestrator = self.PipelineOrchestrator(str(self.app_dir))
        manifest = orchestrator.create_pipeline("llmsec_test.json", project_name="T")
        pipeline_id = manifest["pipeline_id"]
        orchestrator.generate_dfd(pipeline_id)

        with patch("app.services.llm_threat_identification.chat", side_effect=OllamaError("down")):
            risks = orchestrator.run_risk_analysis(pipeline_id)

        # A valid deterministic risks.json was still produced.
        self.assertTrue(orchestrator.artifact_exists(pipeline_id, "risks.json"))
        self.assertTrue(risks["unified_risks"])
        self.assertNotEqual(risks.get("pipeline_mode"), "llm_threat_identification_v1")
        for risk in risks["unified_risks"]:
            self.assertIsInstance(risk["dread"], dict)


if __name__ == "__main__":
    unittest.main()
