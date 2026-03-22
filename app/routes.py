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

from app.utils.questionnaire_flow import (
    extract_answer,
    get_first_question_id,
    get_next_question,
    get_question_by_id,
    load_questions,
    split_answer_for_display,
)
from app.utils.save_utils import (
    append_question_to_layer,
    save_adaptive_llm_sec_answers,
    save_answers,
)


AVAILABLE_LAYERS = ["layer1", "layer2", "layer3", "layer4", "layer5", "layer6"]
LLM_SEC_SESSION_KEY = "llm_sec_flow"

main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("home.html", active_tab="home")


@main.route("/favicon.ico")
def favicon():
    return ("", 204)


@main.route("/form")
def form_redirect():
    return redirect(url_for("main.llm_sec"), code=302)


@main.route("/form/<layer_name>", methods=["GET", "POST"])
def form(layer_name):
    questions_path = Path(current_app.root_path) / "questions" / f"{layer_name}.json"

    if not questions_path.exists():
        abort(404, description=f"Question file for {layer_name} not found.")

    with questions_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    else:
        questions = data

    if request.method == "POST":
        save_answers(request.form, layer_name=layer_name)

        try:
            current_index = AVAILABLE_LAYERS.index(layer_name)
            if current_index + 1 < len(AVAILABLE_LAYERS):
                next_layer = AVAILABLE_LAYERS[current_index + 1]
                return redirect(url_for("main.form", layer_name=next_layer))
        except ValueError:
            pass

        return redirect(url_for("main.home"))

    return render_template(
        "form.html",
        active_tab="form",
        layer_name=layer_name,
        questions=questions,
        available_layers=AVAILABLE_LAYERS,
    )


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
    question_catalog = load_questions(current_app.root_path)

    if request.args.get("restart") == "1":
        session.pop(LLM_SEC_SESSION_KEY, None)

    flow_state = _get_llm_sec_flow_state()

    if request.method == "POST":
        current_flow_id = request.form.get("current_flow_id") or flow_state["current_flow_id"]
        current_question = get_question_by_id(current_app.root_path, current_flow_id)

        if current_question is None:
            abort(400, description="Invalid questionnaire state.")

        flow_state["answers"][current_flow_id] = extract_answer(request.form, current_question)

        action = request.form.get("action", "next")

        if action == "back":
            flow_state["current_flow_id"] = _get_previous_flow_id(flow_state["history"], current_flow_id)
        else:
            _truncate_history_after(flow_state["history"], current_flow_id)
            _trim_answers_to_history(flow_state)
            next_flow_id = get_next_question(current_flow_id, flow_state["answers"])

            if next_flow_id is None:
                save_adaptive_llm_sec_answers(
                    flow_state["answers"],
                    question_catalog,
                )
                session.pop(LLM_SEC_SESSION_KEY, None)
                flash("LLM Security Assessment saved successfully.", "success")
                return redirect(url_for("main.llm_sec"))

            if next_flow_id not in flow_state["history"]:
                flow_state["history"].append(next_flow_id)

            flow_state["current_flow_id"] = next_flow_id

        _save_llm_sec_flow_state(flow_state)
        return redirect(url_for("main.llm_sec"))

    current_flow_id = flow_state["current_flow_id"]
    current_question = get_question_by_id(current_app.root_path, current_flow_id)

    if current_question is None:
        abort(500, description="Unable to load the current question.")

    selected_answers, other_answer = split_answer_for_display(
        current_question,
        flow_state["answers"].get(current_flow_id),
    )

    return render_template(
        "llm_sec.html",
        active_tab="llm_sec",
        current_question=current_question,
        current_flow_id=current_flow_id,
        current_answer=flow_state["answers"].get(current_flow_id),
        selected_answers=selected_answers,
        other_answer=other_answer,
        can_go_back=len(flow_state["history"]) > 1,
        is_last_question=get_next_question(current_flow_id, flow_state["answers"]) is None,
        total_questions=len(question_catalog),
        answered_count=len([answer for answer in flow_state["answers"].values() if answer not in (None, "", [])]),
    )


def _get_llm_sec_flow_state():
    state = session.get(LLM_SEC_SESSION_KEY)
    if state:
        return state

    initial_flow_id = get_first_question_id()
    state = {
        "current_flow_id": initial_flow_id,
        "history": [initial_flow_id],
        "answers": {},
    }
    session[LLM_SEC_SESSION_KEY] = state
    return state


def _save_llm_sec_flow_state(state):
    session[LLM_SEC_SESSION_KEY] = state
    session.modified = True


def _get_previous_flow_id(history, current_flow_id):
    if current_flow_id not in history:
        return history[-1]

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


def _trim_answers_to_history(flow_state):
    valid_question_ids = set(flow_state["history"])
    for question_id in list(flow_state["answers"].keys()):
        if question_id not in valid_question_ids:
            del flow_state["answers"][question_id]
