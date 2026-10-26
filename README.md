# TaskFlow

TaskFlow is a portfolio-ready team task management system built with Flask, MySQL, Bootstrap 5, and vanilla JavaScript. It demonstrates semantic HTML, responsive CSS, DOM updates, Fetch API integration, REST design, parameterized SQL, validation, and automated testing.

## Features

- Dashboard counts and completion progress
- MySQL-backed task creation, editing, deletion, and status changes
- To do, In progress, and Completed Kanban columns
- Native drag-and-drop status persistence plus an accessible status select
- Search by title, status/priority filters, and sorting
- Required-field, length, enum, and date validation on the client and server
- Loading/error/success feedback and destructive-action confirmation

## Stack and architecture

The Flask application serves the static frontend and exposes `/api` JSON endpoints. Browser events call the API with `fetch`; route handlers validate payloads and use `mysql-connector-python` parameterized queries. MySQL stores task data and timestamps.

```text
app.py                 Flask factory and static entry point
config.py              Environment-backed configuration
backend/db.py          Connection lifecycle
backend/routes/tasks.py REST task and health endpoints
frontend/              HTML, CSS, Bootstrap, and vanilla JS
schema.sql             Database/table creation and development seed
tests/                 Pytest API validation tests
```

## Windows local setup

Prerequisites: Python 3.11+, MySQL Server 8+, and Git.

1. Create a database/user, then run `schema.sql` in MySQL Workbench or the MySQL client.
2. Create and activate a virtual environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the local MySQL credentials. Never commit `.env`.
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

## Testing

Run `python -m pytest -q`. The test suite verifies the health endpoint, validation, missing IDs, and invalid status handling without touching production data. Full persistence tests require a configured MySQL instance; the local environment used to build this project did not have the MySQL CLI installed.

## Deployment

Deploy the Flask service to a Python host such as Render, Railway, or Fly.io and provision a managed MySQL database. Set every `.env.example` variable in the host's secret environment configuration, use `gunicorn --bind 0.0.0.0:$PORT app:app` as the start command, and set `FRONTEND_ORIGIN` to the actual frontend origin. For a separate static frontend, change its API base URL from the same-origin `/api` path to the deployed API URL and configure CORS accordingly. Do not put database credentials in frontend code.

No hosting account, production database, GitHub remote, or public URL has been configured in this workspace. Those steps require account access and explicit authorization.

## Known limitations

Authentication and per-user task ownership are intentionally not included in this interview project. The current API is suitable for a single-team demo; add authentication and authorization before exposing it to untrusted users.

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
