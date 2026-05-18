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
- `CACHE_ENABLED`
- `CACHE_TTL_SECONDS`
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
- Task filtering, pagination, summaries, and soft delete behavior
- Task comments and file attachment upload/download
- IDOR prevention for workspace and task reads
- Membership removal revoking later access
- Cache behavior for workspace details and task summaries

How test database works:

`conftest.py` sets `DATABASE_URL` to an in-memory SQLite database and overrides FastAPI's `get_db()` dependency. This keeps tests isolated and fast.

Tradeoff:

SQLite is fast but not identical to PostgreSQL. This suite gives quick local feedback, while a larger production pipeline should also run Docker-backed PostgreSQL integration tests.

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

## 19. Full-Stack React Dashboard

The frontend is intentionally simple, but it now exercises the backend end to end.

Main locations:

- App code: `frontend/src/main.jsx`
- Styling: `frontend/src/styles.css`
- Vite entry: `frontend/index.html`
- Frontend dependencies: `frontend/package.json`
- API base config: `frontend/.env.example`

### Frontend State Model

The React app keeps state for:

- auth tokens
- current user profile
- workspace list
- selected workspace
- workspace details and members
- task page and filters
- task summary counts
- selected task details
- comments
- upload file
- form fields
- loading and status messages

Why this matters:

The frontend mirrors the backend product model. A workspace is selected first, then tasks, members, comments, and attachments are loaded within that workspace boundary.

### API Client Pattern

The `request()` helper in `frontend/src/main.jsx` centralizes API calls.

It does three useful things:

- prefixes every path with `VITE_API_BASE_URL`
- adds the bearer token when logged in
- handles both JSON responses and file downloads

For file uploads, it detects `FormData` and does not set `Content-Type` manually. This lets the browser set the correct multipart boundary.

### Auth Flow

Frontend flow:

1. User registers or logs in.
2. The frontend stores the token pair in `localStorage`.
3. Once logged in, `bootstrapSession()` loads `/auth/me` and `/workspaces`.
4. The app shows the dashboard only after authentication.

Tradeoff:

`localStorage` is acceptable for a take-home demo, but production apps should consider HttpOnly cookies to reduce exposure to XSS token theft.

### Workspace Flow

The dashboard supports:

- create workspace
- switch workspace
- load workspace members
- invite a member by email
- remove non-owner members

Implementation detail:

When a workspace changes, `loadWorkspaceBundle()` fetches workspace details, tasks, and task summary together. That keeps the UI synchronized with the selected workspace.

### Task Flow

The dashboard supports:

- create task
- assign task to a workspace member
- filter tasks by status, priority, and assignee
- advance status through the backend workflow
- soft-delete tasks
- inspect a task's detail view

The frontend only offers an advance-status button. The backend still enforces the real workflow, so even if a user manipulates requests manually, invalid transitions are rejected.

### Comments And Attachments

The selected task panel supports:

- adding comments
- uploading a file
- downloading attachments

For downloads, the frontend receives a blob from the API, creates a temporary object URL, clicks an anchor element, and then revokes the object URL.

### Frontend Styling

The UI is designed as a compact operational dashboard:

- sidebar for auth/session/workspace selection
- main area for workspace summary, members, task creation, task list, and task detail
- restrained colors and compact controls
- no marketing page or hero screen

This matches the project goal: demonstrate backend functionality clearly without distracting from backend review.

## 20. Day 2 Backend Features

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

## 21. Day 3 Backend Quality And Caching

Day 3 adds backend polish around caching, test coverage, and API completeness.

Main locations:

- Cache service: `backend/app/services/cache_service.py`
- Cache configuration: `backend/app/core/config.py`
- Workspace cache usage: `backend/app/services/workspace_service.py`
- Task summary cache usage: `backend/app/services/task_service.py`
- Task summary query: `backend/app/repositories/task_repository.py`
- Task summary schema: `backend/app/schemas/task.py`
- Expanded tests: `backend/tests/test_workspaces_tasks.py`

### Redis Cache Service

Concept:

Redis is an in-memory data store often used as a cache. Expensive or frequently requested reads can be served from Redis instead of recomputing them from the database every time.

Implementation:

`CacheService` wraps Redis access with three important behaviors:

- `get_json()` reads JSON data from Redis.
- `set_json()` writes JSON data with a TTL.
- `delete()` and `delete_pattern()` invalidate stale keys.

The service reads:

- `REDIS_URL`
- `CACHE_ENABLED`
- `CACHE_TTL_SECONDS`

If `CACHE_ENABLED=false`, the cache service does nothing. If Redis is unavailable, cache operations fail quietly and the API continues to use the database.

Why this is production friendly:

Caching should improve performance but not become a single point of failure for normal product reads. If Redis is down, the API should still work, just without cached reads.

Tradeoff:

Silent cache fallback is good for availability, but observability should be added later. In production, cache failures should be logged through structured logging or metrics.

### Cached Workspace Details

Location:

- `backend/app/services/workspace_service.py`

Flow:

1. The user requests `GET /api/v1/workspaces/{workspace_id}`.
2. The service first checks membership with `WorkspaceRepository.get_membership()`.
3. If the user is not a member, it returns `404`.
4. If the user is a member, it checks Redis key `workspace:{workspace_id}:detail`.
5. If cached data exists, it returns that.
6. Otherwise it queries the database, serializes the detail response, stores it in Redis, and returns it.

Security detail:

Membership is checked before reading from cache. This matters because cached workspace details contain member data. Without the membership check, cache could accidentally become an authorization bypass.

Invalidation:

Workspace detail cache is invalidated when:

- workspace metadata changes
- a member is invited
- a member is removed

### Cached Task Summary

Locations:

- `backend/app/api/v1/routes/tasks.py`
- `backend/app/services/task_service.py`
- `backend/app/repositories/task_repository.py`
- `backend/app/schemas/task.py`

Endpoint:

`GET /api/v1/workspaces/{workspace_id}/tasks/summary`

Response includes:

- total active tasks
- count by status
- count by priority

Implementation:

`TaskRepository.summarize_workspace()` groups tasks by status and priority while excluding soft-deleted tasks.

`TaskService.summarize_workspace()` checks membership, then reads/writes Redis key `workspace:{workspace_id}:task_summary`.

Invalidation:

Task summary cache is invalidated when:

- a task is created
- a task is updated
- task status changes
- a task is soft-deleted

Tradeoff:

The summary cache uses simple key invalidation. This is easy to reason about. For very high write volume, more advanced strategies such as event-driven invalidation or write-through counters might be considered.

### Pagination And Filtering Tests

Location:

- `backend/tests/test_workspaces_tasks.py`

The tests verify:

- priority filtering
- page and size parameters
- total count
- soft-deleted tasks disappearing from details and summaries

Why this matters:

Pagination bugs are common in real APIs. The test makes sure the response shape includes both `items` and `total`, so a frontend can build reliable paginated views.

### RBAC And IDOR Test Coverage

The test suite now verifies:

- non-owners cannot update workspaces
- outsiders cannot read another workspace
- outsiders cannot read another task
- removed members lose later workspace and task access

This directly supports the security requirements from the assignment.

### PATCH Semantics For Nullable Fields

Location:

- `backend/app/services/task_service.py`
- `backend/app/services/workspace_service.py`

Concept:

In PATCH requests, omitted fields and explicit `null` should mean different things:

- omitted field: leave existing value unchanged
- explicit `null`: clear the nullable value

Implementation:

The services use Pydantic v2's `model_fields_set` to detect whether a field was actually sent.

Example:

```json
{
  "assignee_id": null,
  "description": null
}
```

This clears the task assignee and description. If those keys are omitted, the existing values remain unchanged.

Why this matters:

Without this distinction, clients cannot clear fields like assignee, deadline, or description through the API.

## 22. Bonus Features Added In The Final Full-Stack Pass

These are optional features from `task.txt` that were added after the core backend was complete. They are useful to mention in the interview because they show the project was treated like a real product, not only a list of endpoints.

### Rich Demo Data And Demo Cleanup

Locations:

- `backend/app/api/v1/routes/demo.py`
- `backend/app/services/demo_service.py`
- `backend/app/schemas/demo.py`
- `frontend/src/main.jsx`
- `frontend/src/styles.css`
- `backend/tests/test_workspaces_tasks.py`

Endpoints:

- `POST /api/v1/demo/seed`
- `DELETE /api/v1/demo/seed`

Concept:

Demo data lets a reviewer log in and immediately see a useful workspace without manually creating every task, comment, and workflow state. Demo cleanup lets the same reviewer remove that generated workspace and return to a clean account.

Implementation:

`DemoService.seed_for_user()` looks for a workspace named `TaskFlow Demo` owned by the current user. If it does not exist, it creates one and makes the user the owner through the normal workspace repository path.

It then creates a richer set of sample tasks across `todo`, `in_progress`, `review`, and `done`, adds one comment per sample task, and adds activity rows for demo tasks that are already beyond `todo`.

`DemoService.clear_for_user()` finds the same demo workspace and deletes it only if the current user is the owner. Because workspace relationships use cascade delete, removing the workspace also removes demo tasks, comments, attachments metadata, members, and activity logs.

Frontend behavior:

The dashboard has two small actions:

- `Populate demo data`
- `Remove demo data`

Both buttons call the backend and then reload workspaces and task state. This proves the UI is bound to real API responses, not hardcoded local demo arrays.

Tradeoff:

The demo workspace is identified by name for simplicity. In a production SaaS product, I would prefer a separate `is_demo` flag or a metadata table so a real user cannot accidentally collide with the reserved demo workspace name.

### Default Task Deadline: 24 Hours From Now

Location:

- `frontend/src/main.jsx`

Concept:

Task creation should be fast. A default deadline reduces friction while still allowing the user to change it.

Implementation:

The frontend uses `createEmptyTaskForm()` instead of a static object. Each time the task form is initialized or reset, it calls:

```jsx
deadline: toDateTimeLocal(addHours(new Date(), 24))
```

`addHours()` creates a timestamp 24 hours in the future. `toDateTimeLocal()` formats it for the HTML `datetime-local` input.

Why it is frontend-only:

The backend still accepts `deadline` as optional. This keeps the API flexible for clients that may not want a default deadline, while the React dashboard provides a convenient default for this demo workflow.

Tradeoff:

The default uses the browser's local time. That is good for user experience, but the frontend sends the final value to the backend as ISO time so persisted data is consistent.

### Comment Author And Timestamp

Locations:

- `backend/app/models/comment.py`
- `backend/app/repositories/task_repository.py`
- `backend/app/schemas/task.py`
- `backend/app/services/task_service.py`
- `frontend/src/main.jsx`
- `frontend/src/styles.css`
- `backend/tests/test_workspaces_tasks.py`

Concept:

Comments are collaboration records. A comment without author and time is weak audit information because nobody can explain who said what or when.

Implementation:

`Comment` now has an `author` relationship to `User`.

`CommentRead` includes:

- `author_id`
- `author`
- `body`
- `created_at`

`TaskRepository.list_comments()` uses `selectinload(Comment.author)` so the API can serialize the author without an extra lazy query per comment.

The frontend renders:

- author full name
- creation timestamp via `formatDateTime()`
- comment body

Tradeoff:

The response embeds a small `UserRead` object for convenience. For very large comment feeds, a leaner response could return only `author_id` and let the frontend hydrate users from a separate member map.

### Activity Log For Task Status Changes

Locations:

- `backend/app/models/task_activity.py`
- `backend/app/models/task.py`
- `backend/app/models/__init__.py`
- `backend/alembic/versions/20260518_0002_task_activity_logs.py`
- `backend/app/repositories/task_repository.py`
- `backend/app/services/task_service.py`
- `backend/app/api/v1/routes/tasks.py`
- `backend/app/schemas/task.py`
- `frontend/src/main.jsx`
- `frontend/src/styles.css`
- `backend/tests/test_workspaces_tasks.py`

Endpoint:

`GET /api/v1/tasks/{task_id}/activity`

Concept:

The activity log is an audit trail. It answers: who moved this task, from which status, to which status, and when?

Database model:

`TaskActivityLog` stores:

- `task_id`
- `actor_id`
- `from_status`
- `to_status`
- `created_at`
- `updated_at`

`task_id` cascades on task delete because activity belongs to the task. `actor_id` uses `RESTRICT` so the database does not silently erase who performed the action.

Implementation:

`TaskService.change_status()` validates the workflow first. Only valid transitions are recorded.

Important implementation detail:

The service stores `previous_status = task.status` before assigning the new status. Then it creates the activity row with `from_status=previous_status` and `to_status=next_status`. This ordering matters because otherwise the history would incorrectly show the new status as both the old and new value.

The activity endpoint reuses `_require_task_access()`, so users can only read activity for tasks in workspaces they belong to.

Frontend behavior:

When a task is opened, `loadTask()` fetches:

- task detail
- comments
- activity history

After advancing a selected task, the frontend reloads the selected task detail so the activity list updates immediately.

Tradeoff:

The current activity log tracks status changes only. A production audit system might also track title, assignee, deadline, description, file, and comment events. I kept the scope aligned to the bonus requirement.

### Authentication Rate Limiting

Locations:

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/core/dependencies.py`
- `backend/app/api/v1/routes/auth.py`
- `backend/app/services/cache_service.py`
- `backend/app/services/rate_limit_service.py`
- `backend/tests/test_auth.py`

Protected endpoints:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`

Configuration:

- `RATE_LIMIT_ENABLED`
- `AUTH_RATE_LIMIT_MAX_REQUESTS`
- `AUTH_RATE_LIMIT_WINDOW_SECONDS`

Concept:

Auth endpoints are common brute-force targets. Rate limiting reduces repeated guesses and protects expensive password verification work.

Implementation:

`enforce_auth_rate_limit()` is a FastAPI dependency. It builds a key from:

- endpoint path
- client IP address

Then it calls `RateLimitService.check()`.

`RateLimitService` first tries Redis through `CacheService.increment()`. Redis is preferred because it is shared across app instances. If Redis is disabled or unavailable, it falls back to an in-memory counter so local development and tests still behave predictably.

If the request count exceeds the configured limit, the service raises `429 Too Many Requests`.

Tradeoff:

The in-memory fallback is useful for local runs, but it is not distributed. In production, Redis should stay enabled so all API instances share the same rate-limit counters.

## 23. How To Explain The Request Lifecycle

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

## 24. Final Requirement Checklist

Authentication:

- Registration with bcrypt password hashing: `backend/app/services/auth_service.py`
- Login with access and refresh token: `backend/app/api/v1/routes/auth.py`
- Refresh token rotation: `backend/app/services/auth_service.py`
- Protected `/me`: `backend/app/api/v1/routes/auth.py`
- Password minimum is currently 4 characters for demo usability. The frontend defaults to `1234`; production should use a stronger policy.

Demo data:

- Protected seed endpoint: `backend/app/api/v1/routes/demo.py`
- Protected cleanup endpoint: `backend/app/api/v1/routes/demo.py`
- Demo workspace/task/comment generation: `backend/app/services/demo_service.py`
- Demo workspace removal: `backend/app/services/demo_service.py`
- Frontend demo buttons: `frontend/src/main.jsx`

Workspaces:

- Create/list/details/update/invite/remove: `backend/app/api/v1/routes/workspaces.py`
- Owner-only enforcement: `backend/app/services/workspace_service.py`
- Membership checks for IDOR prevention: `backend/app/repositories/workspace_repository.py`

Tasks:

- Create/list/filter/detail/update/status/soft-delete: `backend/app/api/v1/routes/tasks.py`
- Workflow enforcement: `backend/app/services/task_service.py`
- Assignee membership validation: `backend/app/services/task_service.py`

Attachments:

- Upload/download: `backend/app/api/v1/routes/tasks.py`
- Local disk metadata and access checks: `backend/app/services/task_service.py`

Comments:

- Add/list paginated: `backend/app/api/v1/routes/tasks.py`
- Author and timestamp in API response: `backend/app/schemas/task.py` and `backend/app/repositories/task_repository.py`

Bonus:

- Task status activity log model: `backend/app/models/task_activity.py`
- Activity migration: `backend/alembic/versions/20260518_0002_task_activity_logs.py`
- Activity endpoint: `backend/app/api/v1/routes/tasks.py`
- Auth rate limiting dependency: `backend/app/core/dependencies.py`
- Rate limit service: `backend/app/services/rate_limit_service.py`

Infrastructure:

- Health checks: `backend/app/api/v1/routes/health.py`
- Redis caching: `backend/app/services/cache_service.py`
- Redis-backed auth rate limiting: `backend/app/services/rate_limit_service.py`
- Docker Compose: `backend/docker-compose.yml`
- Alembic migrations: `backend/alembic/versions/20260516_0001_day1_foundation.py` and `backend/alembic/versions/20260518_0002_task_activity_logs.py`
- Environment config: `backend/app/core/config.py` and `backend/.env.example`

Tests:

- Auth tests: `backend/tests/test_auth.py`
- Rate limit test: `backend/tests/test_auth.py`
- Workspace, task, IDOR, file, comment, activity, demo cleanup, cache tests: `backend/tests/test_workspaces_tasks.py`

Frontend:

- Full-stack dashboard: `frontend/src/main.jsx`
- Styling: `frontend/src/styles.css`

## 25. Key Interview Talking Points

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
- I added a full-stack React dashboard to demonstrate the API through real product workflows.
- I added bonus rate limiting on auth endpoints to reduce brute-force risk.
- I added task activity history so status changes become auditable.
- I return comment author and timestamp so collaboration records have context.
- I kept the frontend simple because the backend is the evaluation focus.
