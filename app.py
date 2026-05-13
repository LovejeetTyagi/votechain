"""
VoteChain — Online Voting System
Flask + Firebase backend entry point.

Run locally:
    pip install -r requirements.txt
    cp .env.example .env          # fill in your values
    python app.py

Production (gunicorn):
    gunicorn app:app --bind 0.0.0.0:8000 --workers 4
"""
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os

from config import Config, init_firebase
from auth  import auth_bp
from polls import polls_bp
from votes import votes_bp




# ── Create Flask app ──────────────────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__, static_folder="frontend", static_url_path="")

    # Config
    app.config["SECRET_KEY"] = Config.SECRET_KEY

    # CORS (allow all origins in dev; tighten in production)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Firebase
    init_firebase()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(polls_bp)
    app.register_blueprint(votes_bp)

    # ── Health check ─────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "app": "VoteChain"})

    # ── Serve React/HTML frontend (SPA fallback) ──────────────────────────────
    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(404)
    def not_found(e):
        # For SPA routing: serve index.html for unknown paths
        if not str(e).startswith("/api"):
            return send_from_directory(app.static_folder, "index.html")
        return jsonify({"success": False, "message": "Endpoint not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "message": "Method not allowed."}), 405

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"success": False, "message": "Internal server error."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)


@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    app.logger.error(traceback.format_exc())
    return jsonify({"error": str(e)}), 500    




