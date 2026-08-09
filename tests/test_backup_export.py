from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    app = create_app(Settings(data_dir=data_dir, session_ttl_seconds=60))
    return TestClient(app)


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "备份测试用户",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "backup-test-recovery-secret",
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_backup_check_and_lifevault_export_can_be_restored(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-vault"
    client = make_client(source_dir)
    headers = initialize(client)

    event_title = "不会明文出现在备份中的事件"
    event_body = "一致性快照需要包含刚刚提交的 WAL 数据"
    created = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2001-02-03",
            "title": event_title,
            "content": event_body,
        },
    )
    assert created.status_code == 200

    deleted_memory = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "month",
            "period_key": "2001-02",
            "title": "回收站中的记忆",
            "content": "软删除记录也必须进入备份",
        },
    ).json()["data"]
    deleted = client.request(
        "DELETE",
        f"/api/v1/memories/{deleted_memory['id']}",
        headers=headers,
        json={"revision": deleted_memory["revision"]},
    )
    assert deleted.status_code == 200

    report = client.get("/api/v1/backup/check", headers=headers)
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["ready"] is True
    assert report_data["sqlite_quick_check"] == "ok"
    assert report_data["foreign_key_errors"] == 0
    assert report_data["encrypted_records_verified"] == 3

    response = client.get("/api/v1/backup/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.lifegraph.lifevault+zip"
    )
    assert response.headers["x-lifegraph-backup-format"] == "lifegraph-lifevault-v2"
    assert ".lifevault" in response.headers["content-disposition"]
    assert event_title.encode("utf-8") not in response.content
    assert event_body.encode("utf-8") not in response.content
    assert b"123456" not in response.content

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "manifest.json",
            "repository/vault.json",
            "repository/lifegraph.db",
        }
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == "lifegraph-lifevault"
        assert manifest["format_version"] == 2
        assert manifest["producer"]["version"] == "0.0.8"
        assert manifest["repository"]["schema_version"] == 7
        assert manifest["integrity"]["encrypted_records_verified"] == 3
        for entry in manifest["files"]:
            value = archive.read(entry["path"])
            assert len(value) == entry["size"]
            assert hashlib.sha256(value).hexdigest() == entry["sha256"]

        restored_dir = tmp_path / "restored-vault"
        restored_dir.mkdir()
        (restored_dir / "vault.json").write_bytes(archive.read("repository/vault.json"))
        (restored_dir / "lifegraph.db").write_bytes(archive.read("repository/lifegraph.db"))

    restored_client = make_client(restored_dir)
    unlocked = restored_client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    )
    assert unlocked.status_code == 200
    restored_headers = {
        "Authorization": f"Bearer {unlocked.json()['data']['token']}"
    }
    detail = restored_client.get("/api/v1/dates/2001-02-03", headers=restored_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["events"][0]["title"] == event_title
    trash = restored_client.get("/api/v1/trash", headers=restored_headers)
    assert trash.status_code == 200
    assert trash.json()["data"]["items"][0]["title"] == "回收站中的记忆"


def test_backup_endpoints_require_session(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    initialize(client)
    assert client.get("/api/v1/backup/check").status_code == 401
    assert client.get("/api/v1/backup/export").status_code == 401


def test_backup_controls_are_present_in_settings() -> None:
    project_root = Path(__file__).resolve().parents[1]
    html = (project_root / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (project_root / "frontend" / "app.js").read_text(encoding="utf-8")
    assert 'id="checkBackupButton"' in html
    assert 'id="exportBackupButton"' in html
    assert 'id="backupStatusText"' in html
    assert 'id="importBackupFile"' in html
    assert 'id="importCredentialMethod"' in html
    assert 'id="importCredentialSecret"' in html
    assert 'id="checkImportBackupButton"' in html
    assert 'id="restoreImportBackupButton"' in html
    assert 'id="importBackupStatusText"' in html
    assert '"/api/v1/backup/check"' in javascript
    assert '"/api/v1/backup/export"' in javascript
    assert '"/api/v1/backup/import/check"' in javascript
    assert '"/api/v1/backup/import"' in javascript
    assert 'REPLACE_REPOSITORY' in javascript
    assert 'link.download = filename' in javascript
