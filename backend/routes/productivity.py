from flask import Blueprint, current_app, jsonify, session
from mysql.connector import Error

from backend.activity import serialize_activity
from backend.db import get_connection
from backend.security import login_required

productivity_bp = Blueprint("productivity", __name__)


@productivity_bp.get("/activity")
@login_required
def activity():
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, task_id, action, details, created_at
                   FROM task_activity WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT 50""",
                (session["user_id"],),
            )
            items = [serialize_activity(row) for row in cursor.fetchall()]
            cursor.close()
        return jsonify({"success": True, "data": {"activity": items}})
    except Error:
        current_app.logger.exception("Activity lookup failed")
        return jsonify({"success": False, "error": {"message": "Database unavailable."}}), 503


@productivity_bp.get("/calendar")
@login_required
def calendar():
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, title, description, status, priority, due_date, created_at, updated_at
                   FROM tasks WHERE user_id = %s AND due_date IS NOT NULL
                   ORDER BY due_date ASC, priority DESC""",
                (session["user_id"],),
            )
            tasks = [serialize_activity(row) for row in cursor.fetchall()]
            cursor.close()
        return jsonify({"success": True, "data": {"tasks": tasks}})
    except Error:
        current_app.logger.exception("Calendar lookup failed")
        return jsonify({"success": False, "error": {"message": "Database unavailable."}}), 503


@productivity_bp.get("/notifications")
@login_required
def notifications():
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, task_id, kind, message, is_read, created_at
                   FROM notifications WHERE user_id = %s
                   ORDER BY is_read ASC, created_at DESC LIMIT 30""",
                (session["user_id"],),
            )
            items = [serialize_activity(row) for row in cursor.fetchall()]
            cursor.close()
        return jsonify({"success": True, "data": {"notifications": items}})
    except Error:
        current_app.logger.exception("Notifications lookup failed")
        return jsonify({"success": False, "error": {"message": "Database unavailable."}}), 503


@productivity_bp.get("/reminders")
@login_required
def reminders():
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, title, status, priority, due_date,
                   CASE WHEN due_date < CURRENT_DATE THEN 'overdue' ELSE 'upcoming' END AS kind
                   FROM tasks
                   LEFT JOIN user_preferences ON user_preferences.user_id = tasks.user_id
                   WHERE tasks.user_id = %s AND status <> 'completed'
                     AND due_date IS NOT NULL
                     AND due_date <= DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY)
                     AND ((due_date < CURRENT_DATE AND COALESCE(overdue_alerts, TRUE) = TRUE)
                       OR (due_date >= CURRENT_DATE AND COALESCE(deadline_reminders, TRUE) = TRUE))
                   ORDER BY due_date ASC""",
                (session["user_id"],),
            )
            reminders = [serialize_activity(row) for row in cursor.fetchall()]
            cursor.close()
        return jsonify({"success": True, "data": {"reminders": reminders}})
    except Error:
        current_app.logger.exception("Reminders lookup failed")
        return jsonify({"success": False, "error": {"message": "Database unavailable."}}), 503
