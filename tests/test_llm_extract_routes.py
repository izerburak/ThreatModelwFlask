import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from app import create_app
    from app.services.llm_extract_service import parse_extract_json
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "flask":
        raise
    create_app = None
    parse_extract_json = None


class LlmExtractRoutesTests(unittest.TestCase):
    def setUp(self):
        if create_app is None:
            self.skipTest("Flask is not installed in the active Python environment.")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        self.extract_dir = self.root / "LLM_Extracts"
        self.app_dir.mkdir()

        self.app = create_app()
        self.app.root_path = str(self.app_dir)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_extract_directory_returns_empty_list(self):
        response = self.client.get("/api/llm-extracts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"files": []})

    def test_lists_only_json_and_txt_extracts(self):
        self.extract_dir.mkdir()
        (self.extract_dir / "mid-risk-extract.txt").write_text("{}", encoding="utf-8")
        (self.extract_dir / "critical-risk-extract.json").write_text("{}", encoding="utf-8")
        (self.extract_dir / "ignore.md").write_text("{}", encoding="utf-8")

        response = self.client.get("/api/llm-extracts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"files": ["critical-risk-extract.json", "mid-risk-extract.txt"]},
        )

    def test_reads_txt_with_json_object_embedded(self):
        self.extract_dir.mkdir()
        (self.extract_dir / "extract.txt").write_text('notes\n{"architecture": {"actors": ["Users"]}}\n', encoding="utf-8")

        response = self.client.get("/api/llm-extracts/extract.txt")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["parsed"]["architecture"]["actors"], ["Users"])
        self.assertIsNone(payload["parse_error"])

    def test_rejects_path_traversal(self):
        response = self.client.get("/api/llm-extracts/..%2Fsecret.txt")

        self.assertEqual(response.status_code, 404)

    def test_generate_extract_preserves_response_filename_date(self):
        responses_dir = self.root / "responses"
        prompts_dir = self.root / "LLM-Prompts"
        responses_dir.mkdir()
        prompts_dir.mkdir()
        (prompts_dir / "Response-Extractor-prompt.txt").write_text("Return JSON only.", encoding="utf-8")
        (responses_dir / "llmsec_2026-12-30_10-20-30.json").write_text(
            json.dumps(
                {
                    "answers": [
                        {
                            "flow_id": "Q1",
                            "answer": "Customer support assistant",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch("app.services.llm_extract_service.chat") as mock_chat:
            mock_chat.return_value = {
                "model": "test-model",
                "message": {
                    "role": "assistant",
                    "content": '{"system_summary": {"purpose": "Customer support assistant"}}',
                },
            }

            response = self.client.post(
                "/api/generate-extract",
                json={
                    "response_file": "llmsec_2026-12-30_10-20-30.json",
                    "project_name": "LLM Sentinel",
                    "model_title": "Support TM",
                },
            )

        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["filename"], "llmsec_2026-12-30_10-20-30-extract.json")
        self.assertTrue((self.extract_dir / "llmsec_2026-12-30_10-20-30-extract.json").exists())
        self.assertEqual(
            payload["parsed"]["system_summary"]["purpose"],
            "Customer support assistant",
        )

    def test_parse_extract_json_recovers_fenced_json_with_trailing_commas(self):
        raw = """
        Here is the extract:
        ```json
        {
          "system_summary": {
            "purpose": "Docs assistant",
          },
          "dfd": {
            "actors": [],
          },
        }
        ```
        """

        parsed = parse_extract_json(raw)

        self.assertEqual(parsed["system_summary"]["purpose"], "Docs assistant")
        self.assertEqual(parsed["dfd"]["actors"], [])

    def test_generate_extract_falls_back_when_llm_returns_non_json(self):
        responses_dir = self.root / "responses"
        prompts_dir = self.root / "LLM-Prompts"
        responses_dir.mkdir()
        prompts_dir.mkdir()
        (prompts_dir / "Response-Extractor-prompt.txt").write_text("Return JSON only.", encoding="utf-8")
        (responses_dir / "llmsec_bad_json.json").write_text(
            json.dumps({"answers_by_flow_id": {"Q1": "Docs assistant", "Q2": ["Internal users"]}}),
            encoding="utf-8",
        )

        with patch("app.services.llm_extract_service.chat") as mock_chat:
            mock_chat.return_value = {
                "model": "test-model",
                "message": {"role": "assistant", "content": "I cannot produce JSON for this request."},
            }

            response = self.client.post(
                "/api/generate-extract",
                json={"response_file": "llmsec_bad_json.json", "project_name": "Docs"},
            )

        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["parsed"]["system_summary"]["purpose"], "Docs assistant")
        self.assertEqual(
            payload["parsed"]["llm_parse_error"],
            "LLM returned a response that could not be parsed as JSON.",
        )
        self.assertTrue((self.extract_dir / "llmsec_bad_json-extract.raw.txt").exists())
        self.assertTrue((self.extract_dir / "llmsec_bad_json-extract.json").exists())

    def test_generate_extract_preserves_valid_json_even_when_schema_is_legacy(self):
        responses_dir = self.root / "responses"
        prompts_dir = self.root / "LLM-Prompts"
        responses_dir.mkdir()
        prompts_dir.mkdir()
        (prompts_dir / "Response-Extractor-prompt.txt").write_text("Return JSON only.", encoding="utf-8")
        (responses_dir / "llmsec_legacy_extract.json").write_text(
            json.dumps({"answers_by_flow_id": {"Q1": "Docs assistant", "Q3": ["Web-based chat interface"]}}),
            encoding="utf-8",
        )
        legacy_extract = {
            "system": {
                "name": "DocsAI",
                "description": "Documentation assistant",
            },
            "llm_components": {
                "model": "Large Language Model",
            },
        }

        with patch("app.services.llm_extract_service.chat") as mock_chat:
            mock_chat.return_value = {
                "model": "test-model",
                "message": {"role": "assistant", "content": json.dumps(legacy_extract)},
            }

            response = self.client.post(
                "/api/generate-extract",
                json={"response_file": "llmsec_legacy_extract.json", "project_name": "Docs"},
            )

        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["parsed"], legacy_extract)
        self.assertIsNone(payload["parse_warning"])
        self.assertTrue((self.extract_dir / "llmsec_legacy_extract-extract.json").exists())


if __name__ == "__main__":
    unittest.main()
