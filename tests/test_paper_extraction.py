import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.services.sustainability.paper_extraction import (
    ExtractionError, fetch_source, validate_output, extract, training_sample,
)

TEXT = "Untrusted retrieved documents expose the retrieval pipeline to prompt injection. Input isolation reduces this attack."


def findings():
    return {"attack_surfaces": [{"id": "A1", "name": "Retrieval", "description": "Untrusted retrieval input",
                                 "evidence_quote": "Untrusted retrieved documents expose the retrieval pipeline"}],
            "mitigations": [{"id": "M1", "name": "Isolation", "description": "Isolate input",
                             "attack_surface_ids": ["A1"], "evidence_quote": "Input isolation reduces this attack."}],
            "limitations": []}


class PaperExtractionTests(unittest.TestCase):
    def test_grounding_and_relations(self):
        validate_output(findings(), TEXT)
        bad = findings()
        bad["mitigations"][0]["evidence_quote"] = "This sentence is invented by the model."
        with self.assertRaises(ExtractionError):
            validate_output(bad, TEXT)
        bad = findings()
        bad["mitigations"][0]["attack_surface_ids"] = ["A2"]
        with self.assertRaises(ExtractionError):
            validate_output(bad, TEXT)

    def test_fetch_rejects_non_arxiv_before_network(self):
        for url in ["http://127.0.0.1/abs/2601.12345", "https://arxiv.org.evil.test/abs/2601.12345",
                    "https://arxiv.org:443/abs/2601.12345", "https://arxiv.org/abs/../admin"]:
            with self.assertRaises(ExtractionError):
                fetch_source(url)

    def test_only_checked_paper_is_fetched_and_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app()
            app.config.update(TESTING=True, OPENAI_API_KEY="test-key", PAPER_EXTRACTION_DIR=directory)
            candidates = [{"arxiv_id": f"2601.1234{x}", "paper_url": f"https://arxiv.org/abs/2601.1234{x}",
                           "title": f"Paper {x}"} for x in [1, 2]]
            source = {"url": candidates[1]["paper_url"], "title": "Paper 2", "mode": "abstract", "text": TEXT}
            with patch("app.paper_routes.SustainabilityService.view_state", return_value={"last_scan": {"papers": candidates, "summary": {}}, "keywords": {"security": [], "llm": []}, "custom_keywords": {"security": [], "llm": []}, "strong_candidates": [], "excluded_papers": []}), \
                 patch("app.paper_routes.fetch_source", return_value=source) as fetch, \
                 patch.dict("app.services.sustainability.paper_extraction.PROVIDERS", {"openai": lambda *args: (findings(), {"usage": {"input_tokens": 30}})}):
                client = app.test_client()
                self.assertEqual(client.get("/sustainability/extract").status_code, 200)
                fetch.assert_not_called()
                response = client.post("/sustainability/extract", data={"paper_id": "2601.12342", "model": "test-model"})
                self.assertEqual(response.status_code, 200)
                fetch.assert_called_once_with(candidates[1]["paper_url"], "abstract")
                files = list(Path(directory).glob("*.json"))
                self.assertEqual(len(files), 1)
                run = json.loads(files[0].read_text(encoding="utf-8"))
                self.assertNotIn("test-key", files[0].read_text(encoding="utf-8"))
                exported = client.get(f"/sustainability/extractions/{run['id']}/jsonl")
                self.assertEqual(json.loads(exported.data), training_sample(run))
                self.assertEqual(client.get("/sustainability/extractions/invalid/json").status_code, 404)
                fetch.reset_mock()
                client.post("/sustainability/extract", data={"model": "test-model"})
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
