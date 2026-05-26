import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.pipeline_orchestrator import PipelineOrchestrator


class PipelineOrchestratorTests(unittest.TestCase):
    def setUp(self):
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
        self.assertEqual(graph["metadata"]["graph_mode"], "compact")
        self.assertTrue(updated_manifest["steps"]["dfd_generated"]["done"])
        self.assertIn("dfd_archive", updated_manifest)


if __name__ == "__main__":
    unittest.main()
