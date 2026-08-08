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
            "display_name": "内容中心测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_content_center_browses_all_kinds_and_keeps_memory_tags(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    event = client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_date": "2026-08-05", "title": "完成阶段", "content": "阶段完成。"},
    ).json()["data"]
    memory = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "month",
            "period_key": "2026-07",
            "title": "七月记忆",
            "content": "<p>这个月去了海边。</p>",
            "content_format": "html",
        },
    ).json()["data"]
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"time_scope": "year", "period_key": "2027", "title": "年度计划", "content": "继续整理。"},
    ).json()["data"]
    tag = client.post("/api/v1/tags", headers=headers, json={"name": "旅行"}).json()["data"]
    assert client.post(f"/api/v1/memories/{memory['id']}/tags/{tag['id']}", headers=headers).status_code == 200

    response = client.get("/api/v1/content/browse", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["counts"] == {"event": 1, "memory": 1, "plan": 1}
    assert [item["id"] for item in data["items"]] == [plan["id"], event["id"], memory["id"]]
    memory_item = next(item for item in data["items"] if item["kind"] == "memory")
    assert memory_item["tags"][0]["name"] == "旅行"
    assert memory_item["content_format"] == "html"


def test_content_center_filters_type_range_and_scope_overlap(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    client.post(
        "/api/v1/memories",
        headers=headers,
        json={"time_scope": "month", "period_key": "2026-07", "title": "七月总结", "content": "整月内容"},
    )
    client.post(
        "/api/v1/events",
        headers=headers,
        json={"event_date": "2026-08-05", "title": "八月事件", "content": "事件"},
    )

    response = client.get(
        "/api/v1/content/browse",
        headers=headers,
        params=[
            ("kind", "memory"),
            ("date_from", "2026-07-15"),
            ("date_to", "2026-07-20"),
            ("sort", "date_asc"),
        ],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["kind"] == "memory"
    assert data["items"][0]["time_scope"] == "month"
    assert data["items"][0]["period_key"] == "2026-07"

    bad = client.get(
        "/api/v1/content/browse?date_from=2026-08-09&date_to=2026-08-08",
        headers=headers,
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_BROWSE_RANGE"


def test_content_center_limit_and_locked_state(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    for day in ("2026-08-01", "2026-08-02"):
        response = client.post(
            "/api/v1/events",
            headers=headers,
            json={"event_date": day, "title": day, "content": ""},
        )
        assert response.status_code == 200

    limited = client.get("/api/v1/content/browse?kind=event&limit=1", headers=headers)
    assert limited.status_code == 200
    data = limited.json()["data"]
    assert data["count"] == 1
    assert data["total"] == 2
    assert data["has_more"] is True

    assert client.post("/api/v1/auth/lock").status_code == 200
    assert client.get("/api/v1/content/browse", headers=headers).status_code == 401
