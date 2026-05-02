import unittest
from unittest.mock import patch

try:
    from app import create_app
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "flask":
        raise
    create_app = None


class OllamaRoutesTests(unittest.TestCase):
    def setUp(self):
        if create_app is None:
            self.skipTest("Flask is not installed in the active Python environment.")

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_llm_page_renders_configured_model(self):
        response = self.client.get("/llm")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"qwen3:8b", response.data)

    def test_llm_page_normalizes_bind_host_for_client_requests(self):
        self.app.config["OLLAMA_HOST"] = "0.0.0.0:11434"

        response = self.client.get("/llm")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"http://127.0.0.1:11434", response.data)

    @patch("app.routes.list_models")
    def test_llm_status_reports_available_model(self, list_models_mock):
        list_models_mock.return_value = [{"name": "qwen3:8b"}]

        response = self.client.get("/api/llm/status")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    @patch("app.routes.ollama_chat")
    def test_llm_chat_accepts_messages(self, chat_mock):
        chat_mock.return_value = {
            "model": "qwen3:8b",
            "message": {"role": "assistant", "content": "pong"},
            "done": True,
        }

        response = self.client.post(
            "/api/llm/chat",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"]["content"], "pong")
        chat_mock.assert_called_once()

    def test_llm_chat_rejects_empty_payload(self):
        response = self.client.post("/api/llm/chat", json={})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
