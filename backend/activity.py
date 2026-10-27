from datetime import datetime

from backend.db import get_connection


def record_activity(user_id, task_id, action, details=""):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO task_activity (user_id, task_id, action, details) VALUES (%s, %s, %s, %s)",
            (user_id, task_id, action, details[:500]),
        )
        connection.commit()
        cursor.close()


def serialize_activity(row):
    item = dict(row)
    if isinstance(item.get("created_at"), datetime):
        item["created_at"] = item["created_at"].isoformat()
    return item
