from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings


def register_and_login(client: TestClient, email: str, full_name: str = "Test User") -> tuple[str, str]:
    password = "StrongPass123"
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    return user_id, login_response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_workspace_owner_can_create_invite_and_view_members(client: TestClient) -> None:
    _owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")
    member_id, _member_token = register_and_login(client, "member@example.com", "Member User")

    create_response = client.post(
        "/api/v1/workspaces",
        json={"name": "Platform", "description": "Core product work"},
        headers=auth_header(owner_token),
    )
    assert create_response.status_code == 201
    workspace_id = create_response.json()["id"]

    invite_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "member@example.com"},
        headers=auth_header(owner_token),
    )
    assert invite_response.status_code == 201
    assert invite_response.json()["user"]["id"] == member_id

    detail_response = client.get(f"/api/v1/workspaces/{workspace_id}", headers=auth_header(owner_token))
    assert detail_response.status_code == 200
    assert {member["user"]["email"] for member in detail_response.json()["members"]} == {
        "owner@example.com",
        "member@example.com",
    }


def test_non_owner_cannot_update_workspace(client: TestClient) -> None:
    _owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")
    _member_id, member_token = register_and_login(client, "member@example.com", "Member User")

    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Platform"},
        headers=auth_header(owner_token),
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": "member@example.com"},
        headers=auth_header(owner_token),
    )

    response = client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"name": "Renamed"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 403


def test_task_creation_status_workflow_comments_and_file_upload(client: TestClient, tmp_path: Path) -> None:
    settings.upload_dir = str(tmp_path)
    owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")

    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Platform"},
        headers=auth_header(owner_token),
    ).json()

    create_task_response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tasks",
        json={
            "title": "Build API",
            "description": "Ship the backend slice",
            "assignee_id": owner_id,
            "priority": "high",
        },
        headers=auth_header(owner_token),
    )
    assert create_task_response.status_code == 201
    task = create_task_response.json()
    assert task["status"] == "todo"

    invalid_transition = client.patch(
        f"/api/v1/tasks/{task['id']}/status",
        json={"status": "done"},
        headers=auth_header(owner_token),
    )
    assert invalid_transition.status_code == 400

    next_transition = client.patch(
        f"/api/v1/tasks/{task['id']}/status",
        json={"status": "in_progress"},
        headers=auth_header(owner_token),
    )
    assert next_transition.status_code == 200
    assert next_transition.json()["status"] == "in_progress"

    comment_response = client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"body": "Looks good"},
        headers=auth_header(owner_token),
    )
    assert comment_response.status_code == 201

    upload_response = client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        files={"file": ("note.txt", b"hello taskflow", "text/plain")},
        headers=auth_header(owner_token),
    )
    assert upload_response.status_code == 201
    attachment_id = upload_response.json()["id"]

    detail_response = client.get(f"/api/v1/tasks/{task['id']}", headers=auth_header(owner_token))
    assert detail_response.status_code == 200
    assert len(detail_response.json()["comments"]) == 1
    assert len(detail_response.json()["attachments"]) == 1

    download_response = client.get(f"/api/v1/attachments/{attachment_id}", headers=auth_header(owner_token))
    assert download_response.status_code == 200
    assert download_response.content == b"hello taskflow"


def test_idor_user_cannot_access_another_workspace_or_task(client: TestClient) -> None:
    owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")
    _outsider_id, outsider_token = register_and_login(client, "outsider@example.com", "Outsider User")

    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Private Space"},
        headers=auth_header(owner_token),
    ).json()
    task = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tasks",
        json={"title": "Secret Task", "assignee_id": owner_id, "priority": "critical"},
        headers=auth_header(owner_token),
    ).json()

    workspace_response = client.get(f"/api/v1/workspaces/{workspace['id']}", headers=auth_header(outsider_token))
    assert workspace_response.status_code == 404

    task_response = client.get(f"/api/v1/tasks/{task['id']}", headers=auth_header(outsider_token))
    assert task_response.status_code == 404

