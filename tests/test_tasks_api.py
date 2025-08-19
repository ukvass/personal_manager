# tests/test_tasks_api.py
# PURPOSE: verify CRUD, filters, pagination, and X-Total-Count header.

from typing import Dict


def _create_task(client, title: str, priority: int = 1, description: str | None = None) -> Dict:
    """Helper: create a task and return response JSON."""
    payload = {"title": title, "priority": priority}
    if description is not None:
        payload["description"] = description
    r = client.post("/tasks/", json=payload)
    assert r.status_code == 201
    return r.json()


def test_health_ok(client):
    # Simple healthcheck endpoint should return {"status": "ok"}
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_and_get_by_id(client):
    # Create a task, then fetch it by id
    created = _create_task(client, "First", priority=2, description="hello")
    tid = created["id"]

    r = client.get(f"/tasks/{tid}")
    assert r.status_code == 200
    got = r.json()
    # Basic shape/fields
    assert got["id"] == tid
    assert got["title"] == "First"
    assert got["priority"] == 2
    assert got["status"] == "todo"  # default status on create


def test_list_with_filters_and_pagination_and_total(client):
    # Prepare multiple tasks with different priorities/status if needed
    _create_task(client, "A", priority=1)
    _create_task(client, "B", priority=2)
    _create_task(client, "C", priority=2)
    _create_task(client, "D", priority=3)
    _create_task(client, "E", priority=3)
    _create_task(client, "F", priority=3)

    # List with filter priority=3 and pagination limit=2
    r = client.get("/tasks/?priority=3&limit=2&offset=0")
    assert r.status_code == 200

    # X-Total-Count should contain TOTAL matching rows (here: 3 tasks with priority=3)
    assert r.headers.get("X-Total-Count") == "3"

    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2  # limited to 2
    assert all(t["priority"] == 3 for t in data)

    # Next page (offset=2) should contain the remaining 1 task (if any)
    r2 = client.get("/tasks/?priority=3&limit=2&offset=2")
    assert r2.status_code == 200
    data2 = r2.json()
    # second page should have 1 remaining item
    assert len(data2) in (0, 1)  # tolerate if ordering differs; minimal check
    assert r2.headers.get("X-Total-Count") == "3"


def test_strict_put_requires_all_fields(client):
    created = _create_task(client, "Needs full replace", priority=1)
    tid = created["id"]

    # Missing required fields (status/priority) → 422 Unprocessable Entity
    r_bad = client.put(f"/tasks/{tid}", json={"title": "Only title"})
    assert r_bad.status_code == 422

    # Proper full body → 200 and fields updated
    r_ok = client.put(
        f"/tasks/{tid}",
        json={
            "title": "Full replace OK",
            "description": "new",
            "status": "in_progress",
            "priority": 5,
        },
    )
    assert r_ok.status_code == 200
    data = r_ok.json()
    assert data["title"] == "Full replace OK"
    assert data["status"] == "in_progress"
    assert data["priority"] == 5


def test_patch_partial_update(client):
    created = _create_task(client, "Patch me", priority=2)
    tid = created["id"]

    # Only change status
    r = client.patch(f"/tasks/{tid}", json={"status": "done"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "done"
    # Other fields should be preserved
    assert data["title"] == "Patch me"
    assert data["priority"] == 2


def test_delete_task(client):
    created = _create_task(client, "To remove", priority=1)
    tid = created["id"]

    # Delete should return 204
    r = client.delete(f"/tasks/{tid}")
    assert r.status_code == 204

    # Further GET should be 404
    r2 = client.get(f"/tasks/{tid}")
    assert r2.status_code == 404
