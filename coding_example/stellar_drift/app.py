"""Stellar Drift — star system travel simulator (Flask + canvas, port 5007)."""
import os

from flask import Flask, jsonify, render_template

app = Flask(__name__, root_path=os.path.dirname(os.path.abspath(__file__)))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify(app='stellar_drift', status='ok')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5007, debug=False)
