from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app


def business_timezone():
    name = current_app.config.get("APP_TIMEZONE", "Asia/Kolkata")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        current_app.logger.exception("Invalid APP_TIMEZONE configuration: %s", name)
        raise RuntimeError("Invalid attendance timezone configuration.") from error


def utc_now():
    return datetime.now(timezone.utc)


def business_date(value=None):
    value = value or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(business_timezone()).date()


def mysql_utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def display_time(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.replace(tzinfo=timezone.utc).astimezone(business_timezone()).isoformat()


def serialize_record(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "attendance_date": row["attendance_date"].isoformat(),
        "check_in_at": display_time(row["check_in_at"]),
        "check_out_at": display_time(row["check_out_at"]),
        "status": "checked_out" if row["check_out_at"] else "checked_in",
        "user_name": row.get("user_name"),
        "user_email": row.get("user_email"),
    }
