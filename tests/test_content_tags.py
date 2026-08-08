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
            "display_name": "统一标签测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def create_content(client: TestClient, headers: dict[str, str]) -> dict[str, dict]:
    event = client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_date": "2026-08-08", "title": "发布版本", "content": "事件内容"},
    ).json()["data"]
    memory = client.post(
        "/api/v1/memories",
        headers=headers,
        json={"memory_date": "2026-08-08", "title": "发布记忆", "content": "记忆内容"},
    ).json()["data"]
    plan_response = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"plan_date": "2027-08-08", "title": "未来计划", "content": "计划内容"},
    )
    assert plan_response.status_code == 200
    return {"event": event, "memory": memory, "plan": plan_response.json()["data"]}


def test_unified_tags_attach_to_all_content_kinds_and_render(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    content = create_content(client, headers)
    tag = client.post("/api/v1/tags", headers=headers, json={"name": "重要"}).json()["data"]

    for kind, item in content.items():
        attached = client.post(
            f"/api/v1/content/{kind}/{item['id']}/tags/{tag['id']}", headers=headers
        )
        assert attached.status_code == 200
        listed = client.get(f"/api/v1/content/{kind}/{item['id']}/tags", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["data"] == [{"id": tag["id"], "name": "重要", "color": None}]

    day = client.get("/api/v1/dates/2026-08-08", headers=headers).json()["data"]
    assert day["events"][0]["tags"][0]["name"] == "重要"
    assert day["memories"][0]["tags"][0]["name"] == "重要"
    future = client.get("/api/v1/dates/2027-08-08", headers=headers).json()["data"]
    assert future["plans"][0]["tags"][0]["name"] == "重要"

    browsed = client.get("/api/v1/content/browse", headers=headers).json()["data"]
    assert {item["kind"] for item in browsed["items"]} == {"event", "memory", "plan"}
    assert all(item["tags"][0]["name"] == "重要" for item in browsed["items"])

    listed_tags = client.get("/api/v1/tags", headers=headers).json()["data"]
    usage = next(item for item in listed_tags if item["id"] == tag["id"])
    assert usage["event_count"] == 1
    assert usage["memory_count"] == 1
    assert usage["plan_count"] == 1
    assert usage["total_count"] == 3


def test_unified_tag_detach_and_missing_content(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    content = create_content(client, headers)
    tag = client.post("/api/v1/tags", headers=headers, json={"name": "项目"}).json()["data"]

    event = content["event"]
    assert client.post(
        f"/api/v1/content/event/{event['id']}/tags/{tag['id']}", headers=headers
    ).status_code == 200
    detached = client.delete(
        f"/api/v1/content/event/{event['id']}/tags/{tag['id']}", headers=headers
    )
    assert detached.status_code == 200
    assert client.get(
        f"/api/v1/content/event/{event['id']}/tags", headers=headers
    ).json()["data"] == []

    missing = client.post(
        f"/api/v1/content/plan/not-found/tags/{tag['id']}", headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONTENT_NOT_FOUND"


def test_replace_content_tags_is_atomic_and_returns_saved_tags(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    content = create_content(client, headers)
    event = content["event"]
    first = client.post("/api/v1/tags", headers=headers, json={"name": "第一标签"}).json()["data"]
    second = client.post("/api/v1/tags", headers=headers, json={"name": "第二标签"}).json()["data"]

    assert client.post(
        f"/api/v1/content/event/{event['id']}/tags/{first['id']}", headers=headers
    ).status_code == 200

    replaced = client.put(
        f"/api/v1/content/event/{event['id']}/tags",
        headers=headers,
        json={"tag_ids": [second["id"], second["id"]]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"] == [
        {"id": second["id"], "name": "第二标签", "color": None}
    ]

    invalid = client.put(
        f"/api/v1/content/event/{event['id']}/tags",
        headers=headers,
        json={"tag_ids": [first["id"], "missing-tag"]},
    )
    assert invalid.status_code == 404
    assert invalid.json()["error"]["code"] == "CONTENT_NOT_FOUND"

    listed = client.get(
        f"/api/v1/content/event/{event['id']}/tags", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["data"] == [
        {"id": second["id"], "name": "第二标签", "color": None}
    ]


def test_bulk_content_tags_add_remove_and_atomic_failure(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    content = create_content(client, headers)
    first = client.post("/api/v1/tags", headers=headers, json={"name": "共同"}).json()["data"]
    second = client.post("/api/v1/tags", headers=headers, json={"name": "批量"}).json()["data"]

    event = content["event"]
    memory = content["memory"]
    for kind, item in (("event", event), ("memory", memory)):
        assert client.post(
            f"/api/v1/content/{kind}/{item['id']}/tags/{first['id']}", headers=headers
        ).status_code == 200

    added = client.post(
        "/api/v1/content/bulk/tags",
        headers=headers,
        json={
            "operation": "add",
            "items": [
                {"kind": "event", "content_id": event["id"]},
                {"kind": "memory", "content_id": memory["id"]},
            ],
            "tag_ids": [second["id"]],
        },
    )
    assert added.status_code == 200
    assert len(added.json()["data"]) == 2
    for kind, item in (("event", event), ("memory", memory)):
        names = {
            tag["name"]
            for tag in client.get(
                f"/api/v1/content/{kind}/{item['id']}/tags", headers=headers
            ).json()["data"]
        }
        assert names == {"共同", "批量"}

    removed = client.post(
        "/api/v1/content/bulk/tags",
        headers=headers,
        json={
            "operation": "remove",
            "items": [
                {"kind": "event", "content_id": event["id"]},
                {"kind": "memory", "content_id": memory["id"]},
            ],
            "tag_ids": [first["id"]],
        },
    )
    assert removed.status_code == 200
    for kind, item in (("event", event), ("memory", memory)):
        names = {
            tag["name"]
            for tag in client.get(
                f"/api/v1/content/{kind}/{item['id']}/tags", headers=headers
            ).json()["data"]
        }
        assert names == {"批量"}

    failed = client.post(
        "/api/v1/content/bulk/tags",
        headers=headers,
        json={
            "operation": "add",
            "items": [
                {"kind": "event", "content_id": event["id"]},
                {"kind": "plan", "content_id": "missing-content"},
            ],
            "tag_ids": [first["id"]],
        },
    )
    assert failed.status_code == 404
    assert failed.json()["error"]["code"] == "CONTENT_NOT_FOUND"
    event_tags = client.get(
        f"/api/v1/content/event/{event['id']}/tags", headers=headers
    ).json()["data"]
    assert [tag["name"] for tag in event_tags] == ["批量"]
