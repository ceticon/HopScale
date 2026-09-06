from flask import Flask, jsonify, render_template
import json
import os


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# SÖKVÄGAR
# ============================================================

# HopScale-projektets rotkatalog
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATUS_FILE = os.path.join(BASE_DIR, "hopscale.json")
CONTROL_FILE = os.path.join(BASE_DIR, "control.json")


# ============================================================
# HUVUDSIDA
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# STATUS
# ============================================================

@app.route("/api/status")
def status():

    try:

        with open(STATUS_FILE, "r") as file:
            data = json.load(file)

        return jsonify(data)

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500


# ============================================================
# TARE
# ============================================================

@app.route("/api/tare", methods=["POST"])
def tare():

    try:

        data = {
            "tare": True
        }

        with open(CONTROL_FILE, "w") as file:
            json.dump(data, file, indent=4)

        return jsonify({
            "success": True
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# STARTA FLASK
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )