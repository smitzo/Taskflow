# TaskFlow

TaskFlow is a multi-tenant team task management API built with FastAPI. It provides authentication, workspace membership, task management, file attachments, comments, and supporting infrastructure for PostgreSQL and Redis.

## Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Redis
- Pydantic Settings
- python-jose for JWT access tokens
- passlib with bcrypt for password hashing
- pytest and FastAPI TestClient
- React + Vite for the demo dashboard

## Project Structure

```text
backend/
  app/
    api/v1/routes/      # HTTP routes
    core/               # config, auth helpers, shared dependencies
    db/                 # SQLAlchemy base and session setup
    models/             # SQLAlchemy models
    repositories/       # database queries
    schemas/            # Pydantic request/response schemas
    services/           # business logic
  alembic/              # database migrations
  tests/                # pytest tests
frontend/
  src/                  # simple React dashboard
understanding.md        # detailed interview explanation guide
```

## Implemented Features

- User registration with bcrypt password hashing
- Login with JWT access token and opaque refresh token
- Refresh-token rotation with hashed refresh tokens stored in the database
- Protected current-user profile endpoint
- Workspace creation, listing, details, owner-only update, member invite, and member removal
- Workspace-level access control to prevent IDOR
- Task creation, listing with filters, details, update, status workflow, and soft delete
- Task assignment validation against workspace membership
- Email notification hooks for workspace invitations and task assignment
- Local file upload/download for task attachments
- Task comments with paginated listing
- Redis-backed caching for workspace details and task summaries with safe fallback when Redis is disabled or unavailable
- Task summary endpoint with status and priority counts
- Expanded tests for auth, RBAC, IDOR, pagination, soft delete, file upload/download, comments, and caching behavior
- Alembic migration for the database schema
- Health endpoints for app, database, and Redis checks
- Docker Compose setup for FastAPI, PostgreSQL, and Redis
- Simple React dashboard for registration, login, token refresh, and profile loading
- Full-stack dashboard for workspaces, members, task filters, task workflow, comments, and attachments

## Run With Docker Compose

From `backend/`:

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Versioned health check: `http://localhost:8000/api/v1/health`

The app container runs `alembic upgrade head` before starting Uvicorn.

## Run Backend Locally

From `backend/`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn main:app --reload
```

Make sure `DATABASE_URL` in `.env` points to a running PostgreSQL database.

## Run Tests

From `backend/`:

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use a separate in-memory SQLite database for fast local feedback.

## Run Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. Set `VITE_API_BASE_URL` in `frontend/.env` if your API is not running at `http://localhost:8000/api/v1`.

The frontend demonstrates:

- Register and login
- Create and switch workspaces
- Invite and remove workspace members
- Create tasks with priority, assignee, description, and deadline
- Filter tasks by status, priority, and assignee
- Move tasks through the workflow
- Soft-delete tasks
- View task summaries
- Add comments
- Upload and download attachments

## Configuration

Copy `backend/.env.example` to `backend/.env` and update values as needed:

- `DATABASE_URL`
- `REDIS_URL`
- `CACHE_ENABLED`
- `CACHE_TTL_SECONDS`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS`
- `UPLOAD_DIR`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

If SMTP settings are empty, email notifications are safely skipped and logged to the console. This keeps local setup simple while leaving the integration point ready for Mailtrap, SES, or SendGrid.

## API Endpoints

Authentication:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`

Workspaces:

- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspace_id}`
- `PATCH /api/v1/workspaces/{workspace_id}`
- `POST /api/v1/workspaces/{workspace_id}/members`
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`

Tasks:

- `POST /api/v1/workspaces/{workspace_id}/tasks`
- `GET /api/v1/workspaces/{workspace_id}/tasks`
- `GET /api/v1/workspaces/{workspace_id}/tasks/summary`
- `GET /api/v1/tasks/{task_id}`
- `PATCH /api/v1/tasks/{task_id}`
- `PATCH /api/v1/tasks/{task_id}/status`
- `DELETE /api/v1/tasks/{task_id}`

Attachments and comments:

- `POST /api/v1/tasks/{task_id}/attachments`
- `GET /api/v1/attachments/{attachment_id}`
- `POST /api/v1/tasks/{task_id}/comments`
- `GET /api/v1/tasks/{task_id}/comments`

System:

- `GET /health`
- `GET /api/v1/health`

## Notes

- Keep secrets in environment variables, not source code.
- Caching can be disabled with `CACHE_ENABLED=false`, which is useful for tests or local development without Redis.
- Workspace invites currently add an already-registered user by email. A full invitation acceptance flow can be added later with pending invitation tokens.
- Files are stored on local disk under `UPLOAD_DIR`. Production deployments should use durable object storage such as S3.
- Use `understanding.md` as the explanation guide for architecture, security choices, and implementation details.

## Design Decisions And Tradeoffs

- Route handlers stay thin and delegate business logic to services.
- Repositories own database query details so access-control queries are centralized and testable.
- Workspace membership is checked before returning workspace, task, attachment, or comment data.
- Access tokens are short-lived JWTs; refresh tokens are opaque, rotated, and stored only as hashes.
- Redis cache is used for workspace details and task summaries, but the API falls back to the database if Redis is unavailable.
- Email notifications are synchronous for simplicity. In production, this should move to background jobs.
- The React frontend stores tokens in `localStorage` because it is a demo dashboard. A production browser app should use a stronger token storage strategy such as HttpOnly cookies.

## Known Limitations

- Inviting an email requires the user to already have an account.
- Local file storage is suitable for this project, but production should use object storage.
- Docker Compose is provided, but CI/CD pipeline automation is not included.
- PostgreSQL is the target database; tests use SQLite for fast local isolation.
