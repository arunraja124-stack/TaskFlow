from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from config import Config
from backend.routes.tasks import tasks_bp
from backend.routes.auth import auth_bp
from backend.routes.analytics import analytics_bp
from backend.routes.ai import ai_bp
from backend.routes.productivity import productivity_bp


def create_app(test_config=None):
    app = Flask(__name__, static_folder="frontend", static_url_path="")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})
    app.register_blueprint(tasks_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(analytics_bp, url_prefix="/api")
    app.register_blueprint(ai_bp, url_prefix="/api")
    app.register_blueprint(productivity_bp, url_prefix="/api")

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(404)
    def not_found(error):
        if error.description and getattr(error, "name", "") == "Not Found":
            return jsonify({"success": False, "error": {"message": "Resource not found"}}), 404
        return error

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))
