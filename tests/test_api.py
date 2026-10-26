from unittest.mock import patch

from app import create_app


def test_health_endpoint():
    client = create_app({"TESTING": True, "FRONTEND_ORIGIN": "*"}).test_client()
    result = client.get("/api/health")
    assert result.status_code == 200
    assert result.json["data"]["status"] == "ok"


def test_create_rejects_missing_title():
    client = create_app({"TESTING": True, "FRONTEND_ORIGIN": "*"}).test_client()
    result = client.post("/api/tasks", json={"description": "Missing title"})
    assert result.status_code == 400
    assert "Title is required" in result.json["error"]["message"]


def test_create_rejects_invalid_priority():
    client = create_app({"TESTING": True, "FRONTEND_ORIGIN": "*"}).test_client()
    result = client.post("/api/tasks", json={"title": "Bad task", "priority": "urgent"})
    assert result.status_code == 400
    assert "Priority" in result.json["error"]["message"]


def test_missing_task_returns_404():
    client = create_app({"TESTING": True, "FRONTEND_ORIGIN": "*"}).test_client()
    with patch("backend.routes.tasks.get_task", return_value=None):
        result = client.get("/api/tasks/999")
    assert result.status_code == 404
    assert result.json["error"]["message"] == "Task not found."


def test_status_requires_valid_value():
    client = create_app({"TESTING": True, "FRONTEND_ORIGIN": "*"}).test_client()
    result = client.patch("/api/tasks/1/status", json={"status": "blocked"})
    assert result.status_code == 400
