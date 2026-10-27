import click
from flask import Flask, jsonify, send_from_directory
from mysql.connector import Error
from flask_cors import CORS

from config import Config
from backend.routes.tasks import tasks_bp
from backend.routes.auth import auth_bp
from backend.routes.analytics import analytics_bp
from backend.routes.ai import ai_bp
from backend.routes.productivity import productivity_bp
from backend.routes.reports import reports_bp
from backend.routes.attendance import attendance_bp
from backend.db import get_connection


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
    app.register_blueprint(reports_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp, url_prefix="/api")

    @app.cli.command("promote-admin")
    @click.option("--email", required=True)
    @click.option("--confirm", is_flag=True)
    def promote_admin(email, confirm):
        """Promote one existing member to admin after explicit confirmation."""
        if not confirm:
            raise click.UsageError("Pass --confirm to authorize the role change.")
        normalized_email = email.strip().lower()
        try:
            with get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT id, name, email, role FROM users WHERE email = %s",
                    (normalized_email,),
                )
                user = cursor.fetchone()
                if not user:
                    raise click.ClickException("No user found with that email.")
                if user["role"] == "admin":
                    click.echo("User is already an admin; no change made.")
                    return
                cursor.execute(
                    """UPDATE users SET role = 'admin'
                       WHERE id = %s AND role = 'member'""",
                    (user["id"],),
                )
                if cursor.rowcount != 1:
                    raise click.ClickException("Admin promotion was not applied.")
                connection.commit()
                click.echo(f"Promoted user {user['id']} ({user['email']}) to admin.")
                cursor.close()
        except Error as error:
            raise click.ClickException("Database unavailable.") from error

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
