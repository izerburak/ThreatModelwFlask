import json
import unittest
from unittest.mock import patch

from app.services.llm_risk_review import review_risk_analysis


class LlmRiskReviewTests(unittest.TestCase):
    @patch("app.services.llm_risk_review.chat")
    def test_review_payload_includes_dread_context(self, chat_mock):
        chat_mock.return_value = {
            "model": "local-reviewer",
            "message": {
                "content": json.dumps(
                    {
                        "assessments": [
                            {
                                "code": "LLM01",
                                "applies": True,
                                "assessed_level": "High",
                                "rationale": "Prompt exposure is reachable through the public API.",
                                "priority": "P1",
                                "mitigations": [
                                    {
                                        "title": "Harden prompt boundary",
                                        "action": "Keep retrieved content outside system instructions.",
                                        "priority": "High",
                                    }
                                ],
                            }
                        ]
                    }
                )
            },
        }
        dread = {
            "damage": 3,
            "reproducibility": 2,
            "exploitability": 3,
            "affected_users": 2,
            "discoverability": 2,
            "total": 12,
            "band": "High",
        }
        risk_analysis = {
            "unified_risks": [
                {
                    "code": "LLM01",
                    "name": "Prompt Injection",
                    "risk_level": "High",
                    "score": 12,
                    "dread": dread,
                    "question_evidence": [{"question": "Q30", "answer": "No safeguards"}],
                    "mitigations": ["Separate the system prompt from user input."],
                }
            ]
        }

        reviewed = review_risk_analysis(risk_analysis, {"Q30": "No safeguards"})

        messages = chat_mock.call_args.args[0]
        payload = json.loads(messages[1]["content"])
        candidate = payload["candidate_risks"][0]

        self.assertEqual(candidate["dread"], dread)
        self.assertEqual(candidate["score"], 12)
        self.assertEqual(reviewed["unified_risks"][0]["llm_assessment"]["assessed_level"], "High")
        self.assertEqual(reviewed["llm_review"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
