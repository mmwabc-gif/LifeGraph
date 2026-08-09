from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(
    client: TestClient,
    *,
    name: str,
    pin: str,
    recovery: str,
) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": name,
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": pin,
            "recovery_secret": recovery,
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def add_event(client: TestClient, headers: dict[str, str], title: str) -> dict:
    response = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2001-02-03",
            "title": title,
            "content": f"{title}正文",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def export_backup(client: TestClient, headers: dict[str, str]) -> bytes:
    response = client.get("/api/v1/backup/export", headers=headers)
    assert response.status_code == 200
    return response.content


def upload_payload(content: bytes, *, pin: str, confirm: str | None = None) -> dict:
    data = {
        "credential_method": "pin",
        "credential_secret": pin,
    }
    if confirm is not None:
        data["confirm"] = confirm
    return {
        "files": {
            "backup_file": (
                "test.lifevault",
                content,
                "application/vnd.lifegraph.lifevault+zip",
            )
        },
        "data": data,
    }


def test_lifevault_import_check_restore_and_rescue_backup(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_client = make_client(source_dir)
    source_headers = initialize(
        source_client,
        name="来源仓库",
        pin="654321",
        recovery="source-recovery-credential",
    )
    add_event(source_client, source_headers, "来源事件")
    source_backup = export_backup(source_client, source_headers)

    target_dir = tmp_path / "target"
    target_client = make_client(target_dir)
    target_headers = initialize(
        target_client,
        name="当前仓库",
        pin="123456",
        recovery="target-recovery-credential",
    )
    add_event(target_client, target_headers, "恢复前事件")

    checked = target_client.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        **upload_payload(source_backup, pin="654321"),
    )
    assert checked.status_code == 200
    report = checked.json()["data"]
    assert report["valid"] is True
    assert report["schema_version"] == 11
    assert report["encrypted_records_verified"] == 2
    assert report["record_counts"]["event"] == 1
    assert report["producer_version"] == "0.0.10"

    recovery_check = target_client.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        files={
            "backup_file": (
                "test.lifevault",
                source_backup,
                "application/vnd.lifegraph.lifevault+zip",
            )
        },
        data={
            "credential_method": "recovery",
            "credential_secret": "source-recovery-credential",
        },
    )
    assert recovery_check.status_code == 200
    assert recovery_check.json()["data"]["credential_method"] == "recovery"

    refused = target_client.post(
        "/api/v1/backup/import",
        headers=target_headers,
        **upload_payload(source_backup, pin="654321", confirm="NO"),
    )
    assert refused.status_code == 400
    still_current = target_client.get("/api/v1/dates/2001-02-03", headers=target_headers)
    assert still_current.json()["data"]["events"][0]["title"] == "恢复前事件"

    restored = target_client.post(
        "/api/v1/backup/import",
        headers=target_headers,
        **upload_payload(
            source_backup,
            pin="654321",
            confirm="REPLACE_REPOSITORY",
        ),
    )
    assert restored.status_code == 200
    restored_report = restored.json()["data"]
    assert restored_report["restored"] is True
    assert restored_report["locked"] is True
    assert restored_report["restored_schema_version"] == 11

    # The old session is revoked after repository replacement.
    assert target_client.get("/api/v1/profile", headers=target_headers).status_code == 401
    unlocked = target_client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "654321"}
    )
    assert unlocked.status_code == 200
    restored_headers = {
        "Authorization": f"Bearer {unlocked.json()['data']['token']}"
    }
    detail = target_client.get("/api/v1/dates/2001-02-03", headers=restored_headers)
    assert detail.status_code == 200
    assert [item["title"] for item in detail.json()["data"]["events"]] == ["来源事件"]

    security = target_client.get("/api/v1/security/summary", headers=restored_headers)
    assert security.status_code == 200
    assert security.json()["data"]["audit"][0]["action"] == "repository_restored"

    rescue_path = target_dir / "recovery" / restored_report["rescue_backup_filename"]
    assert rescue_path.exists()
    # The automatic rescue package can independently recover the pre-restore repository.
    rescue_dir = tmp_path / "rescue-restored"
    rescue_dir.mkdir()
    with zipfile.ZipFile(io.BytesIO(rescue_path.read_bytes())) as archive:
        (rescue_dir / "vault.json").write_bytes(archive.read("repository/vault.json"))
        (rescue_dir / "lifegraph.db").write_bytes(archive.read("repository/lifegraph.db"))
    rescue_client = make_client(rescue_dir)
    rescue_unlock = rescue_client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    )
    assert rescue_unlock.status_code == 200
    rescue_headers = {
        "Authorization": f"Bearer {rescue_unlock.json()['data']['token']}"
    }
    rescue_detail = rescue_client.get(
        "/api/v1/dates/2001-02-03", headers=rescue_headers
    )
    assert rescue_detail.json()["data"]["events"][0]["title"] == "恢复前事件"


def test_import_rejects_wrong_credential_and_tampered_package(tmp_path: Path) -> None:
    source = make_client(tmp_path / "source")
    source_headers = initialize(
        source,
        name="来源",
        pin="654321",
        recovery="source-recovery-credential",
    )
    add_event(source, source_headers, "来源事件")
    backup = export_backup(source, source_headers)

    target = make_client(tmp_path / "target")
    target_headers = initialize(
        target,
        name="目标",
        pin="123456",
        recovery="target-recovery-credential",
    )

    wrong = target.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        **upload_payload(backup, pin="000000"),
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_BACKUP_CREDENTIAL"

    input_buffer = io.BytesIO(backup)
    output_buffer = io.BytesIO()
    with zipfile.ZipFile(input_buffer) as source_zip, zipfile.ZipFile(
        output_buffer, "w", zipfile.ZIP_DEFLATED
    ) as target_zip:
        for name in source_zip.namelist():
            value = source_zip.read(name)
            if name == "repository/lifegraph.db":
                value += b"tampered"
            target_zip.writestr(name, value)
    tampered = target.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        **upload_payload(output_buffer.getvalue(), pin="654321"),
    )
    assert tampered.status_code == 400
    assert tampered.json()["error"]["code"] == "BACKUP_IMPORT_CHECK_FAILED"


def test_backup_import_endpoints_require_session(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(
        client,
        name="测试",
        pin="123456",
        recovery="test-recovery-credential",
    )
    backup = export_backup(client, headers)
    assert client.post(
        "/api/v1/backup/import/check", **upload_payload(backup, pin="123456")
    ).status_code == 401
    assert client.post(
        "/api/v1/backup/import",
        **upload_payload(backup, pin="123456", confirm="REPLACE_REPOSITORY"),
    ).status_code == 401


def test_restore_failure_rolls_back_current_repository(
    tmp_path: Path, monkeypatch
) -> None:
    source_client = make_client(tmp_path / "source-failure")
    source_headers = initialize(
        source_client,
        name="来源",
        pin="654321",
        recovery="source-failure-recovery",
    )
    add_event(source_client, source_headers, "来源事件")
    source_backup = export_backup(source_client, source_headers)

    target_dir = tmp_path / "target-failure"
    target_client = make_client(target_dir)
    target_headers = initialize(
        target_client,
        name="目标",
        pin="123456",
        recovery="target-failure-recovery",
    )
    add_event(target_client, target_headers, "应当保留的事件")

    vault = target_client.app.state.vault
    original_verify = vault.database.verify_encrypted_snapshot
    calls = 0

    def fail_only_after_replacement(snapshot_path, master_key):
        nonlocal calls
        calls += 1
        # 1: rescue backup verification; 2: restored live repository verification.
        if calls == 2:
            raise RuntimeError("simulated post-replace verification failure")
        return original_verify(snapshot_path, master_key)

    monkeypatch.setattr(
        vault.database, "verify_encrypted_snapshot", fail_only_after_replacement
    )
    response = target_client.post(
        "/api/v1/backup/import",
        headers=target_headers,
        **upload_payload(
            source_backup,
            pin="654321",
            confirm="REPLACE_REPOSITORY",
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BACKUP_RESTORE_FAILED"

    # The old session and repository remain usable after successful automatic rollback.
    detail = target_client.get("/api/v1/dates/2001-02-03", headers=target_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["events"][0]["title"] == "应当保留的事件"


def test_lifevault_v1_package_without_attachments_remains_importable(tmp_path: Path) -> None:
    source = make_client(tmp_path / "source-v1")
    source_headers = initialize(
        source,
        name="旧备份来源",
        pin="654321",
        recovery="legacy-backup-recovery-secret",
    )
    add_event(source, source_headers, "旧格式兼容事件")
    current_backup = export_backup(source, source_headers)

    with zipfile.ZipFile(io.BytesIO(current_backup)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        manifest["format_version"] = 1
        legacy_paths = {"repository/vault.json", "repository/lifegraph.db"}
        manifest["files"] = [
            entry for entry in manifest.get("files", [])
            if entry.get("path") in legacy_paths
        ]
        files = {name: archive.read(name) for name in legacy_paths}

    legacy_buffer = io.BytesIO()
    with zipfile.ZipFile(legacy_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, value in files.items():
            archive.writestr(name, value)

    target = make_client(tmp_path / "target-v1")
    target_headers = initialize(
        target,
        name="兼容目标",
        pin="123456",
        recovery="legacy-target-recovery-secret",
    )
    checked = target.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        **upload_payload(legacy_buffer.getvalue(), pin="654321"),
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["data"]["format_version"] == 1
    assert checked.json()["data"]["attachment_files_verified"] == 0
