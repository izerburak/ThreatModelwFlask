import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jinja2 import FileSystemLoader

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

    def test_pipeline_manifest_excludes_llm_extraction_step(self):
        orchestrator = PipelineOrchestrator(str(self.app_dir))
        manifest = orchestrator.create_pipeline(self.response_file, project_name="Docs")

        pipeline_dir = self.root / "pipelines" / manifest["pipeline_id"]
        updated_manifest = orchestrator.get_manifest(manifest["pipeline_id"])

        self.assertTrue((pipeline_dir / "response.json").exists())
        self.assertFalse((pipeline_dir / "extraction_raw.json").exists())
        self.assertFalse((pipeline_dir / "llm_extraction.json").exists())
        self.assertFalse((pipeline_dir / "extraction_reviewed.json").exists())
        self.assertNotIn("llm_extraction_generated", updated_manifest["steps"])
        self.assertIn("dfd_generated", updated_manifest["steps"])
        self.assertIn("risk_analysis_completed", updated_manifest["steps"])
        self.assertNotIn("extraction_reviewed", updated_manifest["steps"])

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
        self.app.jinja_loader = FileSystemLoader(str(Path(__file__).resolve().parents[1] / "app" / "templates"))
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

    def test_completed_pipeline_detail_renders(self):
        orchestrator = PipelineOrchestrator(str(self.app_dir))
        manifest = orchestrator.create_pipeline(self.response_file, project_name="Docs", dfd_name="Docs Threat Model")
        pipeline_id = manifest["pipeline_id"]
        pipeline_dir = self.root / "pipelines" / pipeline_id

        (pipeline_dir / "dfd_reactflow.json").write_text(
            json.dumps(
                {
                    "nodes": [{"id": "actor_user", "type": "actor", "data": {"label": "User"}}],
                    "edges": [],
                }
            ),
            encoding="utf-8",
        )
        (pipeline_dir / "risks.json").write_text(
            json.dumps(
                {
                    "overall_status": "High",
                    "unified_risks": [
                        {
                            "code": "LLM01",
                            "name": "Prompt Injection",
                            "risk_level": "High",
                            "mitigations": ["Validate instructions before tool use."],
                        }
                    ],
                    "quick_wins": [],
                }
            ),
            encoding="utf-8",
        )
        manifest["status"] = "risk_analysis_completed"
        manifest["steps"]["dfd_generated"]["done"] = True
        manifest["steps"]["risk_analysis_completed"]["done"] = True
        (pipeline_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        response = self.client.get(f"/pipeline/{pipeline_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Docs Threat Model", response.data)


if __name__ == "__main__":
    unittest.main()
