import os
import json
from flask import Blueprint, render_template, abort, request, redirect, url_for
from app.utils.save_utils import save_answers

AVAILABLE_LAYERS = ["layer1", "layer2", "layer3", "layer4", "layer5", "layer6"]

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template("home.html", active_tab="")

@main.route('/form')
def form_redirect():
    return redirect(url_for('main.form', layer_name=AVAILABLE_LAYERS[0]))


@main.route('/form/<layer_name>')
def form(layer_name):
    filename = f"data/{layer_name}_questions.json"
    if not os.path.exists(filename):
        abort(404, description=f"Question file for {layer_name} not found.")

    with open(filename, 'r') as file:
        questions = json.load(file)

    return render_template(
        "form.html",
        active_tab="form",
        questions=questions,
        layer=layer_name,
        available_layers=AVAILABLE_LAYERS
    )

@main.route('/submit-answers', methods=['POST'])
def submit_answers():
    # Get the layer name from the hidden form input
    layer_name = request.form.get("layer_name", "layer1")
    save_answers(request.form, layer_name=layer_name)
    return redirect(url_for('main.form', layer_name=layer_name))

@main.route('/add-question')
def add_question():
    return render_template("add_question.html", active_tab="add")

@main.route('/dfd')
def dfd():
    return render_template("dfd.html", active_tab="dfd")

@main.route('/risk')
def risk():
    return render_template("risk.html", active_tab="risk")
