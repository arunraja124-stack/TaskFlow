"""Non-destructive TaskFlow authentication migration."""
import secrets

import mysql.connector
from werkzeug.security import generate_password_hash

from config import Config


def column_exists(cursor, table_name, column_name):
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def table_exists(cursor, table_name):
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.TABLES
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
           AND TABLE_TYPE = 'BASE TABLE'""",
        (table_name,),
    )
    return cursor.fetchone()[0] > 0


def migrate():
    connection = mysql.connector.connect(**Config.DB_CONFIG)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
        )
        if not column_exists(cursor, "users", "role"):
            cursor.execute(
                """ALTER TABLE users
                   ADD COLUMN role ENUM('member', 'admin')
                   NOT NULL DEFAULT 'member' AFTER password_hash"""
            )
        cursor.execute("UPDATE users SET role = 'member' WHERE role IS NULL")
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS task_activity (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNSIGNED NOT NULL,
                task_id INT UNSIGNED NULL,
                action VARCHAR(40) NOT NULL,
                details VARCHAR(500) NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_activity_user_created (user_id, created_at),
                INDEX idx_activity_task (task_id),
                CONSTRAINT fk_activity_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
        )
        if not table_exists(cursor, "attendance"):
            cursor.execute(
                """CREATE TABLE attendance (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id INT UNSIGNED NOT NULL,
                    attendance_date DATE NOT NULL,
                    check_in_at DATETIME NOT NULL,
                    check_out_at DATETIME NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_attendance_user_date (user_id, attendance_date),
                    INDEX idx_attendance_date (attendance_date),
                    INDEX idx_attendance_user_date (user_id, attendance_date),
                    CONSTRAINT fk_attendance_user FOREIGN KEY (user_id)
                        REFERENCES users (id) ON DELETE CASCADE
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
            )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS notifications (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNSIGNED NOT NULL,
                task_id INT UNSIGNED NULL,
                kind VARCHAR(40) NOT NULL,
                message VARCHAR(255) NOT NULL,
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_notifications_user_read (user_id, is_read, created_at),
                CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INT UNSIGNED PRIMARY KEY,
                deadline_reminders BOOLEAN NOT NULL DEFAULT TRUE,
                overdue_alerts BOOLEAN NOT NULL DEFAULT TRUE,
                default_view VARCHAR(20) NOT NULL DEFAULT 'dashboard',
                default_priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
                CONSTRAINT fk_preferences_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
        )
        cursor.execute("SHOW COLUMNS FROM tasks LIKE 'user_id'")
        has_user_id = cursor.fetchone() is not None
        if not has_user_id:
            cursor.execute("ALTER TABLE tasks ADD COLUMN user_id INT UNSIGNED NULL AFTER id")
        cursor.execute("SELECT id FROM users WHERE email = %s", ("legacy-owner@taskflow.local",))
        legacy = cursor.fetchone()
        if legacy:
            legacy_id = legacy[0]
        else:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                ("Legacy Task Owner", "legacy-owner@taskflow.local", generate_password_hash(secrets.token_urlsafe(32))),
            )
            legacy_id = cursor.lastrowid
        cursor.execute("UPDATE tasks SET user_id = %s WHERE user_id IS NULL", (legacy_id,))
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id IS NULL")
        orphaned = cursor.fetchone()[0]
        if orphaned:
            raise RuntimeError("Migration left orphaned tasks.")
        cursor.execute("SHOW INDEX FROM tasks WHERE Key_name = 'idx_tasks_user_id'")
        if cursor.fetchone() is None:
            cursor.execute("CREATE INDEX idx_tasks_user_id ON tasks (user_id)")
        cursor.execute(
            """SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tasks'
               AND COLUMN_NAME = 'user_id' AND REFERENCED_TABLE_NAME = 'users'"""
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "ALTER TABLE tasks ADD CONSTRAINT fk_tasks_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE"
            )
        cursor.execute("SELECT COUNT(*) FROM tasks")
        print(f"Migration complete: users table ready; tasks assigned={cursor.fetchone()[0]}; no data dropped.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    migrate()
