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
            "display_name": "地图筛选测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create_memory(client: TestClient, headers: dict[str, str], payload: dict) -> dict:
    response = client.post("/api/v1/memories", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()["data"]


def test_memory_tag_map_uses_and_semantics_and_preserves_scope(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    family = client.post("/api/v1/tags", headers=headers, json={"name": "家庭"}).json()["data"]
    travel = client.post("/api/v1/tags", headers=headers, json={"name": "旅行"}).json()["data"]

    day = create_memory(
        client, headers,
        {"memory_date": "2026-08-08", "title": "东京", "content": "旅行日记"},
    )
    month = create_memory(
        client, headers,
        {"time_scope": "month", "period_key": "2025-05", "title": "五月", "content": "月度回忆"},
    )
    year = create_memory(
        client, headers,
        {"time_scope": "year", "period_key": "2024", "title": "年度", "content": "年度回忆"},
    )
    family_only = create_memory(
        client, headers,
        {"memory_date": "2026-01-02", "title": "家庭聚会", "content": "只有家庭标签"},
    )

    for memory in (day, month, year):
        client.post(f"/api/v1/memories/{memory['id']}/tags/{family['id']}", headers=headers)
        client.post(f"/api/v1/memories/{memory['id']}/tags/{travel['id']}", headers=headers)
    client.post(f"/api/v1/memories/{family_only['id']}/tags/{family['id']}", headers=headers)

    response = client.get(
        "/api/v1/memories/tag-map",
        headers=headers,
        params=[
            ("start", "1990-01-01"),
            ("end", "2089-12-31"),
            ("tag_id", family["id"]),
            ("tag_id", travel["id"]),
        ],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["memory_count"] == 3
    assert data["dates"] == ["2026-08-08"]
    assert data["months"] == ["2025-05", "2026-08"]
    assert data["years"] == ["2024", "2025", "2026"]


def test_memory_tag_map_validates_filter_and_unlock(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    missing_tag = client.get(
        "/api/v1/memories/tag-map?start=2026-01-01&end=2026-12-31", headers=headers
    )
    assert missing_tag.status_code == 400
    assert missing_tag.json()["error"]["code"] == "TAG_FILTER_REQUIRED"

    bad_range = client.get(
        "/api/v1/memories/tag-map?start=2026-12-31&end=2026-01-01&tag_id=x", headers=headers
    )
    assert bad_range.status_code == 400
    assert bad_range.json()["error"]["code"] == "INVALID_DATE_RANGE"

    client.post("/api/v1/auth/lock")
    locked = client.get(
        "/api/v1/memories/tag-map?start=2026-01-01&end=2026-12-31&tag_id=x", headers=headers
    )
    assert locked.status_code == 401
