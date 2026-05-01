import tempfile
import unittest
from pathlib import Path

try:
    from app import create_app
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "flask":
        raise
    create_app = None


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


if __name__ == "__main__":
    unittest.main()
