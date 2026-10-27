# TaskFlow

TaskFlow is a portfolio-ready team task management system built with Flask, MySQL, Bootstrap 5, and vanilla JavaScript. It demonstrates semantic HTML, responsive CSS, DOM updates, Fetch API integration, REST design, parameterized SQL, validation, and automated testing.

## Features

- Dashboard counts and completion progress
- Secure registration, login, logout, CSRF-protected requests, and user-owned tasks
- MySQL-backed task creation, editing, deletion, and status changes
- To do, In progress, and Completed Kanban columns
- Native drag-and-drop status persistence plus an accessible status select
- Search by title, status/priority filters, and sorting
- Required-field, length, enum, and date validation on the client and server
- Loading/error/success feedback and destructive-action confirmation
- Optional Gemini-powered task suggestions
- Overdue and weekly completion analytics
- Upcoming/overdue calendar agenda and recent activity history
- User-scoped reminders and persistent notification storage
- Dark-mode preference with responsive navigation
- Dedicated Settings page for profile, password, notification, task-view, priority, and theme preferences
- Member attendance with business-date check-in/check-out and an admin team report

## Stack and architecture

The Flask application serves the static frontend and exposes `/api` JSON endpoints. Browser events call the API with `fetch`; route handlers validate payloads and use `mysql-connector-python` parameterized queries. MySQL stores task data and timestamps.

```text
app.py                 Flask factory and static entry point
config.py              Environment-backed configuration
backend/db.py          Connection lifecycle
backend/routes/tasks.py REST task and health endpoints
backend/routes/auth.py  Registration, login, logout, and CSRF
backend/routes/analytics.py User-scoped productivity statistics
backend/routes/ai.py      Optional Gemini task assistance
backend/routes/productivity.py Calendar, activity, reminders, notifications
backend/routes/attendance.py Member attendance and admin attendance reporting, notifications
frontend/              HTML, CSS, Bootstrap, and vanilla JS
schema.sql             Database/table creation
migrate.py             Non-destructive migration for existing databases
tests/                 Pytest API validation tests
```

## Windows local setup

Prerequisites: Python 3.11+, MySQL Server 8+, and Git.

1. Create a database/user, then run `schema.sql` in MySQL Workbench or the MySQL client for a new database. For the existing TaskFlow database, run `python migrate.py`; it creates `users`, adds `tasks.user_id`, assigns orphaned legacy tasks to a non-loginable legacy owner, and never drops data.
2. Create and activate a virtual environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the local MySQL credentials. Never commit `.env`. Set `GEMINI_API_KEY` only when AI suggestions are desired; keep it server-side. The current default model is `gemini-2.5-flash`; override `GEMINI_MODEL` only with a model enabled for your key. Set `SESSION_COOKIE_SECURE=true` when serving over HTTPS.
4. Start the server:

   ```powershell
   python app.py
   ```

5. Open <http://127.0.0.1:5000>. Verify the API with `GET http://127.0.0.1:5000/api/health`.

## API contract

All responses use `{ "success": boolean, "data": ... }`; errors use `{ "success": false, "error": { "message": "..." } }`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Service health (does not require the database) |
| GET | `/api/tasks?search=&status=&priority=&sort=` | List/filter tasks |
| GET | `/api/tasks/<id>` | Read one task |
| POST | `/api/tasks` | Create a task |
| PUT | `/api/tasks/<id>` | Update task fields |
| PATCH | `/api/tasks/<id>/status` | Change status |
| DELETE | `/api/tasks/<id>` | Delete a task |
| POST | `/api/auth/register` | Register and start a session |
| POST | `/api/auth/login` | Sign in |
| POST | `/api/auth/logout` | Sign out |
| PUT | `/api/auth/profile` | Update the authenticated user's name and email |
| POST | `/api/auth/password` | Change password after current-password verification |
| GET | `/api/auth/preferences` | Read authenticated user's settings |
| PUT | `/api/auth/preferences` | Save notification and task-view preferences |
| GET | `/api/analytics` | User-scoped productivity statistics |
| POST | `/api/ai/assist` | Optional structured Gemini suggestions |
| GET | `/api/calendar` | Authenticated user's dated tasks |
| GET | `/api/activity` | Authenticated user's recent task history |
| GET | `/api/reminders` | Authenticated user's upcoming/overdue tasks |
| GET | `/api/notifications` | Authenticated user's stored notifications |
| GET | `/api/attendance/status` | Current user's business-date attendance status |
| GET | `/api/attendance/history` | Current user's attendance history |
| POST | `/api/attendance/check-in` | Check in for the current business date |
| POST | `/api/attendance/check-out` | Check out after checking in |
| GET | `/api/admin/attendance?date=&search=` | Admin-only team attendance report |

## Attendance

Attendance uses the configured `APP_TIMEZONE` (default `Asia/Kolkata`) to determine
the business date. Check-in and check-out timestamps are generated by the server,
stored as UTC values in MySQL `DATETIME` columns, and converted to the configured
business timezone for API and UI display. Members can create at most one record per
business date and can check out only once after checking in. No absence, lateness,
or shift policy is inferred.

Members use `/attendance.html`. Administrators can use `/admin-attendance.html` to
view date-filtered team records and counts. Promote an existing account with the
protected command (never public registration):

```powershell
flask --app app promote-admin --email existing@example.com --confirm
```

Set `APP_TIMEZONE=Asia/Kolkata` in `.env` to make the default explicit. Run the
isolated test suite with `python -m pytest -q`; it creates a temporary MySQL
database and never inserts attendance records into the live database.

## Testing

Run `python -m pytest -q`. The suite creates and removes an isolated temporary MySQL database, testing password hashing, duplicate registration, CSRF, session protection, ownership isolation, CRUD, analytics, settings validation, profile persistence, password changes, and missing-AI-key handling. It never uses production `taskflow_db` data.

## Deployment

Deploy the Flask service to a Python host such as Render, Railway, or Fly.io and provision a managed MySQL database. Set every `.env.example` variable in the host's secret environment configuration, use `gunicorn --bind 0.0.0.0:$PORT app:app` as the start command, and set `SESSION_COOKIE_SECURE=true` behind HTTPS. Because Flask serves the frontend from the same origin, set `FRONTEND_ORIGIN` to the deployed application origin; no separate frontend service is required. Run `python migrate.py` against the existing hosted database before first use. Do not put database credentials or `GEMINI_API_KEY` in frontend code.

No hosting account, production database, GitHub remote, or public URL has been configured in this workspace. Those steps require account access and explicit authorization.

## Known limitations

The Gemini assistant is optional and depends on provider quota and network availability. Authentication does not include email verification, password reset, or account deletion yet. The settings page supports profile updates, secure password changes, theme persistence, notification preferences, and default task view/priority preferences. The legacy pre-auth task is assigned to an inaccessible migration owner rather than exposed across users.

Run `python migrate.py` after updating an existing database. The migration only creates missing tables, columns, indexes, and relationships; it does not drop databases or existing rows.

## Two-minute interview explanation

“TaskFlow is a Flask REST application backed by MySQL. The browser renders a responsive Bootstrap dashboard and uses vanilla JavaScript Fetch calls to load and mutate tasks without full page reloads. The API validates every input, uses parameterized SQL, returns consistent JSON, and exposes a health check. The Kanban board uses native drag-and-drop, while each card also has a status select for keyboard and mobile users. Configuration and credentials come from environment variables, and pytest covers the health and validation behavior. I would deploy the API with a managed MySQL service and keep the frontend origin restricted through CORS.”

## Interview questions and answers

1. **Why Flask?** It is small, explicit, and well suited to a focused REST API.
2. **Why parameterized queries?** They separate data from SQL and prevent injection.
3. **Why validate on both sides?** Client validation improves UX; server validation is the security boundary.
4. **How does drag-and-drop persist?** The drop handler sends a PATCH request for the task status.
5. **How is XSS reduced?** User text is escaped before it is inserted into task-card markup.
6. **What does the health endpoint prove?** That the Flask process and route are responding; it is not a database health check.
7. **Why use environment variables?** Secrets and deployment-specific values stay out of source control.
8. **How are database connections closed?** The context manager closes each connection in a `finally` block.
9. **What happens for a missing task?** The API returns a JSON 404 response.
10. **How are errors presented?** The frontend shows an alert and the API returns a consistent error object.
11. **How does filtering work?** Query parameters become validated SQL clauses with bound values.
12. **Why is the status select important?** It provides a non-drag accessible alternative.
13. **How would you add authentication?** Add identity-bearing sessions/tokens and enforce ownership in every query.
14. **How would you deploy it?** Managed MySQL plus a Python host, environment secrets, CORS origin, and Gunicorn.
15. **What would you improve next?** User accounts, pagination, optimistic UI updates, and integration/browser tests.
