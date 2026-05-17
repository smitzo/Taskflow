from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
import app.services.task_service as task_service_module
import app.services.workspace_service as workspace_service_module


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

    clear_response = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"assignee_id": None, "description": None},
        headers=auth_header(owner_token),
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["assignee_id"] is None
    assert clear_response.json()["description"] is None

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


def test_task_filters_pagination_summary_and_soft_delete(client: TestClient) -> None:
    owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Platform"},
        headers=auth_header(owner_token),
    ).json()

    priorities = ["low", "high", "critical"]
    task_ids = []
    for index, priority in enumerate(priorities):
        response = client.post(
            f"/api/v1/workspaces/{workspace['id']}/tasks",
            json={"title": f"Task {index}", "assignee_id": owner_id, "priority": priority},
            headers=auth_header(owner_token),
        )
        assert response.status_code == 201
        task_ids.append(response.json()["id"])

    filtered_response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/tasks?priority=high&page=1&size=1",
        headers=auth_header(owner_token),
    )
    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["priority"] == "high"

    summary_response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/tasks/summary",
        headers=auth_header(owner_token),
    )
    assert summary_response.status_code == 200
    assert summary_response.json()["total"] == 3
    assert summary_response.json()["by_priority"]["critical"] == 1

    delete_response = client.delete(f"/api/v1/tasks/{task_ids[0]}", headers=auth_header(owner_token))
    assert delete_response.status_code == 204

    deleted_task_response = client.get(f"/api/v1/tasks/{task_ids[0]}", headers=auth_header(owner_token))
    assert deleted_task_response.status_code == 404

    summary_after_delete = client.get(
        f"/api/v1/workspaces/{workspace['id']}/tasks/summary",
        headers=auth_header(owner_token),
    )
    assert summary_after_delete.status_code == 200
    assert summary_after_delete.json()["total"] == 2


def test_remove_member_revokes_workspace_and_task_access(client: TestClient) -> None:
    owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")
    member_id, member_token = register_and_login(client, "member@example.com", "Member User")

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
    task = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tasks",
        json={"title": "Shared Task", "assignee_id": owner_id, "priority": "medium"},
        headers=auth_header(owner_token),
    ).json()

    assert client.get(f"/api/v1/tasks/{task['id']}", headers=auth_header(member_token)).status_code == 200

    remove_response = client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{member_id}",
        headers=auth_header(owner_token),
    )
    assert remove_response.status_code == 204

    assert client.get(f"/api/v1/workspaces/{workspace['id']}", headers=auth_header(member_token)).status_code == 404
    assert client.get(f"/api/v1/tasks/{task['id']}", headers=auth_header(member_token)).status_code == 404


class FakeCacheService:
    store: dict[str, object] = {}

    def get_json(self, key: str):
        return self.store.get(key)

    def set_json(self, key: str, value, ttl_seconds: int | None = None) -> None:
        self.store[key] = value

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)

    def delete_pattern(self, pattern: str) -> None:
        self.store.clear()


def test_workspace_detail_and_task_summary_use_cache(client: TestClient, monkeypatch) -> None:
    FakeCacheService.store = {}
    fake_cache = FakeCacheService()
    monkeypatch.setattr(workspace_service_module, "CacheService", lambda: fake_cache)
    monkeypatch.setattr(task_service_module, "CacheService", lambda: fake_cache)

    owner_id, owner_token = register_and_login(client, "owner@example.com", "Owner User")
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Platform"},
        headers=auth_header(owner_token),
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace['id']}/tasks",
        json={"title": "Cached Task", "assignee_id": owner_id, "priority": "high"},
        headers=auth_header(owner_token),
    )

    first_detail = client.get(f"/api/v1/workspaces/{workspace['id']}", headers=auth_header(owner_token))
    fake_cache.store[f"workspace:{workspace['id']}:detail"]["name"] = "Cached Platform"
    second_detail = client.get(f"/api/v1/workspaces/{workspace['id']}", headers=auth_header(owner_token))
    assert first_detail.status_code == 200
    assert second_detail.status_code == 200
    assert first_detail.json()["name"] == "Platform"
    assert second_detail.json()["name"] == "Cached Platform"

    first_summary = client.get(
        f"/api/v1/workspaces/{workspace['id']}/tasks/summary",
        headers=auth_header(owner_token),
    )
    fake_cache.store[f"workspace:{workspace['id']}:task_summary"]["total"] = 42
    second_summary = client.get(
        f"/api/v1/workspaces/{workspace['id']}/tasks/summary",
        headers=auth_header(owner_token),
    )
    assert first_summary.status_code == 200
    assert second_summary.status_code == 200
    assert first_summary.json()["total"] == 1
    assert second_summary.json()["total"] == 42
