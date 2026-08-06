from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    data_dir = tmp_path / "vault"
    app = create_app(Settings(data_dir=data_dir, session_ttl_seconds=60))
    return TestClient(app), data_dir


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "编辑闭环测试",
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


def stored_bytes(data_dir: Path) -> bytes:
    value = b""
    for candidate in (
        data_dir / "lifegraph.db",
        data_dir / "lifegraph.db-wal",
        data_dir / "lifegraph.db-shm",
    ):
        if candidate.exists():
            value += candidate.read_bytes()
    return value


def test_event_memory_and_plan_can_be_edited_with_encryption(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    headers = initialize(client)

    cases = (
        (
            "events",
            {"time_scope": "year", "period_key": "2026", "title": "旧事件", "content": "旧事件正文"},
            "event",
            "2026",
            "新事件标题",
            "新事件正文必须保持加密",
        ),
        (
            "memories",
            {"time_scope": "month", "period_key": "2026-08", "title": "旧记忆", "content": "旧记忆正文"},
            "memory",
            "2026-08",
            "新记忆标题",
            "新记忆正文必须保持加密",
        ),
        (
            "plans",
            {"time_scope": "day", "period_key": "2080-01-02", "title": "旧计划", "content": "旧计划正文"},
            "plan",
            "2080-01-02",
            "新计划标题",
            "新计划正文必须保持加密",
        ),
    )

    for endpoint, create_payload, response_key, period_key, new_title, new_content in cases:
        created_response = client.post(f"/api/v1/{endpoint}", headers=headers, json=create_payload)
        assert created_response.status_code == 200
        created = created_response.json()["data"]
        assert created["revision"] == 1

        updated_response = client.put(
            f"/api/v1/{endpoint}/{created['id']}",
            headers=headers,
            json={"title": new_title, "content": new_content, "revision": created["revision"]},
        )
        assert updated_response.status_code == 200
        updated = updated_response.json()["data"]
        assert updated["title"] == new_title
        assert updated["content"] == new_content
        assert updated["revision"] == 2
        assert updated["created_at"] == created["created_at"]
        assert updated["updated_at"] >= created["updated_at"]
        assert updated["time_scope"] == create_payload["time_scope"]
        assert updated["period_key"] == create_payload["period_key"]

        detail = client.get(
            f"/api/v1/periods/{create_payload['time_scope']}/{period_key}",
            headers=headers,
        )
        assert detail.status_code == 200
        items = detail.json()["data"][endpoint]
        assert len(items) == 1
        assert items[0]["id"] == created["id"]
        assert items[0]["title"] == new_title
        assert items[0]["content"] == new_content
        assert items[0]["revision"] == 2

        database_bytes = stored_bytes(data_dir)
        assert new_title.encode("utf-8") not in database_bytes
        assert new_content.encode("utf-8") not in database_bytes
        assert response_key in {"event", "memory", "plan"}


def test_edit_rejects_stale_revision_and_missing_content(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    headers = initialize(client)

    created = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-05",
            "title": "初始事件",
            "content": "初始正文",
        },
    ).json()["data"]

    first_update = client.put(
        f"/api/v1/events/{created['id']}",
        headers=headers,
        json={"title": "第一次修改", "content": "第一次正文", "revision": 1},
    )
    assert first_update.status_code == 200
    assert first_update.json()["data"]["revision"] == 2

    stale_update = client.put(
        f"/api/v1/events/{created['id']}",
        headers=headers,
        json={"title": "过期修改", "content": "不应覆盖", "revision": 1},
    )
    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "REVISION_CONFLICT"

    missing = client.put(
        "/api/v1/events/not-a-real-content-id",
        headers=headers,
        json={"title": "不存在", "content": "", "revision": 1},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONTENT_NOT_FOUND"

    detail = client.get("/api/v1/dates/2026-08-05", headers=headers).json()["data"]
    assert detail["events"][0]["title"] == "第一次修改"
    assert detail["events"][0]["revision"] == 2
