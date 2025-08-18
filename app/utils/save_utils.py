import os
import json
from datetime import datetime
from flask import current_app

# def save_answers(form_data, layer_name="layer1"):
#     """
#     form_data: request.form (ImmutableMultiDict)
#     layer_name: 'layer1' .. 'layer6'
#     Kayıt: app/responses/<layer_name>/response_YYYY-MM-DDTHH-MM-SS.json
#     """
#     answers = {}

#     # form içindeki her alanı gez; layer_name hidden alanını atla
#     for key in form_data.keys():
#         if key == "layer_name":
#             continue
#         values = form_data.getlist(key)
#         if not values:
#             continue
#         # Tek seçimleri string, çoklu seçimleri liste olarak yaz
#         answers[key] = values[0] if len(values) == 1 else values

#     # Uygulama kökünden klasörleri oluştur
#     base_dir = current_app.root_path  # ..../app
#     layer_dir = os.path.join(base_dir, "responses", layer_name)
#     os.makedirs(layer_dir, exist_ok=True)

#     # Zaman damgaları ve dosya adı
#     ts_file = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
#     out_path = os.path.join(layer_dir, f"response_{ts_file}.json")

#     payload = {
#         "layer": layer_name,
#         "timestamp": datetime.now().isoformat(timespec="seconds"),
#         "answers": answers
#     }

#     with open(out_path, "w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2, ensure_ascii=False)

#     return out_path

def save_answers(form_data, layer_name="layer1"):
    import os, json
    from datetime import datetime

    answers = {}
    for key in form_data.keys():
        vals = form_data.getlist(key)
        # 1’den fazla değer varsa liste bırak, tekse string’e indir
        if len(vals) == 0:
            answers[key] = None
        elif len(vals) == 1:
            answers[key] = vals[0]
        else:
            answers[key] = vals

    result = {
        "timestamp": datetime.now().isoformat(),
        "layer": layer_name,
        "answers": answers,
    }

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("responses", exist_ok=True)
    filename = f"{layer_name}_answers_{timestamp_str}.json"
    filepath = os.path.join("responses", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

