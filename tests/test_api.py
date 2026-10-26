import uuid
from datetime import date, timedelta

import mysql.connector
import pytest

from app import create_app
from config import Config


@pytest.fixture()
def client(monkeypatch):
    database = f"taskflow_test_{uuid.uuid4().hex[:12]}"
    admin_config = dict(Config.DB_CONFIG)
    admin_config.pop("database", None)
    connection = mysql.connector.connect(**admin_config)
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE `{database}`")
    cursor.execute(f"USE `{database}`")
    cursor.execute("""CREATE TABLE users (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL,
        email VARCHAR(254) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE tasks (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id INT UNSIGNED NOT NULL,
        title VARCHAR(160) NOT NULL, description VARCHAR(2000) NOT NULL DEFAULT '',
        status ENUM('todo', 'in_progress', 'completed') NOT NULL DEFAULT 'todo',
        priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
        due_date DATE NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE task_activity (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id INT UNSIGNED NOT NULL,
        task_id INT UNSIGNED NULL, action VARCHAR(40) NOT NULL,
        details VARCHAR(500) NOT NULL DEFAULT '',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE notifications (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id INT UNSIGNED NOT NULL,
        task_id INT UNSIGNED NULL, kind VARCHAR(40) NOT NULL,
        message VARCHAR(255) NOT NULL, is_read BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE user_preferences (
        user_id INT UNSIGNED PRIMARY KEY, deadline_reminders BOOLEAN NOT NULL DEFAULT TRUE,
        overdue_alerts BOOLEAN NOT NULL DEFAULT TRUE, default_view VARCHAR(20) NOT NULL DEFAULT 'dashboard',
        default_priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium'
    )""")
    connection.commit()
    cursor.close()
    connection.close()
    test_config = dict(Config.DB_CONFIG)
    test_config["database"] = database
    monkeypatch.setattr(Config, "DB_CONFIG", test_config)
    app = create_app({"TESTING": True, "FRONTEND_ORIGIN": "*", "GEMINI_API_KEY": ""})
    yield app.test_client()
    cleanup = mysql.connector.connect(**admin_config)
    cleanup_cursor = cleanup.cursor()
    cleanup_cursor.execute(f"DROP DATABASE `{database}`")
    cleanup.commit()
    cleanup_cursor.close()
    cleanup.close()


def csrf(client):
    return client.get("/api/auth/csrf").json["data"]["csrf_token"]


def register(client, email="one@example.com"):
    token = csrf(client)
    result = client.post(
        "/api/auth/register",
        json={"name": "User One", "email": email, "password": "secure-pass-123", "password_confirmation": "secure-pass-123"},
        headers={"X-CSRF-Token": token},
    )
    assert result.status_code == 201
    return result


def test_health_and_anonymous_protection(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/tasks").status_code == 401


def test_registration_hashes_password_and_duplicate_is_generic(client):
    register(client)
    connection = mysql.connector.connect(**Config.DB_CONFIG)
    cursor = connection.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE email = %s", ("one@example.com",))
    password_hash = cursor.fetchone()[0]
    assert password_hash != "secure-pass-123"
    cursor.close()
    connection.close()
    token = csrf(client)
    duplicate = client.post("/api/auth/register", json={"name": "Other", "email": "one@example.com", "password": "secure-pass-123", "password_confirmation": "secure-pass-123"}, headers={"X-CSRF-Token": token})
    assert duplicate.status_code == 409


def test_login_logout_and_crud(client):
    register(client)
    token = csrf(client)
    created = client.post("/api/tasks", json={"title": "Owned task", "priority": "high"}, headers={"X-CSRF-Token": token})
    assert created.status_code == 201
    task_id = created.json["data"]["id"]
    assert client.get(f"/api/tasks/{task_id}").status_code == 200
    token = csrf(client)
    assert client.put(f"/api/tasks/{task_id}", json={"title": "Updated task"}, headers={"X-CSRF-Token": token}).status_code == 200
    token = csrf(client)
    assert client.patch(f"/api/tasks/{task_id}/status", json={"status": "completed"}, headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/api/analytics").json["data"]["completed"] == 1
    token = csrf(client)
    assert client.delete(f"/api/tasks/{task_id}", headers={"X-CSRF-Token": token}).status_code == 200
    token = csrf(client)
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/api/tasks").status_code == 401


def test_cross_user_task_is_not_accessible(client):
    register(client)
    token = csrf(client)
    task_id = client.post("/api/tasks", json={"title": "Private task"}, headers={"X-CSRF-Token": token}).json["data"]["id"]
    token = csrf(client)
    client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    token = csrf(client)
    register(client, "two@example.com")
    assert client.get(f"/api/tasks/{task_id}").status_code == 404
    token = csrf(client)
    assert client.patch(f"/api/tasks/{task_id}/status", json={"status": "completed"}, headers={"X-CSRF-Token": token}).status_code == 404


def test_validation_csrf_and_ai_configuration(client):
    register(client)
    assert client.post("/api/tasks", json={"title": "Missing token"}).status_code == 403
    token = csrf(client)
    assert client.post("/api/tasks", json={"description": "Missing title"}, headers={"X-CSRF-Token": token}).status_code == 400
    token = csrf(client)
    ai = client.post("/api/ai/suggest-tasks", json={"description": "Plan a release"}, headers={"X-CSRF-Token": token})
    assert ai.status_code == 503


def test_activity_calendar_and_reminders_are_user_scoped(client):
    register(client)
    token = csrf(client)
    created = client.post(
        "/api/tasks",
        json={"title": "Dated task", "due_date": (date.today() + timedelta(days=3)).isoformat()},
        headers={"X-CSRF-Token": token},
    )
    assert created.status_code == 201
    assert client.get("/api/activity").json["data"]["activity"][0]["action"] == "created"
    assert client.get("/api/calendar").json["data"]["tasks"][0]["title"] == "Dated task"
    assert client.get("/api/reminders").json["data"]["reminders"][0]["kind"] == "upcoming"


def test_settings_profile_preferences_and_password(client):
    register(client)
    assert client.get("/api/auth/preferences").json["data"]["preferences"]["default_priority"] == "medium"
    token = csrf(client)
    updated = client.put(
        "/api/auth/profile",
        json={"name": "Updated User", "email": "updated@example.com"},
        headers={"X-CSRF-Token": token},
    )
    assert updated.status_code == 200
    assert client.get("/api/auth/me").json["data"]["user"]["name"] == "Updated User"
    token = csrf(client)
    preferences = client.put(
        "/api/auth/preferences",
        json={"deadline_reminders": False, "overdue_alerts": True, "default_view": "calendar", "default_priority": "high"},
        headers={"X-CSRF-Token": token},
    )
    assert preferences.status_code == 200
    assert client.get("/api/auth/preferences").json["data"]["preferences"]["default_view"] == "calendar"
    token = csrf(client)
    assert client.post(
        "/api/auth/password",
        json={"current_password": "secure-pass-123", "new_password": "new-secure-pass-456", "password_confirmation": "new-secure-pass-456"},
        headers={"X-CSRF-Token": token},
    ).status_code == 200
    token = csrf(client)
    assert client.post("/api/auth/login", json={"email": "updated@example.com", "password": "new-secure-pass-456"}, headers={"X-CSRF-Token": token}).status_code == 200


def test_settings_validation_and_csrf(client):
    register(client)
    assert client.put("/api/auth/profile", json={"name": "", "email": "bad"}).status_code == 403
    token = csrf(client)
    assert client.put("/api/auth/profile", json={"name": "", "email": "bad"}, headers={"X-CSRF-Token": token}).status_code == 400
    token = csrf(client)
    assert client.put("/api/auth/preferences", json={"deadline_reminders": True, "overdue_alerts": True, "default_view": "unknown", "default_priority": "medium"}, headers={"X-CSRF-Token": token}).status_code == 400
