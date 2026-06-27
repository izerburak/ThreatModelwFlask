import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from app import create_app
    from app.services.llm_extract_service import generate_llm_extract
    from app.services.risk_analysis_service import _risk_name, build_risk_analysis
    from app.utils.save_utils import save_adaptive_llm_sec_answers
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "flask":
        raise
    create_app = None


OLD_STYLE_QUESTION = {
    "id": 1,
    "text": "What is the primary purpose of the LLM in this system?",
    "type": "single",
    "options": ["Customer support assistant"],
    "owasp_llm": ["LLM09"],
    "severity_weight": 2,
    "confidence_weight": 4,
}

NEW_STYLE_QUESTION = {
    "id": 48,
    "text": "Which web application entry points can initiate or influence the LLM workflow?",
    "type": "multi",
    "options": ["Public chat page"],
    "owasp_llm": ["LLM01"],
    "severity_weight": 4,
    "confidence_weight": 5,
    "category": "web_attack_surface",
    "scope": ["llm", "web"],
    "owasp_web": ["A01:2025"],
    "owasp_api": ["API2:2023"],
}

LEGACY_CONTEXT_QUESTION = {
    "id": 2,
    "text": "Who can directly interact with the LLM system?",
    "type": "multi",
    "options": ["Anonymous public internet users"],
    "dfd_impact": ["actor", "trust_boundary", "data_flow"],
    "risk_context": ["prompt_injection", "abuse"],
    "mitigation_context": ["authentication", "rate_limiting"],
}


class PipelineCompatibilityTests(unittest.TestCase):
    def setUp(self):
        if create_app is None:
            self.skipTest("Flask is not installed in the active Python environment.")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        self.questions_dir = self.app_dir / "questions"
        self.responses_dir = self.root / "responses"
        self.prompts_dir = self.root / "LLM-Prompts"
        self.questions_dir.mkdir(parents=True)
        self.responses_dir.mkdir()
        self.prompts_dir.mkdir()
        (self.questions_dir / "questionsDb.json").write_text(
            json.dumps([OLD_STYLE_QUESTION, LEGACY_CONTEXT_QUESTION, NEW_STYLE_QUESTION]),
            encoding="utf-8",
        )
        (self.prompts_dir / "Response-Extractor-prompt.txt").write_text("Return JSON only.", encoding="utf-8")

        self.app = create_app()
        self.app.root_path = str(self.app_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_old_and_new_question_schema_save_and_risk_mapping(self):
        question_catalog = {
            "Q1": {
                "flow_id": "Q1",
                "id": "1",
                "source_id": "1",
                "text": OLD_STYLE_QUESTION["text"],
            },
            "Q48": {
                "flow_id": "Q48",
                "id": "48",
                "source_id": "48",
                "text": NEW_STYLE_QUESTION["text"],
                "category": NEW_STYLE_QUESTION["category"],
                "scope": NEW_STYLE_QUESTION["scope"],
            },
        }

        with self.app.app_context():
            save_adaptive_llm_sec_answers(
                {
                    "Q1": "Customer support assistant",
                    "Q48": ["Public chat page"],
                },
                question_catalog,
            )

        saved_files = list(self.responses_dir.glob("llmsec_*.json"))
        self.assertEqual(len(saved_files), 1)
        saved_payload = json.loads(saved_files[0].read_text(encoding="utf-8"))

        self.assertEqual(
            saved_payload["answers_by_flow_id"],
            {
                "Q1": "Customer support assistant",
                "Q48": ["Public chat page"],
            },
        )
        self.assertEqual(saved_payload["answers"][1]["flow_id"], "Q48")
        self.assertEqual(saved_payload["answers"][1]["question_id"], "48")
        self.assertEqual(saved_payload["answers"][1]["source_question_id"], "48")
        self.assertEqual(saved_payload["answers"][1]["text"], NEW_STYLE_QUESTION["text"])
        self.assertNotIn("category", saved_payload["answers"][1])

        # Risk discovery is now catalog + DREAD driven (no per-question owasp arrays,
        # no severity_weight/confidence_weight). Codes are derived from the *answers*.
        risk_payload = build_risk_analysis(str(self.app_dir), saved_payload)
        self.assertEqual(risk_payload["answers_analyzed"], 2)

        llm_codes = {risk["code"] for risk in risk_payload["owasp_llm"]}
        self.assertIn("LLM01", llm_codes)  # prompt injection always applies to an LLM surface

        # Every risk must be DREAD-scored, level-banded, and grounded in answers that
        # were actually present (Q1 or Q48 only) - never a question that was not asked.
        present_questions = {"Q1", "Q48"}
        for risk in risk_payload["unified_risks"]:
            self.assertIsInstance(risk["dread"], dict)
            self.assertIn("average", risk["dread"])
            self.assertIn(risk["risk_level"], {"Low", "Medium", "High", "Critical"})
            self.assertTrue(risk["question_evidence"], f"{risk['code']} has no grounded evidence")
            for item in risk["question_evidence"]:
                self.assertIn(item["question"], present_questions)

    def test_legacy_q1_q82_only_record_still_works(self):
        # An old record with only Q1-Q82 must not crash and must surface grounded risks;
        # the missing Q83-Q91 signals are reported as missing_information, not errors.
        response_payload = {
            "answers_by_flow_id": {
                "Q2": ["Anonymous public internet users"],
                "Q4": "Yes",
                "Q24": ["Personally identifiable information (PII)"],
            }
        }

        risk_payload = build_risk_analysis(str(self.app_dir), response_payload)
        mapped_codes = {risk["code"] for risk in risk_payload["owasp_llm"]}

        self.assertIn("LLM01", mapped_codes)   # always applies
        self.assertIn("LLM10", mapped_codes)   # anonymous public surface (Q2)
        self.assertIn("LLM02", mapped_codes)   # sensitive data (Q4/Q24)

        # Evidence only cites questions that were answered.
        for risk in risk_payload["unified_risks"]:
            for item in risk["question_evidence"]:
                self.assertIn(item["question"], {"Q2", "Q4", "Q24"})

        # Missing new-question signals are reported (spec-mandated messages), not errors.
        missing = " ".join(risk_payload["missing_information"])
        self.assertIn("User/tenant scale was not provided.", risk_payload["missing_information"])
        self.assertIn("Business/regulatory impact was not provided.", risk_payload["missing_information"])
        self.assertIn("Replay/reproducibility behavior was not provided.", risk_payload["missing_information"])

    def test_owasp_framework_code_names_are_resolved(self):
        self.assertEqual(_risk_name("owasp_llm", "LLM06"), "Excessive Agency")
        self.assertEqual(_risk_name("owasp_web", "A05:2025"), "Injection")
        self.assertEqual(_risk_name("owasp_api", "API5:2023"), "Broken Function Level Authorization")
        self.assertEqual(_risk_name("owasp_web", "A99:2025"), "A99:2025")
        self.assertEqual(_risk_name("owasp_api", "API99:2023"), "API99:2023")
        self.assertEqual(_risk_name("unknown", "X1"), "X1")

    def test_llm_extract_prompt_uses_answer_essentials(self):
        response_payload = {
            "answers_by_flow_id": {"Q48": ["Public chat page"]},
            "answers": [
                {
                    "flow_id": "Q48",
                    "question_id": "48",
                    "source_question_id": "48",
                    "text": NEW_STYLE_QUESTION["text"],
                    "answer": ["Public chat page"],
                    "category": "web_attack_surface",
                    "owasp_web": ["A01:2025"],
                }
            ],
        }
        response_file = "llmsec_test.json"
        (self.responses_dir / response_file).write_text(json.dumps(response_payload), encoding="utf-8")

        with patch("app.services.llm_extract_service.chat") as mock_chat:
            mock_chat.return_value = {
                "model": "test-model",
                "message": {"role": "assistant", "content": '{"top_risks": []}'},
            }

            generate_llm_extract(str(self.app_dir), {"project_name": "Compat"}, response_file)

        user_payload = json.loads(mock_chat.call_args.args[0][1]["content"])
        self.assertNotIn("response", user_payload)
        self.assertEqual(
            user_payload["answers"],
            [
                {
                    "flow_id": "Q48",
                    "text": NEW_STYLE_QUESTION["text"],
                    "answer": ["Public chat page"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
