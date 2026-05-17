# TaskFlow Day 1 Understanding Guide

This file is written as an interview explanation guide. The goal is not only to know what the code does, but to explain why each piece exists, where it lives, and what tradeoffs were made.

## 1. What Day 1 Implements

Day 1 from `task.txt` asks for project setup, database models, authentication, Alembic migration, Docker Compose, and register/login/me endpoints. In this codebase, Day 1 delivers:

- Layered FastAPI backend structure under `backend/app/`
- SQLAlchemy models for users, refresh tokens, workspaces, members, tasks, attachments, and comments
- Alembic migration that creates the Day 1 database schema
- JWT access-token authentication
- Opaque refresh-token rotation
- Bcrypt password hashing
- Protected `/me` endpoint
- Health endpoints
- Docker Compose for app, PostgreSQL, and Redis
- A simple React dashboard under `frontend/`
- Focused auth tests under `backend/tests/`

The implemented auth endpoints are in `backend/app/api/v1/routes/auth.py`.

## 2. Layered Architecture

Layered architecture means each part of the backend has one clear responsibility. This makes the code easier to test, extend, and review.

The layers are:

- API routes: `backend/app/api/v1/routes/`
- Services: `backend/app/services/`
- Repositories: `backend/app/repositories/`
- Models: `backend/app/models/`
- Schemas: `backend/app/schemas/`
- Core utilities: `backend/app/core/`
- Database setup: `backend/app/db/`

How it works in our code:

- `backend/app/api/v1/routes/auth.py` receives HTTP requests and returns responses.
- It delegates business logic to `AuthService` in `backend/app/services/auth_service.py`.
- `AuthService` uses `UserRepository` and `TokenRepository` from `backend/app/repositories/`.
- Repositories query SQLAlchemy models from `backend/app/models/`.
- Request and response shapes are defined with Pydantic schemas in `backend/app/schemas/`.

Why this matters in an interview:

If all logic is placed directly inside route handlers, the code becomes hard to test and hard to change. With this structure, a route remains thin, service logic can be tested separately, and database queries are isolated.

Tradeoff:

For a very small app, this structure creates more files than a single `main.py`. For a take-home backend with six modules, the extra structure is worth it because Day 2 and Day 3 features can be added without turning route files into large scripts.

## 3. FastAPI App Initialization

Location:

- `backend/app/main.py`
- `backend/main.py`

`backend/app/main.py` defines `create_app()`. This function creates the FastAPI app, configures CORS, includes the API router, and defines the root `/health` route.

`backend/main.py` only imports the app:

```python
from app.main import app
```

This keeps Uvicorn simple:

```bash
uvicorn main:app --reload
```

Concept:

An app factory makes startup configuration explicit. It is useful when tests need to create or configure an app in a controlled way.

How CORS is implemented:

`backend/app/main.py` uses `CORSMiddleware`. Allowed origins come from `settings.cors_origins`, which is defined in `backend/app/core/config.py`.

Why CORS matters:

The React frontend runs on `localhost:5173` and the API runs on `localhost:8000`. Browsers block cross-origin requests unless the backend explicitly allows them.

## 4. Configuration With Environment Variables

Location:

- `backend/app/core/config.py`
- `backend/.env.example`

The `Settings` class uses `pydantic-settings`. It reads values from environment variables and `.env`.

Important settings:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS`

Why this matters:

Secrets and environment-specific values should not be hardcoded. The same code should run locally, in Docker, in CI, and in production by changing environment variables.

Implementation detail:

`cors_origins` accepts comma-separated text from `.env`, then `parse_cors_origins()` turns it into a Python list.

Tradeoff:

The default `JWT_SECRET_KEY` is only a development fallback. Real deployments must override it. This is documented in `.env.example`.

## 5. Database Setup

Locations:

- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/app/models/`

`backend/app/db/base.py` defines the SQLAlchemy `Base` class. Every model inherits from it, so SQLAlchemy can collect all table metadata.

`backend/app/db/session.py` creates:

- `engine`: database connection factory
- `SessionLocal`: per-request database session factory

The `build_engine()` function adds SQLite-specific `check_same_thread=False` only when the URL starts with `sqlite`. This keeps tests simple while production still uses PostgreSQL.

Concept:

A SQLAlchemy `Session` is a unit of work. It tracks objects, sends SQL to the database, and commits or rolls back changes.

Where sessions are injected:

- `backend/app/core/dependencies.py`

`get_db()` creates a session, yields it to the route, and closes it afterward.

## 6. Database Models

Locations:

- `backend/app/models/user.py`
- `backend/app/models/refresh_token.py`
- `backend/app/models/workspace.py`
- `backend/app/models/workspace_member.py`
- `backend/app/models/task.py`
- `backend/app/models/attachment.py`
- `backend/app/models/comment.py`
- `backend/app/models/mixins.py`

### User Model

Location: `backend/app/models/user.py`

Fields:

- `id`: UUID string primary key
- `email`: unique indexed email
- `full_name`: display name
- `hashed_password`: bcrypt hash
- `is_active`: account status
- `created_at`, `updated_at`: inherited from `TimestampMixin`

Why `hashed_password` exists:

We never store plain passwords. The register endpoint receives a password, hashes it, and only stores the hash.

### RefreshToken Model

Location: `backend/app/models/refresh_token.py`

Fields:

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `revoked_at`

Why refresh tokens are stored:

Access tokens are short-lived JWTs. Refresh tokens allow the client to get a new access token without logging in again. Storing refresh tokens gives us server-side control: we can revoke them, expire them, and rotate them.

Why we store `token_hash` instead of the raw refresh token:

If the database leaks, raw refresh tokens would be immediately usable. Hashing them means the database stores only a fingerprint.

### Workspace And WorkspaceMember Models

Locations:

- `backend/app/models/workspace.py`
- `backend/app/models/workspace_member.py`

These are included on Day 1 to prepare the database for Day 2.

Important idea:

Multi-tenancy is modeled through workspaces. A user can belong to many workspaces, and a workspace can have many users. That many-to-many relationship is represented by `workspace_members`.

`WorkspaceRole` supports:

- `owner`
- `member`

This is the foundation for owner-only actions and role enforcement later.

### Task Model

Location: `backend/app/models/task.py`

Tasks belong to a workspace and can be assigned to a user. The model includes:

- `status`: `todo`, `in_progress`, `review`, `done`
- `priority`: `low`, `medium`, `high`, `critical`
- `deadline`
- `is_deleted`

Why `is_deleted` exists:

The task asks for soft delete. Soft delete means we mark a row as deleted instead of removing it from the database. This preserves auditability and prevents accidental data loss.

### Attachment And Comment Models

Locations:

- `backend/app/models/attachment.py`
- `backend/app/models/comment.py`

These prepare for Day 2 modules. Attachments store file metadata, not file bytes. Comments belong to tasks and track the author.

## 7. Alembic Migrations

Locations:

- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/20260516_0001_day1_foundation.py`

Concept:

Alembic migrations version-control database schema changes. Instead of relying on `Base.metadata.create_all()` in production, we apply explicit migrations.

How our migration works:

`20260516_0001_day1_foundation.py` creates:

- `users`
- `refresh_tokens`
- `workspaces`
- `workspace_members`
- `tasks`
- `attachments`
- `comments`

It also creates indexes and foreign keys.

Important production point:

The Dockerfile starts the app with:

```bash
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000
```

That means the schema is upgraded before the API starts.

Tradeoff:

Running migrations during app startup is convenient for a take-home project. In a larger production system, migrations are often run as a separate release step so failures do not happen inside application boot.

## 8. Pydantic Schemas

Locations:

- `backend/app/schemas/user.py`
- `backend/app/schemas/auth.py`

Concept:

Pydantic schemas define the shape of incoming requests and outgoing responses.

Examples:

- `UserCreate`: register request body
- `UserRead`: safe user response
- `LoginRequest`: login request body
- `RefreshTokenRequest`: refresh request body
- `TokenPair`: token response

Why schemas matter:

The database model has `hashed_password`, but the response schema does not. This prevents accidentally returning sensitive data.

Implementation detail:

`UserRead` uses `ConfigDict(from_attributes=True)`, which lets Pydantic create a response from a SQLAlchemy `User` object.

## 9. Password Hashing With Bcrypt

Location:

- `backend/app/core/security.py`

Functions:

- `hash_password()`
- `verify_password()`

Concept:

Passwords must be hashed, not encrypted and not stored in plain text. Hashing is one-way. Bcrypt is intentionally slow, which makes brute-force attacks more expensive.

How registration uses it:

`AuthService.register()` in `backend/app/services/auth_service.py` calls:

```python
hash_password(payload.password)
```

The resulting hash is stored in `users.hashed_password`.

How login uses it:

`AuthService.login()` loads the user by email, then calls:

```python
verify_password(password, user.hashed_password)
```

Tradeoff:

Bcrypt is widely supported and required by the task. Alternatives like Argon2 are also strong, but bcrypt keeps the implementation aligned with the assignment.

## 10. Access Tokens With JWT

Location:

- `backend/app/core/security.py`

Functions:

- `create_access_token()`
- `decode_access_token()`

Concept:

A JWT is a signed token containing claims. Our access token contains:

- `sub`: user ID
- `type`: `access`
- `iat`: issued-at timestamp
- `exp`: expiration timestamp

Why access tokens are short-lived:

If an access token leaks, it is usable until it expires. Short expiration limits damage.

How `/me` uses JWT:

`get_current_user()` in `backend/app/core/dependencies.py`:

1. Reads the bearer token from the `Authorization` header.
2. Decodes and validates it with `decode_access_token()`.
3. Loads the user from the database.
4. Rejects invalid, missing, or inactive users with `401`.

Tradeoff:

JWT access tokens are stateless, so they are fast to validate. The tradeoff is that revoking a JWT before expiration is harder unless we add token denylisting or very short lifetimes.

## 11. Refresh Token Rotation

Locations:

- `backend/app/core/security.py`
- `backend/app/models/refresh_token.py`
- `backend/app/repositories/token_repository.py`
- `backend/app/services/auth_service.py`

Concept:

Refresh token rotation means each refresh request invalidates the old refresh token and returns a new one.

Flow:

1. User logs in.
2. API returns an access token and a refresh token.
3. The refresh token is hashed and stored in the database.
4. Client sends refresh token to `/api/v1/auth/refresh`.
5. API hashes the submitted token and searches for an active matching token.
6. If valid, old token is revoked.
7. A new access token and refresh token are issued.

Why this is safer:

If someone steals an old refresh token after it has been used, it will no longer work.

Tradeoff:

Refresh token rotation requires database state. This adds a query to the refresh flow, but it gives stronger control than completely stateless refresh JWTs.

## 12. API Routes

Location:

- `backend/app/api/v1/routes/auth.py`

Endpoints:

`POST /api/v1/auth/register`

- Accepts `UserCreate`
- Creates a user
- Returns `UserRead`

`POST /api/v1/auth/login`

- Accepts `LoginRequest`
- Verifies email and password
- Returns `TokenPair`

`POST /api/v1/auth/refresh`

- Accepts `RefreshTokenRequest`
- Rotates refresh token
- Returns a new `TokenPair`

`GET /api/v1/auth/me`

- Requires bearer access token
- Returns the current user profile

Why routes stay thin:

The route functions mostly call `AuthService`. Business logic belongs in the service layer so future changes do not make the HTTP layer messy.

## 13. Authentication Dependency

Location:

- `backend/app/core/dependencies.py`

`OAuth2PasswordBearer` extracts the bearer token from the request header:

```text
Authorization: Bearer <access_token>
```

Then `get_current_user()` validates the token and returns the user.

Why dependency injection matters:

FastAPI dependencies let us reuse authentication across protected endpoints. Day 2 workspace and task routes can depend on `get_current_user()` without duplicating token parsing.

Security point:

Authentication only answers "who are you?" Authorization answers "are you allowed to access this resource?" Day 2 must add workspace membership checks to prevent IDOR.

## 14. IDOR Prevention Foundation

Concept:

IDOR means Insecure Direct Object Reference. It happens when a user can access another user's resource just by guessing or changing an ID in the URL.

What Day 1 does:

- Uses authentication for protected endpoints.
- Uses UUID string IDs, which are harder to enumerate than integers.
- Creates workspace membership and role tables for authorization checks.

What Day 2 must do:

Every workspace/task/comment/file query must verify that the current user is a member of the relevant workspace before returning data.

How to explain this honestly:

Day 1 implements authentication and prepares the authorization model. Full IDOR prevention becomes testable once workspace and task endpoints exist.

## 15. Health Checks

Locations:

- `backend/app/main.py`
- `backend/app/api/v1/routes/health.py`

Endpoints:

- `/health`
- `/api/v1/health`

`/health` returns a simple status for container and load balancer checks.

`/api/v1/health` checks:

- Database with `SELECT 1`
- Redis with `PING` when the Redis client is available

Tradeoff:

The versioned health endpoint reports Redis as unavailable if it cannot connect, but the overall service is degraded only when the database fails. For Day 1, the database is essential; Redis becomes more important once caching is implemented.

## 16. Docker Compose

Location:

- `backend/docker-compose.yml`
- `backend/Dockerfile`

Services:

- `app`: FastAPI backend
- `postgres`: PostgreSQL 16
- `redis`: Redis 7

Why Docker Compose matters:

It gives reviewers a predictable way to start the project without manually installing PostgreSQL and Redis.

Implementation details:

- Postgres has a healthcheck using `pg_isready`.
- The app waits for Postgres to become healthy.
- The app loads variables from `.env`.
- The app runs migrations before Uvicorn starts.

## 17. Tests

Locations:

- `backend/tests/conftest.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_workspaces_tasks.py`

What tests cover:

- Registration success
- Login success
- `/me` with access token
- Refresh token rotation
- Duplicate email failure
- Wrong password failure
- Missing token failure
- Workspace creation and member invitations
- Owner-only workspace update enforcement
- Task creation and status workflow validation
- Task comments and file attachment upload/download
- IDOR prevention for workspace and task reads

How test database works:

`conftest.py` sets `DATABASE_URL` to an in-memory SQLite database and overrides FastAPI's `get_db()` dependency. This keeps tests isolated and fast.

Tradeoff:

SQLite is fast but not identical to PostgreSQL. For Day 3, add integration tests against the Docker Postgres service to catch database-specific issues.

## 18. React Frontend

Locations:

- `frontend/package.json`
- `frontend/index.html`
- `frontend/src/main.jsx`
- `frontend/src/styles.css`

What it demonstrates:

- Register
- Login
- Store token pair locally for the demo
- Call protected `/auth/me`
- Refresh tokens
- Sign out locally

Why it is intentionally simple:

The assignment says frontend polish is not the focus. This dashboard proves the backend auth flow works end-to-end without distracting from backend evaluation.

Tradeoff:

Tokens are stored in `localStorage` for speed and simplicity. In production, token storage needs a stronger browser security design, often involving HttpOnly cookies.

## 19. Day 2 Backend Features

Day 2 adds the core product behavior on top of the Day 1 auth foundation.

Main locations:

- Workspace routes: `backend/app/api/v1/routes/workspaces.py`
- Task, attachment, and comment routes: `backend/app/api/v1/routes/tasks.py`
- Workspace business logic: `backend/app/services/workspace_service.py`
- Task business logic: `backend/app/services/task_service.py`
- Email integration boundary: `backend/app/services/email_service.py`
- Workspace queries: `backend/app/repositories/workspace_repository.py`
- Task queries: `backend/app/repositories/task_repository.py`
- Workspace schemas: `backend/app/schemas/workspace.py`
- Task/comment/attachment schemas: `backend/app/schemas/task.py`
- Pagination schema: `backend/app/schemas/common.py`

### Workspace API

Implemented endpoints:

- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspace_id}`
- `PATCH /api/v1/workspaces/{workspace_id}`
- `POST /api/v1/workspaces/{workspace_id}/members`
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`

Concept:

A workspace is the tenant boundary. Users do not get global access to all records. They only see workspaces where they have a row in `workspace_members`.

Implementation:

`WorkspaceService.create()` creates the workspace and also creates an owner membership for the creator. This is important because authorization later depends on membership rows, not only `created_by_id`.

Owner-only behavior:

`WorkspaceService._require_owner()` loads both the workspace and the current user's membership. If there is no membership, it returns `404`. If the user is a member but not owner, it returns `403`.

Why `404` for non-members:

Returning `404` prevents IDOR information leaks. An outsider should not be able to learn whether a workspace ID exists.

Invite behavior:

`WorkspaceService.invite_member()` accepts an email, finds an existing registered user, creates a `workspace_members` row, and sends a notification through `EmailService`.

Tradeoff:

The current implementation invites already-registered users. A fuller production system would add a `workspace_invitations` table with pending invitation tokens so non-registered emails can accept later.

### Task API

Implemented endpoints:

- `POST /api/v1/workspaces/{workspace_id}/tasks`
- `GET /api/v1/workspaces/{workspace_id}/tasks`
- `GET /api/v1/tasks/{task_id}`
- `PATCH /api/v1/tasks/{task_id}`
- `PATCH /api/v1/tasks/{task_id}/status`
- `DELETE /api/v1/tasks/{task_id}`

Concept:

Tasks belong to workspaces, so every task action first proves the current user is a member of the task's workspace.

Implementation:

`TaskService._require_workspace_member()` protects workspace-scoped task creation and listing.

`TaskService._require_task_access()` protects task-by-ID actions by using `TaskRepository.get_accessible_by_id()`. That repository query joins `tasks` to `workspace_members`, so a user can only load a task if they belong to the task's workspace.

This is the main IDOR prevention pattern for task endpoints.

Task assignment:

When creating or updating a task, `TaskService._validate_assignee()` checks two things:

- the assignee user exists
- the assignee is a member of the same workspace

This prevents assigning tasks to random users outside the tenant.

Status workflow:

`TaskService.allowed_transitions` defines the allowed workflow:

```text
todo -> in_progress -> review -> done
```

The status endpoint rejects skipped transitions, such as `todo -> done`, with `400`.

Soft delete:

`TaskService.soft_delete()` sets `is_deleted = True`. Queries exclude deleted tasks by default. This keeps data available for future audit/history work.

### Pagination And Filtering

Location:

- `backend/app/schemas/common.py`
- `backend/app/repositories/task_repository.py`

Task listing supports:

- `status`
- `priority`
- `assignee_id`
- `page`
- `size`

`PaginatedResponse` returns:

- `items`
- `page`
- `size`
- `total`

Tradeoff:

Offset pagination is simple and works well for a take-home project. For very large datasets, cursor pagination is usually better because it avoids deep offset scans.

### File Attachments

Implemented endpoints:

- `POST /api/v1/tasks/{task_id}/attachments`
- `GET /api/v1/attachments/{attachment_id}`

Concept:

The database stores file metadata. The file bytes are stored on disk under `UPLOAD_DIR`.

Implementation:

`TaskService.attach_file()`:

1. Verifies task access.
2. Creates the upload directory if needed.
3. Saves the uploaded file with a UUID-based stored filename.
4. Stores metadata in the `attachments` table.

`TaskService.get_attachment_file()` verifies that the current user has access to the attachment through the task's workspace before returning the file.

Tradeoff:

Local disk storage is simple for a take-home project. Production should use durable object storage like S3, MinIO, or GCS.

### Comments

Implemented endpoints:

- `POST /api/v1/tasks/{task_id}/comments`
- `GET /api/v1/tasks/{task_id}/comments`

Concept:

Comments belong to tasks. Since tasks belong to workspaces, comment access is protected by task access.

Implementation:

`TaskService.add_comment()` and `TaskService.list_comments()` both call `_require_task_access()` first. This means outsiders cannot comment on or read comments for tasks outside their workspace.

### Email Notifications

Location:

- `backend/app/services/email_service.py`
- `backend/app/core/config.py`

Email is used for:

- workspace invitation notifications
- task assignment notifications

If SMTP is not configured, `EmailService` logs a skipped email message and returns. This makes local setup easy.

If SMTP is configured, it sends email through Python's `smtplib` using:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

Tradeoff:

Synchronous email is simple and explicit. In production, sending should move to a background job queue so user requests do not wait on SMTP latency.

## 20. Day 3 Implementation Plan

Day 3 should add:

- Redis caching for workspace details or task summaries
- More PostgreSQL-backed integration tests
- Broader pagination/filtering tests
- More README polish around submission
- Optional rate limiting or activity logs

## 21. How To Explain The Request Lifecycle

Example: Login

1. The browser submits email and password to `POST /api/v1/auth/login`.
2. `backend/app/api/v1/routes/auth.py` receives the request.
3. The route calls `AuthService.login()`.
4. `AuthService` asks `UserRepository` to load the user by email.
5. `verify_password()` checks the submitted password against the bcrypt hash.
6. `create_access_token()` creates a signed JWT.
7. `create_refresh_token()` creates a random refresh token.
8. `TokenRepository.create()` stores only the hash of the refresh token.
9. The service commits the database transaction.
10. The API returns the token pair to the client.

Example: Protected `/me`

1. The client sends `Authorization: Bearer <token>`.
2. FastAPI dependency `get_current_user()` extracts the token.
3. `decode_access_token()` validates signature, expiry, and token type.
4. `UserRepository.get_by_id()` loads the current user.
5. The route returns `UserRead`, which excludes sensitive fields.

Example: Workspace Details With IDOR Prevention

1. The client calls `GET /api/v1/workspaces/{workspace_id}` with a bearer token.
2. `get_current_user()` authenticates the user.
3. `WorkspaceService.get_detail()` calls `WorkspaceRepository.get_detail_for_user()`.
4. The repository query joins `workspaces` with `workspace_members`.
5. If the user is not a member, no row is returned.
6. The API returns `404` instead of leaking whether the workspace exists.

Example: Task Assignment

1. A workspace member calls `POST /api/v1/workspaces/{workspace_id}/tasks`.
2. `TaskService.create()` verifies the creator is a workspace member.
3. If `assignee_id` is provided, `_validate_assignee()` verifies the assignee belongs to the same workspace.
4. The task is created.
5. `EmailService` sends or logs an assignment notification.

## 22. Key Interview Talking Points

- I separated route handlers, business logic, and database queries so the code is easier to test and extend.
- I used bcrypt for passwords because passwords need slow one-way hashing.
- I used JWTs only for short-lived access tokens.
- I used opaque refresh tokens stored as hashes so refresh tokens can be revoked and rotated.
- I used environment variables for configuration so secrets are not hardcoded.
- I added Alembic migrations instead of relying on automatic table creation in production.
- I prepared multi-tenant models early so Day 2 authorization can be built around workspace membership.
- I enforce workspace membership before returning workspace, task, attachment, or comment data.
- I return `404` for resources outside a user's workspace to avoid IDOR information leaks.
- I validate task assignees against workspace membership.
- I kept the frontend simple because the backend is the evaluation focus.
