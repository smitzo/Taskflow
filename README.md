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
- SQLAlchemy models for users, workspaces, workspace members, tasks, attachments, comments, and refresh tokens
- Alembic migration for the database schema
- Health endpoints for app, database, and Redis checks
- Docker Compose setup for FastAPI, PostgreSQL, and Redis
- Simple React dashboard for registration, login, token refresh, and profile loading

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

## API Endpoints

Authentication:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`

System:

- `GET /health`
- `GET /api/v1/health`

## Configuration

Copy `backend/.env.example` to `backend/.env` and update values as needed:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS`

## Notes

- Keep secrets in environment variables, not source code.
- Use `understanding.md` as the explanation guide for architecture, security choices, and implementation details.

