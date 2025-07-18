import os
import json
from datetime import datetime

def save_answers(form_data, layer_name="layer1"):
    """
    Save submitted answers to a timestamped JSON file.
    Parameters:
    - form_data: request.form (MultiDict)
    - layer_name: string identifier for the layer (e.g., "layer1", "layer2")
    """
    answers = {}
    for key in form_data.keys():
        answers[key] = form_data.getlist(key)

    result = {
        "timestamp": datetime.now().isoformat(),
        "layer": layer_name,
        "answers": answers
    }

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs('data', exist_ok=True)
    filename = f"{layer_name}_answers_{timestamp_str}.json"
    filepath = os.path.join('data', filename)

    with open(filepath, 'w') as f:
        json.dump(result, f, indent=2)

    return filepath

