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
            "display_name": "标签测试",
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


def test_memory_tag_create_attach_render_and_detach(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    memory_response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "memory_date": "2026-08-08",
            "title": "标签闭环",
            "content": "验证记忆标签。",
        },
    )
    assert memory_response.status_code == 200
    memory = memory_response.json()["data"]

    tag_response = client.post(
        "/api/v1/tags",
        headers=headers,
        json={"name": "项目", "color": None},
    )
    assert tag_response.status_code == 200
    tag = tag_response.json()["data"]

    attached = client.post(
        f"/api/v1/memories/{memory['id']}/tags/{tag['id']}",
        headers=headers,
    )
    assert attached.status_code == 200
    assert attached.json()["data"] == {"attached": True}

    tags = client.get(f"/api/v1/memories/{memory['id']}/tags", headers=headers)
    assert tags.status_code == 200
    assert tags.json()["data"] == [{"id": tag["id"], "name": "项目", "color": None}]

    detail = client.get("/api/v1/dates/2026-08-08", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["memories"][0]["tags"] == [
        {"id": tag["id"], "name": "项目", "color": None}
    ]

    detached = client.delete(
        f"/api/v1/memories/{memory['id']}/tags/{tag['id']}",
        headers=headers,
    )
    assert detached.status_code == 200
    assert detached.json()["data"] == {"detached": True}
    assert client.get(
        f"/api/v1/memories/{memory['id']}/tags", headers=headers
    ).json()["data"] == []


def test_memory_tag_attach_rejects_missing_memory_or_tag(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    tag = client.post(
        "/api/v1/tags", headers=headers, json={"name": "家庭"}
    ).json()["data"]

    missing_memory = client.post(
        f"/api/v1/memories/not-found/tags/{tag['id']}", headers=headers
    )
    assert missing_memory.status_code == 404
    assert missing_memory.json()["error"]["code"] == "CONTENT_NOT_FOUND"
