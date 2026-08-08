from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path / "vault", session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "统一地图筛选测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create(client: TestClient, headers: dict[str, str], kind: str, payload: dict) -> dict:
    endpoint = {"event": "events", "memory": "memories", "plan": "plans"}[kind]
    response = client.post(f"/api/v1/{endpoint}", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()["data"]


def attach(client: TestClient, headers: dict[str, str], kind: str, content_id: str, tag_id: str) -> None:
    response = client.post(
        f"/api/v1/content/{kind}/{content_id}/tags/{tag_id}", headers=headers
    )
    assert response.status_code == 200


def test_content_tag_map_combines_all_kinds_and_preserves_scope(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    important = client.post("/api/v1/tags", headers=headers, json={"name": "重要"}).json()["data"]
    project = client.post("/api/v1/tags", headers=headers, json={"name": "项目"}).json()["data"]

    event = create(
        client,
        headers,
        "event",
        {"event_date": "2026-08-08", "title": "发布", "content": "事件"},
    )
    memory = create(
        client,
        headers,
        "memory",
        {"time_scope": "month", "period_key": "2025-05", "title": "五月回忆", "content": "记忆"},
    )
    plan = create(
        client,
        headers,
        "plan",
        {"time_scope": "year", "period_key": "2027", "title": "年度计划", "content": "计划"},
    )
    important_only = create(
        client,
        headers,
        "memory",
        {"memory_date": "2026-01-02", "title": "只有重要", "content": "不应命中双标签"},
    )

    for kind, item in (("event", event), ("memory", memory), ("plan", plan)):
        attach(client, headers, kind, item["id"], important["id"])
        attach(client, headers, kind, item["id"], project["id"])
    attach(client, headers, "memory", important_only["id"], important["id"])

    response = client.get(
        "/api/v1/content/tag-map",
        headers=headers,
        params=[
            ("start", "1990-01-01"),
            ("end", "2089-12-31"),
            ("tag_id", important["id"]),
            ("tag_id", project["id"]),
        ],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content_count"] == 3
    assert data["counts"] == {"event": 1, "memory": 1, "plan": 1}
    assert data["dates"] == ["2026-08-08"]
    assert data["months"] == ["2025-05", "2026-08"]
    assert data["years"] == ["2025", "2026", "2027"]


def test_content_tag_map_can_limit_kinds_and_checks_period_overlap(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    tag = client.post("/api/v1/tags", headers=headers, json={"name": "年度"}).json()["data"]

    event = create(
        client,
        headers,
        "event",
        {"time_scope": "year", "period_key": "2026", "title": "年度事件", "content": ""},
    )
    memory = create(
        client,
        headers,
        "memory",
        {"memory_date": "2026-08-08", "title": "日记", "content": ""},
    )
    attach(client, headers, "event", event["id"], tag["id"])
    attach(client, headers, "memory", memory["id"], tag["id"])

    response = client.get(
        "/api/v1/content/tag-map",
        headers=headers,
        params=[
            ("start", "2026-08-01"),
            ("end", "2026-08-31"),
            ("tag_id", tag["id"]),
            ("kind", "event"),
        ],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content_count"] == 1
    assert data["counts"] == {"event": 1, "memory": 0, "plan": 0}
    assert data["dates"] == []
    assert data["months"] == []
    assert data["years"] == ["2026"]


def test_content_tag_map_validates_filter_range_and_unlock(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    missing_tag = client.get(
        "/api/v1/content/tag-map?start=2026-01-01&end=2026-12-31", headers=headers
    )
    assert missing_tag.status_code == 400
    assert missing_tag.json()["error"]["code"] == "TAG_FILTER_REQUIRED"

    bad_range = client.get(
        "/api/v1/content/tag-map?start=2026-12-31&end=2026-01-01&tag_id=x", headers=headers
    )
    assert bad_range.status_code == 400
    assert bad_range.json()["error"]["code"] == "INVALID_DATE_RANGE"

    client.post("/api/v1/auth/lock")
    locked = client.get(
        "/api/v1/content/tag-map?start=2026-01-01&end=2026-12-31&tag_id=x", headers=headers
    )
    assert locked.status_code == 401
