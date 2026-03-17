import os
import json
from pathlib import Path
import os
from flask import Blueprint, render_template, abort, request, redirect, url_for, jsonify, current_app, flash
from app.utils.save_utils import save_answers, append_question_to_layer, save_layer8_answers

AVAILABLE_LAYERS = ["layer1", "layer2", "layer3", "layer4", "layer5", "layer6"]

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template("home.html", active_tab="home")

@main.route("/favicon.ico")
def favicon():
    return ("", 204)

@main.route("/form")
def form_redirect():
    # Always go to /form/layer1
    return redirect(url_for("main.form", layer_name="layer1"), code=302)

@main.route("/form/<layer_name>", methods=["GET", "POST"])
def form(layer_name):
    questions_path = Path(current_app.root_path) / "questions" / f"{layer_name}.json"

    if not questions_path.exists():
        abort(404, description=f"Question file for {layer_name} not found.")

    with questions_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # JSON root can be a list or {"questions": [...]}; support both
    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    else:
        questions = data

    if request.method == "POST":
        # Save answers (sent names will be q_<id> or q_<id>[])
        save_answers(request.form, layer_name=layer_name)

        # Proceed to the next layer (optional)
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
        available_layers=AVAILABLE_LAYERS
    )

@main.route('/add-question', methods=["GET", "POST"])
def add_question():
    if request.method == "POST":
        # Expecting JSON (to be sent via fetch)
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

    # GET: render template
    return render_template("add_question.html", active_tab="add")

@main.route('/dfd', methods=["GET", "POST"])
def dfd():
    # Get the responses directory path
    responses_dir = Path(current_app.root_path).parent / "responses"
    
    # Get all JSON files from responses directory
    response_files = []
    if responses_dir.exists():
        response_files = sorted([f.name for f in responses_dir.glob("*.json")])
    
    if request.method == "POST":
        selected_file = request.form.get("response_file")
        # TODO: Process the selected file and generate threat model
        # For now, just pass it back to show selection
        return render_template(
            "dfd.html", 
            active_tab="dfd",
            response_files=response_files,
            selected_file=selected_file
        )
    
    return render_template(
        "dfd.html", 
        active_tab="dfd",
        response_files=response_files
    )

@main.route('/risk', methods=["GET", "POST"])
def risk():
    # Get the responses directory path
    responses_dir = Path(current_app.root_path).parent / "responses"
    
    # Get all JSON files from responses directory
    response_files = []
    if responses_dir.exists():
        response_files = sorted([f.name for f in responses_dir.glob("*.json")])
    
    if request.method == "POST":
        selected_file = request.form.get("response_file")
        # TODO: Process the selected file and generate threat model with local LLM
        return render_template(
            "risk.html", 
            active_tab="risk",
            response_files=response_files,
            selected_file=selected_file
        )
    
    return render_template(
        "risk.html", 
        active_tab="risk",
        response_files=response_files
    )

# ---------------------------------------------------------------------------
# LLM Sec  – Layer 8 questionnaire (LLM-specific threat surface mapping)
# Future steps: DFD generation, OWASP LLM threat derivation, Garak execution
# ---------------------------------------------------------------------------
@main.route('/llm-sec', methods=["GET", "POST"])
def llm_sec():
    q_dir = Path(current_app.root_path) / "questions"

    if request.method == "GET":
        # Step 1: Render Layer 1
        layer = "layer1"
        q_path = q_dir / f"{layer}.json"
        
        if not q_path.exists():
            abort(404, description=f"{layer}.json not found.")

        with q_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            questions = data["questions"] if isinstance(data, dict) and "questions" in data else data

        layer_data = {
            "name": "Layer 1 - LLM System Architecture & Data Flow Discovery",
            "layer_id": layer,
            "questions": questions
        }

        return render_template(
            "llm_sec.html",
            active_tab="llm_sec",
            layer_data=layer_data,
            step=1,
            hidden_fields={}
        )

    # Handle POST
    step = int(request.form.get("current_step", 1))

    if step == 1:
        # Step 2: Receive Layer 1 data, render Layer 2
        hidden_fields = {}
        for key in request.form.keys():
            if key.startswith("q_"):
                hidden_fields[key] = request.form.getlist(key)

        layer = "layer2"
        q_path = q_dir / f"{layer}.json"
        
        if not q_path.exists():
            abort(404, description=f"{layer}.json not found.")

        with q_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            questions = data["questions"] if isinstance(data, dict) and "questions" in data else data

        layer_data = {
            "name": "Layer 2 - LLM Security Controls & Risk Assessment",
            "layer_id": layer,
            "questions": questions
        }

        return render_template(
            "llm_sec.html",
            active_tab="llm_sec",
            layer_data=layer_data,
            step=2,
            hidden_fields=hidden_fields
        )

    elif step == 2:
        # Step 3: Receive Layer 1+2 data, save
        save_layer8_answers(request.form)
        flash("LLM Sec answers saved successfully!", "success")
        return redirect(url_for("main.llm_sec"))
