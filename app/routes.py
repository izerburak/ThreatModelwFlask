import json
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from app.question_flow import clear_question_flow_caches, get_question_flow_engine
from app.services.dfd_service import (
    export_diagram_as_mermaid,
    export_diagram_as_plantuml,
    list_response_files,
    load_model_record,
    load_response_payload,
    save_model_record,
)
from app.services.llm_generator import build_mock_dfd_payload
from app.services.ollama_client import OllamaError, chat as ollama_chat, get_ollama_config, list_models
from app.services.extract_to_reactflow import extract_to_reactflow
from app.services.llm_extract_service import generate_llm_extract
from app.services.risk_analysis_service import build_risk_analysis, suggested_extract_filename
from app.services.garak_service import garak_report_path, garak_status
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


@main.route("/dfd")
def dfd():
    ollama_config = get_ollama_config(current_app.config)
    return render_template(
        "dfd.html",
        active_tab="dfd",
        response_files=list_response_files(current_app.root_path),
        ollama_model=ollama_config["model"],
        ollama_host=ollama_config["host"],
    )


@main.route("/dfd/editor/<model_id>")
def dfd_editor(model_id):
    model_record = load_model_record(current_app.root_path, model_id)
    if model_record is None:
        abort(404, description="Threat model not found.")

    editor_script_path = Path(current_app.root_path) / "static" / "js" / "dfd_editor.js"
    editor_asset_version = int(editor_script_path.stat().st_mtime) if editor_script_path.exists() else 1

    return render_template(
        "dfd_editor.html",
        active_tab="dfd",
        model_id=model_id,
        model_record=model_record,
        editor_asset_version=editor_asset_version,
    )


@main.route("/reactflow-test")
def reactflow_test():
    return render_template(
        "reactflow_test.html",
        active_tab="reactflow_test",
    )


@main.route("/dfd-mapper-lab")
def dfd_mapper_lab():
    return render_template(
        "dfd_mapper_lab.html",
        active_tab="dfd_mapper_lab",
        response_files=list_response_files(current_app.root_path),
    )


@main.route("/llm")
def llm_chat():
    ollama_config = get_ollama_config(current_app.config)
    return render_template(
        "llm.html",
        active_tab="llm",
        ollama_model=ollama_config["model"],
        ollama_host=ollama_config["host"],
    )


@main.route("/garak")
def garak():
    return render_template(
        "garak.html",
        active_tab="garak",
        garak_status=garak_status(current_app.root_path),
    )


@main.route("/garak/reports/<path:report_path>")
def garak_report(report_path):
    try:
        report_file = garak_report_path(current_app.root_path, report_path)
    except (FileNotFoundError, ValueError):
        abort(404, description="Garak report not found.")

    return send_file(report_file)


@main.route("/api/llm/status")
def llm_status():
    ollama_config = get_ollama_config(current_app.config)
    try:
        models = list_models(current_app.config)
    except OllamaError as exc:
        return jsonify(
            {
                "ok": False,
                "host": ollama_config["host"],
                "model": ollama_config["model"],
                "error": str(exc),
            }
        ), 503

    model_names = [model.get("name") for model in models if model.get("name")]
    return jsonify(
        {
            "ok": ollama_config["model"] in model_names,
            "host": ollama_config["host"],
            "model": ollama_config["model"],
            "available_models": model_names,
        }
    )


@main.route("/api/llm/chat", methods=["POST"])
def llm_chat_api():
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages")

    if messages is None and payload.get("message"):
        messages = [{"role": "user", "content": payload.get("message")}]

    try:
        response = ollama_chat(messages, current_app.config)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except OllamaError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503

    return jsonify({"ok": True, **response})


@main.route("/api/llm-extracts")
def list_llm_extracts():
    return jsonify({"files": _list_llm_extract_files(current_app.root_path)})


@main.route("/api/llm-extracts/<filename>")
def get_llm_extract(filename):
    allowed_files = _list_llm_extract_files(current_app.root_path)
    if filename not in allowed_files:
        abort(404, description="LLM extract file not found.")

    extract_dir = _llm_extracts_dir(current_app.root_path).resolve()
    extract_path = (extract_dir / filename).resolve()
    if extract_path.parent != extract_dir:
        abort(404, description="LLM extract file not found.")

    raw = extract_path.read_text(encoding="utf-8")
    parsed, parse_error = _parse_extract_json(raw)
    return jsonify(
        {
            "filename": filename,
            "raw": raw,
            "parsed": parsed,
            "parse_error": parse_error,
        }
    )


@main.route("/api/responses/<filename>")
def get_response(filename):
    try:
        response_payload = load_response_payload(current_app.root_path, filename)
    except (FileNotFoundError, ValueError):
        abort(404, description="Response file not found.")

    return jsonify(
        {
            "filename": filename,
            "answers_by_flow_id": _answers_by_flow_id(response_payload),
            "raw": response_payload,
        }
    )


@main.route("/api/reactflow/from-extract", methods=["POST"])
def reactflow_from_extract():
    payload = request.get_json(silent=True) or {}
    graph = extract_to_reactflow(payload)
    return jsonify(graph)


@main.route("/api/generate-extract", methods=["POST"])
def generate_extract():
    payload = request.get_json(silent=True) or {}
    normalized_payload = _normalize_generation_payload(payload)

    response_file = normalized_payload.get("response_file")
    if not response_file:
        return jsonify({"success": False, "error": "A survey response file is required."}), 400

    try:
        extract = generate_llm_extract(
            current_app.root_path,
            normalized_payload,
            response_file,
            current_app.config,
        )
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Selected response file was not found."}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except OllamaError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503

    return jsonify({"success": True, **extract})


@main.route("/api/generate-dfd", methods=["POST"])
def generate_dfd():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=False)
    normalized_payload = _normalize_generation_payload(payload)

    response_file = normalized_payload.get("response_file")
    if not response_file:
        return jsonify({"success": False, "error": "A survey response file is required."}), 400

    try:
        response_payload = load_response_payload(current_app.root_path, response_file)
        model_record = build_mock_dfd_payload(normalized_payload, response_payload, response_file)
        save_model_record(current_app.root_path, model_record["model_id"], model_record)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Selected response file was not found."}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify(
        {
            "success": True,
            "model_id": model_record["model_id"],
            "redirect_url": url_for("main.dfd_editor", model_id=model_record["model_id"]),
        }
    )


@main.route("/api/save-model/<model_id>", methods=["POST"])
def save_dfd_model(model_id):
    model_record = load_model_record(current_app.root_path, model_id)
    if model_record is None:
        return jsonify({"success": False, "error": "Threat model not found."}), 404

    payload = request.get_json(silent=True) or {}
    diagram = payload.get("diagram")
    if not isinstance(diagram, dict):
        return jsonify({"success": False, "error": "Diagram payload is required."}), 400

    model_record["diagram"] = diagram
    model_record["last_saved_at"] = payload.get("saved_at")
    save_model_record(current_app.root_path, model_id, model_record)

    return jsonify({"success": True, "model_id": model_id})


@main.route("/api/export/json/<model_id>")
def export_dfd_json(model_id):
    model_record = load_model_record(current_app.root_path, model_id)
    if model_record is None:
        abort(404, description="Threat model not found.")

    return Response(
        json.dumps(model_record["diagram"], indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{model_id}.json"'},
    )


@main.route("/api/export/mermaid/<model_id>")
def export_dfd_mermaid(model_id):
    model_record = load_model_record(current_app.root_path, model_id)
    if model_record is None:
        abort(404, description="Threat model not found.")

    return Response(
        export_diagram_as_mermaid(model_record["diagram"]),
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{model_id}.mmd"'},
    )


@main.route("/api/export/plantuml/<model_id>")
def export_dfd_plantuml(model_id):
    model_record = load_model_record(current_app.root_path, model_id)
    if model_record is None:
        abort(404, description="Threat model not found.")

    return Response(
        export_diagram_as_plantuml(model_record["diagram"]),
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{model_id}.puml"'},
    )


@main.route("/risk", methods=["GET", "POST"])
def risk():
    response_files = list_response_files(current_app.root_path)
    extract_files = _list_llm_extract_files(current_app.root_path)
    selected_file = None
    selected_extract = None
    analysis = None
    analysis_error = None

    if request.method == "POST":
        selected_file = request.form.get("response_file")
        selected_extract = request.form.get("extract_file") or ""

        try:
            response_payload = load_response_payload(current_app.root_path, selected_file)
            extract_payload = _load_extract_payload(selected_extract) if selected_extract else None
            analysis = build_risk_analysis(current_app.root_path, response_payload, extract_payload)
        except FileNotFoundError:
            analysis_error = "Selected response or extract file was not found."
        except ValueError as exc:
            analysis_error = str(exc)

    suggested_extract = suggested_extract_filename(selected_file) if selected_file else ""

    return render_template(
        "risk.html",
        active_tab="risk",
        response_files=response_files,
        extract_files=extract_files,
        selected_file=selected_file,
        selected_extract=selected_extract,
        suggested_extract=suggested_extract,
        analysis=analysis,
        analysis_error=analysis_error,
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


def _normalize_generation_payload(payload):
    normalized = {}

    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, list):
                normalized[key] = value if len(value) > 1 else value[0]
            else:
                normalized[key] = value

    option_keys = {
        "include_trust_boundaries",
        "include_risk_tags",
        "auto_layout",
        "editable_canvas",
    }

    for option_key in option_keys:
        option_value = normalized.get(option_key, False)
        if isinstance(option_value, str):
            normalized[option_key] = option_value.lower() in {"1", "true", "yes", "on"}
        else:
            normalized[option_key] = bool(option_value)

    return normalized


def _llm_extracts_dir(app_root_path):
    return Path(app_root_path).parent / "LLM_Extracts"


def _list_llm_extract_files(app_root_path):
    extract_dir = _llm_extracts_dir(app_root_path)
    if not extract_dir.exists() or not extract_dir.is_dir():
        return []

    allowed_suffixes = {".json", ".txt"}
    files = []
    for file_path in extract_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in allowed_suffixes:
            files.append(file_path.name)
    return sorted(files)


def _parse_extract_json(raw):
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw[index:])
            if isinstance(parsed, dict):
                return parsed, None
        except json.JSONDecodeError:
            continue

    return None, "Could not parse extract as JSON."


def _load_extract_payload(filename):
    if not filename:
        return None

    allowed_files = _list_llm_extract_files(current_app.root_path)
    if filename not in allowed_files:
        raise FileNotFoundError(filename)

    extract_dir = _llm_extracts_dir(current_app.root_path).resolve()
    extract_path = (extract_dir / filename).resolve()
    if extract_path.parent != extract_dir:
        raise ValueError("Invalid extract file selection.")

    raw = extract_path.read_text(encoding="utf-8")
    parsed, parse_error = _parse_extract_json(raw)
    if parse_error:
        raise ValueError(parse_error)
    return parsed


def _answers_by_flow_id(response_payload):
    if not isinstance(response_payload, dict):
        return {}

    compact_answers = response_payload.get("answers_by_flow_id")
    if isinstance(compact_answers, dict):
        return compact_answers

    answers = response_payload.get("answers")
    if not isinstance(answers, list):
        return {}

    normalized = {}
    for answer_record in answers:
        if not isinstance(answer_record, dict):
            continue

        flow_id = answer_record.get("flow_id")
        answer = answer_record.get("answer")
        if isinstance(flow_id, str) and flow_id.strip() and answer not in (None, "", []):
            normalized[flow_id.strip()] = answer

    return normalized
