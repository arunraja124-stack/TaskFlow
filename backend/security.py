import secrets
from functools import wraps

from flask import jsonify, session


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def require_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not secrets.compare_digest(request_token(), session.get("csrf_token", "")):
            return jsonify({"success": False, "error": {"message": "Invalid CSRF token."}}), 403
        return view(*args, **kwargs)

    return wrapped


def request_token():
    from flask import request

    return request.headers.get("X-CSRF-Token", "")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": {"message": "Authentication required."}}), 401
        return view(*args, **kwargs)

    return wrapped
