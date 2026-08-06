import sqlite3
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
            "display_name": "软删除闭环测试",
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


def table_row(data_dir: Path, table: str, content_id: str) -> sqlite3.Row:
    connection = sqlite3.connect(data_dir / "lifegraph.db")
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            f"SELECT nonce, ciphertext, revision, deleted_at FROM {table} WHERE id=?",
            (content_id,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return row


def test_event_memory_and_plan_are_soft_deleted_and_status_is_recomputed(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    headers = initialize(client)

    cases = (
        (
            "events",
            "events",
            {"time_scope": "day", "period_key": "2026-08-05", "title": "待删事件", "content": "保留密文"},
            "day",
            "2026-08-05",
            "has_event",
        ),
        (
            "memories",
            "memories",
            {"time_scope": "month", "period_key": "2026-08", "title": "待删记忆", "content": "保留密文"},
            "month",
            "2026-08",
            "has_memory",
        ),
        (
            "plans",
            "plans",
            {"time_scope": "year", "period_key": "2080", "title": "待删计划", "content": "保留密文"},
            "year",
            "2080",
            "has_plan",
        ),
    )

    for endpoint, table, create_payload, scope, period_key, flag in cases:
        created_response = client.post(f"/api/v1/{endpoint}", headers=headers, json=create_payload)
        assert created_response.status_code == 200
        created = created_response.json()["data"]
        before = table_row(data_dir, table, created["id"])

        deleted_response = client.request(
            "DELETE",
            f"/api/v1/{endpoint}/{created['id']}",
            headers=headers,
            json={"revision": created["revision"]},
        )
        assert deleted_response.status_code == 200
        deleted = deleted_response.json()["data"]
        assert deleted["id"] == created["id"]
        assert deleted["revision"] == 2
        assert deleted["deleted_at"]

        after = table_row(data_dir, table, created["id"])
        assert after["deleted_at"]
        assert after["revision"] == 2
        assert after["nonce"] == before["nonce"]
        assert after["ciphertext"] == before["ciphertext"]

        detail = client.get(f"/api/v1/periods/{scope}/{period_key}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"][endpoint] == []

        statuses = client.get(
            "/api/v1/dates/content-status?start=1990-01-01&end=2090-01-01",
            headers=headers,
        )
        assert statuses.status_code == 200
        data = statuses.json()["data"]
        map_name = {"day": "dates", "month": "months", "year": "years"}[scope]
        assert not data[map_name].get(period_key, {}).get(flag, False)


def test_delete_rejects_stale_revision_missing_and_repeated_delete(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    headers = initialize(client)

    created = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-05",
            "title": "并发删除测试",
            "content": "正文",
        },
    ).json()["data"]

    updated = client.put(
        f"/api/v1/events/{created['id']}",
        headers=headers,
        json={"title": "已更新", "content": "新正文", "revision": 1},
    ).json()["data"]
    assert updated["revision"] == 2

    stale = client.request(
        "DELETE",
        f"/api/v1/events/{created['id']}",
        headers=headers,
        json={"revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"

    deleted = client.request(
        "DELETE",
        f"/api/v1/events/{created['id']}",
        headers=headers,
        json={"revision": 2},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["revision"] == 3

    repeated = client.request(
        "DELETE",
        f"/api/v1/events/{created['id']}",
        headers=headers,
        json={"revision": 3},
    )
    assert repeated.status_code == 404
    assert repeated.json()["error"]["code"] == "CONTENT_NOT_FOUND"

    missing = client.request(
        "DELETE",
        "/api/v1/events/not-a-real-content-id",
        headers=headers,
        json={"revision": 1},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONTENT_NOT_FOUND"
