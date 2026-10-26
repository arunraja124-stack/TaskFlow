from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request, session
from mysql.connector import Error

from backend.db import get_connection
from backend.activity import record_activity
from backend.security import login_required, require_csrf

tasks_bp = Blueprint("tasks", __name__)
VALID_STATUSES = {"todo", "in_progress", "completed"}
VALID_PRIORITIES = {"low", "medium", "high"}


def log_activity(action, task_id, details=""):
    try:
        record_activity(session["user_id"], task_id, action, details)
    except Error:
        current_app.logger.warning("Unable to record task activity", exc_info=True)


def response(data=None, message=None, status=200):
    body = {"success": status < 400}
    if data is not None:
        body["data"] = data
    if message:
        body["error" if status >= 400 else "message"] = {"message": message} if status >= 400 else message
    return jsonify(body), status


def serialize_task(row):
    task = dict(row)
    for key in ("created_at", "updated_at"):
        if isinstance(task.get(key), datetime):
            task[key] = task[key].isoformat()
    if isinstance(task.get("due_date"), date):
        task["due_date"] = task["due_date"].isoformat()
    return task


def parse_payload(payload, partial=False):
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."
    allowed = {"title", "description", "priority", "due_date", "status"}
    unknown = set(payload) - allowed
    if unknown:
        return None, f"Unsupported field: {sorted(unknown)[0]}."
    if not partial or "title" in payload:
        title = payload.get("title", "").strip() if isinstance(payload.get("title", ""), str) else ""
        if not title:
            return None, "Title is required."
        if len(title) > 160:
            return None, "Title must be 160 characters or fewer."
        payload["title"] = title
    if "description" in payload and (not isinstance(payload["description"], str) or len(payload["description"]) > 2000):
        return None, "Description must be 2000 characters or fewer."
    if "priority" in payload and payload["priority"] not in VALID_PRIORITIES:
        return None, "Priority must be low, medium, or high."
    if "status" in payload and payload["status"] not in VALID_STATUSES:
        return None, "Status must be todo, in_progress, or completed."
    if "due_date" in payload and payload["due_date"]:
        try:
            due = date.fromisoformat(payload["due_date"])
            if due < date.today():
                return None, "Due date cannot be in the past."
        except (TypeError, ValueError):
            return None, "Due date must use YYYY-MM-DD format."
    return payload, None


@tasks_bp.get("/health")
def health():
    return response({"status": "ok", "service": "taskflow-api"})


@tasks_bp.get("/tasks")
@login_required
def list_tasks():
    query = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    sort = request.args.get("sort", "created_at")
    sort_columns = {"due_date": "due_date", "created_at": "created_at", "priority": "priority"}
    if status and status not in VALID_STATUSES:
        return response(message="Invalid status filter.", status=400)
    if priority and priority not in VALID_PRIORITIES:
        return response(message="Invalid priority filter.", status=400)
    order_column = sort_columns.get(sort, "created_at")
    order = "FIELD(priority, 'high', 'medium', 'low'), created_at DESC" if sort == "priority" else f"{order_column} ASC"
    clauses, values = ["user_id = %s"], [session["user_id"]]
    if query:
        clauses.append("title LIKE %s")
        values.append(f"%{query}%")
    if status:
        clauses.append("status = %s")
        values.append(status)
    if priority:
        clauses.append("priority = %s")
        values.append(priority)
    sql = f"SELECT id, title, description, status, priority, due_date, created_at, updated_at FROM tasks WHERE {' AND '.join(clauses)} ORDER BY {order}"
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(sql, tuple(values))
            tasks = [serialize_task(row) for row in cursor.fetchall()]
            cursor.close()
        return response({"tasks": tasks, "count": len(tasks)})
    except Error:
        current_app.logger.exception("Unable to list tasks")
        return response(message="Database unavailable.", status=503)


@tasks_bp.post("/tasks")
@login_required
@require_csrf
def create_task():
    payload, error = parse_payload(request.get_json(silent=True) or {})
    if error:
        return response(message=error, status=400)
    payload.setdefault("description", "")
    payload.setdefault("priority", "medium")
    payload.setdefault("status", "todo")
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO tasks (user_id, title, description, priority, status, due_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (session["user_id"], payload["title"], payload["description"], payload["priority"], payload["status"], payload.get("due_date") or None),
            )
            connection.commit()
            task_id = cursor.lastrowid
            cursor.close()
        log_activity("created", task_id, payload["title"])
        return response({"id": task_id}, "Task created.", 201)
    except Error:
        current_app.logger.exception("Unable to create task")
        return response(message="Database unavailable.", status=503)


def get_task(task_id):
    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, title, description, status, priority, due_date, created_at, updated_at FROM tasks WHERE id = %s AND user_id = %s", (task_id, session["user_id"]))
        task = cursor.fetchone()
        cursor.close()
    return serialize_task(task) if task else None


@tasks_bp.get("/tasks/<int:task_id>")
@login_required
def read_task(task_id):
    try:
        task = get_task(task_id)
        return response({"task": task}) if task else response(message="Task not found.", status=404)
    except Error:
        current_app.logger.exception("Unable to read task")
        return response(message="Database unavailable.", status=503)


@tasks_bp.put("/tasks/<int:task_id>")
@login_required
@require_csrf
def update_task(task_id):
    payload, error = parse_payload(request.get_json(silent=True) or {}, partial=True)
    if error:
        return response(message=error, status=400)
    fields = [key for key in ("title", "description", "priority", "status", "due_date") if key in payload]
    if not fields:
        return response(message="At least one editable field is required.", status=400)
    values = [None if payload[key] == "" and key == "due_date" else payload[key] for key in fields]
    assignments = ", ".join(f"{field} = %s" for field in fields)
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(f"UPDATE tasks SET {assignments} WHERE id = %s AND user_id = %s", (*values, task_id, session["user_id"]))
            if cursor.rowcount == 0:
                cursor.close()
                return response(message="Task not found.", status=404)
            connection.commit()
            cursor.close()
        log_activity("updated", task_id, ", ".join(fields))
        return response(message="Task updated.")
    except Error:
        current_app.logger.exception("Unable to update task")
        return response(message="Database unavailable.", status=503)


@tasks_bp.patch("/tasks/<int:task_id>/status")
@login_required
@require_csrf
def update_status(task_id):
    payload = request.get_json(silent=True) or {}
    if payload.get("status") not in VALID_STATUSES:
        return response(message="Status must be todo, in_progress, or completed.", status=400)
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE tasks SET status = %s WHERE id = %s AND user_id = %s", (payload["status"], task_id, session["user_id"]))
            if cursor.rowcount == 0:
                cursor.close()
                return response(message="Task not found.", status=404)
            connection.commit()
            cursor.close()
        log_activity("status_changed", task_id, payload["status"])
        return response(message="Task status updated.")
    except Error:
        current_app.logger.exception("Unable to update task status")
        return response(message="Database unavailable.", status=503)


@tasks_bp.delete("/tasks/<int:task_id>")
@login_required
@require_csrf
def delete_task(task_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s", (task_id, session["user_id"]))
            if cursor.rowcount == 0:
                cursor.close()
                return response(message="Task not found.", status=404)
            connection.commit()
            cursor.close()
        log_activity("deleted", task_id)
        return response(message="Task deleted.")
    except Error:
        current_app.logger.exception("Unable to delete task")
        return response(message="Database unavailable.", status=503)
