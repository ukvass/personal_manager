# >>> PATCH: tests/test_tasks_extra.py
# What changed:
# - Added test_total_count_matches_results to verify that the X-Total-Count header
#   matches the actual number of returned items, including when filters/search are applied.

from typing import Dict


def _create_task(client, title: str, priority: int = 1, description: str | None = None) -> Dict:
    """Helper: create a task and return response JSON."""
    payload = {"title": title, "priority": priority}
    if description is not None:
        payload["description"] = description
    r = client.post("/api/v1/tasks/", json=payload)
    assert r.status_code == 201
    return r.json()


def test_search_by_q(client):
    t1 = _create_task(client, "Hello world", description="greeting")
    t2 = _create_task(client, "Buy milk", description="shopping")
    t3 = _create_task(client, "HELLO again", description="caps")

    r = client.get("/api/v1/tasks/?q=hello")
    assert r.status_code == 200
    results = r.json()
    titles = [t["title"] for t in results]
    assert t1["title"] in titles
    assert t3["title"] in titles
    assert t2["title"] not in titles


def test_bulk_delete(client):
    t1 = _create_task(client, "Delete me 1")
    t2 = _create_task(client, "Delete me 2")
    t3 = _create_task(client, "Keep me")

    r = client.post("/api/v1/tasks/bulk_delete", json={"ids": [t1["id"], t2["id"]]})
    assert r.status_code == 200
    assert r.json()["deleted"] == 2

    r2 = client.get("/api/v1/tasks/")
    ids = [t["id"] for t in r2.json()]
    assert t3["id"] in ids
    assert t1["id"] not in ids
    assert t2["id"] not in ids


def test_bulk_complete(client):
    t1 = _create_task(client, "Finish homework")
    t2 = _create_task(client, "Write report")

    r = client.post("/api/v1/tasks/bulk_complete", json={"ids": [t1["id"], t2["id"]]})
    assert r.status_code == 200
    assert r.json()["updated"] == 2

    r2 = client.get("/api/v1/tasks/")
    got = {t["id"]: t for t in r2.json()}
    assert got[t1["id"]]["status"] == "done"
    assert got[t2["id"]]["status"] == "done"


def test_total_count_matches_results(client):
    # Create tasks with different priorities
    _create_task(client, "Count A", priority=1)
    _create_task(client, "Count B", priority=2)
    _create_task(client, "Count C", priority=2)

    # Query with priority=2 (should return exactly 2 tasks)
    r = client.get("/api/v1/tasks/?priority=2")
    assert r.status_code == 200
    results = r.json()
    total = int(r.headers.get("X-Total-Count", "-1"))
    # Check header present and matches length of returned list
    assert total == len(results) == 2
