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
            "display_name": "回收站闭环测试",
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


def row_exists(data_dir: Path, table: str, content_id: str) -> bool:
    with sqlite3.connect(data_dir / "lifegraph.db") as connection:
        row = connection.execute(f"SELECT 1 FROM {table} WHERE id=?", (content_id,)).fetchone()
    return row is not None


def create_and_delete(
    client: TestClient,
    headers: dict[str, str],
    endpoint: str,
    payload: dict,
) -> tuple[dict, dict]:
    created_response = client.post(f"/api/v1/{endpoint}", headers=headers, json=payload)
    assert created_response.status_code == 200
    created = created_response.json()["data"]
    deleted_response = client.request(
        "DELETE",
        f"/api/v1/{endpoint}/{created['id']}",
        headers=headers,
        json={"revision": created["revision"]},
    )
    assert deleted_response.status_code == 200
    return created, deleted_response.json()["data"]


def test_deleted_items_are_listed_and_event_can_be_restored(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    headers = initialize(client)

    created, deleted = create_and_delete(
        client,
        headers,
        "events",
        {
            "time_scope": "day",
            "period_key": "2026-08-05",
            "title": "回收站里的事件",
            "content": "恢复后仍应保持加密",
        },
    )

    trash_response = client.get("/api/v1/trash", headers=headers)
    assert trash_response.status_code == 200
    trash = trash_response.json()["data"]
    assert trash["total"] == 1
    assert trash["counts"] == {"event": 1, "memory": 0, "plan": 0}
    item = trash["items"][0]
    assert item["kind"] == "event"
    assert item["id"] == created["id"]
    assert item["title"] == "回收站里的事件"
    assert item["content"] == "恢复后仍应保持加密"
    assert item["time_scope"] == "day"
    assert item["period_key"] == "2026-08-05"
    assert item["deleted_at"]
    assert item["revision"] == deleted["revision"] == 2

    restored_response = client.post(
        f"/api/v1/trash/event/{created['id']}/restore",
        headers=headers,
        json={"revision": item["revision"]},
    )
    assert restored_response.status_code == 200
    restored = restored_response.json()["data"]
    assert restored["restored"] is True
    assert restored["revision"] == 3

    detail = client.get("/api/v1/dates/2026-08-05", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["events"][0]["title"] == "回收站里的事件"
    assert detail.json()["data"]["events"][0]["revision"] == 3

    statuses = client.get(
        "/api/v1/dates/content-status?start=1990-01-01&end=2090-01-01",
        headers=headers,
    ).json()["data"]
    assert statuses["dates"]["2026-08-05"]["has_event"] is True
    assert client.get("/api/v1/trash", headers=headers).json()["data"]["total"] == 0


def test_trash_item_can_be_permanently_deleted_with_revision_protection(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    headers = initialize(client)

    created, deleted = create_and_delete(
        client,
        headers,
        "memories",
        {
            "time_scope": "month",
            "period_key": "2026-08",
            "title": "准备彻底删除的记忆",
            "content": "这段密文最终会随记录一起删除",
        },
    )
    assert row_exists(data_dir, "memories", created["id"])

    stale = client.request(
        "DELETE",
        f"/api/v1/trash/memory/{created['id']}",
        headers=headers,
        json={"revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
    assert row_exists(data_dir, "memories", created["id"])

    purged = client.request(
        "DELETE",
        f"/api/v1/trash/memory/{created['id']}",
        headers=headers,
        json={"revision": deleted["revision"]},
    )
    assert purged.status_code == 200
    assert purged.json()["data"]["permanently_deleted"] is True
    assert not row_exists(data_dir, "memories", created["id"])

    repeated = client.request(
        "DELETE",
        f"/api/v1/trash/memory/{created['id']}",
        headers=headers,
        json={"revision": deleted["revision"]},
    )
    assert repeated.status_code == 404
    assert repeated.json()["error"]["code"] == "CONTENT_NOT_FOUND"


def test_empty_trash_removes_all_three_content_types(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    headers = initialize(client)

    cases = (
        (
            "events",
            "events",
            {"time_scope": "year", "period_key": "2026", "title": "年度事件", "content": ""},
        ),
        (
            "memories",
            "memories",
            {"time_scope": "month", "period_key": "2026-08", "title": "月度记忆", "content": ""},
        ),
        (
            "plans",
            "plans",
            {"time_scope": "day", "period_key": "2080-01-02", "title": "未来计划", "content": ""},
        ),
    )
    created_ids: list[tuple[str, str]] = []
    for endpoint, table, payload in cases:
        created, _ = create_and_delete(client, headers, endpoint, payload)
        created_ids.append((table, created["id"]))

    trash = client.get("/api/v1/trash", headers=headers).json()["data"]
    assert trash["total"] == 3
    assert trash["counts"] == {"event": 1, "memory": 1, "plan": 1}

    invalid = client.request(
        "DELETE",
        "/api/v1/trash",
        headers=headers,
        json={"confirm": "WRONG"},
    )
    assert invalid.status_code == 422

    emptied = client.request(
        "DELETE",
        "/api/v1/trash",
        headers=headers,
        json={"confirm": "EMPTY_TRASH"},
    )
    assert emptied.status_code == 200
    result = emptied.json()["data"]
    assert result["emptied"] is True
    assert result["total"] == 3
    assert result["counts"] == {"event": 1, "memory": 1, "plan": 1}
    assert client.get("/api/v1/trash", headers=headers).json()["data"]["total"] == 0
    for table, content_id in created_ids:
        assert not row_exists(data_dir, table, content_id)


def test_trash_requires_unlocked_session(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    headers = initialize(client)
    client.post("/api/v1/auth/lock")

    response = client.get("/api/v1/trash", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
