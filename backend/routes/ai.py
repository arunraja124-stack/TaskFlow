import json
import time

from flask import Blueprint, current_app, jsonify, request, session

from backend.security import login_required, require_csrf

ai_bp = Blueprint("ai", __name__)
_last_request = {}


@ai_bp.post("/ai/assist")
@ai_bp.post("/ai/suggest-tasks")
@login_required
@require_csrf
def assist():
    goal = request.get_json(silent=True)
    if not isinstance(goal, dict):
        return jsonify({"success": False, "error": {"message": "Request body must be a JSON object."}}), 400
    text = goal.get("description", goal.get("goal", ""))
    text = text.strip() if isinstance(text, str) else ""
    if not text or len(text) > 2000:
        return jsonify({"success": False, "error": {"message": "Enter a task description between 1 and 2000 characters."}}), 400
    now = time.monotonic()
    if now - _last_request.get(session["user_id"], 0) < 10:
        return jsonify({"success": False, "error": {"message": "Please wait a few seconds before requesting assistance again."}}), 429
    if not current_app.config["GEMINI_API_KEY"]:
        return jsonify({"success": False, "error": {"message": "AI assistance is not configured. Add GEMINI_API_KEY on the server."}}), 503
    _last_request[session["user_id"]] = now
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=current_app.config["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=10000),
        )
        prompt = (
            "Return only valid JSON with exactly these keys: title (string), description (string), "
            "priority (one of low, medium, high), subtasks (array of strings). "
            "Do not include sensitive data. Turn this task description into a practical task draft: " + text
        )
        response = client.models.generate_content(
            model=current_app.config["GEMINI_MODEL"], contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        data = json.loads(response.text)
        if not isinstance(data.get("title"), str) or not isinstance(data.get("description"), str) or not isinstance(data.get("subtasks"), list):
            raise ValueError("Invalid AI response structure")
        data["title"] = data["title"].strip()[:160]
        data["description"] = data["description"].strip()[:2000]
        data["subtasks"] = [item.strip()[:500] for item in data["subtasks"] if isinstance(item, str) and item.strip()][:10]
        if data.get("priority") not in {"low", "medium", "high"}:
            data["priority"] = "medium"
        return jsonify({"success": True, "data": data})
    except (json.JSONDecodeError, ValueError, TypeError):
        current_app.logger.warning("AI provider returned an invalid suggestion structure")
        return jsonify({"success": False, "error": {"message": "AI returned an invalid suggestion. Please try again."}}), 502
    except Exception:
        current_app.logger.warning("AI provider request failed")
        return jsonify({"success": False, "error": {"message": "AI assistance is temporarily unavailable. You can continue creating tasks manually."}}), 502
