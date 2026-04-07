import unittest
import importlib.util
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT_PATH / "app" / "utils" / "questionnaire_flow.py"
SPEC = importlib.util.spec_from_file_location("questionnaire_flow", MODULE_PATH)
questionnaire_flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(questionnaire_flow)

build_survey_state = questionnaire_flow.build_survey_state
get_follow_up_questions = questionnaire_flow.get_follow_up_questions


def _pending(answers):
    return build_survey_state(answers, ROOT_PATH)["pending_question_queue"]


class QuestionnaireFlowTests(unittest.TestCase):
    def test_q2_public_user_branch_appends_all_then_next_after(self):
        answers = {
            "Q1": "answered",
            "Q2": ["Anonymous public internet users", "Authenticated public users"],
        }

        self.assertEqual(_pending(answers), ["Q3", "Q25", "Q26", "Q34", "Q4"])

    def test_q4_yes_branch_appends_q24_then_q5(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "Yes",
        }

        self.assertEqual(_pending(answers), ["Q24", "Q5"])

    def test_q6_matching_branch_appends_q7_q30_then_q8(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": ["File uploads"],
        }

        self.assertEqual(_pending(answers), ["Q7", "Q30", "Q8"])

    def test_q8_rag_branch_appends_branch_questions_without_recursing_children(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": "Structured application data only",
            "Q7": "answered",
            "Q8": "Vector database retrieval",
        }

        self.assertEqual(_pending(answers), ["Q27", "Q36", "Q20", "Q32", "Q9"])

    def test_q10_not_no_branch_appends_q32_then_q11(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": "Structured application data only",
            "Q7": "answered",
            "Q8": "No RAG",
            "Q9": "answered",
            "Q10": "Yes",
        }

        self.assertEqual(_pending(answers), ["Q32", "Q11"])

    def test_q11_not_any_of_branch_appends_q18_then_q12(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": "Structured application data only",
            "Q7": "answered",
            "Q8": "No RAG",
            "Q9": "answered",
            "Q10": "No",
            "Q11": ["Model firewall"],
        }

        self.assertEqual(_pending(answers), ["Q18", "Q12"])

    def test_q12_not_includes_none_branch_appends_q13_q14_q15_then_q17(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": "Structured application data only",
            "Q7": "answered",
            "Q8": "No RAG",
            "Q9": "answered",
            "Q10": "No",
            "Q11": "None",
            "Q12": ["Read internal knowledge", "Create or update tickets/records"],
        }

        self.assertEqual(_pending(answers), ["Q13", "Q14", "Q15", "Q17"])

    def test_q15_matching_branch_appends_all_then_q17(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": "Structured application data only",
            "Q7": "answered",
            "Q8": "No RAG",
            "Q9": "answered",
            "Q10": "No",
            "Q11": "None",
            "Q12": ["Create or update tickets/records"],
            "Q13": "answered",
            "Q14": "answered",
            "Q15": ["Send emails or notifications"],
        }

        self.assertEqual(_pending(answers), ["Q31", "Q28", "Q16", "Q39", "Q17"])

    def test_q22_does_not_append_duplicate_answered_questions(self):
        answers = {
            "Q1": "answered",
            "Q2": "Internal employees only",
            "Q3": "answered",
            "Q25": "answered",
            "Q26": "answered",
            "Q4": "No",
            "Q5": "answered",
            "Q6": "Structured application data only",
            "Q7": "answered",
            "Q8": "No RAG",
            "Q9": "answered",
            "Q10": "No",
            "Q11": "None",
            "Q12": ["Create or update tickets/records"],
            "Q13": "answered",
            "Q14": "answered",
            "Q15": ["Send emails or notifications"],
            "Q31": "already answered",
            "Q28": "answered",
            "Q16": "answered",
            "Q39": "answered",
            "Q17": "answered",
            "Q35": "answered",
            "Q19": "answered",
            "Q20": "answered",
            "Q21": "answered",
            "Q22": "API response consumed by other systems",
        }

        self.assertEqual(_pending(answers), ["Q23"])

    def test_follow_up_questions_for_q2_match_expected_example(self):
        answers = {
            "Q2": ["Anonymous public internet users"],
        }

        self.assertEqual(
            get_follow_up_questions("Q2", answers, ROOT_PATH),
            ["Q3", "Q25", "Q26", "Q34", "Q4"],
        )


if __name__ == "__main__":
    unittest.main()
