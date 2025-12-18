from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)



OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


DEPARTMENTS = [
    "Recursos Humanos",
    "Finanzas",
    "Tecnologías",
    "Redes",
    "Infraestructura"
]

# Estado del usuario
user_state = {
    "selected_area": None,
    "last_departments": []  
}


# ============================================================
# 1️⃣ ANALIZAR TEXTO → IA devuelve porcentajes normalizados
# ============================================================
@app.route("/analizar", methods=["POST"])
def analizar():
    data = request.json
    if not data or "asunto" not in data:
        return jsonify({"error": "Debes enviar el campo 'asunto'"}), 400

    asunto = data["asunto"]
    area_actual = user_state["selected_area"]

    # Llamada a OpenRouter
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "Referer": "https://siac-ia.oaxaca.gob.mx",
    "X-Title": "SIAC IA"
   }


    prompt = f"""
    Clasifica este texto en las siguientes áreas:

    {DEPARTMENTS}

    Debes devolver ÚNICAMENTE un JSON válido así:

    [
      {{"area": "Área", "score": 0.00}}
    ]

    IMPORTANTE:
    - NO expliques nada.
    - NO escribas texto adicional.
    - NO coloques comentarios.
    - SOLO devuelve el JSON puro.

    Texto a analizar: "{asunto}"
    """

    body = {
        "model": "gpt-4o-mini",
        "temperature": 0,  # ✅ para hacerlo más determinista
        "messages": [
            {"role": "system", "content": "Eres un modelo experto en clasificación. Devuelves SOLO JSON válido."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=body)
        resp.raise_for_status()

        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Si la IA devuelve texto extra, recortar solo el JSON
        if not raw.startswith("["):
            start = raw.find("[")
            end = raw.rfind("]") + 1
            raw = raw[start:end]

        # Convertir JSON seguro (sin eval)
        try:
            departamentos_raw = json.loads(raw)
        except Exception:
            return jsonify({
                "error": "La IA devolvió un JSON inválido.",
                "raw": raw
            }), 500

        # NORMALIZAR LOS SCORES PARA QUE SUMEN 100%
        total_score = sum(float(d["score"]) for d in departamentos_raw)

        if total_score == 0:
            return jsonify({
                "area_actual": area_actual,
                "msg": "No se detectó relación clara con ninguna área.",
                "departments": [],
                "instruccion": "Intenta describir tu problema con más detalle."
            }), 200

        departamentos_convertidos = []
        valid_areas_for_issue = []

        for d in departamentos_raw:
            raw_score = float(d["score"])
            if raw_score <= 0:
                continue  # ignorar áreas con score cero

            porcentaje_real = (raw_score / total_score) * 100
            porcentaje_final = round(porcentaje_real, 2)

            departamentos_convertidos.append({
                "area": d["area"],
                "probabilidad": f"{porcentaje_final}%"
            })
            valid_areas_for_issue.append(d["area"])

        # ✅ Guardamos solo las áreas que la IA consideró relevantes
        user_state["last_departments"] = valid_areas_for_issue

        return jsonify({
            "area_actual": area_actual,
            "msg": "Estas son las áreas sugeridas para tu asunto:",
            "departments": departamentos_convertidos,
            "instruccion": "Selecciona un área enviando un POST a /canalizar (de entre las sugeridas)."
        })

    except Exception as e:
        return jsonify({"error": f"No se pudo analizar: {e}"}), 500


# ============================================================
# 2️⃣ CANALIZAR ÁREA → mensaje de bienvenida
# ============================================================
@app.route("/canalizar", methods=["POST"])
def canalizar():
    data = request.json
    if "area" not in data:
        return jsonify({"error": "Debes enviar 'area'"}), 400

    area = data["area"]

    # ✅ Solo permitimos elegir entre las áreas sugeridas por la IA
    valid_areas = user_state.get("last_departments") or []

    if area not in valid_areas:
        return jsonify({
            "error": "Área no válida para el asunto analizado.",
            "areas_sugeridas": valid_areas
        }), 400

    user_state["selected_area"] = area

    return jsonify({
        "msg": f"Bienvenido al área de {area}. ¿En qué te podemos ayudar?"
    })


# ============================================================
# 3️⃣ RESET
# ============================================================
@app.route("/reset", methods=["POST"])
def reset():
    user_state["selected_area"] = None
    user_state["last_departments"] = []
    return jsonify({"msg": "Estado reiniciado."})

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
# ============================================================
