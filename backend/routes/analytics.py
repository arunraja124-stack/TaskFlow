from flask import Blueprint, jsonify
from mysql.connector import Error

from backend.db import get_connection
from backend.security import login_required

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/analytics")
@login_required
def analytics():
    from flask import session, current_app

    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            user_id = session["user_id"]
            cursor.execute(
                """SELECT
                    COUNT(*) AS total,
                    SUM(status = 'todo') AS todo,
                    SUM(status = 'in_progress') AS in_progress,
                    SUM(status = 'completed') AS completed,
                    SUM(status <> 'completed' AND due_date IS NOT NULL AND due_date < CURRENT_DATE) AS overdue,
                    SUM(status = 'completed' AND updated_at >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)) AS weekly_completed
                   FROM tasks WHERE user_id = %s""",
                (user_id,),
            )
            stats = cursor.fetchone()
            cursor.close()
        total = int(stats["total"] or 0)
        completed = int(stats["completed"] or 0)
        return jsonify({"success": True, "data": {
            "total": total, "todo": int(stats["todo"] or 0),
            "in_progress": int(stats["in_progress"] or 0), "completed": completed,
            "overdue": int(stats["overdue"] or 0), "weekly_completed": int(stats["weekly_completed"] or 0),
            "completion_rate": round(completed / total * 100) if total else 0,
        }})
    except Error:
        current_app.logger.exception("Analytics database error")
        return jsonify({"success": False, "error": {"message": "Database unavailable."}}), 503
