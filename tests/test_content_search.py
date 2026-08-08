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
            "display_name": "统一搜索测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_content_search_spans_all_kinds_keyword_and_tags(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    event = client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_date": "2026-08-08", "title": "发布版本", "content": "完成统一搜索发布。"},
    ).json()["data"]
    memory = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "month",
            "period_key": "2026-07",
            "title": "七月回忆",
            "content": "<p>记录 <strong>统一搜索</strong> 的想法。</p>",
            "content_format": "html",
        },
    ).json()["data"]
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"plan_date": "2027-01-02", "title": "搜索计划", "content": "继续完善统一搜索。"},
    ).json()["data"]

    project = client.post("/api/v1/tags", headers=headers, json={"name": "项目"}).json()["data"]
    important = client.post("/api/v1/tags", headers=headers, json={"name": "重要"}).json()["data"]
    for kind, item in (("event", event), ("memory", memory), ("plan", plan)):
        assert client.post(
            f"/api/v1/content/{kind}/{item['id']}/tags/{project['id']}", headers=headers
        ).status_code == 200
    assert client.post(
        f"/api/v1/content/event/{event['id']}/tags/{important['id']}", headers=headers
    ).status_code == 200

    response = client.get("/api/v1/content/search", headers=headers, params={"q": "统一搜索"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["counts"] == {"event": 1, "memory": 1, "plan": 1}
    assert {item["kind"] for item in data["items"]} == {"event", "memory", "plan"}
    assert all(item["tags"] for item in data["items"])

    both_tags = client.get(
        "/api/v1/content/search",
        headers=headers,
        params=[("tag_id", project["id"]), ("tag_id", important["id"])],
    )
    assert both_tags.status_code == 200
    assert [item["id"] for item in both_tags.json()["data"]["items"]] == [event["id"]]


def test_content_search_filters_kinds_and_period_overlap(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    memory = client.post(
        "/api/v1/memories",
        headers=headers,
        json={"time_scope": "month", "period_key": "2026-07", "title": "七月总结", "content": "整月记录"},
    ).json()["data"]
    client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_date": "2026-07-18", "title": "七月事件", "content": "事件内容"},
    )

    response = client.get(
        "/api/v1/content/search",
        headers=headers,
        params=[
            ("kind", "memory"),
            ("date_from", "2026-07-15"),
            ("date_to", "2026-07-20"),
        ],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["id"] == memory["id"]
    assert data["items"][0]["kind"] == "memory"
    assert data["items"][0]["time_scope"] == "month"

    bad = client.get(
        "/api/v1/content/search?date_from=2026-08-09&date_to=2026-08-08", headers=headers
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_SEARCH_RANGE"


def test_content_search_keeps_memory_search_compatibility_and_requires_unlock(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    memory = client.post(
        "/api/v1/memories",
        headers=headers,
        json={"memory_date": "2026-08-08", "title": "兼容搜索", "content": "旧接口仍可用"},
    ).json()["data"]

    old = client.get("/api/v1/memories/search?q=兼容", headers=headers)
    assert old.status_code == 200
    assert [item["id"] for item in old.json()["data"]["items"]] == [memory["id"]]
    assert old.json()["data"]["items"][0]["kind"] == "memory"

    assert client.post("/api/v1/auth/lock").status_code == 200
    assert client.get("/api/v1/content/search?q=test", headers=headers).status_code == 401


def test_content_search_supports_content_center_sorting(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    older = client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_date": "2026-07-01", "title": "较早事件", "content": "排序测试"},
    ).json()["data"]
    newer = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"plan_date": "2027-08-01", "title": "较新计划", "content": "排序测试"},
    ).json()["data"]

    ascending = client.get(
        "/api/v1/content/search",
        headers=headers,
        params={"q": "排序测试", "sort": "date_asc"},
    )
    assert ascending.status_code == 200
    assert [item["id"] for item in ascending.json()["data"]["items"]] == [older["id"], newer["id"]]

    descending = client.get(
        "/api/v1/content/search",
        headers=headers,
        params={"q": "排序测试", "sort": "date_desc"},
    )
    assert descending.status_code == 200
    assert [item["id"] for item in descending.json()["data"]["items"]] == [newer["id"], older["id"]]
