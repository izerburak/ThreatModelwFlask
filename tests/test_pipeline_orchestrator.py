import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from app import create_app
    from app.services.pipeline_orchestrator import PipelineOrchestrator
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "flask":
        raise
    create_app = None
    PipelineOrchestrator = None


class PipelineOrchestratorTests(unittest.TestCase):
    def setUp(self):
        if PipelineOrchestrator is None:
            self.skipTest("Flask is not installed in the active Python environment.")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        self.responses_dir = self.root / "responses"
        self.app_dir.mkdir()
        self.responses_dir.mkdir()
        self.response_file = "llmsec_test.json"
        (self.responses_dir / self.response_file).write_text(
            json.dumps(
                {
                    "answers_by_flow_id": {
                        "Q1": "Docs assistant",
                        "Q2": ["Authenticated public users"],
                        "Q3": ["REST API endpoint"],
                        "Q7": ["Input filtering"],
                        "Q17": "Third-party cloud API",
                    }
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pipeline_uses_single_raw_extraction_artifact(self):
        orchestrator = PipelineOrchestrator(str(self.app_dir))
        manifest = orchestrator.create_pipeline(self.response_file, project_name="Docs")

        with patch("app.services.pipeline_orchestrator.generate_llm_extract") as mock_generate:
            mock_generate.return_value = {
                "parsed": {
                    "system_summary": {
                        "purpose": "Docs assistant",
                        "exposure": "Unknown",
                        "architecture_style": "Unknown",
                        "overall_dfd_confidence": "Low",
                    },
                    "dfd": {},
                }
            }
            orchestrator.generate_extraction(manifest["pipeline_id"])

        pipeline_dir = self.root / "pipelines" / manifest["pipeline_id"]
        updated_manifest = orchestrator.get_manifest(manifest["pipeline_id"])

        self.assertTrue((pipeline_dir / "extraction_raw.json").exists())
        self.assertFalse((pipeline_dir / "llm_extraction.json").exists())
        self.assertFalse((pipeline_dir / "extraction_reviewed.json").exists())
        self.assertIn("llm_extraction_generated", updated_manifest["steps"])
        self.assertNotIn("extraction_reviewed", updated_manifest["steps"])
        self.assertEqual(
            updated_manifest["steps"]["llm_extraction_generated"]["artifact"],
            "extraction_raw.json",
        )

    def test_pipeline_dfd_uses_static_mapper_without_extraction_artifact(self):
        orchestrator = PipelineOrchestrator(str(self.app_dir))
        manifest = orchestrator.create_pipeline(self.response_file, project_name="Docs", dfd_name="Docs DFD")

        graph = orchestrator.generate_dfd(manifest["pipeline_id"])
        pipeline_dir = self.root / "pipelines" / manifest["pipeline_id"]
        updated_manifest = orchestrator.get_manifest(manifest["pipeline_id"])
        node_ids = {node["id"] for node in graph["nodes"]}
        edges = {(edge["source"], edge["target"], edge["label"]) for edge in graph["edges"]}

        self.assertTrue((pipeline_dir / "dfd_reactflow.json").exists())
        self.assertFalse((pipeline_dir / "extraction_raw.json").exists())
        self.assertIn("actor_authenticated_user", node_ids)
        self.assertIn("entry_rest_api", node_ids)
        self.assertIn(("actor_authenticated_user", "entry_rest_api", "Authenticated request"), edges)
        self.assertEqual(graph["metadata"]["pipeline_source"], "static_dfd_mapper")
        self.assertEqual(graph["metadata"]["graph_mode"], "canonical")
        self.assertTrue(graph["metadata"]["canonical_graph"])
        self.assertTrue(updated_manifest["steps"]["dfd_generated"]["done"])
        self.assertIn("dfd_archive", updated_manifest)


class PipelineStartApiTests(unittest.TestCase):
    def setUp(self):
        if create_app is None:
            self.skipTest("Flask is not installed in the active Python environment.")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        self.responses_dir = self.root / "responses"
        self.app_dir.mkdir()
        self.responses_dir.mkdir()
        self.response_file = "llmsec_test.json"
        (self.responses_dir / self.response_file).write_text(
            json.dumps({"answers_by_flow_id": {"Q1": "Docs assistant"}}),
            encoding="utf-8",
        )
        self.app = create_app()
        self.app.root_path = str(self.app_dir)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.routes._start_pipeline_background")
    def test_pipeline_start_api_returns_manifest_urls_and_starts_worker(self, start_background):
        response = self.client.post(
            "/api/pipeline/start",
            data={
                "response_filename": self.response_file,
                "project_name": "Docs",
                "dfd_name": "Docs Threat Model",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(payload["ok"])
        self.assertIn("/pipeline/", payload["detail_url"])
        self.assertIn("/api/pipeline/", payload["manifest_url"])
        start_background.assert_called_once()

        manifest_path = self.root / "pipelines" / payload["pipeline_id"] / "manifest.json"
        self.assertTrue(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
