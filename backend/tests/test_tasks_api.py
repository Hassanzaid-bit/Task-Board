"""Integration tests: full request -> auth -> SQL -> response cycle against a real DB."""

from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> int:
    resp = await client.post(
        "/api/v1/projects", json={"name": "Website revamp"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_task_lifecycle_create_and_move(client: AsyncClient, alice: dict):
    headers = alice["headers"]
    project_id = await _create_project(client, headers)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Design landing page",
            "description": "Hero + pricing sections",
            "assignee_id": alice["user"]["id"],
            "due_date": "2026-08-01",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    task = resp.json()
    assert task["status"] == "todo"
    assert task["assignee_name"] == "Alice"

    # Move it to in_progress: status changes, assignee is untouched.
    resp = await client.patch(
        f"/api/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    moved = resp.json()
    assert moved["status"] == "in_progress"
    assert moved["assignee_name"] == "Alice"

    # Board reflects the change.
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks",
        params={"status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == [task["id"]]

    # Text search matches assignee name as well as title/description.
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks", params={"q": "alice"}, headers=headers
    )
    assert [t["id"] for t in resp.json()] == [task["id"]]

    # ...and status, including the human spelling "in progress".
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks", params={"q": "in progress"}, headers=headers
    )
    assert [t["id"] for t in resp.json()] == [task["id"]]
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks", params={"q": "no-such-text"}, headers=headers
    )
    assert resp.json() == []


async def test_mandatory_fields_are_enforced(client: AsyncClient, alice: dict):
    headers = alice["headers"]
    project_id = await _create_project(client, headers)

    # Creation without description/assignee is rejected.
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Missing everything else"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "validation_error"

    # A non-existent assignee is rejected cleanly, not with a DB error.
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Task",
            "description": "Desc",
            "assignee_id": 9999,
            "due_date": "2026-08-01",
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Assignee does not exist" in resp.json()["detail"]["message"]

    # Required fields cannot be cleared on edit.
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Task",
            "description": "Desc",
            "assignee_id": alice["user"]["id"],
            "due_date": "2026-08-01",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]

    for payload in ({"assignee_id": None}, {"due_date": None}, {"description": None}):
        resp = await client.patch(f"/api/v1/tasks/{task_id}", json=payload, headers=headers)
        assert resp.status_code == 422, payload


async def test_invalid_status_is_rejected_with_422(client: AsyncClient, alice: dict):
    headers = alice["headers"]
    project_id = await _create_project(client, headers)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Task",
            "description": "Desc",
            "assignee_id": alice["user"]["id"],
            "due_date": "2026-08-01",
            "status": "not-a-status",
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_input"


async def test_endpoints_require_auth(client: AsyncClient):
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"
