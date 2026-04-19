import json
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.question_flow import clear_question_flow_caches, get_question_flow_engine
from app.utils.save_utils import (
    append_question_to_layer,
    save_adaptive_llm_sec_answers,
)


LLM_SEC_SESSION_KEY = "llm_sec_flow"

main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("home.html", active_tab="home")


@main.route("/favicon.ico")
def favicon():
    return ("", 204)


@main.route("/add-question", methods=["GET", "POST"])
def add_question():
    if request.method == "POST":
        if not request.is_json:
            return jsonify({"ok": False, "error": "Expected JSON"}), 400

        payload = request.get_json()
        layer = payload.get("layer")
        text = payload.get("text", "").strip()
        options = payload.get("options", []) or []

        if not layer or not text:
            return jsonify({"ok": False, "error": "layer and text required"}), 400

        try:
            qpath, new_q = append_question_to_layer(layer, text, options)
            clear_question_flow_caches()
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

        return jsonify({"ok": True, "path": qpath, "question": new_q})

    return render_template("add_question.html", active_tab="add")


@main.route("/dfd", methods=["GET", "POST"])
def dfd():
    responses_dir = Path(current_app.root_path).parent / "responses"
    response_files = []

    if responses_dir.exists():
        response_files = sorted([f.name for f in responses_dir.glob("*.json")])

    if request.method == "POST":
        selected_file = request.form.get("response_file")
        return render_template(
            "dfd.html",
            active_tab="dfd",
            response_files=response_files,
            selected_file=selected_file,
        )

    return render_template(
        "dfd.html",
        active_tab="dfd",
        response_files=response_files,
    )


@main.route("/risk", methods=["GET", "POST"])
def risk():
    responses_dir = Path(current_app.root_path).parent / "responses"
    response_files = []

    if responses_dir.exists():
        response_files = sorted([f.name for f in responses_dir.glob("*.json")])

    if request.method == "POST":
        selected_file = request.form.get("response_file")
        return render_template(
            "risk.html",
            active_tab="risk",
            response_files=response_files,
            selected_file=selected_file,
        )

    return render_template(
        "risk.html",
        active_tab="risk",
        response_files=response_files,
    )


@main.route("/llm-sec", methods=["GET", "POST"])
def llm_sec():
    flow_engine = get_question_flow_engine(current_app.root_path)

    if request.args.get("restart") == "1":
        session.pop(LLM_SEC_SESSION_KEY, None)

    flow_state = _get_llm_sec_flow_state(flow_engine)

    if request.method == "POST":
        current_flow_id = request.form.get("current_flow_id") or flow_state["current_flow_id"]
        current_question = flow_engine.get_question(current_flow_id)

        if current_question is None:
            abort(400, description="Invalid questionnaire state.")

        flow_state["answers"][current_flow_id] = flow_engine.extract_answer(request.form, current_question)

        action = request.form.get("action", "next")

        if action == "back":
            flow_state["current_flow_id"] = _get_previous_flow_id(flow_state["history"], current_flow_id, flow_engine)
        else:
            _truncate_history_after(flow_state["history"], current_flow_id)
            flow_state["answers"] = flow_engine.trim_answers_to_active_path(flow_state["answers"])
            next_flow_id = flow_engine.get_current_or_next_unanswered(flow_state["answers"])

            if next_flow_id is None:
                save_adaptive_llm_sec_answers(
                    flow_state["answers"],
                    flow_engine.question_catalog,
                )
                session.pop(LLM_SEC_SESSION_KEY, None)
                flash("LLM Security Assessment saved successfully.", "success")
                return redirect(url_for("main.llm_sec"))

            if not flow_state["history"] or flow_state["history"][-1] != current_flow_id:
                flow_state["history"].append(current_flow_id)

            if next_flow_id not in flow_state["history"]:
                flow_state["history"].append(next_flow_id)

            flow_state["current_flow_id"] = next_flow_id

        _save_llm_sec_flow_state(flow_state)
        return redirect(url_for("main.llm_sec"))

    current_flow_id = flow_state["current_flow_id"]
    current_question = flow_engine.get_question(current_flow_id)
    active_question_path = flow_engine.get_question_path(flow_state["answers"])

    if current_question is None:
        abort(500, description="Unable to load the current question.")

    selected_answers, other_answer = flow_engine.split_answer_for_display(
        current_question,
        flow_state["answers"].get(current_flow_id),
    )
    next_flow_id = flow_engine.get_next_question(current_flow_id, flow_state["answers"])
    current_answer_value = flow_state["answers"].get(current_flow_id)
    is_current_answered = current_answer_value not in (None, "", [])
    is_terminal_step = bool(active_question_path) and current_flow_id == active_question_path[-1]

    return render_template(
        "llm_sec.html",
        active_tab="llm_sec",
        current_question=current_question,
        current_flow_id=current_flow_id,
        current_answer=current_answer_value,
        selected_answers=selected_answers,
        other_answer=other_answer,
        can_go_back=len(flow_state["history"]) > 1,
        is_last_question=next_flow_id is None and is_terminal_step and is_current_answered,
        total_questions=len(active_question_path),
        answered_count=len(
            [
                question_id
                for question_id in active_question_path
                if flow_state["answers"].get(question_id) not in (None, "", [])
            ]
        ),
    )


def _get_llm_sec_flow_state(flow_engine):
    state = session.get(LLM_SEC_SESSION_KEY)
    if state:
        current_flow_id = state.get("current_flow_id")
        answers = flow_engine.trim_answers_to_active_path(state.get("answers") or {})
        active_path = flow_engine.get_question_path(answers)
        next_unanswered = flow_engine.get_current_or_next_unanswered(answers)
        history = [qid for qid in (state.get("history") or []) if qid in active_path]

        if active_path:
            if not history:
                history = [active_path[0]]
            if next_unanswered and next_unanswered not in history:
                history.append(next_unanswered)

            repaired_state = {
                "current_flow_id": current_flow_id if current_flow_id in active_path else (next_unanswered or active_path[0]),
                "history": history,
                "answers": answers,
            }
            session[LLM_SEC_SESSION_KEY] = repaired_state
            return repaired_state

    initial_flow_id = flow_engine.get_start_question()
    state = {
        "current_flow_id": initial_flow_id,
        "history": [initial_flow_id] if initial_flow_id else [],
        "answers": {},
    }
    session[LLM_SEC_SESSION_KEY] = state
    return state


def _save_llm_sec_flow_state(state):
    session[LLM_SEC_SESSION_KEY] = state
    session.modified = True


def _get_previous_flow_id(history, current_flow_id, flow_engine):
    if current_flow_id not in history:
        return history[-1] if history else flow_engine.get_start_question()

    current_index = history.index(current_flow_id)
    if current_index == 0:
        return current_flow_id

    return history[current_index - 1]


def _truncate_history_after(history, current_flow_id):
    if current_flow_id not in history:
        history.append(current_flow_id)
        return

    current_index = history.index(current_flow_id)
    del history[current_index + 1:]
