from datetime import date

from flask import Blueprint, current_app, jsonify, request, session
from mysql.connector import Error, IntegrityError

from backend.attendance import business_date, mysql_utc, serialize_record, utc_now
from backend.db import get_connection
from backend.security import login_required, require_csrf

attendance_bp = Blueprint("attendance", __name__)


def response(data=None, message=None, status=200):
    body = {"success": status < 400}
    if data is not None:
        body["data"] = data
    if message:
        body["error" if status >= 400 else "message"] = {"message": message} if status >= 400 else message
    return jsonify(body), status


def _record(cursor, user_id, attendance_day):
    cursor.execute(
        """SELECT id, user_id, attendance_date, check_in_at, check_out_at
           FROM attendance WHERE user_id = %s AND attendance_date = %s""",
        (user_id, attendance_day),
    )
    return cursor.fetchone()


def _parse_date(raw):
    if not raw:
        return business_date()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _admin_required(view):
    from functools import wraps

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT role FROM users WHERE id = %s", (session["user_id"],))
                user = cursor.fetchone()
                cursor.close()
            if not user or user[0] != "admin":
                return response(message="Administrator access required.", status=403)
        except Error:
            current_app.logger.exception("Unable to authorize admin attendance request")
            return response(message="Database unavailable.", status=503)
        return view(*args, **kwargs)

    return wrapped


@attendance_bp.get("/attendance/status")
@login_required
def status():
    day = business_date()
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            row = _record(cursor, session["user_id"], day)
            cursor.close()
        return response({"business_date": day.isoformat(), "record": serialize_record(row) if row else None})
    except Error:
        current_app.logger.exception("Unable to load attendance status")
        return response(message="Database unavailable.", status=503)


@attendance_bp.get("/attendance/history")
@login_required
def history():
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except ValueError:
        return response(message="Invalid history limit.", status=400)
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, user_id, attendance_date, check_in_at, check_out_at
                   FROM attendance WHERE user_id = %s
                   ORDER BY attendance_date DESC LIMIT %s""",
                (session["user_id"], limit),
            )
            rows = cursor.fetchall()
            cursor.close()
        return response({"records": [serialize_record(row) for row in rows]})
    except Error:
        current_app.logger.exception("Unable to load attendance history")
        return response(message="Database unavailable.", status=503)


@attendance_bp.post("/attendance/check-in")
@login_required
@require_csrf
def check_in():
    day = business_date()
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """INSERT INTO attendance
                       (user_id, attendance_date, check_in_at)
                       VALUES (%s, %s, %s)""",
                    (session["user_id"], day, mysql_utc(utc_now())),
                )
                connection.commit()
            except IntegrityError:
                connection.rollback()
                return response(message="You have already checked in for this business date.", status=409)
            row = _record(cursor, session["user_id"], day)
            cursor.close()
        return response({"record": serialize_record(row)}, "Checked in successfully.", 201)
    except Error:
        current_app.logger.exception("Unable to check in")
        return response(message="Database unavailable.", status=503)


@attendance_bp.post("/attendance/check-out")
@login_required
@require_csrf
def check_out():
    day = business_date()
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            row = _record(cursor, session["user_id"], day)
            if not row:
                cursor.close()
                return response(message="Check in before checking out.", status=409)
            if row["check_out_at"]:
                cursor.close()
                return response(message="You have already checked out for this business date.", status=409)
            cursor.execute(
                """UPDATE attendance SET check_out_at = %s
                   WHERE id = %s AND check_out_at IS NULL""",
                (mysql_utc(utc_now()), row["id"]),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return response(message="Attendance status changed; please refresh and try again.", status=409)
            connection.commit()
            row = _record(cursor, session["user_id"], day)
            cursor.close()
        return response({"record": serialize_record(row)}, "Checked out successfully.")
    except Error:
        current_app.logger.exception("Unable to check out")
        return response(message="Database unavailable.", status=503)


@attendance_bp.get("/admin/attendance")
@_admin_required
def admin_attendance():
    day = _parse_date(request.args.get("date"))
    if not day:
        return response(message="Invalid attendance date.", status=400)
    search = request.args.get("search", "").strip()
    try:
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'member'")
            total = cursor.fetchone()["total"]
            query = """SELECT a.id, a.user_id, a.attendance_date, a.check_in_at, a.check_out_at,
                              u.name AS user_name, u.email AS user_email
                       FROM attendance a JOIN users u ON u.id = a.user_id
                       WHERE a.attendance_date = %s"""
            params = [day]
            if search:
                query += " AND (u.name LIKE %s OR u.email LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            query += " ORDER BY u.name ASC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            cursor.close()
        records = [serialize_record(row) for row in rows]
        checked_in = len(records)
        checked_out = sum(record["status"] == "checked_out" for record in records)
        return response({"date": day.isoformat(), "counts": {
            "members": total, "checked_in": checked_in, "checked_out": checked_out,
            "currently_checked_in": checked_in - checked_out,
        }, "records": records})
    except Error:
        current_app.logger.exception("Unable to load admin attendance")
        return response(message="Database unavailable.", status=503)
