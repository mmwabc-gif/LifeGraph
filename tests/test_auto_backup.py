from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.backup import inspect_lifevault_package


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "自动备份测试者",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "automatic-backup-recovery-secret",
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def add_event(client: TestClient, headers: dict[str, str], title: str) -> None:
    response = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-06",
            "title": title,
            "content": f"{title}的私密正文",
        },
    )
    assert response.status_code == 200


def test_auto_backup_policy_creates_initial_backup_and_history(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    add_event(client, headers, "首个事件")

    default_status = client.get("/api/v1/backup/auto", headers=headers)
    assert default_status.status_code == 200
    default = default_status.json()["data"]
    assert default["enabled"] is False
    assert default["frequency"] == "daily"
    assert default["retention_count"] == 10
    assert default["history_count"] == 0

    enabled = client.put(
        "/api/v1/backup/auto",
        headers=headers,
        json={
            "enabled": True,
            "frequency": "daily",
            "retention_count": 5,
            "create_initial_backup": True,
        },
    )
    assert enabled.status_code == 200
    status = enabled.json()["data"]
    assert status["enabled"] is True
    assert status["frequency"] == "daily"
    assert status["retention_count"] == 5
    assert status["last_success_at"]
    assert status["last_filename"].startswith("lifegraph-auto-")
    assert status["history_count"] == 1

    history = client.get("/api/v1/backup/auto/history", headers=headers)
    assert history.status_code == 200
    item = history.json()["data"]["items"][0]
    assert item["valid"] is True
    assert item["schema_version"] == 3
    assert item["producer_version"] == "0.0.5"

    downloaded = client.get(
        f"/api/v1/backup/auto/history/{item['filename']}", headers=headers
    )
    assert downloaded.status_code == 200
    package = inspect_lifevault_package(downloaded.content)
    assert package.manifest["producer"]["version"] == "0.0.5"
    assert "自动备份测试者".encode("utf-8") not in downloaded.content
    assert "首个事件".encode("utf-8") not in downloaded.content
    metadata = json.loads(package.metadata_bytes.decode("utf-8"))
    assert metadata["backup_policy"]["enabled"] is True
    assert "123456" not in package.metadata_bytes.decode("utf-8")


def test_due_automatic_backup_runs_after_ordinary_api_activity(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)

    configured = client.put(
        "/api/v1/backup/auto",
        headers=headers,
        json={
            "enabled": True,
            "frequency": "daily",
            "retention_count": 10,
            "create_initial_backup": False,
        },
    )
    assert configured.status_code == 200
    assert configured.json()["data"]["history_count"] == 0

    # The middleware checks the due policy after a successful ordinary API write.
    add_event(client, headers, "触发自动备份")
    history = client.get("/api/v1/backup/auto/history", headers=headers)
    assert len(history.json()["data"]["items"]) == 1

    # Another ordinary request within the daily interval does not create a duplicate.
    profile = client.get("/api/v1/profile", headers=headers)
    assert profile.status_code == 200
    history = client.get("/api/v1/backup/auto/history", headers=headers)
    assert len(history.json()["data"]["items"]) == 1


def test_manual_auto_backup_retention_delete_and_clear(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    response = client.put(
        "/api/v1/backup/auto",
        headers=headers,
        json={
            "enabled": False,
            "frequency": "weekly",
            "retention_count": 3,
            "create_initial_backup": False,
        },
    )
    assert response.status_code == 200

    for _ in range(5):
        created = client.post("/api/v1/backup/auto/run", headers=headers)
        assert created.status_code == 200
        assert created.json()["data"]["created"] is True

    history = client.get("/api/v1/backup/auto/history", headers=headers)
    items = history.json()["data"]["items"]
    assert len(items) == 3

    deleted = client.delete(
        f"/api/v1/backup/auto/history/{items[0]['filename']}", headers=headers
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["history_count"] == 2

    cleared = client.post(
        "/api/v1/backup/auto/history/clear",
        headers=headers,
        json={"confirm": "CLEAR_AUTO_BACKUPS"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["deleted_count"] == 2
    assert cleared.json()["data"]["history_count"] == 0
    assert list((tmp_path / "vault" / "backups" / "auto").glob("*.lifevault")) == []


def test_auto_backup_endpoints_require_session(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    assert client.get("/api/v1/backup/auto").status_code == 401
    assert client.put(
        "/api/v1/backup/auto",
        json={"enabled": True, "frequency": "daily", "retention_count": 10},
    ).status_code == 401
    assert client.post("/api/v1/backup/auto/run").status_code == 401
    assert client.get("/api/v1/backup/auto/history").status_code == 401

    # Keep the authenticated control path explicit.
    assert client.get("/api/v1/backup/auto", headers=headers).status_code == 200


def test_automatic_backup_failure_does_not_fail_saved_content(
    tmp_path: Path, monkeypatch
) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    configured = client.put(
        "/api/v1/backup/auto",
        headers=headers,
        json={
            "enabled": True,
            "frequency": "daily",
            "retention_count": 10,
            "create_initial_backup": False,
        },
    )
    assert configured.status_code == 200

    def fail_backup(**_kwargs):
        raise OSError("simulated automatic backup disk failure")

    monkeypatch.setattr("app.security.vault.build_lifevault_backup", fail_backup)
    response = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-06",
            "title": "仍应保存",
            "content": "自动备份失败不能回滚这条内容",
        },
    )
    assert response.status_code == 200

    detail = client.get("/api/v1/dates/2026-08-06", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["events"][0]["title"] == "仍应保存"

    status = client.get("/api/v1/backup/auto", headers=headers).json()["data"]
    assert status["history_count"] == 0
    assert "simulated automatic backup disk failure" in status["last_error"]


def test_old_metadata_without_backup_policy_uses_safe_defaults(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    metadata_path = data_dir / "vault.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.pop("backup_policy", None)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    response = client.get("/api/v1/backup/auto", headers=headers)
    assert response.status_code == 200
    status = response.json()["data"]
    assert status["enabled"] is False
    assert status["frequency"] == "daily"
    assert status["retention_count"] == 10


def test_auto_backup_filename_cannot_escape_history_directory(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    response = client.delete(
        "/api/v1/backup/auto/history/..%2Fvault.json", headers=headers
    )
    assert response.status_code in {404, 405}
    assert (tmp_path / "vault" / "vault.json").exists()
