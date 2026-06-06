import importlib.util
import unittest
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT_PATH / "app" / "question_flow.py"
SPEC = importlib.util.spec_from_file_location("question_flow", MODULE_PATH)
question_flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(question_flow)


def _engine():
    question_flow.clear_question_flow_caches()
    return question_flow.QuestionFlowEngine(ROOT_PATH)


def _pending(answers):
    return _engine()._build_survey_state(answers)["pending_question_ids"]


def _answered_to_q8():
    return {
        "Q1": "Customer support assistant",
        "Q2": ["Internal employees only"],
        "Q25": "Single sign-on (SSO)",
        "Q26": "Role-based access control (RBAC)",
        "Q41": "User identity consistently enforced end-to-end",
        "Q50": "Yes, revalidated on every sensitive request",
        "Q3": ["CLI or local scripts"],
        "Q40": "Single-tenant system",
        "Q4": "No",
        "Q5": ["Direct user prompts"],
        "Q6": ["Structured application data only"],
        "Q7": ["Input filtering"],
    }


def _answered_to_q12():
    answers = _answered_to_q8()
    answers.update(
        {
            "Q8": ["No RAG"],
            "Q43": "No reuse",
            "Q9": ["Backend API"],
            "Q10": "No",
            "Q11": "None",
        }
    )
    return answers


def _answered_to_q42_with_q20_from_rag():
    answers = _answered_to_q8()
    answers.update(
        {
            "Q8": ["Internal knowledge base", "Documentation"],
            "Q27": "Yes, consistently enforced",
            "Q36": "Yes, strongly protected",
            "Q20": "No",
            "Q32": "DLP or content inspection mechanisms",
            "Q43": "No reuse",
            "Q68": "No shared indexing or cache exists",
            "Q69": "Yes, strong write controls and review",
            "Q9": ["Backend API"],
            "Q10": "No",
            "Q11": "None",
            "Q12": ["None"],
            "Q45": "No access to secrets or hidden data",
            "Q17": "Self-hosted on internal infrastructure",
            "Q35": "Security review and supply chain controls",
            "Q19": "Stored in configuration files",
        }
    )
    return answers


class QuestionnaireFlowTests(unittest.TestCase):
    def test_loads_all_questions_from_catalog(self):
        self.assertEqual(len(_engine().question_catalog), 82)

    def test_scenario_a_public_web_llm(self):
        answers = {
            "Q1": "Customer support assistant",
            "Q2": ["Anonymous public internet users"],
        }
        self.assertEqual(_pending(answers), ["Q25", "Q26", "Q41", "Q50", "Q34", "Q3"])

        answers.update(
            {
                "Q25": "No authentication required",
                "Q26": "No authorization controls",
                "Q41": "No identity propagation",
                "Q50": "No authentication or session context exists",
                "Q34": "No protections",
                "Q3": ["Web-based chat interface"],
            }
        )
        self.assertEqual(_pending(answers), ["Q48", "Q49", "Q51", "Q52", "Q58", "Q59", "Q40"])

    def test_scenario_b_rag_enabled(self):
        answers = _answered_to_q8()
        answers["Q8"] = ["Internal knowledge base", "Documentation"]

        self.assertEqual(_pending(answers), ["Q27", "Q36", "Q20", "Q32", "Q43", "Q68", "Q69", "Q9"])

    def test_scenario_c_duplicate_q20_continues_to_q21(self):
        answers = _answered_to_q42_with_q20_from_rag()
        answers.update(
            {
                "Q42": ["No one (static configuration)"],
                "Q71": "Yes, versioned with approval and audit trail",
            }
        )

        self.assertEqual(_pending(answers), ["Q21"])

    def test_scenario_d_tool_access_enabled(self):
        answers = _answered_to_q12()
        answers["Q12"] = ["Search", "Database", "Internal APIs"]

        self.assertEqual(
            _pending(answers),
            ["Q13", "Q14", "Q53", "Q54", "Q55", "Q56", "Q57", "Q58", "Q59", "Q72", "Q15", "Q44"],
        )

    def test_scenario_e_external_api_call(self):
        answers = _answered_to_q12()
        answers.update(
            {
                "Q12": ["Search", "Database", "Internal APIs"],
                "Q13": ["SQL/NoSQL"],
                "Q14": "Directly",
            }
        )

        self.assertEqual(_pending(answers)[:4], ["Q60", "Q61", "Q62", "Q63"])

    def test_scenario_f_action_beyond_text_generation(self):
        answers = _answered_to_q12()
        answers.update(
            {
                "Q12": ["Search", "Database", "Internal APIs"],
                "Q13": ["SQL/NoSQL"],
                "Q14": "No",
                "Q53": "Yes, with object-level authorization checks",
                "Q54": "Yes, with strict field-level authorization",
                "Q55": "Yes, but permission checks follow the current user",
                "Q56": "No, calls use user-scoped identity",
                "Q57": "Yes, reviewed and minimized",
                "Q58": "Yes, complete inventory and classification",
                "Q59": "No, only approved production APIs",
                "Q72": "Dedicated secret manager with least privilege",
                "Q15": ["Create or update tickets/records"],
            }
        )

        self.assertEqual(
            _pending(answers),
            ["Q31", "Q28", "Q16", "Q39", "Q65", "Q66", "Q75", "Q79", "Q80", "Q81", "Q82", "Q44"],
        )

    def test_scenario_g_rich_output(self):
        answers = _answered_to_q42_with_q20_from_rag()
        answers.update(
            {
                "Q42": ["No one (static configuration)"],
                "Q71": "Yes, versioned with approval and audit trail",
                "Q21": ["Markdown or rich text"],
            }
        )

        self.assertEqual(_pending(answers), ["Q64", "Q65", "Q66", "Q22"])

    def test_scenario_h_finish_reaches_end(self):
        engine = _engine()
        answers = {}
        defaults = {
            "Q1": "Customer support assistant",
            "Q2": ["Internal employees only"],
            "Q3": ["CLI or local scripts"],
            "Q4": "No",
            "Q6": ["Structured application data only"],
            "Q8": ["No RAG"],
            "Q10": "No",
            "Q11": "None",
            "Q12": ["None"],
            "Q20": "No",
            "Q21": ["Plain text only"],
            "Q22": ["No significant trust boundary"],
            "Q29": ["No significant trust boundary"],
            "Q42": ["No one (static configuration)"],
            "Q73": "Yes, encryption is enforced end-to-end where applicable",
            "Q81": ["All sensitive communication is encrypted"],
            "Q82": ["No sensitive data is transmitted"],
        }

        for _ in range(120):
            next_question = engine.get_current_or_next_unanswered(answers)
            if next_question is None:
                break
            answers[next_question] = defaults.get(next_question, "No")
        else:
            self.fail("Questionnaire did not reach END within 120 answers.")

        self.assertIn("Q38", answers)
        self.assertIsNone(engine.get_current_or_next_unanswered(answers))

    def test_condition_operators_handle_strings_lists_and_missing_values(self):
        self.assertEqual(question_flow._evaluate_condition({"equals": "Yes"}, "Yes"), (True, False))
        self.assertEqual(question_flow._evaluate_condition({"not_equals": "No"}, "Yes"), (True, False))
        self.assertEqual(question_flow._evaluate_condition({"any_of": ["Search"]}, ["Database", "Search"]), (True, False))
        self.assertEqual(question_flow._evaluate_condition({"not_any_of": ["None"]}, ["Search"]), (True, False))
        self.assertEqual(question_flow._evaluate_condition({"not_includes": "No RAG"}, ["Documentation"]), (True, False))
        self.assertEqual(question_flow._evaluate_condition({"equals": "Yes"}, None), (False, True))


if __name__ == "__main__":
    unittest.main()
