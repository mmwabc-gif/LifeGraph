from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "备份健康测试者",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "backup-health-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def enable_backup(
    client: TestClient,
    headers: dict[str, str],
    *,
    create_initial_backup: bool,
) -> dict:
    response = client.put(
        "/api/v1/backup/auto",
        headers=headers,
        json={
            "enabled": True,
            "frequency": "daily",
            "retention_count": 10,
            "create_initial_backup": create_initial_backup,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_backup_health_reports_disabled_and_missing_states(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)

    disabled = client.get("/api/v1/backup/auto", headers=headers).json()["data"]
    assert disabled["health"]["code"] == "disabled"
    assert disabled["health"]["level"] == "neutral"

    missing = enable_backup(
        client,
        headers,
        create_initial_backup=False,
    )
    assert missing["health"]["code"] == "missing"
    assert missing["health"]["level"] == "warning"
    assert missing["health"]["latest_backup"] is None


def test_new_auto_backup_is_fully_verified_and_healthy(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    status = enable_backup(client, headers, create_initial_backup=True)

    assert status["health"]["code"] == "healthy"
    assert status["health"]["verification"]["verified"] is True
    assert status["last_verified_filename"] == status["last_filename"]
    assert status["last_verified_at"]
    assert status["last_verification_error"] is None


def test_verify_latest_backup_rechecks_exact_disk_file(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    status = enable_backup(client, headers, create_initial_backup=True)

    response = client.post(
        "/api/v1/backup/auto/verify-latest",
        headers=headers,
    )
    assert response.status_code == 200
    report = response.json()["data"]
    assert report["verified"] is True
    assert report["filename"] == status["last_filename"]
    assert report["sqlite_quick_check"] == "ok"
    assert report["foreign_key_errors"] == 0
    assert report["encrypted_records_verified"] >= 1
    assert report["status"]["health"]["code"] == "healthy"


def test_backup_health_reports_overdue_without_running_backup_endpoint_hook(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    enable_backup(client, headers, create_initial_backup=True)

    metadata_path = data_dir / "vault.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    metadata["backup_policy"]["last_success_at"] = old
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    response = client.get("/api/v1/backup/auto", headers=headers)
    assert response.status_code == 200
    health = response.json()["data"]["health"]
    assert health["code"] == "overdue"
    assert health["level"] == "warning"
    assert health["overdue"] is True
    assert health["overdue_seconds"] >= 24 * 60 * 60


def test_tampered_latest_backup_is_reported_and_verification_fails(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    status = enable_backup(client, headers, create_initial_backup=True)

    path = data_dir / "backups" / "auto" / status["last_filename"]
    content = bytearray(path.read_bytes())
    content[len(content) // 2] ^= 0xFF
    path.write_bytes(bytes(content))

    status_response = client.get("/api/v1/backup/auto", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["data"]["health"]["code"] == "invalid"

    verified = client.post("/api/v1/backup/auto/verify-latest", headers=headers)
    assert verified.status_code == 400
    assert verified.json()["error"]["code"] == "AUTO_BACKUP_VERIFY_FAILED"

    refreshed = client.get("/api/v1/backup/auto", headers=headers).json()["data"]
    assert refreshed["last_verification_error"]
    assert refreshed["health"]["level"] == "error"


def test_backup_health_ui_and_reminder_hooks_are_present() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (root / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "autoBackupHealthCard",
        "autoBackupHealthBadge",
        "autoBackupHealthTitle",
        "autoBackupHealthMessage",
        "autoBackupHealthMeta",
        "verifyLatestAutoBackupButton",
    ):
        assert f'id="{element_id}"' in html
    assert 'async function verifyLatestAutoBackup()' in javascript
    assert 'async function refreshBackupHealthReminder()' in javascript
    assert 'data-backup-alert' not in html
    assert 'button.dataset.backupAlert = alertLevel' in javascript
    assert 'LifeGraph v0.0.4.6：备份健康状态、超期提醒与最近备份快速验证' in stylesheet
