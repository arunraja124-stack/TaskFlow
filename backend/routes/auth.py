from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session
from mysql.connector import Error, IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from backend.db import get_connection
from backend.security import csrf_token, require_csrf

auth_bp = Blueprint("auth", __name__)


def result(data=None, message=None, status=200):
    body = {"success": status < 400}
    if data is not None:
        body["data"] = data
    if message:
        body["error" if status >= 400 else "message"] = {"message": message} if status >= 400 else message
    return jsonify(body), status


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
        return user
    except Error:
        current_app.logger.exception("Unable to load current user")
        return None


@auth_bp.get("/csrf")
def csrf():
    return result({"csrf_token": csrf_token()})


@auth_bp.get("/me")
def me():
    user = current_user()
    return result({"user": user}) if user else result(message="Authentication required.", status=401)


@auth_bp.post("/register")
@require_csrf
def register():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "").strip() if isinstance(payload.get("name"), str) else ""
    email = payload.get("email", "").strip().lower() if isinstance(payload.get("email"), str) else ""
    password = payload.get("password", "")
    confirmation = payload.get("password_confirmation", "")
    if not name or len(name) > 100:
        return result(message="Name is required and must be 100 characters or fewer.", status=400)
    if "@" not in email or len(email) > 254:
        return result(message="Enter a valid email address.", status=400)
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        return result(message="Password must be between 8 and 128 characters.", status=400)
    if password != confirmation:
        return result(message="Passwords do not match.", status=400)
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password)),
            )
            connection.commit()
            user_id = cursor.lastrowid
            cursor.close()
        session.clear()
        session.permanent = True
        session["user_id"] = user_id
        csrf_token()
        return result({"user": {"id": user_id, "name": name, "email": email}}, "Registration successful.", 201)
    except IntegrityError:
        return result(message="Unable to register with those details.", status=409)
    except Error:
        current_app.logger.exception("Registration database error")
        return result(message="Database unavailable.", status=503)


@auth_bp.post("/login")
@require_csrf
def login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "").strip().lower() if isinstance(payload.get("email"), str) else ""
    password = payload.get("password", "")
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id, name, email, password_hash FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
        if not user or not check_password_hash(user["password_hash"], password):
            return result(message="Invalid email or password.", status=401)
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        csrf_token()
        return result({"user": {key: user[key] for key in ("id", "name", "email")}}, "Login successful.")
    except Error:
        current_app.logger.exception("Login database error")
        return result(message="Database unavailable.", status=503)


@auth_bp.post("/logout")
@require_csrf
def logout():
    session.clear()
    return result(message="Logged out.")


def _validate_profile(payload):
    name = payload.get("name", "").strip() if isinstance(payload.get("name"), str) else ""
    email = payload.get("email", "").strip().lower() if isinstance(payload.get("email"), str) else ""
    if not name or len(name) > 100:
        return None, "Name is required and must be 100 characters or fewer."
    if "@" not in email or len(email) > 254:
        return None, "Enter a valid email address."
    return {"name": name, "email": email}, None


@auth_bp.put("/profile")
@require_csrf
def update_profile():
    user_id = session.get("user_id")
    if not user_id:
        return result(message="Authentication required.", status=401)
    payload = request.get_json(silent=True) or {}
    profile, validation_error = _validate_profile(payload)
    if validation_error:
        return result(message=validation_error, status=400)
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE email = %s AND id <> %s",
                (profile["email"], user_id),
            )
            if cursor.fetchone():
                cursor.close()
                return result(message="Unable to update profile with those details.", status=409)
            cursor.execute(
                "UPDATE users SET name = %s, email = %s WHERE id = %s",
                (profile["name"], profile["email"], user_id),
            )
            connection.commit()
            cursor.close()
        return result({"user": {"id": user_id, **profile}}, "Profile updated.")
    except Error:
        current_app.logger.exception("Profile update database error")
        return result(message="Database unavailable.", status=503)


@auth_bp.post("/password")
@require_csrf
def change_password():
    user_id = session.get("user_id")
    if not user_id:
        return result(message="Authentication required.", status=401)
    payload = request.get_json(silent=True) or {}
    current_password = payload.get("current_password", "")
    new_password = payload.get("new_password", "")
    confirmation = payload.get("password_confirmation", "")
    if not all(isinstance(value, str) for value in (current_password, new_password, confirmation)):
        return result(message="Password values are required.", status=400)
    if len(new_password) < 8 or len(new_password) > 128:
        return result(message="New password must be between 8 and 128 characters.", status=400)
    if new_password != confirmation:
        return result(message="Passwords do not match.", status=400)
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or not check_password_hash(user["password_hash"], current_password):
                cursor.close()
                return result(message="Current password is incorrect.", status=400)
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (generate_password_hash(new_password), user_id),
            )
            connection.commit()
            cursor.close()
        return result(message="Password updated.")
    except Error:
        current_app.logger.exception("Password update database error")
        return result(message="Database unavailable.", status=503)


def _preferences(cursor, user_id):
    cursor.execute(
        """SELECT deadline_reminders, overdue_alerts, default_view, default_priority
           FROM user_preferences WHERE user_id = %s""",
        (user_id,),
    )
    preferences = cursor.fetchone()
    if preferences:
        return preferences
    cursor.execute(
        """INSERT INTO user_preferences
           (user_id, deadline_reminders, overdue_alerts, default_view, default_priority)
           VALUES (%s, TRUE, TRUE, 'dashboard', 'medium')""",
        (user_id,),
    )
    return {
        "deadline_reminders": True,
        "overdue_alerts": True,
        "default_view": "dashboard",
        "default_priority": "medium",
    }


@auth_bp.get("/preferences")
def get_preferences():
    user_id = session.get("user_id")
    if not user_id:
        return result(message="Authentication required.", status=401)
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            preferences = _preferences(cursor, user_id)
            connection.commit()
            cursor.close()
        return result({"preferences": preferences})
    except Error:
        current_app.logger.exception("Preferences load database error")
        return result(message="Database unavailable.", status=503)


@auth_bp.put("/preferences")
@require_csrf
def update_preferences():
    user_id = session.get("user_id")
    if not user_id:
        return result(message="Authentication required.", status=401)
    payload = request.get_json(silent=True) or {}
    allowed_views = {"dashboard", "board", "calendar"}
    allowed_priorities = {"low", "medium", "high"}
    default_view = payload.get("default_view")
    default_priority = payload.get("default_priority")
    if default_view not in allowed_views or default_priority not in allowed_priorities:
        return result(message="Choose a valid default view and priority.", status=400)
    deadline_reminders = payload.get("deadline_reminders")
    overdue_alerts = payload.get("overdue_alerts")
    if not isinstance(deadline_reminders, bool) or not isinstance(overdue_alerts, bool):
        return result(message="Notification preferences must be true or false.", status=400)
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO user_preferences
                   (user_id, deadline_reminders, overdue_alerts, default_view, default_priority)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   deadline_reminders = VALUES(deadline_reminders),
                   overdue_alerts = VALUES(overdue_alerts),
                   default_view = VALUES(default_view),
                   default_priority = VALUES(default_priority)""",
                (user_id, deadline_reminders, overdue_alerts, default_view, default_priority),
            )
            connection.commit()
            cursor.close()
        return result({"preferences": payload}, "Preferences updated.")
    except Error:
        current_app.logger.exception("Preferences update database error")
        return result(message="Database unavailable.", status=503)
