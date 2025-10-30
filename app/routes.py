import os
import json
from pathlib import Path
import os
from flask import Blueprint, render_template, abort, request, redirect, url_for, jsonify, current_app
from app.utils.save_utils import save_answers, append_question_to_layer

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

    # JSON kökü liste veya {"questions": [...]} olabilir; ikisini de destekle
    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    else:
        questions = data

    if request.method == "POST":
        # Cevapları kaydet (send edilen name'ler q_<id> veya q_<id>[] olacak)
        save_answers(request.form, layer_name=layer_name)

        # Sonraki layer'a geçiş (isteğe bağlı)
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
        # JSON bekliyoruz (fetch ile gönderilecek)
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

@main.route('/dfd')
def dfd():
    return render_template("dfd.html", active_tab="dfd")

@main.route('/risk')
def risk():
    return render_template("risk.html", active_tab="risk")
