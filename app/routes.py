import json
import logging
from threading import Thread
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
    archive_dfd_graph,
    export_diagram_as_mermaid,
    export_diagram_as_plantuml,
    list_dfd_archives,
    list_response_files,
    load_dfd_archive,
    load_model_record,
    load_response_payload,
    save_model_record,
)
from app.services.llm_generator import build_mock_dfd_payload
from app.services.ollama_client import OllamaError, chat as ollama_chat, get_ollama_config, list_models
from app.services.extract_to_reactflow import extract_to_reactflow
from app.services.llm_extract_service import generate_llm_extract
from app.services.pipeline_orchestrator import PIPELINE_STEPS, PipelineOrchestrator
from app.services.risk_analysis_service import RISK_RANK, build_risk_analysis, suggested_extract_filename, unify_risks
from app.services.garak_service import garak_report_path, garak_status
from app.services.static_dfd_mapper import build_static_dfd_from_answers
from app.utils.save_utils import (
    append_question_to_catalog,
    save_adaptive_llm_sec_answers,
)


LLM_SEC_SESSION_KEY = "llm_sec_flow"

LOGGER = logging.getLogger(__name__)

main = Blueprint("main", __name__)


@main.route("/")
def home():
    orchestrator = _pipeline_orchestrator()
    selected_pipeline = request.args.get("pipeline") or ""
    return render_template(
        "home.html",
        active_tab="home",
        **_home_security_analysis(orchestrator, selected_pipeline),
    )


@main.route("/favicon.ico")
def favicon():
    return ("", 204)


@main.route("/add-question", methods=["GET", "POST"])
def add_question():
    if request.method == "POST":
        if not request.is_json:
            return jsonify({"ok": False, "error": "Expected JSON"}), 400

        payload = request.get_json()
        text = payload.get("text", "").strip()
        options = payload.get("options", []) or []

        if not text:
            return jsonify({"ok": False, "error": "question text required"}), 400

        try:
            qpath, new_q = append_question_to_catalog(text, options)
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
        dfd_files=list_dfd_archives(current_app.root_path),
        selected_dfd=request.args.get("dfd") or "",
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


@main.route("/pipeline")
def pipeline_index():
    orchestrator = _pipeline_orchestrator()
    return render_template(
        "pipeline_index.html",
        active_tab="pipeline",
        response_files=list_response_files(current_app.root_path),
        pipelines=orchestrator.list_pipelines(),
    )


@main.route("/pipeline/start", methods=["POST"])
def pipeline_start():
    response_filename = request.form.get("response_filename") or ""
    project_name = request.form.get("project_name") or ""
    dfd_name = request.form.get("dfd_name") or ""
    auditor_name = request.form.get("auditor_name") or ""
    orchestrator = _pipeline_orchestrator()

    try:
        manifest = orchestrator.create_pipeline(
            response_filename,
            project_name=project_name,
            dfd_name=dfd_name,
            auditor_name=auditor_name,
        )
    except FileNotFoundError:
        flash("Selected questionnaire response was not found.", "danger")
        return redirect(url_for("main.pipeline_index"))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("main.pipeline_index"))

    try:
        manifest = orchestrator.run_until_risk_analysis(manifest["pipeline_id"])
        flash("Pipeline created and risk analysis completed.", "success")
    except Exception as exc:
        flash(f"Pipeline workspace was created, but automation stopped: {exc}", "warning")

    return redirect(url_for("main.pipeline_detail", pipeline_id=manifest["pipeline_id"]))


@main.route("/api/pipeline/start", methods=["POST"])
def pipeline_start_api():
    payload = request.get_json(silent=True) if request.is_json else request.form
    payload = payload or {}
    response_filename = payload.get("response_filename") or ""
    project_name = payload.get("project_name") or ""
    dfd_name = payload.get("dfd_name") or ""
    auditor_name = payload.get("auditor_name") or ""
    orchestrator = _pipeline_orchestrator()

    try:
        manifest = orchestrator.create_pipeline(
            response_filename,
            project_name=project_name,
            dfd_name=dfd_name,
            auditor_name=auditor_name,
        )
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "Selected questionnaire response was not found."}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    _start_pipeline_background(
        manifest["pipeline_id"],
        current_app.root_path,
        dict(current_app.config),
    )

    return (
        jsonify(
            {
                "ok": True,
                "pipeline_id": manifest["pipeline_id"],
                "detail_url": url_for("main.pipeline_detail", pipeline_id=manifest["pipeline_id"]),
                "manifest_url": url_for("main.pipeline_manifest_api", pipeline_id=manifest["pipeline_id"]),
            }
        ),
        201,
    )


@main.route("/pipeline/<pipeline_id>")
def pipeline_detail(pipeline_id):
    orchestrator = _pipeline_orchestrator()
    try:
        manifest = orchestrator.get_manifest(pipeline_id)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        abort(404, description="Pipeline not found.")

    artifacts = []
    artifacts_by_name = {}
    pipeline_workspace = orchestrator.pipeline_workspace(pipeline_id)
    dfd_preview = None
    risk_preview = None
    artifact_order = list(PIPELINE_STEPS.values())
    for artifact_name in artifact_order:
        exists = orchestrator.artifact_exists(pipeline_id, artifact_name)
        artifact_path = pipeline_workspace / artifact_name
        artifact = {
            "name": artifact_name,
            "exists": exists,
            "path": str(artifact_path),
            "url": url_for("main.pipeline_artifact", pipeline_id=pipeline_id, artifact_name=artifact_name)
            if exists
            else None,
        }
        artifacts.append(artifact)
        artifacts_by_name[artifact_name] = artifact
        if artifact_name == "dfd_reactflow.json" and exists:
            try:
                dfd_payload = orchestrator.load_artifact(pipeline_id, artifact_name)
                dfd_preview = _dfd_preview_payload(dfd_payload)
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                dfd_preview = None
        if artifact_name == "risks.json" and exists:
            try:
                risk_payload = orchestrator.load_artifact(pipeline_id, artifact_name)
                risk_preview = _risk_preview_payload(risk_payload)
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                risk_preview = None

    return render_template(
        "pipeline_detail.html",
        active_tab="pipeline",
        manifest=manifest,
        artifacts=artifacts,
        artifacts_by_name=artifacts_by_name,
        pipeline_workspace=str(pipeline_workspace),
        dfd_preview=dfd_preview,
        risk_preview=risk_preview,
        dfd_view_url=url_for("main.dfd_mapper_lab", dfd=manifest.get("dfd_archive"))
        if manifest.get("dfd_archive")
        else None,
        risk_view_url=url_for("main.risk", pipeline=manifest["pipeline_id"])
        if risk_preview
        else None,
    )


@main.route("/pipeline/<pipeline_id>/garak-plan", methods=["POST"])
def pipeline_garak_plan(pipeline_id):
    orchestrator = _pipeline_orchestrator()
    try:
        orchestrator.create_garak_plan(pipeline_id)
        flash("Garak plan created from saved OWASP risks.", "success")
    except FileNotFoundError:
        flash("Risk analysis artifact is required before creating a Garak plan.", "danger")
    except (ValueError, json.JSONDecodeError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("main.pipeline_detail", pipeline_id=pipeline_id))


@main.route("/api/pipeline/<pipeline_id>/manifest")
def pipeline_manifest_api(pipeline_id):
    orchestrator = _pipeline_orchestrator()
    try:
        return jsonify(orchestrator.get_manifest(pipeline_id))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        abort(404, description="Pipeline not found.")


@main.route("/api/pipeline/<pipeline_id>/artifact/<artifact_name>")
def pipeline_artifact(pipeline_id, artifact_name):
    orchestrator = _pipeline_orchestrator()
    try:
        return jsonify(orchestrator.load_artifact(pipeline_id, artifact_name))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        abort(404, description="Pipeline artifact not found.")


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


@main.route("/api/dfd-graphs")
def list_dfd_graphs():
    return jsonify({"files": list_dfd_archives(current_app.root_path)})


@main.route("/api/dfd-graphs/<filename>")
def get_dfd_graph(filename):
    try:
        payload = load_dfd_archive(current_app.root_path, filename)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        abort(404, description="DFD graph not found.")

    return jsonify({"filename": filename, "graph": payload})


@main.route("/api/reactflow/from-extract", methods=["POST"])
def reactflow_from_extract():
    payload = request.get_json(silent=True) or {}
    graph = extract_to_reactflow(payload)
    return jsonify(graph)


@main.route("/api/static-dfd-map", methods=["POST"])
def static_dfd_map():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"ok": False, "error": "Expected a JSON object containing questionnaire answers."}), 400

    raw_answers = payload
    if isinstance(payload, dict) and "answers" in payload:
        raw_answers = payload["answers"]
        if isinstance(raw_answers, list):
            raw_answers = {"answers": raw_answers}

    try:
        graph = build_static_dfd_from_answers(raw_answers)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({"ok": True, "graph": graph})


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
    orchestrator = _pipeline_orchestrator()
    risk_runs = _pipeline_risk_runs(orchestrator)
    selected_pipeline = request.args.get("pipeline") or ""
    selected_manifest = None
    selected_file = None
    selected_extract = None
    analysis = None
    analysis_error = None

    if selected_pipeline:
        try:
            selected_manifest = orchestrator.get_manifest(selected_pipeline)
            analysis = orchestrator.load_artifact(selected_pipeline, "risks.json")
            analysis = _with_unified_risks(analysis)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            analysis_error = "Selected pipeline risk analysis was not found."
    elif request.method == "POST":
        selected_file = request.form.get("response_file")
        selected_extract = request.form.get("extract_file") or ""

        try:
            response_payload = load_response_payload(current_app.root_path, selected_file)
            extract_payload = _load_extract_payload(selected_extract) if selected_extract else None
            analysis = build_risk_analysis(current_app.root_path, response_payload, extract_payload)
            analysis = _with_unified_risks(analysis)
        except FileNotFoundError:
            analysis_error = "Selected response or extract file was not found."
        except ValueError as exc:
            analysis_error = str(exc)

    suggested_extract = suggested_extract_filename(selected_file) if selected_file else ""

    return render_template(
        "risk.html",
        active_tab="risk",
        risk_runs=risk_runs,
        selected_pipeline=selected_pipeline,
        selected_manifest=selected_manifest,
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

        submitted_answer = flow_engine.extract_answer(request.form, current_question)
        flow_state["answers"][current_flow_id] = submitted_answer
        current_app.logger.debug(
            "LLM security questionnaire submitted %s with answer=%r",
            current_flow_id,
            submitted_answer,
        )

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


def _pipeline_orchestrator():
    return PipelineOrchestrator(current_app.root_path, current_app.config)


def _start_pipeline_background(pipeline_id, app_root_path, app_config):
    worker = Thread(
        target=_run_pipeline_background,
        args=(pipeline_id, app_root_path, app_config),
        daemon=True,
    )
    worker.start()


def _run_pipeline_background(pipeline_id, app_root_path, app_config):
    orchestrator = PipelineOrchestrator(app_root_path, app_config)
    try:
        orchestrator.run_until_risk_analysis(pipeline_id)
    except Exception:
        # Per-step errors are already recorded in the manifest; log the traceback too
        # so background failures are diagnosable instead of silently swallowed.
        LOGGER.exception("Background pipeline %s failed", pipeline_id)


def _dfd_preview_payload(payload):
    if not isinstance(payload, dict):
        return None

    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    edges = payload.get("edges") if isinstance(payload.get("edges"), list) else []

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": [
            {
                "id": node.get("id"),
                "type": node.get("type") or "process",
                "label": (node.get("data") or {}).get("label") or node.get("id") or "Unnamed node",
            }
            for node in nodes[:12]
            if isinstance(node, dict)
        ],
        "edges": [
            {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "label": edge.get("label") or "flow",
            }
            for edge in edges[:12]
            if isinstance(edge, dict)
        ],
    }


def _risk_preview_payload(payload):
    if not isinstance(payload, dict):
        return None

    payload = _with_unified_risks(payload)
    extract_risks = payload.get("extract_risks") if isinstance(payload.get("extract_risks"), list) else []
    mapped_risks = payload.get("mapped_risks") if isinstance(payload.get("mapped_risks"), list) else []
    unified_risks = payload.get("unified_risks") if isinstance(payload.get("unified_risks"), list) else []
    quick_wins = payload.get("quick_wins") if isinstance(payload.get("quick_wins"), list) else []

    return {
        "overall_status": payload.get("overall_status") or "Unknown",
        "risk_count": len(unified_risks),
        "mitigation_count": sum(
            1
            for risk in unified_risks
            if isinstance(risk, dict) and risk.get("mitigations")
        )
        or len([risk for risk in extract_risks if isinstance(risk, dict) and risk.get("mitigation")]),
        "quick_win_count": len(quick_wins),
    }


def _home_security_analysis(orchestrator, selected_pipeline):
    risk_runs = _pipeline_risk_runs(orchestrator)
    available_ids = {run.get("pipeline_id") for run in risk_runs}
    selected_pipeline = selected_pipeline if selected_pipeline in available_ids else ""
    if not selected_pipeline and risk_runs:
        selected_pipeline = risk_runs[0].get("pipeline_id") or ""

    selected_manifest = None
    analysis = None
    analysis_error = None

    if selected_pipeline:
        try:
            selected_manifest = orchestrator.get_manifest(selected_pipeline)
            analysis = orchestrator.load_artifact(selected_pipeline, "risks.json")
            analysis = _with_unified_risks(analysis)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            analysis_error = "Selected pipeline risk analysis was not found."

    return {
        "risk_runs": risk_runs,
        "selected_pipeline": selected_pipeline,
        "selected_manifest": selected_manifest,
        "analysis": analysis,
        "analysis_error": analysis_error,
        "home_summary": _home_analysis_summary(analysis, selected_manifest),
    }


def _home_analysis_summary(analysis, manifest):
    levels = ("Critical", "High", "Medium", "Low")
    empty_counts = {level: 0 for level in levels}
    if not isinstance(analysis, dict):
        return {
            "level_counts": empty_counts,
            "chart_data": [{"label": level, "count": 0} for level in levels],
            "total_risks": 0,
            "mitigation_count": 0,
            "quick_win_count": 0,
            "top_risks": [],
            "mitigation_risks": [],
            "project_name": manifest.get("project_name") if isinstance(manifest, dict) else "",
            "analysis_name": manifest.get("dfd_name") if isinstance(manifest, dict) else "",
            "updated_at": manifest.get("updated_at") if isinstance(manifest, dict) else "",
        }

    unified_risks = analysis.get("unified_risks") if isinstance(analysis.get("unified_risks"), list) else []
    quick_wins = analysis.get("quick_wins") if isinstance(analysis.get("quick_wins"), list) else []
    level_counts = dict(empty_counts)
    mitigation_risks = []

    for risk in unified_risks:
        if not isinstance(risk, dict):
            continue
        level = str(risk.get("risk_level") or "").strip().title()
        if level in level_counts:
            level_counts[level] += 1
        if risk.get("mitigations"):
            mitigation_risks.append(risk)

    return {
        "level_counts": level_counts,
        "chart_data": [{"label": level, "count": level_counts[level]} for level in levels],
        "total_risks": len([risk for risk in unified_risks if isinstance(risk, dict)]),
        "mitigation_count": len(mitigation_risks),
        "quick_win_count": len(quick_wins),
        "top_risks": [risk for risk in unified_risks if isinstance(risk, dict)][:5],
        "mitigation_risks": mitigation_risks[:5],
        "project_name": manifest.get("project_name") if isinstance(manifest, dict) else "",
        "analysis_name": manifest.get("dfd_name") if isinstance(manifest, dict) else "",
        "updated_at": manifest.get("updated_at") if isinstance(manifest, dict) else "",
    }


def _with_unified_risks(analysis):
    if not isinstance(analysis, dict):
        return analysis
    enriched = dict(analysis)
    if not isinstance(enriched.get("unified_risks"), list):
        enriched["unified_risks"] = unify_risks(
            enriched.get("extract_risks") if isinstance(enriched.get("extract_risks"), list) else [],
            enriched.get("mapped_risks") if isinstance(enriched.get("mapped_risks"), list) else [],
        )
    unified_levels = [
        risk.get("risk_level")
        for risk in enriched.get("unified_risks", [])
        if isinstance(risk, dict) and risk.get("risk_level")
    ]
    if unified_levels:
        enriched["overall_status"] = max(unified_levels, key=lambda level: RISK_RANK.get(level, 0))
        enriched["status_source"] = "Combined risk model"
    return enriched


def _pipeline_risk_runs(orchestrator):
    runs = []
    for manifest in orchestrator.list_pipelines():
        pipeline_id = manifest.get("pipeline_id")
        if not pipeline_id:
            continue
        try:
            if not orchestrator.artifact_exists(pipeline_id, "risks.json"):
                continue
            risks = orchestrator.load_artifact(pipeline_id, "risks.json")
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
        preview = _risk_preview_payload(risks) or {}
        runs.append(
            {
                "pipeline_id": pipeline_id,
                "label": manifest.get("project_name") or manifest.get("source_response") or pipeline_id,
                "dfd_name": manifest.get("dfd_name"),
                "auditor_name": manifest.get("auditor_name"),
                "updated_at": manifest.get("updated_at"),
                **preview,
            }
        )
    return sorted(runs, key=lambda item: item.get("updated_at") or "", reverse=True)


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
