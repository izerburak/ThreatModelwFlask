import sys
import importlib.util
from pathlib import Path

repo_root = Path(__file__).resolve().parent
root_path = repo_root

# Load module directly
module_path = repo_root / "app" / "utils" / "questionnaire_flow.py"
spec = importlib.util.spec_from_file_location("questionnaire_flow", module_path)
qflow = importlib.util.module_from_spec(spec)
sys.modules["questionnaire_flow"] = qflow
spec.loader.exec_module(qflow)

def run_test():
    print("Testing flow parser...")
    first_q = qflow.get_first_question_id()
    print(f"First Question: {first_q}")
    
    questions = qflow.load_questions(root_path)
    print(f"Loaded {len(questions)} questions")
    
    # Test path where everything is NO / internal
    print("\n--- Test Path: All No / None ---")
    answers = {}
    curr = first_q
    while curr is not None:
        print(f"-> {curr}: {questions[curr]['text']}")
        
        # answer NO or None
        if curr == "Q2": answers[curr] = ["Internal employees only"]
        elif curr == "Q4": answers[curr] = ["No"]
        elif curr == "Q5": answers[curr] = ["Direct user prompts"]
        elif curr == "Q6": answers[curr] = ["User text input only"]
        elif curr == "Q8": answers[curr] = ["No RAG"]
        elif curr == "Q9": answers[curr] = ["Frontend"]
        elif curr == "Q10": answers[curr] = ["No"]
        elif curr == "Q11": answers[curr] = ["None"]
        elif curr == "Q12": answers[curr] = ["None"]
        elif curr == "Q13": answers[curr] = ["None"]
        elif curr == "Q14": answers[curr] = ["No"]
        elif curr == "Q15": answers[curr] = ["Generate text responses only"]
        elif curr == "Q17": answers[curr] = ["Self-hosted on internal infrastructure"]
        elif curr == "Q19": answers[curr] = ["Hardcoded in application logic"]
        elif curr == "Q21": answers[curr] = ["Plain text only"]
        elif curr == "Q22": answers[curr] = ["Internal admin dashboard"]
        elif curr == "Q23": answers[curr] = ["No significant trust boundary"]
        elif curr == "Q29": answers[curr] = ["Public chat interface"]
        curr = qflow.get_next_question(curr, answers, root_path)

if __name__ == "__main__":
    run_test()
