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
            "display_name": "标签管理测试",
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


def create_memory(client: TestClient, headers: dict[str, str], title: str = "一次旅行") -> dict:
    response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "memory_date": "2026-08-08",
            "title": title,
            "content": "用于验证标签管理。",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_tag_management_lists_usage_renames_and_deletes_without_deleting_memory(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    memory = create_memory(client, headers)

    family = client.post("/api/v1/tags", headers=headers, json={"name": "家庭"}).json()["data"]
    travel = client.post("/api/v1/tags", headers=headers, json={"name": "旅行"}).json()["data"]
    assert family["memory_count"] == 0
    assert travel["memory_count"] == 0

    attached = client.post(
        f"/api/v1/memories/{memory['id']}/tags/{travel['id']}",
        headers=headers,
    )
    assert attached.status_code == 200

    listed = client.get("/api/v1/tags", headers=headers)
    assert listed.status_code == 200
    by_name = {tag["name"]: tag for tag in listed.json()["data"]}
    assert by_name["家庭"]["memory_count"] == 0
    assert by_name["旅行"]["memory_count"] == 1

    renamed = client.put(
        f"/api/v1/tags/{travel['id']}",
        headers=headers,
        json={"name": "远行", "color": None},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "远行"
    assert renamed.json()["data"]["memory_count"] == 1

    memory_tags = client.get(f"/api/v1/memories/{memory['id']}/tags", headers=headers)
    assert memory_tags.status_code == 200
    assert memory_tags.json()["data"] == [
        {"id": travel["id"], "name": "远行", "color": None}
    ]

    deleted = client.delete(f"/api/v1/tags/{travel['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {
        "id": travel["id"],
        "name": "远行",
        "event_count": 0,
        "memory_count": 1,
        "plan_count": 0,
        "total_count": 1,
        "deleted": True,
    }

    assert client.get(
        f"/api/v1/memories/{memory['id']}/tags", headers=headers
    ).json()["data"] == []
    detail = client.get("/api/v1/dates/2026-08-08", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["memories"][0]["title"] == "一次旅行"


def test_tag_management_rejects_duplicate_names_case_insensitively(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    first = client.post("/api/v1/tags", headers=headers, json={"name": "Travel"})
    assert first.status_code == 200

    duplicate = client.post("/api/v1/tags", headers=headers, json={"name": " travel "})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "TAG_NAME_CONFLICT"

    other = client.post("/api/v1/tags", headers=headers, json={"name": "家庭"}).json()["data"]
    rename_duplicate = client.put(
        f"/api/v1/tags/{other['id']}",
        headers=headers,
        json={"name": "TRAVEL", "color": None},
    )
    assert rename_duplicate.status_code == 409
    assert rename_duplicate.json()["error"]["code"] == "TAG_NAME_CONFLICT"


def test_tag_management_missing_tag_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    update = client.put(
        "/api/v1/tags/not-found",
        headers=headers,
        json={"name": "不存在", "color": None},
    )
    assert update.status_code == 404
    assert update.json()["error"]["code"] == "CONTENT_NOT_FOUND"

    delete = client.delete("/api/v1/tags/not-found", headers=headers)
    assert delete.status_code == 404
    assert delete.json()["error"]["code"] == "CONTENT_NOT_FOUND"
